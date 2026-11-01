"""título normalizado de cada extracción en su columna

`job_extractions.title_normalized`, copia de `data["title_normalized"]`: el embudo agrupa por
puesto sin leer el JSON entero de cada extracción. Se rellena con lo que ya hay.

Revision ID: 0033
Revises: 0032
Create Date: 2026-11-01 18:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | Sequence[str] | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_extractions") as batch_op:
        batch_op.add_column(sa.Column("title_normalized", sa.Text(), nullable=True))
    # Solo si es texto: lo que no lo sea no es un título y el embudo lo contaría mal.
    op.execute(
        "UPDATE job_extractions SET title_normalized = json_extract(data, '$.title_normalized') "
        "WHERE json_type(data, '$.title_normalized') = 'text'"
    )


def downgrade() -> None:
    with op.batch_alter_table("job_extractions") as batch_op:
        batch_op.drop_column("title_normalized")
