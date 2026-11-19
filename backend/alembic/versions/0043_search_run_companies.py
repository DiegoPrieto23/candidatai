"""«Buscar ahora» revisa también las empresas con portal propio

`search_runs.company_ids` y `search_runs.task_ids`: las empresas que se revisan a la vez que los
portales y sus tareas del worker. `source_runs.search_run_id`: la búsqueda a la que pertenece cada
recorrido (de un portal o de una empresa).

Revision ID: 0043
Revises: 0042
Create Date: 2026-11-19 16:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0043"
down_revision: str | Sequence[str] | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("search_runs") as batch_op:
        batch_op.add_column(sa.Column("company_ids", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("task_ids", sa.JSON(), nullable=True))
    with op.batch_alter_table("source_runs") as batch_op:
        batch_op.add_column(sa.Column("search_run_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_source_runs_search_run_id_search_runs", "search_runs", ["search_run_id"], ["id"]
        )
        batch_op.create_index("ix_source_runs_search_run_id", ["search_run_id"])


def downgrade() -> None:
    with op.batch_alter_table("source_runs") as batch_op:
        batch_op.drop_index("ix_source_runs_search_run_id")
        batch_op.drop_constraint("fk_source_runs_search_run_id_search_runs", type_="foreignkey")
        batch_op.drop_column("search_run_id")
    with op.batch_alter_table("search_runs") as batch_op:
        batch_op.drop_column("task_ids")
        batch_op.drop_column("company_ids")
