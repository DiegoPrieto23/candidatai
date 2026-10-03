"""indicaciones de la carta por oferta (fase 08c)

Tabla `cover_letter_briefs`: lo que el usuario quiere que diga la carta de esa oferta y su
límite de palabras. Mandan sobre `preferences.cover_letter` del perfil.

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-03 21:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cover_letter_briefs",
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("max_words", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_cover_letter_briefs_job_id_jobs")
        ),
        sa.PrimaryKeyConstraint("job_id", name=op.f("pk_cover_letter_briefs")),
    )


def downgrade() -> None:
    op.drop_table("cover_letter_briefs")
