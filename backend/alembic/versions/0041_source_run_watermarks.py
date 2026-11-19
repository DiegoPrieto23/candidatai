"""marca de agua y contadores de cada recorrido del agente

Columnas nuevas en `source_runs`: `existing`, `skipped_known`, `filtered_out`, `left_by_limit`,
`reopened` (0 en los recorridos de antes), `stop_reason` y `watermarks` (JSON con lo más reciente
que vio cada búsqueda, para que la siguiente pare ahí).

Revision ID: 0041
Revises: 0040
Create Date: 2026-11-19 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0041"
down_revision: str | Sequence[str] | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COUNTERS = ("existing", "skipped_known", "filtered_out", "left_by_limit", "reopened")


def upgrade() -> None:
    with op.batch_alter_table("source_runs") as batch_op:
        for name in COUNTERS:
            batch_op.add_column(sa.Column(name, sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("stop_reason", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("watermarks", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("source_runs") as batch_op:
        batch_op.drop_column("watermarks")
        batch_op.drop_column("stop_reason")
        for name in reversed(COUNTERS):
            batch_op.drop_column(name)
