"""preferencias de agente y modelo

Fase 24.4 (ADR-037): tabla `agent_preferences` (agente por defecto, modelo o preset por agente y
agente por acción) y el modelo o preset con que se lanzó cada ejecución en `agent_runs`.

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-16 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | Sequence[str] | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_preferences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("agent", sa.String(length=32), nullable=True),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("preset", sa.String(length=40), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_preferences")),
        sa.UniqueConstraint("scope", "key", name=op.f("uq_agent_preferences_scope")),
    )
    with op.batch_alter_table("agent_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("model", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("preset", sa.String(length=40), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("agent_runs", schema=None) as batch_op:
        batch_op.drop_column("preset")
        batch_op.drop_column("model")
    op.drop_table("agent_preferences")
