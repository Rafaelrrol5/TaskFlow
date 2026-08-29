import re

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.exceptions import BadRequest

from database import db, limiter
from models import Categoria, Tarefa
from routes.auth import login_obrigatorio


categorias_bp = Blueprint("categorias", __name__)

NOME_MAXIMO = 100
ICONE_MAXIMO = 20
COR_PADRAO = "#7C6DF2"
COR_HEXADECIMAL = re.compile(r"^#[0-9a-fA-F]{6}$")
CAMPOS_CATEGORIA = {"nome", "cor", "icone"}


def erro(mensagem, codigo=400):
    return jsonify({"erro": mensagem}), codigo


def normalizar_nome(valor):
    return " ".join(valor.split())


def chave_nome(valor):
    return normalizar_nome(valor).casefold()


def obter_json():
    if not request.is_json:
        return None, erro("Content-Type deve ser application/json.", 415)
    try:
        dados = request.get_json()
    except BadRequest:
        return None, erro("JSON inválido.")
    if not isinstance(dados, dict):
        return None, erro("O corpo da requisição deve ser um objeto JSON.")
    return dados, None


def validar_categoria(dados, criacao=False):
    desconhecidos = set(dados) - CAMPOS_CATEGORIA
    if desconhecidos:
        return f"Campos não permitidos: {', '.join(sorted(desconhecidos))}."
    if criacao and "nome" not in dados:
        return "O nome da categoria é obrigatório."
    if not criacao and not dados:
        return "Informe ao menos um campo para atualizar."

    if "nome" in dados:
        if not isinstance(dados["nome"], str):
            return "O nome da categoria deve ser um texto."
        nome = normalizar_nome(dados["nome"])
        if not nome:
            return "O nome da categoria é obrigatório."
        if len(nome) > NOME_MAXIMO:
            return f"O nome deve ter no máximo {NOME_MAXIMO} caracteres."

    if "cor" in dados:
        if not isinstance(dados["cor"], str) or not COR_HEXADECIMAL.fullmatch(
            dados["cor"]
        ):
            return "A cor deve usar o formato hexadecimal #RRGGBB."

    if "icone" in dados and dados["icone"] is not None:
        if not isinstance(dados["icone"], str):
            return "O ícone deve ser um texto ou nulo."
        if len(dados["icone"].strip()) > ICONE_MAXIMO:
            return f"O ícone deve ter no máximo {ICONE_MAXIMO} caracteres."
    return None


def buscar_categoria(categoria_id):
    return db.session.scalar(
        db.select(Categoria).where(
            Categoria.id == categoria_id,
            Categoria.user_id == g.usuario_atual.id,
        )
    )


def aplicar_dados(categoria, dados):
    if "nome" in dados:
        categoria.nome = normalizar_nome(dados["nome"])
        categoria.nome_chave = categoria.nome.casefold()
    if "cor" in dados:
        categoria.cor = dados["cor"].upper()
    if "icone" in dados:
        categoria.icone = dados["icone"].strip() or None if dados["icone"] else None


def confirmar_alteracao():
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return erro("Já existe uma categoria com esse nome.", 409)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Falha ao persistir categoria")
        return erro("Não foi possível salvar a categoria.", 500)
    return None


@categorias_bp.get("/categorias")
@login_obrigatorio
def listar_categorias():
    consulta = (
        db.select(Categoria)
        .where(Categoria.user_id == g.usuario_atual.id)
        .order_by(Categoria.nome_chave.asc())
    )
    return jsonify([categoria.to_dict() for categoria in db.session.scalars(consulta)])


@categorias_bp.post("/categorias")
@limiter.limit("30 per minute")
@login_obrigatorio
def criar_categoria():
    dados, resposta_erro = obter_json()
    if resposta_erro:
        return resposta_erro
    mensagem = validar_categoria(dados, criacao=True)
    if mensagem:
        return erro(mensagem)

    categoria = Categoria(
        user_id=g.usuario_atual.id,
        cor=COR_PADRAO,
    )
    aplicar_dados(categoria, dados)
    db.session.add(categoria)
    falha = confirmar_alteracao()
    if falha:
        return falha
    return jsonify(categoria.to_dict()), 201


@categorias_bp.put("/categorias/<int:categoria_id>")
@limiter.limit("60 per minute")
@login_obrigatorio
def editar_categoria(categoria_id):
    categoria = buscar_categoria(categoria_id)
    if categoria is None:
        return erro("Categoria não encontrada.", 404)

    dados, resposta_erro = obter_json()
    if resposta_erro:
        return resposta_erro
    mensagem = validar_categoria(dados)
    if mensagem:
        return erro(mensagem)

    nome_anterior = categoria.nome
    aplicar_dados(categoria, dados)
    if categoria.nome != nome_anterior:
        db.session.execute(
            db.update(Tarefa)
            .where(
                Tarefa.user_id == g.usuario_atual.id,
                Tarefa.categoria == nome_anterior,
            )
            .values(categoria=categoria.nome)
        )

    falha = confirmar_alteracao()
    if falha:
        return falha
    return jsonify(categoria.to_dict())


@categorias_bp.delete("/categorias/<int:categoria_id>")
@limiter.limit("60 per minute")
@login_obrigatorio
def excluir_categoria(categoria_id):
    categoria = buscar_categoria(categoria_id)
    if categoria is None:
        return erro("Categoria não encontrada.", 404)

    db.session.execute(
        db.update(Tarefa)
        .where(
            Tarefa.user_id == g.usuario_atual.id,
            Tarefa.categoria == categoria.nome,
        )
        .values(categoria=None)
    )
    db.session.delete(categoria)
    falha = confirmar_alteracao()
    if falha:
        return falha
    return jsonify({"mensagem": "Categoria excluída sem remover tarefas."})

