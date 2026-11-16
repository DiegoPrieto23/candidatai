"""conversaciones del asistente del portal

Tabla `assistant_conversations` y `assistant_requests.conversation_id`: el «Asistente» pasa a
funcionar como un chat con conversaciones independientes. Cada petición que ya existía queda en una
conversación propia, con su pregunta como título.

Revision ID: 0039
Revises: 0038
Create Date: 2026-11-16 18:00:00

"""

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.models.base import UTCDateTime

revision: str = "0039"
down_revision: str | Sequence[str] | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TITLE_CHARS = 60


def _title(text: str) -> str:
    """Copia fija de `assistant.conversation_title` (una migración no cambia con la app)."""
    flat = re.sub(r"\s+", " ", text).strip()
    if len(flat) <= TITLE_CHARS:
        return flat
    cut = flat[:TITLE_CHARS].rsplit(" ", 1)[0] if " " in flat[:TITLE_CHARS] else flat[:TITLE_CHARS]
    return cut.rstrip(" ,.;:¿?¡!") + "…"


def upgrade() -> None:
    op.create_table(
        "assistant_conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("created_at", UTCDateTime(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), nullable=False),
    )
    op.create_index(
        "ix_assistant_conversations_updated_at", "assistant_conversations", ["updated_at"]
    )
    with op.batch_alter_table("assistant_requests") as batch_op:
        batch_op.add_column(sa.Column("conversation_id", sa.Integer(), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT id, text, created_at, COALESCE(answered_at, created_at) "
            "FROM assistant_requests ORDER BY id"
        )
    ).all()
    for request_id, text, created_at, updated_at in rows:
        conversation_id = conn.execute(
            sa.text(
                "INSERT INTO assistant_conversations (title, created_at, updated_at) "
                "VALUES (:title, :created, :updated) RETURNING id"
            ),
            {"title": _title(text), "created": created_at, "updated": updated_at},
        ).scalar_one()
        conn.execute(
            sa.text("UPDATE assistant_requests SET conversation_id = :c WHERE id = :r"),
            {"c": conversation_id, "r": request_id},
        )

    with op.batch_alter_table("assistant_requests") as batch_op:
        batch_op.alter_column("conversation_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "fk_assistant_requests_conversation_id",
            "assistant_conversations",
            ["conversation_id"],
            ["id"],
        )
        batch_op.create_index("ix_assistant_requests_conversation_id", ["conversation_id"])


def downgrade() -> None:
    with op.batch_alter_table("assistant_requests") as batch_op:
        batch_op.drop_index("ix_assistant_requests_conversation_id")
        batch_op.drop_constraint("fk_assistant_requests_conversation_id", type_="foreignkey")
        batch_op.drop_column("conversation_id")
    op.drop_index("ix_assistant_conversations_updated_at", table_name="assistant_conversations")
    op.drop_table("assistant_conversations")
