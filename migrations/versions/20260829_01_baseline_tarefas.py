"""baseline tarefas

Revision ID: 20260829_01
Revises: 
Create Date: 2026-08-29 07:06:42.974860

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260829_01'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    tabelas = sa.inspect(op.get_bind()).get_table_names()
    if "tarefas" in tabelas:
        return

    op.create_table(
        "tarefas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("categoria", sa.String(length=100), nullable=True),
        sa.Column("prioridade", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("data_criacao", sa.DateTime(), nullable=False),
        sa.Column("data_limite", sa.Date(), nullable=True),
        sa.Column("data_conclusao", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    raise RuntimeError(
        "Downgrade bloqueado para evitar a exclusão da tabela de tarefas."
    )

