"""búsquedas abiertas en la terminal del agente

Tabla `search_runs`: de qué búsqueda hay que avisar («Buscando…», terminada) y si ya se ha cerrado
el aviso. Lo demás (portales recorridos, ofertas nuevas) sale de `source_runs` y `jobs`.

Revision ID: 0035
Revises: 0034
Create Date: 2026-11-03 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import UTCDateTime

revision: str = "0035"
down_revision: str | Sequence[str] | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "search_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_ids", sa.JSON(), nullable=False),
        sa.Column("after_source_run_id", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=True),
        sa.Column("started_at", UTCDateTime(), nullable=False),
        sa.Column("finished_at", UTCDateTime(), nullable=True),
        sa.Column("dismissed_at", UTCDateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("search_runs")
