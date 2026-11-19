"""reaperturas de ofertas: huella no única y `jobs.reopening_of`

Una vacante cerrada por la empresa (o caducada) que vuelve a publicarse pasado
`dedup.reopen_after_days` entra como una oferta nueva enlazada a la antigua (`reopening_of`) y con
su misma huella, así que `jobs.fingerprint` deja de ser única (sigue indexada).

Revision ID: 0042
Revises: 0041
Create Date: 2026-11-19 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0042"
down_revision: str | Sequence[str] | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_constraint("uq_jobs_fingerprint", type_="unique")
        batch_op.create_index("ix_jobs_fingerprint", ["fingerprint"])
        batch_op.add_column(sa.Column("reopening_of", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_jobs_reopening_of_jobs", "jobs", ["reopening_of"], ["id"])
        batch_op.create_index("ix_jobs_reopening_of", ["reopening_of"])


def downgrade() -> None:
    # Con reaperturas guardadas, la huella repetida impide volver a hacerla única: se avisa.
    bind = op.get_bind()
    repeated = bind.execute(
        sa.text("SELECT fingerprint FROM jobs GROUP BY fingerprint HAVING COUNT(*) > 1 LIMIT 1")
    ).first()
    if repeated is not None:
        raise RuntimeError(
            "Hay ofertas reabiertas con la misma huella que otra: bórralas antes de volver atrás."
        )
    with op.batch_alter_table("jobs") as batch_op:
        batch_op.drop_index("ix_jobs_reopening_of")
        batch_op.drop_constraint("fk_jobs_reopening_of_jobs", type_="foreignkey")
        batch_op.drop_column("reopening_of")
        batch_op.drop_index("ix_jobs_fingerprint")
        batch_op.create_unique_constraint("uq_jobs_fingerprint", ["fingerprint"])
