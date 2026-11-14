"""peticiones al asistente del portal

Tabla `assistant_requests`: lo que el usuario escribe en «Pídeselo a tu agente» (el texto nunca va
en la orden del agente, solo su `id`), la ejecución o el encargo que lo atiende y la respuesta.

Revision ID: 0037
Revises: 0036
Create Date: 2026-11-14 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import UTCDateTime

revision: str = "0037"
down_revision: str | Sequence[str] | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "assistant_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("agent_runs.id"), nullable=True),
        sa.Column("request_id", sa.Integer(), sa.ForeignKey("agent_requests.id"), nullable=True),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("links", sa.JSON(), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("answered_at", UTCDateTime(), nullable=True),
    )
    op.create_index("ix_assistant_requests_run_id", "assistant_requests", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_assistant_requests_run_id", table_name="assistant_requests")
    op.drop_table("assistant_requests")
