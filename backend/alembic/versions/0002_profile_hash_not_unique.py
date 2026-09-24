"""profile_versions.content_hash: índice normal en vez de único

Volver a un contenido anterior (v1 -> v2 -> v1) tiene que crear una versión nueva que pase a ser
la actual. Lo que se evita es repetir la versión más reciente, y eso lo hace el servicio.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-24 18:00:00

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("profile_versions", schema=None) as batch_op:
        batch_op.drop_constraint("uq_profile_versions_content_hash", type_="unique")
        batch_op.create_index(
            batch_op.f("ix_profile_versions_content_hash"), ["content_hash"], unique=False
        )


def downgrade() -> None:
    # Falla si hay versiones con el mismo hash (se volvió a un contenido anterior).
    with op.batch_alter_table("profile_versions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_profile_versions_content_hash"))
        batch_op.create_unique_constraint("uq_profile_versions_content_hash", ["content_hash"])
