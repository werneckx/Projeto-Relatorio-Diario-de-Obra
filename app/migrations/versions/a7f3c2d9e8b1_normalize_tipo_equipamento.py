"""normalize tipo equipamento

Revision ID: a7f3c2d9e8b1
Revises: 4c0d0a1fb1ab
Create Date: 2026-06-16 14:45:00.000000

"""
from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = "a7f3c2d9e8b1"
down_revision = "4c0d0a1fb1ab"
branch_labels = None
depends_on = None


DEFAULT_TIPOS = [
    "Acesso e Andaimes",
    "Bombeamento e Drenagem",
    "Compactação",
    "Concretagem",
    "Corte e Demolição",
    "Escavação e Terraplenagem",
    "Ferramentas Elétricas",
    "Ferramentas Manuais",
    "Fundação",
    "Geração de Energia",
    "Içamento e Elevação",
    "Limpeza e Acabamento",
    "Movimentação de Cargas",
    "Pavimentação",
    "Perfuração",
    "Solda e Corte Térmico",
    "Topografia e Medição",
    "Transporte",
    "Segurança e Sinalização",
    "Não informado",
]


def _get_or_create_tipo(conn, nome, now, is_system=False):
    nome = (nome or "").strip() or "Não informado"
    existing = conn.execute(
        sa.text("SELECT id FROM aux_tipo_equipamento WHERE nome = :nome"),
        {"nome": nome},
    ).scalar()
    if existing:
        return existing

    conn.execute(
        sa.text(
            """
            INSERT INTO aux_tipo_equipamento (nome, ativo, is_system, criado_em, modificado_em)
            VALUES (:nome, :ativo, :is_system, :criado_em, :modificado_em)
            """
        ),
        {"nome": nome, "ativo": True, "is_system": is_system, "criado_em": now, "modificado_em": now},
    )
    return conn.execute(
        sa.text("SELECT id FROM aux_tipo_equipamento WHERE nome = :nome"),
        {"nome": nome},
    ).scalar()


def upgrade():
    op.create_table(
        "aux_tipo_equipamento",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nome", sa.String(length=100), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("criado_por", sa.Integer(), nullable=True),
        sa.Column("modificado_por", sa.Integer(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=True),
        sa.Column("modificado_em", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("nome", name="uq_aux_tipo_equipamento_nome"),
    )
    op.create_index("ix_aux_tipo_equipamento_nome", "aux_tipo_equipamento", ["nome"], unique=False)
    op.create_index("ix_aux_tipo_equipamento_ativo", "aux_tipo_equipamento", ["ativo"], unique=False)

    conn = op.get_bind()
    now = datetime.utcnow()

    for nome in DEFAULT_TIPOS:
        _get_or_create_tipo(conn, nome, now, is_system=True)

    with op.batch_alter_table("aux_equipamentos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tipo_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_aux_equipamentos_tipo_id", ["tipo_id"], unique=False)

    equipamentos = conn.execute(
        sa.text("SELECT id, tipo FROM aux_equipamentos")
    ).mappings().all()
    for equipamento in equipamentos:
        tipo_nome = (equipamento["tipo"] or "").strip() or "Não informado"
        tipo_id = _get_or_create_tipo(conn, tipo_nome, now, is_system=False)
        conn.execute(
            sa.text("UPDATE aux_equipamentos SET tipo_id = :tipo_id WHERE id = :id"),
            {"tipo_id": tipo_id, "id": equipamento["id"]},
        )

    with op.batch_alter_table("aux_equipamentos", schema=None) as batch_op:
        batch_op.alter_column("tipo_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_aux_equipamentos_tipo_id_aux_tipo_equipamento",
            "aux_tipo_equipamento",
            ["tipo_id"],
            ["id"],
        )
        batch_op.drop_column("tipo")


def downgrade():
    conn = op.get_bind()

    with op.batch_alter_table("aux_equipamentos", schema=None) as batch_op:
        batch_op.add_column(sa.Column("tipo", sa.String(length=100), nullable=True))

    conn.execute(
        sa.text(
            """
            UPDATE aux_equipamentos
            SET tipo = (
                SELECT aux_tipo_equipamento.nome
                FROM aux_tipo_equipamento
                WHERE aux_tipo_equipamento.id = aux_equipamentos.tipo_id
            )
            """
        )
    )

    with op.batch_alter_table("aux_equipamentos", schema=None) as batch_op:
        batch_op.drop_constraint("fk_aux_equipamentos_tipo_id_aux_tipo_equipamento", type_="foreignkey")
        batch_op.drop_index("ix_aux_equipamentos_tipo_id")
        batch_op.drop_column("tipo_id")

    op.drop_index("ix_aux_tipo_equipamento_ativo", table_name="aux_tipo_equipamento")
    op.drop_index("ix_aux_tipo_equipamento_nome", table_name="aux_tipo_equipamento")
    op.drop_table("aux_tipo_equipamento")
