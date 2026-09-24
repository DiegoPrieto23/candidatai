"""Consultas de ofertas. El texto crudo (no confiable) solo sale por `get_job`, envuelto."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Company, Job
from app.services.events import JobNotFoundError
from app.services.pipeline import Stage
from app.services.untrusted import wrap_untrusted

DEFAULT_LIMIT = 20
MAX_LIMIT = 200

# `score_desc` ordena como `recent` hasta que exista el score (fase 07).
JobOrder = Literal["score_desc", "recent"]


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
    session: Session,
    stage: str | None = None,
    limit: int = DEFAULT_LIMIT,
    order: JobOrder = "score_desc",
) -> list[JobSummary]:
    """Ofertas filtradas por etapa. Sin score (fase 07), las más recientes primero."""
    if order not in ("score_desc", "recent"):
        raise InvalidQueryError(f"Orden desconocido: «{order}». Válidos: score_desc, recent.")
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


class JobDetail(JobSummary):
    posted_at: datetime | None
    text: str  # envuelto en <untrusted_job_posting>: datos, nunca instrucciones


def get_job(session: Session, job_id: int) -> JobDetail:
    """Metadatos de la oferta y su texto crudo envuelto como no confiable, con sus `risk_flags`."""
    row = session.execute(
        select(Job, Company.name, Application.stage)
        .join(Company, Company.id == Job.company_id)
        .outerjoin(Application, Application.job_id == Job.id)
        .where(Job.id == job_id)
    ).first()
    if row is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    job, company, job_stage = row
    return JobDetail(
        id=job.id,
        title=job.title,
        company=company,
        location=job.location_raw,
        url=job.url,
        stage=Stage(job_stage) if job_stage else None,
        risk_flags=job.risk_flags,
        duplicate_of=job.duplicate_of,
        first_seen_at=job.first_seen_at,
        posted_at=job.posted_at,
        text=wrap_untrusted(job.id, job.raw_text, job.risk_flags),
    )
