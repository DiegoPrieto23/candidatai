"""prioridades de plataforma sin empates

Fase 27.3: la prioridad de una plataforma (`sources.config.priority` de las `agent_browse`) pasa a
ser un puesto único, 1…N. Hasta ahora todas entraban con 5 y podían empatar: se ordenan por
`(prioridad, nombre)` y se numeran. Solo corrige datos, sin eventos. Idempotente.

`downgrade` no recupera los empates (no se guardaron), pero deja las prioridades en 1…10, que es lo
único que admitía el esquema anterior.

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-23 18:00:00

"""

import json
import sys
from collections.abc import Callable, Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | Sequence[str] | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _priority(config: dict[str, Any]) -> int | None:
    value = config.get("priority")
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _order(priority: int | None) -> int:
    return sys.maxsize if priority is None else priority


def _rewrite(new_priority: Callable[[int], int]) -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, name, config FROM sources WHERE kind = 'agent_browse'")
    ).all()
    platforms = []
    for source_id, name, raw in rows:
        config = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
        platforms.append((source_id, " ".join(str(name).split()).casefold(), config))
    # Sin prioridad válida, al final; los empates, por nombre (como `browse.platforms_in_order`).
    platforms.sort(key=lambda p: (_order(_priority(p[2])), p[1], p[0]))
    for position, (source_id, _, config) in enumerate(platforms, start=1):
        priority = new_priority(position)
        if _priority(config) != priority:
            config["priority"] = priority
            bind.execute(
                sa.text("UPDATE sources SET config = :config WHERE id = :id"),
                {"config": json.dumps(config), "id": source_id},
            )


def upgrade() -> None:
    _rewrite(lambda position: position)


def downgrade() -> None:
    _rewrite(lambda position: min(position, 10))
