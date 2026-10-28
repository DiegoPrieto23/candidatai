"""entrevistas futuras que se marcaron como hechas antes de su día vuelven a programadas

Hasta ahora se podía marcar como hecha una entrevista antes de su día (un clic de más). Ya no se
puede, pero las que se marcaron así siguen como «hecha» y no salen en «Próximos 7 días». Esta
migración las devuelve a «programada», como el botón «Deshacer hecha»: borra su `interview_done`,
quita el enlace de lo que apuntara a ese evento (un borrador de agradecimiento) y recalcula
`last_event_at`. La etapa no cambia: `interview_done` no mueve de `in_process`.

Solo las que aún no han llegado a su día (en hora de Madrid, la zona por defecto del calendario):
una que ya pasó pudo celebrarse de verdad. En SQL y sin el código de la app, para no depender del
de mañana. Idempotente.

Revision ID: 0031
Revises: 0030
Create Date: 2026-10-28 12:00:00

"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | Sequence[str] | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ZONE = ZoneInfo("Europe/Madrid")


def _local(value: str | datetime) -> datetime:
    moment = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    return moment.replace(tzinfo=UTC).astimezone(ZONE)


def upgrade() -> None:
    conn = op.get_bind()
    today = datetime.now(ZONE).date()
    rows = conn.execute(
        sa.text(
            "SELECT id, job_id, starts_at FROM milestones "
            "WHERE kind = 'interview' AND status = 'done'"
        )
    ).all()
    for milestone_id, job_id, starts_at in rows:
        if _local(starts_at).date() <= today:
            continue
        event_ids = [
            event_id
            for event_id, payload in conn.execute(
                sa.text(
                    "SELECT id, payload FROM events WHERE job_id = :job AND type = 'interview_done'"
                ),
                {"job": job_id},
            )
            if (json.loads(payload) if isinstance(payload, str) else payload or {}).get(
                "milestone_id"
            )
            == milestone_id
        ]
        for event_id in event_ids:
            for table in ("replies", "message_drafts"):
                conn.execute(
                    sa.text(f"UPDATE {table} SET event_id = NULL WHERE event_id = :id"),
                    {"id": event_id},
                )
            conn.execute(sa.text("DELETE FROM events WHERE id = :id"), {"id": event_id})
        conn.execute(
            sa.text(
                "UPDATE milestones SET status = 'scheduled', sequence = sequence + 1 WHERE id = :id"
            ),
            {"id": milestone_id},
        )
        conn.execute(
            sa.text(
                "UPDATE applications SET last_event_at = "
                "(SELECT MAX(occurred_at) FROM events WHERE events.job_id = :job) "
                "WHERE job_id = :job"
            ),
            {"job": job_id},
        )


def downgrade() -> None:
    # Solo corrige datos: no hay nada que deshacer en el esquema.
    pass
