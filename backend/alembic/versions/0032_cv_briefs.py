"""indicaciones del CV por oferta

Tabla `cv_briefs`: lo que el usuario quiere que tenga en cuenta el CV a medida de esa oferta (qué
destacar, el idioma…). Las escribe en la ficha y las lee `generate-cv` con `get_cv_brief`.

Revision ID: 0032
Revises: 0031
Create Date: 2026-10-28 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | Sequence[str] | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cv_briefs",
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_cv_briefs_job_id_jobs")),
        sa.PrimaryKeyConstraint("job_id", name=op.f("pk_cv_briefs")),
    )


def downgrade() -> None:
    op.drop_table("cv_briefs")
