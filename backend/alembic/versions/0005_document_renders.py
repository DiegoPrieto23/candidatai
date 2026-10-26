"""document_renders: contenido y presentación separados

`documents` guarda solo el contenido; cada combinación de plantilla y opciones es un
`document_render` con sus ficheros, páginas, cobertura y avisos. `applications.document_id` pasa a
`render_id`. Los documentos anteriores con ficheros pasan a un render `legacy` seleccionado.

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-28 18:26:29

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_renders",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.String(length=64), nullable=False),
        sa.Column("template_hash", sa.String(length=64), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("docx_path", sa.String(length=500), nullable=True),
        sa.Column("pdf_path", sa.String(length=500), nullable=True),
        sa.Column("pages", sa.Integer(), nullable=False),
        sa.Column("keyword_coverage", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("selected", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_renders_document_id_documents"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_renders")),
    )
    with op.batch_alter_table("document_renders", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_document_renders_document_id"), ["document_id"], unique=False
        )

    # Documentos con ficheros de antes de esta migración: un render `legacy` seleccionado.
    op.execute(
        """
        INSERT INTO document_renders (document_id, template_id, template_hash, options, docx_path,
            pdf_path, pages, keyword_coverage, warnings, selected, created_at)
        SELECT id, 'legacy', '', '{}', docx_path, pdf_path, COALESCE(pages, 0), '{}', '[]', 1,
            created_at
        FROM documents
        WHERE docx_path IS NOT NULL OR pdf_path IS NOT NULL
        """
    )

    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.add_column(sa.Column("render_id", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE applications SET render_id = (
            SELECT r.id FROM document_renders r WHERE r.document_id = applications.document_id
        )
        WHERE document_id IS NOT NULL
        """
    )
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_applications_document_id_documents"), type_="foreignkey"
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_applications_render_id_document_renders"),
            "document_renders",
            ["render_id"],
            ["id"],
        )
        batch_op.drop_column("document_id")

    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.drop_column("pdf_path")
        batch_op.drop_column("pages")
        batch_op.drop_column("docx_path")


def downgrade() -> None:
    # Se conserva el render seleccionado de cada documento; los demás se pierden.
    with op.batch_alter_table("documents", schema=None) as batch_op:
        batch_op.add_column(sa.Column("docx_path", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("pdf_path", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("pages", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE documents SET
            docx_path = (SELECT docx_path FROM document_renders r
                         WHERE r.document_id = documents.id AND r.selected = 1),
            pdf_path = (SELECT pdf_path FROM document_renders r
                        WHERE r.document_id = documents.id AND r.selected = 1),
            pages = (SELECT pages FROM document_renders r
                     WHERE r.document_id = documents.id AND r.selected = 1)
        """
    )

    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.add_column(sa.Column("document_id", sa.Integer(), nullable=True))
    op.execute(
        """
        UPDATE applications SET document_id = (
            SELECT r.document_id FROM document_renders r WHERE r.id = applications.render_id
        )
        WHERE render_id IS NOT NULL
        """
    )
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_applications_render_id_document_renders"), type_="foreignkey"
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_applications_document_id_documents"),
            "documents",
            ["document_id"],
            ["id"],
        )
        batch_op.drop_column("render_id")

    with op.batch_alter_table("document_renders", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_document_renders_document_id"))
    op.drop_table("document_renders")
