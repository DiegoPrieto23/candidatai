"""avisos al usuario (captcha, login…)

Tabla `user_prompts`: lo que el agente o el worker te piden hacer en el navegador, para enseñarlo
en un pop-up de la UI y esperar tu respuesta un tiempo limitado.

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-10 14:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user_prompts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("url", sa.String(length=2000), nullable=True),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("attempt_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name=op.f("fk_user_prompts_source_id_sources")
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["application_attempts.id"],
            name=op.f("fk_user_prompts_attempt_id_application_attempts"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_prompts")),
    )
    with op.batch_alter_table("user_prompts", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_user_prompts_status"), ["status"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("user_prompts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_user_prompts_status"))
    op.drop_table("user_prompts")
