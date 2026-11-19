"""El asistente, también en una terminal

`assistant_requests.cancelled_at`: una petición abierta en tu terminal (`mode = terminal`) no tiene
ejecución ni encargo que cancelar; se marca aquí al cancelarla desde el panel.

Revision ID: 0044
Revises: 0043
Create Date: 2026-11-19 19:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0044"
down_revision: str | Sequence[str] | None = "0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("assistant_requests") as batch_op:
        batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("assistant_requests") as batch_op:
        batch_op.drop_column("cancelled_at")
