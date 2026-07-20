"""add workflow group approval rules

Revision ID: c2f4a9d8e7b6
Revises: b9d4e1f2a6c3
Create Date: 2026-07-20 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c2f4a9d8e7b6"
down_revision = "b9d4e1f2a6c3"
branch_labels = None
depends_on = None


def _index_exists(table_name, index_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(index.get("name") == index_name for index in inspector.get_indexes(table_name))


def _table_exists(table_name):
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return table_name in inspector.get_table_names()


def upgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if not _table_exists("workflow_grupos"):
        op.create_table(
            "workflow_grupos",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("empresa_id", sa.Integer(), nullable=False),
            sa.Column("workflow_id", sa.Integer(), nullable=False),
            sa.Column("nome", sa.String(length=100), nullable=False),
            sa.Column("ordem", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("regra_aprovacao", sa.Enum("TODOS", "QUALQUER"), nullable=False, server_default="TODOS"),
            sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("criado_por", sa.Integer(), nullable=True),
            sa.Column("modificado_por", sa.Integer(), nullable=True),
            sa.Column("criado_em", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.Column("modificado_em", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            sa.ForeignKeyConstraint(["criado_por"], ["usuarios.id"], name="fk_workflow_grupo_criado_por"),
            sa.ForeignKeyConstraint(["empresa_id"], ["empresa.id"], name="fk_workflow_grupo_empresa"),
            sa.ForeignKeyConstraint(["modificado_por"], ["usuarios.id"], name="fk_workflow_grupo_modificado_por"),
            sa.ForeignKeyConstraint(["workflow_id"], ["workflow_definicoes.id"], name="fk_workflow_grupo_workflow"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("workflow_id", "ordem", name="uk_workflow_grupo_ordem"),
        )
        op.create_index("idx_workflow_grupo_empresa", "workflow_grupos", ["empresa_id"], unique=False)
        op.create_index("idx_workflow_grupo_workflow", "workflow_grupos", ["workflow_id"], unique=False)

    with op.batch_alter_table("workflow_etapas", schema=None) as batch_op:
        batch_op.add_column(sa.Column("grupo_id", sa.Integer(), nullable=True))
        batch_op.create_index("idx_workflow_etapa_grupo", ["grupo_id"], unique=False)
        batch_op.create_foreign_key("fk_workflow_etapa_grupo", "workflow_grupos", ["grupo_id"], ["id"])

    with op.batch_alter_table("workflow_execucao_etapas", schema=None) as batch_op:
        batch_op.add_column(sa.Column("grupo_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "regra_aprovacao",
                sa.Enum("TODOS", "QUALQUER"),
                nullable=False,
                server_default="TODOS",
            )
        )
        batch_op.create_index("idx_workflow_exec_etapa_grupo", ["grupo_id"], unique=False)
        batch_op.create_foreign_key("fk_workflow_exec_etapa_grupo", "workflow_grupos", ["grupo_id"], ["id"])

    if _index_exists("rdo_aprovacoes", "uk_rdo_nivel"):
        with op.batch_alter_table("rdo_aprovacoes", schema=None) as batch_op:
            batch_op.drop_index("uk_rdo_nivel")
            batch_op.create_index("uk_rdo_nivel_aprovador", ["rdo_id", "nivel", "aprovador_id"], unique=True)

    if dialect == "mysql":
        op.execute(
            "ALTER TABLE rdo_aprovacoes "
            "MODIFY status ENUM('PENDENTE','APROVADO','REJEITADO','CANCELADO') DEFAULT 'PENDENTE'"
        )


def downgrade():
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "mysql":
        op.execute(
            "ALTER TABLE rdo_aprovacoes "
            "MODIFY status ENUM('PENDENTE','APROVADO','REJEITADO') DEFAULT 'PENDENTE'"
        )

    if _index_exists("rdo_aprovacoes", "uk_rdo_nivel_aprovador"):
        with op.batch_alter_table("rdo_aprovacoes", schema=None) as batch_op:
            batch_op.drop_index("uk_rdo_nivel_aprovador")
            batch_op.create_index("uk_rdo_nivel", ["rdo_id", "nivel"], unique=True)

    with op.batch_alter_table("workflow_execucao_etapas", schema=None) as batch_op:
        batch_op.drop_constraint("fk_workflow_exec_etapa_grupo", type_="foreignkey")
        batch_op.drop_index("idx_workflow_exec_etapa_grupo")
        batch_op.drop_column("regra_aprovacao")
        batch_op.drop_column("grupo_id")

    with op.batch_alter_table("workflow_etapas", schema=None) as batch_op:
        batch_op.drop_constraint("fk_workflow_etapa_grupo", type_="foreignkey")
        batch_op.drop_index("idx_workflow_etapa_grupo")
        batch_op.drop_column("grupo_id")

    if _table_exists("workflow_grupos"):
        op.drop_index("idx_workflow_grupo_workflow", table_name="workflow_grupos")
        op.drop_index("idx_workflow_grupo_empresa", table_name="workflow_grupos")
        op.drop_table("workflow_grupos")
