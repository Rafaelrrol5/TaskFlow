"""produtividade, categorias e arquivamento

Revision ID: 20260829_03
Revises: 20260829_02
Create Date: 2026-08-29 10:40:00

"""
from alembic import op
import sqlalchemy as sa


revision = "20260829_03"
down_revision = "20260829_02"
branch_labels = None
depends_on = None


def upgrade():
    conexao = op.get_bind()

    op.add_column(
        "usuarios",
        sa.Column(
            "onboarding_concluido",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        )
    )

    with op.batch_alter_table("tarefas") as batch_op:
        batch_op.add_column(
            sa.Column(
                "arquivada",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column("data_arquivamento", sa.DateTime(), nullable=True)
        )
        batch_op.create_check_constraint(
            "ck_tarefas_arquivamento_consistente",
            "(arquivada = 0 AND data_arquivamento IS NULL) OR "
            "(arquivada = 1 AND data_arquivamento IS NOT NULL)",
        )

    op.create_index(
        "ix_tarefas_usuario_arquivada",
        "tarefas",
        ["user_id", "arquivada"],
        unique=False,
    )
    op.create_index(
        "ix_tarefas_usuario_prazo",
        "tarefas",
        ["user_id", "data_limite"],
        unique=False,
    )

    op.create_table(
        "categorias",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("nome_chave", sa.String(length=100), nullable=False),
        sa.Column(
            "cor",
            sa.String(length=7),
            nullable=False,
            server_default="#7C6DF2",
        ),
        sa.Column("icone", sa.String(length=20), nullable=True),
        sa.CheckConstraint(
            "length(trim(nome)) BETWEEN 1 AND 100",
            name="ck_categorias_nome_tamanho",
        ),
        sa.CheckConstraint(
            "length(nome_chave) BETWEEN 1 AND 100",
            name="ck_categorias_nome_chave_tamanho",
        ),
        sa.CheckConstraint(
            "length(cor) = 7",
            name="ck_categorias_cor_tamanho",
        ),
        sa.CheckConstraint(
            "icone IS NULL OR length(icone) <= 20",
            name="ck_categorias_icone_tamanho",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["usuarios.id"],
            name="fk_categorias_user_id_usuarios",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "nome_chave",
            name="uq_categorias_usuario_nome",
        ),
    )
    op.create_index(
        "ix_categorias_user_id",
        "categorias",
        ["user_id"],
        unique=False,
    )

    categorias = sa.table(
        "categorias",
        sa.column("user_id", sa.Integer()),
        sa.column("nome", sa.String()),
        sa.column("nome_chave", sa.String()),
        sa.column("cor", sa.String()),
        sa.column("icone", sa.String()),
    )
    existentes = conexao.execute(
        sa.text(
            "SELECT id, user_id, categoria FROM tarefas "
            "WHERE categoria IS NOT NULL ORDER BY id"
        )
    ).all()
    vistos = set()
    nomes_canonicos = {}
    novas = []
    for tarefa_id, user_id, nome_original in existentes:
        nome = " ".join(nome_original.split())
        if not nome:
            continue
        chave = nome.casefold()
        identificador = (user_id, chave)
        if identificador not in vistos:
            vistos.add(identificador)
            nomes_canonicos[identificador] = nome
            novas.append(
                {
                    "user_id": user_id,
                    "nome": nome,
                    "nome_chave": chave,
                    "cor": "#7C6DF2",
                    "icone": None,
                }
            )
        nome_canonico = nomes_canonicos[identificador]
        if nome_original != nome_canonico:
            conexao.execute(
                sa.text("UPDATE tarefas SET categoria = :nome WHERE id = :id"),
                {"nome": nome_canonico, "id": tarefa_id},
            )
    if novas:
        op.bulk_insert(categorias, novas)

    conexao.execute(
        sa.text("UPDATE tarefas SET categoria = NULL WHERE trim(categoria) = ''")
    )
    conexao.execute(sa.text("PRAGMA optimize"))


def downgrade():
    raise RuntimeError(
        "Downgrade bloqueado porque removeria categorias e dados de arquivamento."
    )

