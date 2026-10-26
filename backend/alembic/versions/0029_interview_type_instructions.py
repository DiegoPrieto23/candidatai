"""tipo de entrevista e indicaciones para prepararla

`milestones.interview_type`: qué ronda es (`hr`, `technical`, `case`, `final`, `other`), para que la
guía y el simulacro se adapten sin adivinarlo por el título. `milestones.prep_instructions`: lo que
el usuario quiere que tengan en cuenta «Preparar» y «Simulacro» en esa entrevista. Las dos vacías en
las entrevistas que ya había.

Revision ID: 0029
Revises: 0028
Create Date: 2026-10-26 21:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | Sequence[str] | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("milestones") as batch_op:
        batch_op.add_column(sa.Column("interview_type", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("prep_instructions", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("milestones") as batch_op:
        batch_op.drop_column("prep_instructions")
        batch_op.drop_column("interview_type")
