"""ofertas resumen y alertas por correo (fase 09b)

`jobs.platform` y `jobs.detail_level`, índice único parcial (`platform`, `external_id`) y tabla
`email_messages` con los `Message-ID` ya procesados.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-02 19:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("platform", sa.String(length=32), nullable=True))
        batch_op.add_column(
            sa.Column("detail_level", sa.String(length=16), server_default="full", nullable=False)
        )
        batch_op.create_index(
            "uq_jobs_platform_external",
            ["platform", "external_id"],
            unique=True,
            sqlite_where=sa.text("platform IS NOT NULL AND external_id IS NOT NULL"),
        )

    op.create_table(
        "email_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.String(length=998), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("jobs_found", sa.Integer(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name=op.f("fk_email_messages_source_id_sources")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_messages")),
        sa.UniqueConstraint("message_id", name=op.f("uq_email_messages_message_id")),
    )
    with op.batch_alter_table("email_messages", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_email_messages_source_id"), ["source_id"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("email_messages", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_email_messages_source_id"))
    op.drop_table("email_messages")

    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_index("uq_jobs_platform_external")
        batch_op.drop_column("detail_level")
        batch_op.drop_column("platform")
