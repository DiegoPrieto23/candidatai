"""fecha y motivo de cierre en la proyección

Fase 27.6: `applications.closed_at` (cuándo se cerró la oferta) y `applications.closed_by` (con qué
evento: `discarded`, `rejected`, `duplicate_detected`…). `last_event_at` no sirve para eso porque una
nota posterior al cierre lo mueve.

El relleno sale de los eventos y no crea ninguno: en una oferta cerrada, el último evento de cierre
es el que la cerró (si después se reabrió, no estaría cerrada; si se volvió a cerrar, ese cierre es
más reciente). Se hace en SQL y no con `rebuild_projection` para no depender del código de la app
de mañana. Idempotente.

Revision ID: 0028
Revises: 0027
Create Date: 2026-10-23 22:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | Sequence[str] | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Los eventos que llevan a `closed` en `services/pipeline.TRANSITIONS` a día de hoy.
CLOSING = (
    "duplicate_detected",
    "hard_filter_failed",
    "discarded",
    "rejected",
    "withdrawn",
    "expired",
    "accepted",
)

_LAST_CLOSE = f"""
    SELECT {{column}} FROM events
    WHERE events.job_id = applications.job_id
      AND events.type IN ({", ".join(f"'{t}'" for t in CLOSING)})
    ORDER BY events.occurred_at DESC, events.id DESC
    LIMIT 1
"""


def upgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.add_column(sa.Column("closed_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("closed_by", sa.String(length=32), nullable=True))
    op.execute(
        f"""
        UPDATE applications SET
            closed_at = ({_LAST_CLOSE.format(column="occurred_at")}),
            closed_by = ({_LAST_CLOSE.format(column="type")})
        WHERE stage = 'closed'
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("applications") as batch:
        batch.drop_column("closed_by")
        batch.drop_column("closed_at")
