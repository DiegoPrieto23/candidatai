"""ejecuciones en segundo plano y cola de encargos

Tabla `agent_runs`: las ejecuciones del agente sin ventana que lanza la UI y ejecuta el worker
(fase 19). Tabla `agent_requests`: los encargos para la próxima sesión interactiva.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-12 13:16:19

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_requests",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("milestone_id", sa.Integer(), nullable=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("agent_name", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_agent_requests_job_id_jobs")
        ),
        sa.ForeignKeyConstraint(
            ["milestone_id"],
            ["milestones.id"],
            name=op.f("fk_agent_requests_milestone_id_milestones"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_requests")),
    )
    with op.batch_alter_table("agent_requests", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_agent_requests_job_id"), ["job_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_agent_requests_status"), ["status"], unique=False)

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("milestone_id", sa.Integer(), nullable=True),
        sa.Column("agent", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("command", sa.JSON(), nullable=False),
        sa.Column("unset_env", sa.JSON(), nullable=False),
        sa.Column("output_format", sa.String(length=32), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("progress", sa.JSON(), nullable=False),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("usage", sa.JSON(), nullable=True),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_agent_runs_job_id_jobs")),
        sa.ForeignKeyConstraint(
            ["milestone_id"], ["milestones.id"], name=op.f("fk_agent_runs_milestone_id_milestones")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
    )
    with op.batch_alter_table("agent_runs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_agent_runs_job_id"), ["job_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_agent_runs_status"), ["status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("agent_runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_agent_runs_status"))
        batch_op.drop_index(batch_op.f("ix_agent_runs_job_id"))

    op.drop_table("agent_runs")
    with op.batch_alter_table("agent_requests", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_agent_requests_status"))
        batch_op.drop_index(batch_op.f("ix_agent_requests_job_id"))

    op.drop_table("agent_requests")
