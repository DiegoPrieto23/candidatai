"""Consultas de ofertas. El texto crudo (no confiable) solo sale por `get_job`, envuelto."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Application, Company, Job, Match
from app.schemas.llm_io import JobExtraction
from app.services import extractions
from app.services.events import EventOut, JobNotFoundError
from app.services.pipeline import EventType, Stage, job_events
from app.services.untrusted import wrap_untrusted

DEFAULT_LIMIT = 20
MAX_LIMIT = 200

# `score_desc`: por el score del último match; las ofertas sin score, al final y por fecha.
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
    score: int | None  # del último match; None si aún no se ha puntuado


def _last_match():
    """Subconsulta con el último match de cada oferta."""
    return (
        select(Match.job_id.label("job_id"), func.max(Match.id).label("match_id"))
        .group_by(Match.job_id)
        .subquery()
    )


def _summary_query():
    """Oferta, empresa, etapa y score del último match (outer joins: puede no haber)."""
    last = _last_match()
    return (
        select(Job, Company.name, Application.stage, Match.score)
        .join(Company, Company.id == Job.company_id)
        .outerjoin(Application, Application.job_id == Job.id)
        .outerjoin(last, last.c.job_id == Job.id)
        .outerjoin(Match, Match.id == last.c.match_id)
    )


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
    """Ofertas filtradas por etapa, por score (las sin score al final) o las más recientes."""
    if order not in ("score_desc", "recent"):
        raise InvalidQueryError(f"Orden desconocido: «{order}». Válidos: score_desc, recent.")
    if not 1 <= limit <= MAX_LIMIT:
        raise InvalidQueryError(f"`limit` debe estar entre 1 y {MAX_LIMIT}.")
    recent = (Job.first_seen_at.desc(), Job.id.desc())
    ordering = (Match.score.desc().nulls_last(), *recent) if order == "score_desc" else recent
    query = _summary_query().order_by(*ordering).limit(limit)
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
            score=score,
        )
        for job, company, job_stage, score in session.execute(query).all()
    ]


class JobDetail(JobSummary):
    posted_at: datetime | None
    text: str  # envuelto en <untrusted_job_posting>: datos, nunca instrucciones


def get_job(session: Session, job_id: int) -> JobDetail:
    """Metadatos de la oferta y su texto crudo envuelto como no confiable, con sus `risk_flags`."""
    row = session.execute(_summary_query().where(Job.id == job_id)).first()
    if row is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    job, company, job_stage, score = row
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
        score=score,
        posted_at=job.posted_at,
        text=wrap_untrusted(job.id, job.raw_text, job.risk_flags),
    )


# --- Vistas para la UI (API REST) ---------------------------------------------------------------
# La UI muestra el texto a una persona (React lo escapa): va sin envoltorio. Ningún modelo lo lee.

RemoteMode = Literal["onsite", "hybrid", "remote", "unknown"]


class JobRow(JobSummary):
    remote_mode: RemoteMode | None  # de la extracción vigente; None si aún no hay


class JobPage(BaseModel):
    items: list[JobRow]
    total: int
    limit: int
    offset: int


def _escape_like(value: str) -> str:
    return value.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def search_jobs(
    session: Session,
    stage: str | None = None,
    q: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
) -> JobPage:
    """Página de ofertas para la bandeja: filtro por etapa, búsqueda en título y empresa."""
    if not 1 <= limit <= MAX_LIMIT:
        raise InvalidQueryError(f"`limit` debe estar entre 1 y {MAX_LIMIT}.")
    if offset < 0:
        raise InvalidQueryError("`offset` no puede ser negativo.")
    filters = []
    if stage is not None:
        filters.append(Application.stage == parse_stage(stage).value)
    if q is not None and q.strip():
        pattern = f"%{_escape_like(q.strip())}%"
        filters.append(
            or_(
                Job.title.ilike(pattern, escape="!"),
                Company.name.ilike(pattern, escape="!"),
            )
        )
    base = _summary_query().where(*filters)
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = session.execute(
        base.order_by(Job.first_seen_at.desc(), Job.id.desc()).limit(limit).offset(offset)
    ).all()
    latest = extractions.latest_rows(session, [job.id for job, *_ in rows])
    items = []
    for job, company, job_stage, score in rows:
        extraction = latest.get(job.id)
        items.append(
            JobRow(
                id=job.id,
                title=job.title,
                company=company,
                location=job.location_raw,
                url=job.url,
                stage=Stage(job_stage) if job_stage else None,
                risk_flags=job.risk_flags,
                duplicate_of=job.duplicate_of,
                first_seen_at=job.first_seen_at,
                score=score,
                remote_mode=extraction.data.get("remote_mode") if extraction else None,
            )
        )
    return JobPage(items=items, total=total, limit=limit, offset=offset)


class InjectionReport(BaseModel):
    source: str  # `system` o `agent`
    agent_name: str | None
    excerpt: str | None
    occurred_at: datetime


class InjectionWarning(BaseModel):
    """Por qué la oferta puede llevar contenido dirigido a una IA."""

    risk_flags: list[str]  # detectados por el código al darla de alta
    reports: list[InjectionReport]  # eventos `injection_suspected` (sistema o agente)


class ExtractionView(BaseModel):
    extraction_id: int
    created_at: datetime
    data: JobExtraction


class JobView(JobSummary):
    posted_at: datetime | None
    raw_text: str  # contenido no confiable: se muestra como texto, nunca se interpreta
    extraction: ExtractionView | None
    events: list[EventOut]
    injection: InjectionWarning | None  # None si no hay nada sospechoso


def get_job_view(session: Session, job_id: int) -> JobView:
    """Ficha completa de una oferta para la UI."""
    row = session.execute(_summary_query().where(Job.id == job_id)).first()
    if row is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    job, company, job_stage, score = row
    extraction_row = extractions.latest_rows(session, [job.id]).get(job.id)
    events = job_events(session, job_id)
    reports = [
        InjectionReport(
            source=str(e.payload.get("source") or e.actor),
            agent_name=e.agent_name,
            excerpt=e.payload.get("excerpt"),
            occurred_at=e.occurred_at,
        )
        for e in events
        if e.type == EventType.INJECTION_SUSPECTED
    ]
    injection = (
        InjectionWarning(risk_flags=job.risk_flags, reports=reports)
        if job.risk_flags or reports
        else None
    )
    return JobView(
        id=job.id,
        title=job.title,
        company=company,
        location=job.location_raw,
        url=job.url,
        stage=Stage(job_stage) if job_stage else None,
        risk_flags=job.risk_flags,
        duplicate_of=job.duplicate_of,
        first_seen_at=job.first_seen_at,
        score=score,
        posted_at=job.posted_at,
        raw_text=job.raw_text,
        extraction=(
            ExtractionView(
                extraction_id=extraction_row.id,
                created_at=extraction_row.created_at,
                data=JobExtraction.model_validate(extraction_row.data),
            )
            if extraction_row
            else None
        ),
        events=[EventOut.model_validate(e, from_attributes=True) for e in events],
        injection=injection,
    )
