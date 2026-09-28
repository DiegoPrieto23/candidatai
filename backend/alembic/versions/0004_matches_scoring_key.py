"""matches.scoring_key: huella de cómo se puntuó cada match

Un match también está desfasado si cambian la versión del scorer, las políticas de puntuación y
filtros, los alias de skills o el modelo de embeddings (p. ej. al instalar el extra `matching`).
Los matches anteriores a esta migración quedan con `scoring_key` nulo (desfasados).

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-28 16:10:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.add_column(sa.Column("scoring_key", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("matches", schema=None) as batch_op:
        batch_op.drop_column("scoring_key")
