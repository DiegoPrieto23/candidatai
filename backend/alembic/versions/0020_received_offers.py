"""ofertas recibidas

Tabla `received_offers`: la oferta que ha hecho la empresa de un proceso (fase 21), una por oferta
de empleo. Los importes son privados por defecto (`amounts_private`).

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-12 16:05:09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "received_offers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("base_salary", sa.Integer(), nullable=True),
        sa.Column("variable", sa.Integer(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("period", sa.String(length=8), nullable=False),
        sa.Column("benefits", sa.Text(), nullable=True),
        sa.Column("work_mode", sa.String(length=16), nullable=True),
        sa.Column("location", sa.String(length=200), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("respond_by", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("amounts_private", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_received_offers_job_id_jobs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_received_offers")),
        sa.UniqueConstraint("job_id", name=op.f("uq_received_offers_job_id")),
    )


def downgrade() -> None:
    op.drop_table("received_offers")
