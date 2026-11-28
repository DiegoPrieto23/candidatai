"""Preguntas y permisos desde el portal

`user_prompts.run_id` (la ejecución sin ventana que lo pidió) y `user_prompts.tool` (en un
permiso, la herramienta). `agent_permission_rules`: lo que se permite siempre sin preguntar.

Revision ID: 0046
Revises: 0045
Create Date: 2026-11-27 23:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0046"
down_revision: str | Sequence[str] | None = "0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_prompts") as batch_op:
        batch_op.add_column(sa.Column("run_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("tool", sa.String(length=80), nullable=True))
        batch_op.create_index(batch_op.f("ix_user_prompts_run_id"), ["run_id"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_user_prompts_run_id_agent_runs"), "agent_runs", ["run_id"], ["id"]
        )
    op.create_table(
        "agent_permission_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tool", sa.String(length=80), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_permission_rules")),
        sa.UniqueConstraint("tool", "detail", name=op.f("uq_agent_permission_rules_tool")),
    )


def downgrade() -> None:
    op.drop_table("agent_permission_rules")
    with op.batch_alter_table("user_prompts") as batch_op:
        batch_op.drop_constraint(
            batch_op.f("fk_user_prompts_run_id_agent_runs"), type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_user_prompts_run_id"))
        batch_op.drop_column("tool")
        batch_op.drop_column("run_id")
