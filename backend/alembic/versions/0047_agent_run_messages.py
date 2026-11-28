"""Mensajes al agente desde el portal

`agent_run_events.delivered_at`: cuándo se le pasó al agente un mensaje del usuario escrito
mientras trabajaba (con la respuesta de su siguiente herramienta).

Revision ID: 0047
Revises: 0046
Create Date: 2026-11-28 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0047"
down_revision: str | Sequence[str] | None = "0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("agent_run_events") as batch_op:
        batch_op.add_column(sa.Column("delivered_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("agent_run_events") as batch_op:
        batch_op.drop_column("delivered_at")
