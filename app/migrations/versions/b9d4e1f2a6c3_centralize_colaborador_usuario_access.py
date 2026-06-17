"""centralize colaborador usuario access

Revision ID: b9d4e1f2a6c3
Revises: a7f3c2d9e8b1
Create Date: 2026-06-17 09:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "b9d4e1f2a6c3"
down_revision = "a7f3c2d9e8b1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.add_column(sa.Column("primeiro_acesso_em", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "troca_senha_obrigatoria",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.create_index("uq_usuarios_empresa_email", ["empresa_id", "email"], unique=True)
        batch_op.create_index("uq_usuarios_empresa_colaborador", ["empresa_id", "colaborador_id"], unique=True)


def downgrade():
    with op.batch_alter_table("usuarios", schema=None) as batch_op:
        batch_op.drop_index("uq_usuarios_empresa_colaborador")
        batch_op.drop_index("uq_usuarios_empresa_email")
        batch_op.drop_column("troca_senha_obrigatoria")
        batch_op.drop_column("primeiro_acesso_em")
