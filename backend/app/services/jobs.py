"""Consultas de ofertas. El texto crudo (no confiable) solo sale por `get_job`, envuelto."""

from datetime import datetime
from typing import Literal, get_args

from pydantic import BaseModel
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models import Application, Company, Job, Match
from app.models import JobExtraction as JobExtractionRow
from app.schemas.llm_io import JobExtraction, Salary
from app.services import application_archive, extractions, network
from app.services.events import EventOut, JobNotFoundError
from app.services.pipeline import EventType, Stage, job_events
from app.services.signals import JobSignals
from app.services.signals import read as read_signals
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
    # Posible cierre y republicación (fase 16): observaciones del código, no veredictos.
    signals: JobSignals = JobSignals()


def last_match_subquery():
    """Subconsulta con el último match de cada oferta."""
    return (
        select(Match.job_id.label("job_id"), func.max(Match.id).label("match_id"))
        .group_by(Match.job_id)
        .subquery()
    )


def _summary_query():
    """Oferta, empresa, etapa y score del último match (outer joins: puede no haber)."""
    last = last_match_subquery()
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
            signals=read_signals(job),
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
        signals=read_signals(job),
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
    salary: Salary | None  # de la extracción vigente; None si no lo indica o aún no hay
    known_contacts: int = 0  # personas de tu red de LinkedIn en la empresa (fase 18)
    # Cuándo y con qué evento se cerró (fase 27.6); None si no está cerrada.
    closed_at: datetime | None = None
    closed_by: str | None = None


# Orden de la bandeja. Las ofertas sin el dato (sin score, sin salario o sin cerrar) van siempre al
# final. `closed` es la fecha de cierre: solo tiene sentido en la etapa `closed`.
JobSort = Literal["date", "score", "salary", "closed"]
JOB_SORTS: tuple[str, ...] = get_args(JobSort)
SortDirection = Literal["asc", "desc"]

# Para comparar salarios de distinto periodo, todo se pasa a anual (≈ 1760 horas al año).
_SALARY_PER_YEAR = {"month": 12, "hour": 1760}


class JobPage(BaseModel):
    items: list[JobRow]
    total: int
    limit: int
    offset: int


def _row_salary(data: dict | None) -> Salary | None:
    salary = (data or {}).get("salary")
    if not salary or (salary.get("min") is None and salary.get("max") is None):
        return None
    return Salary.model_validate(salary)


def _escape_like(value: str) -> str:
    return value.replace("!", "!!").replace("%", "!%").replace("_", "!_")


def _annual_salary(extraction: type[JobExtractionRow]):
    """Punto medio del rango salarial de la extracción, anualizado; NULL si no lo indica."""
    salary = extraction.data["salary"]
    low, high = salary["min"].as_float(), salary["max"].as_float()
    period = salary["period"].as_string()
    per_year = case(
        *((period == name, factor) for name, factor in _SALARY_PER_YEAR.items()), else_=1
    )
    return (func.coalesce(low, high) + func.coalesce(high, low)) / 2 * per_year


def _ordering(sort: str, direction: str, salary):
    if sort not in JOB_SORTS:
        valid = ", ".join(JOB_SORTS)
        raise InvalidQueryError(f"Orden desconocido: «{sort}». Válidos: {valid}.")
    if direction not in ("asc", "desc"):
        raise InvalidQueryError(f"Sentido desconocido: «{direction}». Válidos: asc, desc.")
    desc = direction == "desc"
    recent = (Job.first_seen_at.desc(), Job.id.desc())
    if sort == "date":
        return recent if desc else (Job.first_seen_at.asc(), Job.id.asc())
    columns = {"score": Match.score, "salary": salary, "closed": Application.closed_at}
    column = columns[sort]
    return ((column.desc() if desc else column.asc()).nulls_last(), *recent)


def search_jobs(
    session: Session,
    stage: str | None = None,
    q: str | None = None,
    limit: int = DEFAULT_LIMIT,
    offset: int = 0,
    sort: JobSort = "date",
    direction: SortDirection = "desc",
) -> JobPage:
    """Página de ofertas para la bandeja: filtro por etapa, búsqueda en título y empresa, y orden
    por fecha de alta, score, salario o fecha de cierre."""
    if not 1 <= limit <= MAX_LIMIT:
        raise InvalidQueryError(f"`limit` debe estar entre 1 y {MAX_LIMIT}.")
    if offset < 0:
        raise InvalidQueryError("`offset` no puede ser negativo.")
    last_extraction = (
        select(JobExtractionRow.job_id, func.max(JobExtractionRow.id).label("id"))
        .group_by(JobExtractionRow.job_id)
        .subquery()
    )
    current = aliased(JobExtractionRow)
    ordering = _ordering(sort, direction, _annual_salary(current))
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
        base.add_columns(Application.closed_at, Application.closed_by)
        .outerjoin(last_extraction, last_extraction.c.job_id == Job.id)
        .outerjoin(current, current.id == last_extraction.c.id)
        .order_by(*ordering)
        .limit(limit)
        .offset(offset)
    ).all()
    latest = extractions.latest_rows(session, [job.id for job, *_ in rows])
    known = network.known_counts(session, [job.id for job, *_ in rows])
    items = []
    for job, company, job_stage, score, closed_at, closed_by in rows:
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
                signals=read_signals(job),
                duplicate_of=job.duplicate_of,
                first_seen_at=job.first_seen_at,
                score=score,
                remote_mode=extraction.data.get("remote_mode") if extraction else None,
                salary=_row_salary(extraction.data if extraction else None),
                known_contacts=known.get(job.id, 0),
                closed_at=closed_at,
                closed_by=closed_by,
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
    # Carpeta con la copia de lo enviado (relativa a la carpeta de datos), si ya se archivó.
    archive_folder: str | None = None


SENT_STAGES = frozenset({Stage.APPLIED, Stage.IN_PROCESS, Stage.CLOSED})


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
        signals=read_signals(job),
        duplicate_of=job.duplicate_of,
        first_seen_at=job.first_seen_at,
        score=score,
        posted_at=job.posted_at,
        raw_text=job.raw_text,
        # Solo mira el disco si se envió (etapa posterior a `applied` o cerrada después).
        archive_folder=(
            application_archive.relative_folder(job.id) if job_stage in SENT_STAGES else None
        ),
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
