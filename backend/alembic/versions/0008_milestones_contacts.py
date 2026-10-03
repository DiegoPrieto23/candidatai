"""hitos y contactos de los procesos (fase 10)

Tablas `milestones` (entrevistas, pruebas, plazos; con su evento) y `contacts`.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-03 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "milestones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("starts_at", sa.DateTime(), nullable=False),
        sa.Column("ends_at", sa.DateTime(), nullable=True),
        sa.Column("all_day", sa.Boolean(), nullable=False),
        sa.Column("location", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"], ["events.id"], name=op.f("fk_milestones_event_id_events")
        ),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_milestones_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_milestones")),
    )
    with op.batch_alter_table("milestones", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_milestones_job_id"), ["job_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_milestones_starts_at"), ["starts_at"], unique=False)

    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("role", sa.String(length=200), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("linkedin", sa.String(length=500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_contacts_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contacts")),
    )
    with op.batch_alter_table("contacts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_contacts_job_id"), ["job_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("contacts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_contacts_job_id"))
    op.drop_table("contacts")

    with op.batch_alter_table("milestones", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_milestones_starts_at"))
        batch_op.drop_index(batch_op.f("ix_milestones_job_id"))
    op.drop_table("milestones")
