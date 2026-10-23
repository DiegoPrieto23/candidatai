"""guía de preparación de una entrevista en PDF

`milestones.prep_guide`: la guía que guarda `prepare-interview` con `save_interview_guide` (el
contenido estructurado, el fichero PDF que maqueta la app y cuándo se guardó). Ver ADR-044.

Revision ID: 0025
Revises: 0024
Create Date: 2026-10-23 13:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | Sequence[str] | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("milestones") as batch_op:
        batch_op.add_column(sa.Column("prep_guide", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("milestones") as batch_op:
        batch_op.drop_column("prep_guide")
