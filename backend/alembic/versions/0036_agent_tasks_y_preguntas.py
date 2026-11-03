"""avisos de lo que lanzan los botones y preguntas del agente en la app

Tabla `agent_tasks`: de qué hay que avisar («Leyendo ofertas…», «Generando el CV…») y si ya se ha
cerrado el aviso. Cómo va sale de `mcp_calls` y, en segundo plano, de `agent_runs`.

`user_prompts` admite preguntas (`kind = question`): `options`, las respuestas para elegir;
`answer`, lo que contestó el usuario; `job_id`, la oferta de la que va.

Revision ID: 0036
Revises: 0035
Create Date: 2026-11-03 21:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import UTCDateTime

revision: str = "0036"
down_revision: str | Sequence[str] | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=True),
        sa.Column("milestone_id", sa.Integer(), nullable=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("agent_runs.id"), nullable=True),
        sa.Column("total", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=True),
        sa.Column("started_at", UTCDateTime(), nullable=False),
        sa.Column("finished_at", UTCDateTime(), nullable=True),
        sa.Column("dismissed_at", UTCDateTime(), nullable=True),
    )
    op.create_index("ix_agent_tasks_dismissed_at", "agent_tasks", ["dismissed_at"])
    with op.batch_alter_table("user_prompts") as batch:
        batch.add_column(sa.Column("options", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("answer", sa.Text(), nullable=True))
        batch.add_column(sa.Column("job_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("user_prompts") as batch:
        batch.drop_column("job_id")
        batch.drop_column("answer")
        batch.drop_column("options")
    op.drop_index("ix_agent_tasks_dismissed_at", table_name="agent_tasks")
    op.drop_table("agent_tasks")
