from datetime import date, datetime, timezone

from flask import Blueprint, current_app, g, jsonify, request
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest

from database import db, limiter
from models import Categoria, Tarefa
from routes.auth import login_obrigatorio
from routes.categorias import COR_PADRAO, normalizar_nome, validar_categoria
from routes.tarefas import CAMPOS_EDITAVEIS, aplicar_dados, limpar_arquivadas_expiradas, validar_dados


backup_bp = Blueprint("backup", __name__)

VERSAO_BACKUP = 1
MAXIMO_TAREFAS = 5000
MAXIMO_CATEGORIAS = 500
CAMPOS_RAIZ = {"version", "exportado_em", "tarefas", "categorias", "configuracoes"}
CAMPOS_TAREFA_BACKUP = CAMPOS_EDITAVEIS | {
    "data_criacao",
    "data_conclusao",
    "arquivada",
    "data_arquivamento",
}
CAMPOS_CATEGORIA_BACKUP = {"nome", "cor", "icone"}
CAMPOS_CONFIGURACOES = {"onboarding_concluido"}


def erro(mensagem, codigo=400):
    return jsonify({"erro": mensagem}), codigo


def data_hora_iso(valor, campo, obrigatoria=False):
    if valor is None and not obrigatoria:
        return None, None
    if not isinstance(valor, str):
        return None, f"{campo} deve ser uma data ISO válida."
    try:
        analisada = datetime.fromisoformat(valor.removesuffix("Z") + ("+00:00" if valor.endswith("Z") else ""))
    except ValueError:
        return None, f"{campo} deve ser uma data ISO válida."
    if analisada.tzinfo is not None:
        analisada = analisada.astimezone(timezone.utc).replace(tzinfo=None)
    return analisada, None


def validar_estrutura_backup(conteudo):
    if not isinstance(conteudo, dict) or set(conteudo) != CAMPOS_RAIZ:
        return None, "Estrutura principal do backup inválida."
    if conteudo.get("version") != VERSAO_BACKUP:
        return None, "Versão de backup não suportada."
    if not isinstance(conteudo.get("exportado_em"), str):
        return None, "Data de exportação inválida."
    _, mensagem_data = data_hora_iso(
        conteudo["exportado_em"], "exportado_em", obrigatoria=True
    )
    if mensagem_data:
        return None, mensagem_data
    if not isinstance(conteudo.get("tarefas"), list):
        return None, "A lista de tarefas é inválida."
    if not isinstance(conteudo.get("categorias"), list):
        return None, "A lista de categorias é inválida."
    if len(conteudo["tarefas"]) > MAXIMO_TAREFAS:
        return None, f"O backup excede o limite de {MAXIMO_TAREFAS} tarefas."
    if len(conteudo["categorias"]) > MAXIMO_CATEGORIAS:
        return None, f"O backup excede o limite de {MAXIMO_CATEGORIAS} categorias."

    configuracoes = conteudo.get("configuracoes")
    if not isinstance(configuracoes, dict) or set(configuracoes) != CAMPOS_CONFIGURACOES:
        return None, "As configurações do backup são inválidas."
    if not isinstance(configuracoes["onboarding_concluido"], bool):
        return None, "A configuração de onboarding é inválida."

    categorias = []
    nomes = {}
    for indice, item in enumerate(conteudo["categorias"], start=1):
        if not isinstance(item, dict) or set(item) != CAMPOS_CATEGORIA_BACKUP:
            return None, f"Categoria {indice} possui estrutura inválida."
        mensagem = validar_categoria(item, criacao=True)
        if mensagem:
            return None, f"Categoria {indice}: {mensagem}"
        nome = normalizar_nome(item["nome"])
        chave = nome.casefold()
        if chave in nomes:
            return None, "O backup contém categorias duplicadas."
        categoria = {
            "nome": nome,
            "nome_chave": chave,
            "cor": item.get("cor", COR_PADRAO).upper(),
            "icone": item.get("icone").strip() or None if item.get("icone") else None,
        }
        nomes[chave] = nome
        categorias.append(categoria)

    tarefas = []
    for indice, item in enumerate(conteudo["tarefas"], start=1):
        if not isinstance(item, dict) or set(item) != CAMPOS_TAREFA_BACKUP:
            return None, f"Tarefa {indice} possui estrutura inválida."
        editaveis = {campo: item[campo] for campo in CAMPOS_EDITAVEIS}
        mensagem = validar_dados(editaveis, criacao=True)
        if mensagem:
            return None, f"Tarefa {indice}: {mensagem}"
        if not isinstance(item["arquivada"], bool):
            return None, f"Tarefa {indice}: arquivada deve ser booleana."

        criacao, mensagem = data_hora_iso(
            item["data_criacao"], "data_criacao", obrigatoria=True
        )
        if mensagem:
            return None, f"Tarefa {indice}: {mensagem}"
        conclusao, mensagem = data_hora_iso(item["data_conclusao"], "data_conclusao")
        if mensagem:
            return None, f"Tarefa {indice}: {mensagem}"
        arquivamento, mensagem = data_hora_iso(
            item["data_arquivamento"], "data_arquivamento"
        )
        if mensagem:
            return None, f"Tarefa {indice}: {mensagem}"
        if item["arquivada"] != (arquivamento is not None):
            return None, f"Tarefa {indice}: dados de arquivamento inconsistentes."

        categoria = editaveis["categoria"]
        if categoria:
            chave = normalizar_nome(categoria).casefold()
            if chave not in nomes:
                return None, f"Tarefa {indice}: categoria inexistente no backup."
            editaveis["categoria"] = nomes[chave]

        tarefas.append(
            {
                "editaveis": editaveis,
                "data_criacao": criacao,
                "data_conclusao": conclusao,
                "arquivada": item["arquivada"],
                "data_arquivamento": arquivamento,
            }
        )

    return {
        "categorias": categorias,
        "tarefas": tarefas,
        "configuracoes": configuracoes,
    }, None


@backup_bp.get("/backup")
@limiter.limit("10 per minute")
@login_obrigatorio
def exportar_backup():
    limpar_arquivadas_expiradas()
    tarefas = db.session.scalars(
        db.select(Tarefa)
        .where(Tarefa.user_id == g.usuario_atual.id)
        .order_by(Tarefa.id.asc())
    ).all()
    categorias = db.session.scalars(
        db.select(Categoria)
        .where(Categoria.user_id == g.usuario_atual.id)
        .order_by(Categoria.nome_chave.asc())
    ).all()

    conteudo = {
        "version": VERSAO_BACKUP,
        "exportado_em": datetime.now(timezone.utc).isoformat(),
        "tarefas": [
            {
                "titulo": tarefa.titulo,
                "descricao": tarefa.descricao,
                "categoria": tarefa.categoria,
                "prioridade": tarefa.prioridade,
                "status": tarefa.status,
                "data_criacao": tarefa.data_criacao.isoformat() + "Z",
                "data_limite": tarefa.data_limite.isoformat() if tarefa.data_limite else None,
                "data_conclusao": tarefa.data_conclusao.isoformat() + "Z" if tarefa.data_conclusao else None,
                "arquivada": tarefa.arquivada,
                "data_arquivamento": tarefa.data_arquivamento.isoformat() + "Z" if tarefa.data_arquivamento else None,
            }
            for tarefa in tarefas
        ],
        "categorias": [
            {"nome": item.nome, "cor": item.cor, "icone": item.icone}
            for item in categorias
        ],
        "configuracoes": {
            "onboarding_concluido": g.usuario_atual.onboarding_concluido,
        },
    }
    resposta = jsonify(conteudo)
    resposta.headers["Content-Disposition"] = (
        f'attachment; filename="taskflow-backup-{date.today().isoformat()}.json"'
    )
    return resposta


@backup_bp.post("/backup/restaurar")
@limiter.limit("5 per hour")
@login_obrigatorio
def restaurar_backup():
    if not request.is_json:
        return erro("Content-Type deve ser application/json.", 415)
    try:
        dados = request.get_json()
    except BadRequest:
        return erro("JSON inválido.")
    if not isinstance(dados, dict) or set(dados) != {"confirmar", "backup"}:
        return erro("Estrutura da restauração inválida.")
    if dados.get("confirmar") is not True:
        return erro("Confirme a substituição dos dados para continuar.")

    validado, mensagem = validar_estrutura_backup(dados.get("backup"))
    if mensagem:
        return erro(mensagem)

    try:
        db.session.execute(
            db.delete(Tarefa).where(Tarefa.user_id == g.usuario_atual.id)
        )
        db.session.execute(
            db.delete(Categoria).where(Categoria.user_id == g.usuario_atual.id)
        )

        for item in validado["categorias"]:
            db.session.add(Categoria(user_id=g.usuario_atual.id, **item))

        for item in validado["tarefas"]:
            tarefa = Tarefa(
                user_id=g.usuario_atual.id,
                data_criacao=item["data_criacao"],
                data_conclusao=item["data_conclusao"],
                arquivada=item["arquivada"],
                data_arquivamento=item["data_arquivamento"],
            )
            aplicar_dados(tarefa, item["editaveis"])
            tarefa.data_conclusao = item["data_conclusao"]
            db.session.add(tarefa)

        g.usuario_atual.onboarding_concluido = validado["configuracoes"][
            "onboarding_concluido"
        ]
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("Falha ao restaurar backup")
        return erro("Não foi possível restaurar o backup.", 500)

    return jsonify({"mensagem": "Backup restaurado com sucesso."})

