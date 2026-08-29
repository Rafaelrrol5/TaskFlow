import re
from functools import wraps

from flask import Blueprint, g, jsonify, request, session
from flask_wtf.csrf import generate_csrf
from sqlalchemy.exc import IntegrityError

from database import db, limiter
from models import Usuario


auth_bp = Blueprint("auth", __name__)

USUARIO_PADRAO = re.compile(r"^[a-z0-9_.-]+$")
USUARIO_MINIMO = 3
USUARIO_MAXIMO = 50
SENHA_MINIMA = 10
SENHA_MAXIMA = 128
CAMPOS_AUTENTICACAO = {"usuario", "senha"}


def erro(mensagem, codigo=400):
    return jsonify({"erro": mensagem}), codigo


def normalizar_usuario(valor):
    return valor.strip().casefold()


def ler_credenciais():
    if not request.is_json:
        return None, erro("Content-Type deve ser application/json.", 415)

    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return None, erro("JSON inválido.")

    desconhecidos = set(dados) - CAMPOS_AUTENTICACAO
    if desconhecidos:
        return None, erro(
            f"Campos não permitidos: {', '.join(sorted(desconhecidos))}."
        )

    usuario = dados.get("usuario")
    senha = dados.get("senha")
    if not isinstance(usuario, str) or not isinstance(senha, str):
        return None, erro("Usuário e senha são obrigatórios.")

    return {"usuario": normalizar_usuario(usuario), "senha": senha}, None


def validar_cadastro(credenciais):
    usuario = credenciais["usuario"]
    senha = credenciais["senha"]

    if not USUARIO_MINIMO <= len(usuario) <= USUARIO_MAXIMO:
        return (
            f"O usuário deve ter entre {USUARIO_MINIMO} e {USUARIO_MAXIMO} caracteres."
        )
    if not USUARIO_PADRAO.fullmatch(usuario):
        return "Use apenas letras, números, ponto, hífen ou sublinhado no usuário."
    if not SENHA_MINIMA <= len(senha) <= SENHA_MAXIMA:
        return f"A senha deve ter entre {SENHA_MINIMA} e {SENHA_MAXIMA} caracteres."
    return None


def login_obrigatorio(funcao):
    @wraps(funcao)
    def protegida(*args, **kwargs):
        usuario_id = session.get("user_id")
        if not isinstance(usuario_id, int):
            return erro("Autenticação necessária.", 401)

        usuario = db.session.get(Usuario, usuario_id)
        if usuario is None:
            session.clear()
            return erro("Sessão inválida ou expirada.", 401)

        g.usuario_atual = usuario
        return funcao(*args, **kwargs)

    return protegida


def resposta_sessao(usuario=None):
    return jsonify(
        {
            "autenticado": usuario is not None,
            "usuario": usuario.to_dict() if usuario else None,
            "csrf_token": generate_csrf(),
        }
    )


@auth_bp.get("/sessao")
def consultar_sessao():
    usuario_id = session.get("user_id")
    usuario = db.session.get(Usuario, usuario_id) if isinstance(usuario_id, int) else None
    if usuario_id is not None and usuario is None:
        session.clear()
    return resposta_sessao(usuario)


@auth_bp.post("/usuarios")
@limiter.limit("5 per minute")
def cadastrar_usuario():
    credenciais, resposta_erro = ler_credenciais()
    if resposta_erro:
        return resposta_erro

    mensagem = validar_cadastro(credenciais)
    if mensagem:
        return erro(mensagem)

    existente = db.session.scalar(
        db.select(Usuario).where(Usuario.nome == credenciais["usuario"])
    )
    if existente:
        return erro("Nome de usuário já está em uso.", 409)

    usuario = Usuario(nome=credenciais["usuario"])
    usuario.definir_senha(credenciais["senha"])
    db.session.add(usuario)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return erro("Nome de usuário já está em uso.", 409)

    session.clear()
    session["user_id"] = usuario.id
    session.permanent = True
    return resposta_sessao(usuario), 201


@auth_bp.post("/login")
@limiter.limit("5 per minute")
def login():
    credenciais, resposta_erro = ler_credenciais()
    if resposta_erro:
        return resposta_erro

    usuario = db.session.scalar(
        db.select(Usuario).where(Usuario.nome == credenciais["usuario"])
    )
    if usuario is None or not usuario.verificar_senha(credenciais["senha"]):
        return erro("Usuário ou senha inválidos.", 401)

    session.clear()
    session["user_id"] = usuario.id
    session.permanent = True
    return resposta_sessao(usuario)


@auth_bp.post("/logout")
@login_obrigatorio
def logout():
    session.clear()
    return resposta_sessao()


@auth_bp.patch("/preferencias")
@limiter.limit("30 per minute")
@login_obrigatorio
def atualizar_preferencias():
    if not request.is_json:
        return erro("Content-Type deve ser application/json.", 415)
    dados = request.get_json(silent=True)
    if not isinstance(dados, dict):
        return erro("JSON inválido.")
    if set(dados) != {"onboarding_concluido"}:
        return erro("Informe apenas a preferência onboarding_concluido.")
    if not isinstance(dados["onboarding_concluido"], bool):
        return erro("onboarding_concluido deve ser verdadeiro ou falso.")

    g.usuario_atual.onboarding_concluido = dados["onboarding_concluido"]
    db.session.commit()
    return jsonify({"usuario": g.usuario_atual.to_dict()})

