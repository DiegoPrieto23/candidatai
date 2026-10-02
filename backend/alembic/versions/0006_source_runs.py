"""source_runs: ejecuciones de las fuentes (fase 09; también la usa la 09b)

Además, índice (`source_id`, `external_id`) en `jobs` para que los conectores reconozcan una oferta
ya vista por su id en la fuente.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-02 16:09:51

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=False),
        sa.Column("actor", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("found", sa.Integer(), nullable=False),
        sa.Column("after_filters", sa.Integer(), nullable=False),
        sa.Column("created", sa.Integer(), nullable=False),
        sa.Column("completed", sa.Integer(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name=op.f("fk_source_runs_source_id_sources")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_runs")),
    )
    with op.batch_alter_table("source_runs", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_source_runs_source_id"), ["source_id"], unique=False)

    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.create_index("ix_jobs_source_external", ["source_id", "external_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_index("ix_jobs_source_external")

    with op.batch_alter_table("source_runs", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_source_runs_source_id"))

    op.drop_table("source_runs")
