"""matches.extraction_id: con qué extracción se calculó cada match

Un match está desfasado si la oferta tiene una extracción más reciente o el perfil una versión más
reciente. Los matches anteriores a esta migración quedan con `extraction_id` nulo (desfasados).

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-28 12:52:27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.add_column(sa.Column("extraction_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_matches_extraction_id_job_extractions"),
            "job_extractions",
            ["extraction_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_matches_extraction_id_job_extractions"), type_="foreignkey"
        )
        batch_op.drop_column("extraction_id")
