"""varios buzones de alertas

Fase 27.4: `mail_sources`, un buzón por fila (IMAP o una carpeta de `.eml`), con el
nombre de la variable de `.env` que guarda su contraseña y nunca la contraseña; y
`mail_source_changes`, la auditoría de altas, cambios y bajas (qué campos, sin valores). La cuenta
`CAI_IMAP_*` de siempre la crea la app al arrancar, como «Principal».

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-23 20:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | Sequence[str] | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "mail_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=True),
        sa.Column("port", sa.Integer(), nullable=True),
        sa.Column("security", sa.String(length=16), nullable=False),
        sa.Column("user", sa.String(length=320), nullable=True),
        sa.Column("folder", sa.String(length=200), nullable=False),
        sa.Column("replies_folder", sa.String(length=200), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("read_replies", sa.Boolean(), nullable=False),
        sa.Column("secret_ref", sa.String(length=64), nullable=True),
        sa.Column("from_env", sa.Boolean(), nullable=False),
        sa.Column("allow_private", sa.Boolean(), nullable=False),
        sa.Column("last_polled_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mail_sources")),
        sa.UniqueConstraint("label", name=op.f("uq_mail_sources_label")),
    )
    op.create_table(
        "mail_source_changes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("mail_source_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("fields", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mail_source_changes")),
    )


def downgrade() -> None:
    op.drop_table("mail_source_changes")
    op.drop_table("mail_sources")
