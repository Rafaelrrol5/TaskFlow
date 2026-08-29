import os
import secrets
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import click
from flask import Flask, jsonify, render_template, request
from flask_wtf.csrf import CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

from database import csrf, db, limiter, migrate


def caminho_recurso(*partes):
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base.joinpath(*partes)


def variavel_booleana(nome, padrao=False):
    valor = os.getenv(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "yes", "on"}


def create_app(configuracao=None):
    app = Flask(
        __name__,
        template_folder=str(caminho_recurso("templates")),
        static_folder=str(caminho_recurso("static")),
    )
    ambiente_producao = os.getenv("APP_ENV", "development").lower() == "production"
    secret_key = os.getenv("SECRET_KEY")

    if ambiente_producao and not secret_key:
        raise RuntimeError("SECRET_KEY é obrigatória em produção.")

    app.config.from_mapping(
        SECRET_KEY=secret_key or secrets.token_hex(32),
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL", "sqlite:///tarefas.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        MAX_CONTENT_LENGTH=2 * 1024 * 1024,
        PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=ambiente_producao,
        SESSION_COOKIE_NAME="taskflow_session",
        WTF_CSRF_TIME_LIMIT=3600,
        RATELIMIT_DEFAULT="120 per minute",
        RATELIMIT_HEADERS_ENABLED=True,
        RATELIMIT_STORAGE_URI=os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
        PRODUCAO=ambiente_producao,
        TRUST_PROXY=variavel_booleana("TRUST_PROXY"),
    )

    if configuracao:
        app.config.update(configuracao)

    if app.config["TRUST_PROXY"]:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    migrate.init_app(app, db, compare_type=True, render_as_batch=True)
    csrf.init_app(app)
    limiter.init_app(app)

    from models import Categoria, Tarefa, Usuario  # noqa: F401
    from routes.auth import auth_bp
    from routes.backup import backup_bp
    from routes.categorias import categorias_bp
    from routes.tarefas import tarefas_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(categorias_bp)
    app.register_blueprint(tarefas_bp)

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.after_request
    def adicionar_headers_seguranca(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "font-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'"
        )
        if response.mimetype == "application/json":
            response.headers["Cache-Control"] = "no-store"
        if app.config["PRODUCAO"] and request.is_secure:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

    @app.errorhandler(CSRFError)
    def csrf_invalido(_erro):
        return jsonify({"erro": "Token CSRF ausente, inválido ou expirado."}), 400

    @app.errorhandler(400)
    def requisicao_invalida(_erro):
        return jsonify({"erro": "Requisição inválida."}), 400

    @app.errorhandler(404)
    def recurso_nao_encontrado(_erro):
        return jsonify({"erro": "Recurso não encontrado."}), 404

    @app.errorhandler(405)
    def metodo_nao_permitido(_erro):
        return jsonify({"erro": "Método HTTP não permitido."}), 405

    @app.errorhandler(429)
    def limite_excedido(_erro):
        return jsonify({"erro": "Muitas requisições. Tente novamente em instantes."}), 429

    @app.errorhandler(413)
    def corpo_muito_grande(_erro):
        return jsonify({"erro": "Corpo da requisição muito grande."}), 413

    @app.errorhandler(500)
    def erro_interno(erro):
        db.session.rollback()
        app.logger.error("Erro interno não tratado", exc_info=erro)
        return jsonify({"erro": "Erro interno do servidor."}), 500

    @app.cli.command("db-backup")
    def backup_banco():
        """Cria backup consistente do banco SQLite antes de uma migration."""
        url = db.engine.url
        if url.get_backend_name() != "sqlite" or not url.database:
            raise click.ClickException("Este comando suporta somente SQLite.")

        origem = Path(url.database).resolve()
        if not origem.exists():
            raise click.ClickException(f"Banco não encontrado: {origem}")

        pasta_backup = origem.parent / "backups"
        pasta_backup.mkdir(parents=True, exist_ok=True)
        horario = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        destino = pasta_backup / f"{origem.stem}-{horario}.db"

        with sqlite3.connect(origem) as banco_origem:
            with sqlite3.connect(destino) as banco_destino:
                banco_origem.backup(banco_destino)

        click.echo(f"Backup criado em: {destino}")

    return app


app = create_app()


if __name__ == "__main__":
    debug_ativo = variavel_booleana("FLASK_DEBUG")
    app.run(debug=debug_ativo)

