"""configuración propia de cada ejecución en segundo plano

Fase 24.5 (ADR-032): `agent_runs.run_config`, cómo se escribe la configuración que pone el techo
de herramientas de los agentes que lo limitan por configuración (OpenCode). `NULL`: el techo va en
la orden (Claude Code).

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-16 20:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | Sequence[str] | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("agent_runs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("run_config", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("agent_runs", schema=None) as batch_op:
        batch_op.drop_column("run_config")
