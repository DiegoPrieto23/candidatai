"""red de contactos de LinkedIn y referencias en los contactos del proceso

Tabla `network_contacts` (la exportación oficial `Connections.csv`, sin emails) y, en `contacts`,
`relation` (papel en el proceso), `referral` y `referral_at` (referencia pedida o dada) y
`network_contact_id` (la persona de la red de la que sale).

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-12 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "network_contacts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("first_name", sa.String(length=200), nullable=False),
        sa.Column("last_name", sa.String(length=200), nullable=False),
        sa.Column("linkedin_url", sa.String(length=500), nullable=True),
        sa.Column("company", sa.String(length=200), nullable=True),
        sa.Column("company_key", sa.String(length=200), nullable=True),
        sa.Column("position", sa.String(length=300), nullable=True),
        sa.Column("connected_on", sa.Date(), nullable=True),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_network_contacts")),
        sa.UniqueConstraint("linkedin_url", name=op.f("uq_network_contacts_linkedin_url")),
    )
    with op.batch_alter_table("network_contacts", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_network_contacts_company_key"), ["company_key"], unique=False
        )

    with op.batch_alter_table("contacts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("relation", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("referral", sa.String(length=16), nullable=True))
        batch_op.add_column(sa.Column("referral_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("network_contact_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_contacts_network_contact_id"), ["network_contact_id"], unique=False
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_contacts_network_contact_id_network_contacts"),
            "network_contacts",
            ["network_contact_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("contacts", schema=None) as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_contacts_network_contact_id_network_contacts"), type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_contacts_network_contact_id"))
        batch_op.drop_column("network_contact_id")
        batch_op.drop_column("referral_at")
        batch_op.drop_column("referral")
        batch_op.drop_column("relation")

    with op.batch_alter_table("network_contacts", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_network_contacts_company_key"))
    op.drop_table("network_contacts")
