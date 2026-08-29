"""usuarios e isolamento de tarefas

Revision ID: 20260829_02
Revises: 20260829_01
Create Date: 2026-08-29 07:06:44.097591

"""
import os
import re
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from werkzeug.security import generate_password_hash


# revision identifiers, used by Alembic.
revision = '20260829_02'
down_revision = '20260829_01'
branch_labels = None
depends_on = None


def upgrade():
    conexao = op.get_bind()
    total_tarefas = conexao.execute(
        sa.text("SELECT COUNT(*) FROM tarefas")
    ).scalar_one()
    dados_invalidos = conexao.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM tarefas
            WHERE titulo IS NULL
               OR length(trim(titulo)) NOT BETWEEN 1 AND 200
               OR descricao IS NOT NULL AND length(descricao) > 5000
               OR categoria IS NOT NULL AND length(categoria) > 100
               OR prioridade NOT IN ('baixa', 'media', 'alta')
               OR status NOT IN ('pendente', 'concluida')
            """
        )
    ).scalar_one()

    if dados_invalidos:
        raise RuntimeError(
            "A migration foi interrompida: existem tarefas antigas com dados inválidos."
        )

    usuario_legado = os.getenv("LEGACY_USERNAME", "usuario_legado").strip().casefold()
    senha_legada = os.getenv("LEGACY_USER_PASSWORD")
    if total_tarefas:
        if not re.fullmatch(r"[a-z0-9_.-]{3,50}", usuario_legado):
            raise RuntimeError("LEGACY_USERNAME possui formato inválido.")
        if not senha_legada or not 10 <= len(senha_legada) <= 128:
            raise RuntimeError(
                "Defina LEGACY_USER_PASSWORD com 10 a 128 caracteres antes do upgrade."
            )

    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=50), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column("data_criacao", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "length(nome) BETWEEN 3 AND 50",
            name="ck_usuarios_nome_tamanho",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_usuarios_nome", "usuarios", ["nome"], unique=True)

    with op.batch_alter_table("tarefas") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))

    if total_tarefas:
        resultado = conexao.execute(
            sa.text(
                """
                INSERT INTO usuarios (nome, senha_hash, data_criacao)
                VALUES (:nome, :senha_hash, :data_criacao)
                """
            ),
            {
                "nome": usuario_legado,
                "senha_hash": generate_password_hash(senha_legada),
                "data_criacao": datetime.now(timezone.utc).replace(tzinfo=None),
            },
        )
        usuario_id = resultado.lastrowid
        conexao.execute(
            sa.text("UPDATE tarefas SET user_id = :usuario_id"),
            {"usuario_id": usuario_id},
        )

    with op.batch_alter_table("tarefas") as batch_op:
        batch_op.alter_column(
            "descricao",
            existing_type=sa.Text(),
            type_=sa.String(length=5000),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "user_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.create_foreign_key(
            "fk_tarefas_user_id_usuarios",
            "usuarios",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_check_constraint(
            "ck_tarefas_prioridade",
            "prioridade IN ('baixa', 'media', 'alta')",
        )
        batch_op.create_check_constraint(
            "ck_tarefas_status",
            "status IN ('pendente', 'concluida')",
        )
        batch_op.create_check_constraint(
            "ck_tarefas_titulo_tamanho",
            "length(trim(titulo)) BETWEEN 1 AND 200",
        )
        batch_op.create_check_constraint(
            "ck_tarefas_categoria_tamanho",
            "categoria IS NULL OR length(categoria) <= 100",
        )
        batch_op.create_check_constraint(
            "ck_tarefas_descricao_tamanho",
            "descricao IS NULL OR length(descricao) <= 5000",
        )

    op.create_index("ix_tarefas_user_id", "tarefas", ["user_id"], unique=False)


def downgrade():
    raise RuntimeError(
        "Downgrade bloqueado porque removeria usuários e o vínculo de propriedade."
    )

