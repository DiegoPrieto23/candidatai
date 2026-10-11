"""respuestas por correo y borradores de seguimiento

Tablas `replies` (correos de las empresas de tus procesos, con la propuesta del agente) y
`message_drafts` (borradores de seguimiento y agradecimiento, que la app nunca envía).

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-11 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "replies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.String(length=998), nullable=False),
        sa.Column("origin", sa.String(length=8), nullable=False),
        sa.Column("sender", sa.String(length=320), nullable=False),
        sa.Column("sender_name", sa.String(length=200), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("body_text", sa.Text(), nullable=False),
        sa.Column("risk_flags", sa.JSON(), nullable=False),
        sa.Column("risk_excerpt", sa.String(length=300), nullable=True),
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("proposal", sa.JSON(), nullable=True),
        sa.Column("proposed_at", sa.DateTime(), nullable=True),
        sa.Column("proposed_by", sa.String(length=64), nullable=True),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_replies_job_id_jobs")),
        sa.ForeignKeyConstraint(
            ["event_id"], ["events.id"], name=op.f("fk_replies_event_id_events")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_replies")),
        sa.UniqueConstraint("message_id", name=op.f("uq_replies_message_id")),
    )
    with op.batch_alter_table("replies", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_replies_status"), ["status"], unique=False)
        batch_op.create_index(batch_op.f("ix_replies_job_id"), ["job_id"], unique=False)

    op.create_table(
        "message_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("milestone_id", sa.Integer(), nullable=True),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("agent_name", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_message_drafts_job_id_jobs")
        ),
        sa.ForeignKeyConstraint(
            ["milestone_id"],
            ["milestones.id"],
            name=op.f("fk_message_drafts_milestone_id_milestones"),
        ),
        sa.ForeignKeyConstraint(
            ["event_id"], ["events.id"], name=op.f("fk_message_drafts_event_id_events")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_message_drafts")),
    )
    with op.batch_alter_table("message_drafts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_message_drafts_job_id"), ["job_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("message_drafts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_message_drafts_job_id"))
    op.drop_table("message_drafts")
    with op.batch_alter_table("replies", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_replies_job_id"))
        batch_op.drop_index(batch_op.f("ix_replies_status"))
    op.drop_table("replies")
