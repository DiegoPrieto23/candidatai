"""huecos de skills marcados por el usuario

Tabla `skill_gap_marks`: «No la tengo» (hueco real, para el plan de formación) o «La tengo»
(pendiente de añadir al perfil) para una skill que piden las ofertas y el perfil no cubre.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-11 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "skill_gap_marks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("skill_key", sa.String(length=200), nullable=False),
        sa.Column("skill_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_skill_gap_marks")),
        sa.UniqueConstraint("skill_key", name=op.f("uq_skill_gap_marks_skill_key")),
    )


def downgrade() -> None:
    op.drop_table("skill_gap_marks")
