"""Ayudas de los tests de respuestas por correo (fase 15): ofertas enviadas y correos de ejemplo.

Los correos son los ficticios de `demo/emails/respuestas/` (ver su README).
"""

import shutil
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.models import Company, Job, Source
from app.services import events
from app.services.normalize import normalize_company

DEMO = REPO_ROOT / "demo" / "emails" / "respuestas"
NOW = datetime(2026, 10, 11, 9, 0, tzinfo=UTC)
APPLIED = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)

# Empresa -> URL de la oferta. Brétema y Lonxa publican en un ATS (su dominio no cuenta).
DEMO_COMPANIES = {
    "Brétema Analytics": "https://boards.greenhouse.io/bretema/jobs/1",
    "Lonxa Retail Tech": "https://jobs.lever.co/lonxa/2",
    "Néboa Data": "https://neboa.example/empleo/ae",
    "Rías Software S.L.": "https://careers.riassoftware.example/data-engineer",
    "Castro Labs": "https://castrolabs.example/jobs/de",
}


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


def add_demo_jobs(session: Session) -> dict[str, Job]:
    return {
        company: add_applied_job(session, company, url) for company, url in DEMO_COMPANIES.items()
    }


def copy_to_inbox(files: list[Path]) -> Path:
    """Deja los `.eml` en `data/inbox/respuestas/` (la alternativa local a IMAP)."""
    folder = get_settings().replies_inbox_dir
    folder.mkdir(parents=True, exist_ok=True)
    for path in files:
        shutil.copy(path, folder / path.name)
    return folder
