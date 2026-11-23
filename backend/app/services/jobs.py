"""Consultas de ofertas. El texto crudo (no confiable) solo sale por `get_job`, envuelto."""

from datetime import datetime
from typing import Any, Literal, get_args

from pydantic import BaseModel
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, aliased, defer

from app.models import Application, Company, Event, Job, Match, Source
from app.models import JobExtraction as JobExtractionRow
from app.schemas.llm_io import JobExtraction, Salary
from app.services import application_archive, extractions, network
from app.services.events import EventOut, JobNotFoundError
from app.services.pipeline import TRANSITIONS, EventType, Reached, Stage, job_events, reached_step
from app.services.reopenings import ReopeningOf, reopening_of
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
    # Reapertura de una vacante cerrada por la empresa (fase 45): la oferta de la que viene.
    reopening_of: int | None = None
    first_seen_at: datetime
    score: int | None  # del último match; None si aún no se ha puntuado
    # El código o el agente vieron texto dirigido a una IA (evento `injection_suspected`).
    injection_suspected: bool
    # Posible cierre y republicación (fase 16): observaciones del código, no veredictos.
    signals: JobSignals = JobSignals()


def last_match_subquery():
    """Subconsulta con el último match de cada oferta."""
    return (
        select(Match.job_id.label("job_id"), func.max(Match.id).label("match_id"))
        .group_by(Match.job_id)
        .subquery()
    )


def _summary_query(with_text: bool = True):
    """Oferta, empresa, etapa y score del último match (outer joins: puede no haber).

    Las listas no enseñan el texto de la oferta (`with_text=False`): sin él, SQLite ordena filas
    pequeñas y no miles de descripciones completas. Esas ofertas quedan en la sesión sin el texto:
    leer `raw_text` de ellas haría una consulta por oferta.
    """
    last = last_match_subquery()
    injection = (
        select(Event.id)
        .where(Event.job_id == Job.id, Event.type == EventType.INJECTION_SUSPECTED.value)
        .exists()
    )
    return (
        select(Job, Company.name, Application.stage, Match.score, injection)
        .join(Company, Company.id == Job.company_id)
        .outerjoin(Application, Application.job_id == Job.id)
        .outerjoin(last, last.c.job_id == Job.id)
        .outerjoin(Match, Match.id == last.c.match_id)
        .options(*(() if with_text else (defer(Job.raw_text),)))
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
    query = _summary_query(with_text=False).order_by(*ordering).limit(limit)
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
            reopening_of=job.reopening_of,
            first_seen_at=job.first_seen_at,
            score=score,
            injection_suspected=suspected,
        )
        for job, company, job_stage, score, suspected in session.execute(query).all()
    ]


class JobDetail(JobSummary):
    posted_at: datetime | None
    text: str  # envuelto en <untrusted_job_posting>: datos, nunca instrucciones


def get_job(session: Session, job_id: int) -> JobDetail:
    """Metadatos de la oferta y su texto crudo envuelto como no confiable, con sus `risk_flags`."""
    row = session.execute(_summary_query().where(Job.id == job_id)).first()
    if row is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    job, company, job_stage, score, suspected = row
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
        reopening_of=job.reopening_of,
        first_seen_at=job.first_seen_at,
        score=score,
        injection_suspected=suspected,
        posted_at=job.posted_at,
        text=wrap_untrusted(job.id, job.raw_text, job.risk_flags),
    )


# --- Vistas para la UI (API REST) ---------------------------------------------------------------
# La UI muestra el texto a una persona (React lo escapa): va sin envoltorio. Ningún modelo lo lee.

RemoteMode = Literal["onsite", "hybrid", "remote", "unknown"]
REMOTE_MODES: tuple[str, ...] = get_args(RemoteMode)

# Por qué se cerró una oferta, para la Bandeja. Sale del evento de cierre (`closed_by`) y, en un
# descarte, de su motivo: descartada con `closed` («la han cerrado») la cerró la empresa.
CloseReason = Literal[
    "discarded",
    "filtered_out",
    "rejected",
    "withdrawn",
    "expired",
    "closed_by_company",
    "duplicate",
    "accepted",
]
CLOSE_REASONS: tuple[str, ...] = get_args(CloseReason)
_REASON_BY_EVENT: dict[str, CloseReason] = {
    EventType.DUPLICATE_DETECTED: "duplicate",
    EventType.HARD_FILTER_FAILED: "filtered_out",
    EventType.REJECTED: "rejected",
    EventType.WITHDRAWN: "withdrawn",
    EventType.EXPIRED: "expired",
    EventType.ACCEPTED: "accepted",
}
COMPANY_DISCARD_REASON = "closed"


def close_reason(closed_by: str | None, discard_reason: str | None) -> CloseReason | None:
    """El motivo de cierre a partir del evento que la cerró y, si fue un descarte, su motivo."""
    if closed_by is None:
        return None
    if closed_by == EventType.DISCARDED:
        return "closed_by_company" if discard_reason == COMPANY_DISCARD_REASON else "discarded"
    return _REASON_BY_EVENT.get(closed_by)


def _last_discards():
    """El motivo del último descarte de cada oferta (por fecha y, a igual fecha, por registro)."""
    ranked = (
        select(
            Event.job_id,
            Event.payload["reason"].as_string().label("reason"),
            func.row_number()
            .over(partition_by=Event.job_id, order_by=(Event.occurred_at.desc(), Event.id.desc()))
            .label("n"),
        )
        .where(Event.type == EventType.DISCARDED)
        .subquery()
    )
    return select(ranked.c.job_id, ranked.c.reason).where(ranked.c.n == 1)


def _discard_reasons(session: Session, job_ids: list[int]) -> dict[int, str | None]:
    if not job_ids:
        return {}
    last = _last_discards().subquery()
    rows = session.execute(select(last.c.job_id, last.c.reason).where(last.c.job_id.in_(job_ids)))
    return {job_id: reason for job_id, reason in rows}


def _close_reason_filter(reason: str):
    """Las ofertas cerradas con ese motivo, como condición sobre `applications` y `jobs`."""
    if reason not in CLOSE_REASONS:
        valid = ", ".join(CLOSE_REASONS)
        raise InvalidQueryError(f"Motivo de cierre desconocido: «{reason}». Válidos: {valid}.")
    closed = Application.stage == Stage.CLOSED
    if reason in ("discarded", "closed_by_company"):
        last = _last_discards().subquery()
        by_company = Job.id.in_(
            select(last.c.job_id).where(last.c.reason == COMPANY_DISCARD_REASON)
        )
        discarded = Application.closed_by == EventType.DISCARDED
        return (closed, discarded, by_company if reason == "closed_by_company" else ~by_company)
    events = [event for event, value in _REASON_BY_EVENT.items() if value == reason]
    return (closed, Application.closed_by.in_(events))


class JobRow(JobSummary):
    remote_mode: RemoteMode | None  # de la extracción vigente; None si aún no hay
    salary: Salary | None  # de la extracción vigente; None si no lo indica o aún no hay
    known_contacts: int = 0  # personas de tu red de LinkedIn en la empresa (fase 18)
    # Cuándo y con qué evento se cerró (fase 27.6); None si no está cerrada.
    closed_at: datetime | None = None
    closed_by: str | None = None
    close_reason: CloseReason | None = None  # por qué se cerró; None si no está cerrada


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


def _extraction_filters(remote_mode: str | None, has_salary: bool | None) -> list:
    """Filtros que salen de la extracción vigente (modalidad y salario).

    Van como subconsultas sobre `jobs.id`, para valer igual en el recuento y en la página sin unir
    la extracción a las dos. Una oferta sin extraer cuenta como «modalidad sin indicar» y «sin
    salario»: aún no se sabe nada de ella."""
    if remote_mode is not None and remote_mode not in REMOTE_MODES:
        valid = ", ".join(REMOTE_MODES)
        raise InvalidQueryError(f"Modalidad desconocida: «{remote_mode}». Válidas: {valid}.")
    newest = (
        select(func.max(JobExtractionRow.id)).group_by(JobExtractionRow.job_id).scalar_subquery()
    )
    current = aliased(JobExtractionRow)

    def jobs_where(*conditions):
        return select(current.job_id).where(current.id.in_(newest), *conditions)

    filters = []
    if remote_mode is not None:
        mode = current.data["remote_mode"].as_string()
        if remote_mode == "unknown":
            filters.append(
                or_(
                    Job.id.not_in(select(JobExtractionRow.job_id)),
                    Job.id.in_(jobs_where(or_(mode == "unknown", mode.is_(None)))),
                )
            )
        else:
            filters.append(Job.id.in_(jobs_where(mode == remote_mode)))
    if has_salary is not None:
        salary = current.data["salary"]
        shown = Job.id.in_(
            jobs_where(
                func.coalesce(salary["min"].as_float(), salary["max"].as_float()).is_not(None)
            )
        )
        filters.append(shown if has_salary else ~shown)
    return filters


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
    source_kind: str | None = None,
    remote_mode: RemoteMode | None = None,
    has_salary: bool | None = None,
    has_score: bool | None = None,
    min_score: int | None = None,
    stages: list[str] | None = None,
    reason: str | None = None,
) -> JobPage:
    """Página de ofertas para la bandeja: filtro por etapa (una, `stage`, o varias, `stages`; con
    las dos, las que cumplen ambas), búsqueda en título y empresa, modalidad, con o sin salario,
    con o sin encaje (score), encaje mínimo y motivo de cierre (`reason`: solo cerradas), y orden
    por fecha de alta, score, salario o fecha de cierre."""
    if min_score is not None and not 0 <= min_score <= 100:
        raise InvalidQueryError("`min_score` debe estar entre 0 y 100.")
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
    if stages is not None:
        filters.append(Application.stage.in_([parse_stage(value).value for value in stages]))
    if reason is not None:
        filters.extend(_close_reason_filter(reason))
    if source_kind is not None:
        filters.append(Job.source_id.in_(select(Source.id).where(Source.kind == source_kind)))
    filters.extend(_extraction_filters(remote_mode, has_salary))
    if has_score is not None:
        filters.append(Match.score.is_not(None) if has_score else Match.score.is_(None))
    if min_score is not None:
        filters.append(Match.score >= min_score)
    searching = q is not None and bool(q.strip())
    if q is not None and searching:
        pattern = f"%{_escape_like(q.strip())}%"
        filters.append(
            or_(
                Job.title.ilike(pattern, escape="!"),
                Company.name.ilike(pattern, escape="!"),
            )
        )
    base = _summary_query(with_text=False).where(*filters)
    total = session.scalar(select(func.count()).select_from(base.subquery())) or 0
    # Dos pasos: primero los ids de la página, con columnas cortas (un índice de `jobs` basta y
    # no se leen las filas, largas por el texto de la oferta); después, esas filas enteras. En el
    # primero, solo lo que filtra u ordena: toda oferta tiene empresa (clave foránea), y unir
    # `companies` sin necesidad hace que SQLite recorra `jobs` por otro índice.
    last = last_match_subquery()
    ids = (
        select(Job.id)
        .outerjoin(Application, Application.job_id == Job.id)
        .outerjoin(last, last.c.job_id == Job.id)
        .outerjoin(Match, Match.id == last.c.match_id)
    )
    if searching:
        ids = ids.join(Company, Company.id == Job.company_id)
    if sort == "salary":
        ids = ids.outerjoin(last_extraction, last_extraction.c.job_id == Job.id).outerjoin(
            current, current.id == last_extraction.c.id
        )
    page = session.scalars(
        ids.where(*filters).order_by(*ordering).limit(limit).offset(offset)
    ).all()
    by_id = {
        row[0].id: row
        for row in session.execute(
            base.add_columns(Application.closed_at, Application.closed_by).where(Job.id.in_(page))
        )
    }
    rows = [by_id[job_id] for job_id in page if job_id in by_id]
    latest = extractions.latest_rows(session, [job.id for job, *_ in rows])
    known = network.known_counts(session, [job.id for job, *_ in rows])
    discards = _discard_reasons(
        session, [job.id for job, *rest in rows if rest[-1] == EventType.DISCARDED]
    )
    items = []
    for job, company, job_stage, score, suspected, closed_at, closed_by in rows:
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
                reopening_of=job.reopening_of,
                first_seen_at=job.first_seen_at,
                score=score,
                injection_suspected=suspected,
                remote_mode=extraction.data.get("remote_mode") if extraction else None,
                salary=_row_salary(extraction.data if extraction else None),
                known_contacts=known.get(job.id, 0),
                closed_at=closed_at,
                closed_by=closed_by,
                close_reason=close_reason(closed_by, discards.get(job.id)),
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
    # Si es una reapertura (fase 45), la oferta cerrada de la que viene.
    reopening: ReopeningOf | None = None
    # Si está cerrada: con qué evento y hasta dónde llegó (p. ej. un rechazo tras entrevista).
    closed_by: str | None = None
    close_reason: CloseReason | None = None
    reached: Reached | None = None


SENT_STAGES = frozenset({Stage.APPLIED, Stage.IN_PROCESS, Stage.CLOSED})


def get_job_view(session: Session, job_id: int) -> JobView:
    """Ficha completa de una oferta para la UI."""
    row = session.execute(_summary_query().where(Job.id == job_id)).first()
    if row is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    job, company, job_stage, score, suspected = row
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
        reopening_of=job.reopening_of,
        first_seen_at=job.first_seen_at,
        score=score,
        injection_suspected=suspected,
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
        reopening=reopening_of(session, job),
        **_closing(events) if job_stage == Stage.CLOSED else {},
    )


def _closing(events: list[Event]) -> dict[str, Any]:
    closing = [e for e in events if TRANSITIONS[EventType(e.type)].to == Stage.CLOSED]
    last = closing[-1] if closing else None
    discards = [e for e in events if e.type == EventType.DISCARDED]
    reason = (discards[-1].payload or {}).get("reason") if discards else None
    return {
        "closed_by": last.type if last else None,
        "close_reason": close_reason(last.type, reason) if last else None,
        "reached": reached_step(e.type for e in events),
    }
