"""auditoría de lo que se edita desde «Mi perfil»

Fase 25.7: `profile_edits`, una fila por guardado del perfil, del contexto o de una
muestra de estilo desde la UI, con la sección y el sha256 del fichero antes y después (sin el
texto). No va en `events`: esos son de una oferta.

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-17 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | Sequence[str] | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "profile_edits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("target", sa.String(length=16), nullable=False),
        sa.Column("section", sa.String(length=128), nullable=True),
        sa.Column("action", sa.String(length=16), nullable=False),
        sa.Column("hash_before", sa.String(length=64), nullable=True),
        sa.Column("hash_after", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_profile_edits")),
    )


def downgrade() -> None:
    op.drop_table("profile_edits")
