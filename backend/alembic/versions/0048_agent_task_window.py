"""La ventana del agente, siempre a mano

`agent_tasks`: el fichero donde la ventana deja su PID (`window_token`), el PID, cómo se abrió
(`window_style`), su título y cuándo se vio cerrada sin haber terminado.

Revision ID: 0048
Revises: 0047
Create Date: 2026-11-28 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0048"
down_revision: str | Sequence[str] | None = "0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("agent_tasks") as batch_op:
        batch_op.add_column(sa.Column("window_token", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("window_style", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("window_title", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("window_pid", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("window_closed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("agent_tasks") as batch_op:
        batch_op.drop_column("window_closed_at")
        batch_op.drop_column("window_pid")
        batch_op.drop_column("window_title")
        batch_op.drop_column("window_style")
        batch_op.drop_column("window_token")
