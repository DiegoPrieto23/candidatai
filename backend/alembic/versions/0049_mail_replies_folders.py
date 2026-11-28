"""Varias carpetas de respuestas por buzón

`mail_sources.replies_folders` (lista) sustituye a `replies_folder`, con lo que tuviera cada buzón.
`replies_folders_set`: en la cuenta de `.env`, que se eligieron en la UI.

Revision ID: 0049
Revises: 0048
Create Date: 2026-11-28 20:00:00

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0049"
down_revision: str | Sequence[str] | None = "0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("mail_sources") as batch_op:
        batch_op.add_column(sa.Column("replies_folders", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "replies_folders_set", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, replies_folder FROM mail_sources")).all()
    for row_id, folder in rows:
        conn.execute(
            sa.text("UPDATE mail_sources SET replies_folders = :folders WHERE id = :id"),
            {"folders": json.dumps([folder or "INBOX"]), "id": row_id},
        )
    with op.batch_alter_table("mail_sources") as batch_op:
        batch_op.alter_column("replies_folders", existing_type=sa.JSON(), nullable=False)
        batch_op.drop_column("replies_folder")


def downgrade() -> None:
    with op.batch_alter_table("mail_sources") as batch_op:
        batch_op.add_column(
            sa.Column(
                "replies_folder", sa.String(length=200), nullable=False, server_default="INBOX"
            )
        )
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, replies_folders FROM mail_sources")).all()
    for row_id, folders in rows:
        listed = json.loads(folders) if isinstance(folders, str) else folders
        conn.execute(
            sa.text("UPDATE mail_sources SET replies_folder = :folder WHERE id = :id"),
            {"folder": (listed or ["INBOX"])[0], "id": row_id},
        )
    with op.batch_alter_table("mail_sources") as batch_op:
        batch_op.drop_column("replies_folders_set")
        batch_op.drop_column("replies_folders")
