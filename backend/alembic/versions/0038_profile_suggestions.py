"""propuestas del agente para el perfil

Tabla `profile_suggestions`: lo que el agente propone para un campo del perfil (hoy, el resumen en
inglés) y que el usuario usa o descarta en «Mi perfil». El agente nunca escribe en el perfil desde
aquí.

Revision ID: 0038
Revises: 0037
Create Date: 2026-11-14 20:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import UTCDateTime

revision: str = "0038"
down_revision: str | Sequence[str] | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "profile_suggestions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("field", sa.String(length=40), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("agent_name", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("resolved_at", UTCDateTime(), nullable=True),
    )
    op.create_index("ix_profile_suggestions_status", "profile_suggestions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_profile_suggestions_status", table_name="profile_suggestions")
    op.drop_table("profile_suggestions")
