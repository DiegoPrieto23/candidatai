"""correcciones del CV y versión vigente

Tabla `cv_corrections`: lo que el usuario pide cambiar de un CV ya generado (lo lee `correct-cv`).
En `documents`, `base_document_id` (de qué versión sale), `correction_id` (la corrección que la
originó) y `superseded` («Volver» dejó esa versión detrás: no es la vigente aunque sea más nueva).
Nada se borra.

Revision ID: 0034
Revises: 0033
Create Date: 2026-11-02 09:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | Sequence[str] | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cv_corrections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("base_document_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_cv_corrections_job_id_jobs")
        ),
        sa.ForeignKeyConstraint(
            ["base_document_id"],
            ["documents.id"],
            name=op.f("fk_cv_corrections_base_document_id_documents"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cv_corrections")),
    )
    op.create_index(op.f("ix_cv_corrections_job_id"), "cv_corrections", ["job_id"])
    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("base_document_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("correction_id", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("superseded", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.create_foreign_key(
            batch.f("fk_documents_base_document_id_documents"),
            "documents",
            ["base_document_id"],
            ["id"],
        )
        batch.create_foreign_key(
            batch.f("fk_documents_correction_id_cv_corrections"),
            "cv_corrections",
            ["correction_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint(
            batch.f("fk_documents_correction_id_cv_corrections"), type_="foreignkey"
        )
        batch.drop_constraint(
            batch.f("fk_documents_base_document_id_documents"), type_="foreignkey"
        )
        batch.drop_column("superseded")
        batch.drop_column("correction_id")
        batch.drop_column("base_document_id")
    op.drop_index(op.f("ix_cv_corrections_job_id"), table_name="cv_corrections")
    op.drop_table("cv_corrections")
