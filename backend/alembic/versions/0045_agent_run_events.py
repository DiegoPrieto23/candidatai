"""La conversación de una ejecución en segundo plano

`agent_run_events`: lo que hace el agente en una ejecución sin ventana (arranque, herramientas, su
texto, el resultado), en orden, para seguirla en el portal.

Revision ID: 0045
Revises: 0044
Create Date: 2026-11-27 19:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0045"
down_revision: str | Sequence[str] | None = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_run_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("at", sa.DateTime(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("tool", sa.String(length=80), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=True),
        sa.Column("sub", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["agent_runs.id"], name=op.f("fk_agent_run_events_run_id_agent_runs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_run_events")),
        sa.UniqueConstraint("run_id", "seq", name=op.f("uq_agent_run_events_run_id")),
    )
    op.create_index(
        op.f("ix_agent_run_events_run_id"), "agent_run_events", ["run_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_agent_run_events_run_id"), table_name="agent_run_events")
    op.drop_table("agent_run_events")
