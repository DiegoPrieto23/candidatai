"""origen de cada versión del perfil

Columna `profile_versions.origin`: de dónde viene cada versión (`ui`, `agent`, `undo`, `restore`,
`demo`), para que el historial de «Mi perfil» diga quién hizo el cambio. Las versiones de antes
quedan sin origen.

Revision ID: 0040
Revises: 0039
Create Date: 2026-11-18 10:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: str | Sequence[str] | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("profile_versions") as batch_op:
        batch_op.add_column(sa.Column("origin", sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("profile_versions") as batch_op:
        batch_op.drop_column("origin")
