from datetime import date, timedelta

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy import case
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest

from database import db, limiter
from models import Categoria, Tarefa, agora_utc
from routes.categorias import COR_PADRAO, chave_nome
from routes.auth import login_obrigatorio


tarefas_bp = Blueprint("tarefas", __name__)

PRIORIDADES = {"baixa", "media", "alta"}
STATUS_VALIDOS = {"pendente", "concluida"}
TITULO_MAXIMO = 200
DESCRICAO_MAXIMA = 5000
CATEGORIA_MAXIMA = 100
CAMPOS_EDITAVEIS = {
    "titulo",
    "descricao",
    "categoria",
    "prioridade",
    "status",
    "data_limite",
}
PARAMETROS_LISTAGEM = {"status", "prioridade", "categoria", "ordenar", "ordem"}


def erro(mensagem, codigo=400):
    return jsonify({"erro": mensagem}), codigo


def buscar_tarefa(tarefa_id, arquivada=None):
    consulta = db.select(Tarefa).where(
        Tarefa.id == tarefa_id,
        Tarefa.user_id == g.usuario_atual.id,
    )
    if arquivada is not None:
        consulta = consulta.where(Tarefa.arquivada.is_(arquivada))
    return db.session.scalar(consulta)


def normalizar_espacos(valor):
    return " ".join(valor.split())


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


def validar_dados(dados, criacao=False):
    campos_desconhecidos = set(dados) - CAMPOS_EDITAVEIS
    if campos_desconhecidos:
        return f"Campos não permitidos: {', '.join(sorted(campos_desconhecidos))}."

    if criacao and "titulo" not in dados:
        return "O título é obrigatório."

    if not criacao and not dados:
        return "Informe ao menos um campo para atualizar."

    if "titulo" in dados:
        if not isinstance(dados["titulo"], str):
            return "O título deve ser um texto."
        titulo = normalizar_espacos(dados["titulo"])
        if not titulo:
            return "O título é obrigatório."
        if len(titulo) > TITULO_MAXIMO:
            return f"O título deve ter no máximo {TITULO_MAXIMO} caracteres."

    if "descricao" in dados and dados["descricao"] is not None:
        if not isinstance(dados["descricao"], str):
            return "A descrição deve ser um texto ou nula."
        if len(dados["descricao"].strip()) > DESCRICAO_MAXIMA:
            return f"A descrição deve ter no máximo {DESCRICAO_MAXIMA} caracteres."

    if "categoria" in dados and dados["categoria"] is not None:
        if not isinstance(dados["categoria"], str):
            return "A categoria deve ser um texto ou nula."
        categoria = normalizar_espacos(dados["categoria"])
        if len(categoria) > CATEGORIA_MAXIMA:
            return f"A categoria deve ter no máximo {CATEGORIA_MAXIMA} caracteres."

    if "prioridade" in dados and dados["prioridade"] not in PRIORIDADES:
        return "Prioridade inválida. Use: baixa, media ou alta."

    if "status" in dados and dados["status"] not in STATUS_VALIDOS:
        return "Status inválido. Use: pendente ou concluida."

    if "data_limite" in dados and dados["data_limite"] is not None:
        try:
            date.fromisoformat(dados["data_limite"])
        except (TypeError, ValueError):
            return "Data limite inválida. Use o formato AAAA-MM-DD."

    return None


def aplicar_dados(tarefa, dados):
    for campo in CAMPOS_EDITAVEIS.intersection(dados):
        valor = dados[campo]

        if campo == "titulo":
            valor = normalizar_espacos(valor)
        elif campo == "categoria" and isinstance(valor, str):
            valor = normalizar_espacos(valor) or None
        elif campo == "descricao" and isinstance(valor, str):
            valor = valor.strip() or None
        elif campo == "data_limite" and valor is not None:
            valor = date.fromisoformat(valor)

        setattr(tarefa, campo, valor)

    if "status" in dados:
        if tarefa.status == "concluida" and tarefa.data_conclusao is None:
            tarefa.data_conclusao = agora_utc()
        elif tarefa.status == "pendente":
            tarefa.data_conclusao = None


def garantir_categoria(nome):
    if not nome:
        return
    chave = chave_nome(nome)
    existente = db.session.scalar(
        db.select(Categoria).where(
            Categoria.user_id == g.usuario_atual.id,
            Categoria.nome_chave == chave,
        )
    )
    if existente is None:
        db.session.add(
            Categoria(
                user_id=g.usuario_atual.id,
                nome=normalizar_espacos(nome),
                nome_chave=chave,
                cor=COR_PADRAO,
            )
        )


def limpar_arquivadas_expiradas():
    limite = agora_utc() - timedelta(days=30)
    resultado = db.session.execute(
        db.delete(Tarefa).where(
            Tarefa.user_id == g.usuario_atual.id,
            Tarefa.arquivada.is_(True),
            Tarefa.data_arquivamento.is_not(None),
            Tarefa.data_arquivamento <= limite,
        )
    )
    if resultado.rowcount:
        db.session.commit()
    return resultado.rowcount or 0


def confirmar_alteracao():
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Falha ao persistir alteração de tarefa")
        return erro("Não foi possível salvar a alteração.", 500)
    return None


@tarefas_bp.get("/tarefas")
@login_obrigatorio
def listar_tarefas():
    parametros_desconhecidos = set(request.args) - PARAMETROS_LISTAGEM
    if parametros_desconhecidos:
        return erro(
            f"Parâmetros não permitidos: {', '.join(sorted(parametros_desconhecidos))}."
        )

    consulta = db.select(Tarefa).where(
        Tarefa.user_id == g.usuario_atual.id,
        Tarefa.arquivada.is_(False),
    )

    status = request.args.get("status")
    prioridade = request.args.get("prioridade")
    categoria = request.args.get("categoria")

    if status:
        if status not in STATUS_VALIDOS:
            return erro("Status inválido. Use: pendente ou concluida.")
        consulta = consulta.where(Tarefa.status == status)

    if prioridade:
        if prioridade not in PRIORIDADES:
            return erro("Prioridade inválida. Use: baixa, media ou alta.")
        consulta = consulta.where(Tarefa.prioridade == prioridade)

    if categoria:
        categoria = normalizar_espacos(categoria)
        if len(categoria) > CATEGORIA_MAXIMA:
            return erro(
                f"A categoria deve ter no máximo {CATEGORIA_MAXIMA} caracteres."
            )
        consulta = consulta.where(Tarefa.categoria == categoria)

    ordenar = request.args.get("ordenar")
    ordem = request.args.get("ordem", "asc")

    if ordem not in {"asc", "desc"}:
        return erro("Ordem inválida. Use: asc ou desc.")

    if ordenar == "prioridade":
        peso_prioridade = case(
            (Tarefa.prioridade == "alta", 1),
            (Tarefa.prioridade == "media", 2),
            else_=3,
        )
        consulta = consulta.order_by(
            peso_prioridade.asc() if ordem == "asc" else peso_prioridade.desc()
        )
    elif ordenar == "data_limite":
        sem_prazo = case((Tarefa.data_limite.is_(None), 1), else_=0)
        data_ordenada = (
            Tarefa.data_limite.asc()
            if ordem == "asc"
            else Tarefa.data_limite.desc()
        )
        consulta = consulta.order_by(sem_prazo, data_ordenada)
    elif ordenar:
        return erro("Ordenação inválida. Use: prioridade ou data_limite.")
    else:
        consulta = consulta.order_by(Tarefa.id.asc())

    tarefas = db.session.scalars(consulta).all()
    return jsonify([tarefa.to_dict() for tarefa in tarefas])


@tarefas_bp.get("/tarefas/<int:tarefa_id>")
@login_obrigatorio
def obter_tarefa(tarefa_id):
    tarefa = buscar_tarefa(tarefa_id)
    if tarefa is None:
        return erro("Tarefa não encontrada.", 404)
    return jsonify(tarefa.to_dict())


@tarefas_bp.get("/tarefas/hoje")
@login_obrigatorio
def listar_tarefas_hoje():
    hoje = date.today()
    consulta = db.select(Tarefa).where(
        Tarefa.user_id == g.usuario_atual.id,
        Tarefa.arquivada.is_(False),
    )
    tarefas = db.session.scalars(consulta).all()
    atrasadas = [
        tarefa
        for tarefa in tarefas
        if tarefa.status == "pendente"
        and tarefa.data_limite is not None
        and tarefa.data_limite < hoje
    ]
    do_dia = [
        tarefa
        for tarefa in tarefas
        if tarefa.status == "pendente" and tarefa.data_limite == hoje
    ]
    concluidas = [
        tarefa
        for tarefa in tarefas
        if tarefa.status == "concluida"
        and tarefa.data_conclusao is not None
        and tarefa.data_conclusao.date() == hoje
    ]
    ordenar_prazo = lambda tarefa: (tarefa.data_limite or date.max, tarefa.id)
    return jsonify(
        {
            "atrasadas": [
                tarefa.to_dict() for tarefa in sorted(atrasadas, key=ordenar_prazo)
            ],
            "hoje": [tarefa.to_dict() for tarefa in sorted(do_dia, key=lambda t: t.id)],
            "concluidas": [
                tarefa.to_dict()
                for tarefa in sorted(
                    concluidas,
                    key=lambda t: t.data_conclusao,
                    reverse=True,
                )
            ],
        }
    )


@tarefas_bp.get("/tarefas/arquivadas")
@login_obrigatorio
def listar_tarefas_arquivadas():
    removidas = limpar_arquivadas_expiradas()
    consulta = (
        db.select(Tarefa)
        .where(
            Tarefa.user_id == g.usuario_atual.id,
            Tarefa.arquivada.is_(True),
        )
        .order_by(Tarefa.data_arquivamento.desc())
    )
    return jsonify(
        {
            "tarefas": [
                tarefa.to_dict() for tarefa in db.session.scalars(consulta).all()
            ],
            "removidas": removidas,
        }
    )


@tarefas_bp.post("/tarefas")
@limiter.limit("30 per minute")
@login_obrigatorio
def criar_tarefa():
    dados, resposta_erro = obter_json()
    if resposta_erro:
        return resposta_erro

    mensagem = validar_dados(dados, criacao=True)
    if mensagem:
        return erro(mensagem)

    tarefa = Tarefa(user_id=g.usuario_atual.id)
    aplicar_dados(tarefa, dados)
    garantir_categoria(tarefa.categoria)
    db.session.add(tarefa)
    falha = confirmar_alteracao()
    if falha:
        return falha
    return jsonify(tarefa.to_dict()), 201


@tarefas_bp.put("/tarefas/<int:tarefa_id>")
@limiter.limit("60 per minute")
@login_obrigatorio
def editar_tarefa(tarefa_id):
    tarefa = buscar_tarefa(tarefa_id, arquivada=False)
    if tarefa is None:
        return erro("Tarefa não encontrada.", 404)

    dados, resposta_erro = obter_json()
    if resposta_erro:
        return resposta_erro

    mensagem = validar_dados(dados)
    if mensagem:
        return erro(mensagem)

    aplicar_dados(tarefa, dados)
    garantir_categoria(tarefa.categoria)
    falha = confirmar_alteracao()
    if falha:
        return falha
    return jsonify(tarefa.to_dict())


@tarefas_bp.delete("/tarefas/<int:tarefa_id>")
@limiter.limit("60 per minute")
@login_obrigatorio
def excluir_tarefa(tarefa_id):
    tarefa = buscar_tarefa(tarefa_id)
    if tarefa is None:
        return erro("Tarefa não encontrada.", 404)

    db.session.delete(tarefa)
    falha = confirmar_alteracao()
    if falha:
        return falha
    return jsonify({"mensagem": "Tarefa excluída com sucesso."})


@tarefas_bp.patch("/tarefas/<int:tarefa_id>/concluir")
@limiter.limit("60 per minute")
@login_obrigatorio
def concluir_tarefa(tarefa_id):
    tarefa = buscar_tarefa(tarefa_id, arquivada=False)
    if tarefa is None:
        return erro("Tarefa não encontrada.", 404)

    tarefa.status = "concluida"
    if tarefa.data_conclusao is None:
        tarefa.data_conclusao = agora_utc()
    falha = confirmar_alteracao()
    if falha:
        return falha
    return jsonify(tarefa.to_dict())


@tarefas_bp.post("/tarefas/<int:tarefa_id>/duplicar")
@limiter.limit("30 per minute")
@login_obrigatorio
def duplicar_tarefa(tarefa_id):
    original = buscar_tarefa(tarefa_id, arquivada=False)
    if original is None:
        return erro("Tarefa não encontrada.", 404)

    copia = Tarefa(
        user_id=g.usuario_atual.id,
        titulo=original.titulo,
        descricao=original.descricao,
        categoria=original.categoria,
        prioridade=original.prioridade,
        status="pendente",
        data_limite=original.data_limite,
    )
    db.session.add(copia)
    falha = confirmar_alteracao()
    if falha:
        return falha
    return jsonify(copia.to_dict()), 201


@tarefas_bp.patch("/tarefas/<int:tarefa_id>/arquivar")
@limiter.limit("60 per minute")
@login_obrigatorio
def arquivar_tarefa(tarefa_id):
    tarefa = buscar_tarefa(tarefa_id, arquivada=False)
    if tarefa is None:
        return erro("Tarefa não encontrada.", 404)
    tarefa.arquivada = True
    tarefa.data_arquivamento = agora_utc()
    falha = confirmar_alteracao()
    if falha:
        return falha
    return jsonify(tarefa.to_dict())


@tarefas_bp.patch("/tarefas/<int:tarefa_id>/restaurar")
@limiter.limit("60 per minute")
@login_obrigatorio
def restaurar_tarefa(tarefa_id):
    tarefa = buscar_tarefa(tarefa_id, arquivada=True)
    if tarefa is None:
        return erro("Tarefa arquivada não encontrada.", 404)
    tarefa.arquivada = False
    tarefa.data_arquivamento = None
    falha = confirmar_alteracao()
    if falha:
        return falha
    return jsonify(tarefa.to_dict())

