"""mensajes a personas y dosier de empresa

En `message_drafts`, los mensajes de la fase 18 (LinkedIn y correo de candidatura): `subject` pasa a
admitir nulos (LinkedIn no lleva asunto) y se añaden `recipient_role`, `contact_id`,
`network_contact_id`, `recipient_name` y `attachments`. Tabla `company_research`: el dosier de cada empresa.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-12 20:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("message_drafts", schema=None) as batch_op:
        batch_op.alter_column("subject", existing_type=sa.String(length=300), nullable=True)
        batch_op.add_column(sa.Column("recipient_role", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("contact_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("network_contact_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("recipient_name", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("attachments", sa.JSON(), nullable=True))
        batch_op.create_foreign_key(
            batch_op.f("fk_message_drafts_contact_id_contacts"), "contacts", ["contact_id"], ["id"]
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_message_drafts_network_contact_id_network_contacts"),
            "network_contacts",
            ["network_contact_id"],
            ["id"],
        )

    op.create_table(
        "company_research",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("risk_flags", sa.JSON(), nullable=False),
        sa.Column("file_name", sa.String(length=200), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"], name=op.f("fk_company_research_company_id_companies")
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_company_research_job_id_jobs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_company_research")),
        sa.UniqueConstraint("company_id", name=op.f("uq_company_research_company_id")),
    )


def downgrade() -> None:
    op.drop_table("company_research")
    # Los mensajes de LinkedIn no tienen asunto: se quitan antes de volver a exigirlo.
    op.execute("DELETE FROM message_drafts WHERE subject IS NULL")
    with op.batch_alter_table("message_drafts", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_message_drafts_network_contact_id_network_contacts"),
            type_="foreignkey",
        )
        batch_op.drop_constraint(
            batch_op.f("fk_message_drafts_contact_id_contacts"), type_="foreignkey"
        )
        batch_op.drop_column("attachments")
        batch_op.drop_column("recipient_name")
        batch_op.drop_column("network_contact_id")
        batch_op.drop_column("contact_id")
        batch_op.drop_column("recipient_role")
        batch_op.alter_column("subject", existing_type=sa.String(length=300), nullable=False)
