"""Ayudas de los tests de seguimiento y entrevistas: una oferta ya enviada y sus fechas."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, Job, Source
from app.services import events
from app.services.normalize import normalize_company

NOW = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
APPLIED = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def add_applied_job(
    session: Session, company: str, url: str = "", applied_at: datetime = APPLIED
) -> Job:
    """Oferta enviada (`applied`) el `applied_at` dado, con su empresa."""
    source = session.scalar(select(Source).where(Source.name == "Manual"))
    if source is None:
        source = Source(kind="manual_text", name="Manual")
        session.add(source)
        session.flush()
    row = Company(name=company, normalized_name=normalize_company(company))
    session.add(row)
    session.flush()
    job = Job(
        source_id=source.id,
        company_id=row.id,
        url=url,
        title="Data Engineer",
        raw_text="Texto.",
        fingerprint=f"fp-{row.id}",
    )
    session.add(job)
    session.flush()
    start = datetime(2026, 9, 1, tzinfo=UTC)
    for step in ("found", "extracted", "approved"):
        events.record(session, job.id, step, "user", occurred_at=start)
    events.record(session, job.id, "applied_manually", "user", occurred_at=applied_at)
    session.flush()
    return job
