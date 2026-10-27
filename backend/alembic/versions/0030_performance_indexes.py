"""índices para listas y analítica con muchas ofertas

Medido con 5000 ofertas y 75 000 eventos:

- `events (type, job_id, occurred_at)`: el embudo, la calibración y el kanban buscan eventos de un
  tipo, en todas las ofertas o en una. Con el índice de `(job_id, occurred_at)` leían todos los
  eventos de cada oferta.
- `jobs (company_id, first_seen_at, source_id)` en lugar de `jobs (company_id)`: las filas de
  `jobs` son largas (el texto de la oferta) y `first_seen_at` va detrás del texto, así que leerla
  de la fila es caro. SQLite recorre `jobs` por el índice de `company_id` para ordenar la Bandeja
  y montar el embudo: con estas columnas no tiene que ir a la fila. Sigue sirviendo para buscar
  por empresa.
- `jobs (first_seen_at)`: la Bandeja por fecha de alta, que es el orden por defecto, lee solo las
  25 de la página.

Solo índices: no cambia ningún dato.

Revision ID: 0030
Revises: 0029
Create Date: 2026-10-28 10:00:00

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0030"
down_revision: str | Sequence[str] | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_events_type_job_id_occurred_at", "events", ["type", "job_id", "occurred_at"]
    )
    op.create_index(
        "ix_jobs_company_id_first_seen_at", "jobs", ["company_id", "first_seen_at", "source_id"]
    )
    op.drop_index("ix_jobs_company_id", table_name="jobs")
    op.create_index("ix_jobs_first_seen_at", "jobs", ["first_seen_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_first_seen_at", table_name="jobs")
    op.create_index("ix_jobs_company_id", "jobs", ["company_id"])
    op.drop_index("ix_jobs_company_id_first_seen_at", table_name="jobs")
    op.drop_index("ix_events_type_job_id_occurred_at", table_name="events")
