"""documents.edited_by_user (fase 10.3)

Marca los documentos que el usuario editó en la UI (respuestas de screening y, en la 08c, cartas).
Los existentes quedan en `false`.

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-03 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("edited_by_user", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.drop_column("edited_by_user")
