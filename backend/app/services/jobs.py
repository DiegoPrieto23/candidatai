"""Consultas de ofertas para listados. Nunca devuelven el texto crudo (no confiable)."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Company, Job
from app.services.pipeline import Stage

DEFAULT_LIMIT = 20
MAX_LIMIT = 200


class InvalidQueryError(ValueError):
    pass


class JobSummary(BaseModel):
    id: int
    title: str
    company: str
    location: str | None
    url: str
    stage: Stage | None
    risk_flags: list[str]
    duplicate_of: int | None
    first_seen_at: datetime


def parse_stage(value: str) -> Stage:
    try:
        return Stage(value)
    except ValueError:
        valid = ", ".join(s.value for s in Stage)
        raise InvalidQueryError(f"Etapa desconocida: «{value}». Válidas: {valid}.") from None


def list_jobs(
    session: Session, stage: str | None = None, limit: int = DEFAULT_LIMIT
) -> list[JobSummary]:
    """Ofertas más recientes primero, opcionalmente filtradas por etapa."""
    if not 1 <= limit <= MAX_LIMIT:
        raise InvalidQueryError(f"`limit` debe estar entre 1 y {MAX_LIMIT}.")
    query = (
        select(Job, Company.name, Application.stage)
        .join(Company, Company.id == Job.company_id)
        .outerjoin(Application, Application.job_id == Job.id)
        .order_by(Job.first_seen_at.desc(), Job.id.desc())
        .limit(limit)
    )
    if stage is not None:
        query = query.where(Application.stage == parse_stage(stage).value)
    return [
        JobSummary(
            id=job.id,
            title=job.title,
            company=company,
            location=job.location_raw,
            url=job.url,
            stage=Stage(job_stage) if job_stage else None,
            risk_flags=job.risk_flags,
            duplicate_of=job.duplicate_of,
            first_seen_at=job.first_seen_at,
        )
        for job, company, job_stage in session.execute(query).all()
    ]
