"""preparación y repaso de entrevistas en el hito

`milestones.prep_plan` (el plan de preparación por días que guarda `preparar-entrevista`) y
`milestones.debrief_notes`, `next_steps` y `debriefed_at` (el repaso posterior que guarda
`repasar-entrevista`). `notes` sigue siendo lo que anota el usuario en el formulario del hito.

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-12 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("milestones", schema=None) as batch_op:
        batch_op.add_column(sa.Column("prep_plan", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("debrief_notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("next_steps", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("debriefed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("milestones", schema=None) as batch_op:
        batch_op.drop_column("debriefed_at")
        batch_op.drop_column("next_steps")
        batch_op.drop_column("debrief_notes")
        batch_op.drop_column("prep_plan")
