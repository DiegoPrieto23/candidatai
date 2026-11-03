"""Ayudas de los tests de respuestas por correo (fase 15): ofertas enviadas y correos de ejemplo.

Los correos son los ficticios de `demo/emails/respuestas/` (ver su README).
"""

import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.models import Job
from tests.applied_support import APPLIED, NOW, add_applied_job

DEMO = REPO_ROOT / "demo" / "emails" / "respuestas"

# Empresa -> URL de la oferta. Brétema y Lonxa publican en un ATS (su dominio no cuenta).
DEMO_COMPANIES = {
    "Brétema Analytics": "https://boards.greenhouse.io/bretema/jobs/1",
    "Lonxa Retail Tech": "https://jobs.lever.co/lonxa/2",
    "Néboa Data": "https://neboa.example/empleo/ae",
    "Rías Software S.L.": "https://careers.riassoftware.example/data-engineer",
    "Castro Labs": "https://castrolabs.example/jobs/de",
}


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


__all__ = ["APPLIED", "DEMO", "NOW", "add_applied_job", "add_demo_jobs", "copy_to_inbox"]
