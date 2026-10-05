"""intentos de candidatura asistida (fase 11)

Tabla `application_attempts`: lo que rellenó el navegador, la captura de revisión y el hash del
token de envío de un solo uso.

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-05 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "application_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("screenshot_path", sa.String(length=500), nullable=True),
        sa.Column("confirmation_path", sa.String(length=500), nullable=True),
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("token_used_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_application_attempts_job_id_jobs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_application_attempts")),
    )
    with op.batch_alter_table("application_attempts", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_application_attempts_job_id"), ["job_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_application_attempts_status"), ["status"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("application_attempts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_application_attempts_status"))
        batch_op.drop_index(batch_op.f("ix_application_attempts_job_id"))
    op.drop_table("application_attempts")
