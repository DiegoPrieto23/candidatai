"""Analítica del embudo (fase 10.2): qué ofertas avanzan, por dónde llegan y cuánto tardan.

Todo sale de `events` con consultas agregadas en la BD. Definiciones (también en
`docs/DATA_MODEL.md` §Embudo):

- Cada oferta cuenta una vez por paso, aunque se reabra. El embudo es **acumulado**: una oferta que
  llega a un paso cuenta también en los anteriores (p. ej. un `applied_manually` sin aprobar antes
  cuenta como aprobada), así que la conversión nunca pasa del 100 %.
- **Triada**: tiene `extracted` y no la cerraron los filtros duros, o se reabrió después.
- **Con respuesta**: `reply_received`, `interview_scheduled`, `test_assigned`, `offer_received` o
  `rejected` con fecha igual o posterior al primer envío.
- Las ofertas cerradas por `duplicate_detected` (y no reabiertas) no cuentan: son otra oferta.
- `since` filtra por `first_seen_at`, desde las 00:00 de ese día en Europe/Madrid.
- **Por referencia** (fase 18): `given` si algún contacto del proceso tiene la referencia dada;
  si no, `requested` si se pidió; si no, `none`. La marca no lleva fecha de corte: cuenta aunque
  se diera después del envío.

Solo SQLite: la semana usa `jh_iso_week` (registrada en `app/core/db.py`) y los filtros duros,
`json_each`.
"""

import statistics
from datetime import date, timedelta
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import (
    ColumnElement,
    and_,
    case,
    exists,
    func,
    literal_column,
    or_,
    select,
    true,
    tuple_,
)
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql.expression import CTE

from app.models import Application, Contact, Event, Job, JobExtraction, Source
from app.services.pipeline import EventType, Stage
from app.services.process import start_of_local_day

TOP_TITLES = 8

FunnelStepName = Literal[
    "found", "triaged", "approved", "applied", "replied", "interview", "offer", "accepted"
]
STEPS: tuple[tuple[FunnelStepName, str], ...] = (
    ("found", "Encontradas"),
    ("triaged", "Triadas"),
    ("approved", "Aprobadas"),
    ("applied", "Enviadas"),
    ("replied", "Con respuesta"),
    ("interview", "Entrevista"),
    ("offer", "Oferta"),
    ("accepted", "Aceptadas"),
)
SUMMARY_STEPS = ("found", "approved", "applied", "replied", "interview")

APPLIED_TYPES = (EventType.APPLIED, EventType.APPLIED_MANUALLY)
RESPONSE_TYPES = (
    EventType.REPLY_RECEIVED,
    EventType.INTERVIEW_SCHEDULED,
    EventType.TEST_ASSIGNED,
    EventType.OFFER_RECEIVED,
    EventType.REJECTED,
)

# --- Salida ---------------------------------------------------------------------------------


class FunnelStep(BaseModel):
    step: FunnelStepName
    label: str
    count: int
    rate_from_previous: float | None  # 0-1; `null` en el primero o si el anterior es 0
    rate_from_start: float | None  # 0-1; `null` si no hay ninguna encontrada


class FunnelSummary(BaseModel):
    found: int
    approved: int
    applied: int
    replied: int
    interview: int
    reply_rate: float | None  # con respuesta / enviadas; `null` sin envíos


class SourceFunnel(FunnelSummary):
    source_id: int
    kind: str
    name: str


class TitleFunnel(FunnelSummary):
    title: str  # `title_normalized`; «Otros» y «Sin extraer» en los grupos
    group: Literal["title", "others", "not_extracted"]


class WeekFunnel(FunnelSummary):
    week: str  # ISO, `2026-W39`, de `first_seen_at` en Europe/Madrid
    week_start: date  # lunes


ReferralGroup = Literal["given", "requested", "none"]
REFERRAL_GROUPS: tuple[ReferralGroup, ...] = ("given", "requested", "none")


class ReferralFunnel(FunnelSummary):
    group: ReferralGroup  # referencia dada, solo pedida o sin referencia


class ResponseTime(BaseModel):
    applied: int  # ofertas enviadas (con `applied` o `applied_manually`)
    replied: int
    median_days: float | None
    mean_days: float | None
    awaiting_reply: int  # enviadas sin respuesta y aún en `applied`
    closed_without_reply: int  # enviadas sin respuesta y cerradas (retiradas, caducadas…)


class ReasonCount(BaseModel):
    reason: str  # `payload.reason` de `discarded`; `unspecified` si no lo lleva
    count: int


class FilterCount(BaseModel):
    filter: str  # `payload.failures[].filter` de `hard_filter_failed`
    count: int


class FunnelStats(BaseModel):
    since: date | None
    duplicates_excluded: int
    steps: list[FunnelStep]
    by_source: list[SourceFunnel]
    by_title: list[TitleFunnel]
    by_week: list[WeekFunnel]
    by_referral: list[ReferralFunnel]  # siempre los tres grupos, en ese orden
    response_time: ResponseTime
    discard_reasons: list[ReasonCount]
    hard_filter_failures: list[FilterCount]


# --- Consultas ------------------------------------------------------------------------------


def _event_agg(agg: Any, *types: str) -> Any:
    """Subconsulta correlacionada con `Job`: `agg(occurred_at)` de los eventos de esos tipos."""
    query = select(agg(Event.occurred_at)).where(Event.job_id == Job.id, Event.type.in_(types))
    return query.correlate(Job).scalar_subquery()


def _still_closed_by(event_type: EventType) -> ColumnElement[bool]:
    """El último evento de ese tipo no tiene un `reopened` posterior.

    «Posterior» en el orden de la proyección, (`occurred_at`, `id`): un `reopened` con la misma
    fecha que el cierre, registrado después, también lo reabre.
    """
    closing, last_row = aliased(Event), aliased(Event)
    last_id = (
        select(closing.id)
        .where(closing.job_id == Job.id, closing.type == event_type)
        .order_by(closing.occurred_at.desc(), closing.id.desc())
        .limit(1)
        .correlate(Job)
        .scalar_subquery()
    )
    reopened_after = (
        exists()
        .where(
            Event.job_id == Job.id,
            Event.type == EventType.REOPENED,
            last_row.id == last_id,
            tuple_(Event.occurred_at, Event.id) > tuple_(last_row.occurred_at, last_row.id),
        )
        .correlate(Job)
    )
    return and_(last_id.is_not(None), ~reopened_after)


def _rate(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def _per_job(session: Session, since: date | None) -> tuple[CTE, int]:
    """CTE con una fila por oferta del periodo y sus pasos (0/1, acumulados) y fechas de envío y
    primera respuesta. Devuelve también cuántas se excluyen por duplicadas."""
    scope = []
    if since is not None:
        scope.append(Job.first_seen_at >= start_of_local_day(since))
    duplicate = _still_closed_by(EventType.DUPLICATE_DETECTED)
    duplicates = session.scalar(select(func.count()).select_from(Job).where(*scope, duplicate))

    applied_at = _event_agg(func.min, *APPLIED_TYPES)
    raw = (
        select(
            Job.id.label("job_id"),
            Job.source_id,
            Job.first_seen_at,
            applied_at.label("applied_at"),
            and_(
                _event_agg(func.min, EventType.EXTRACTED).is_not(None),
                ~_still_closed_by(EventType.HARD_FILTER_FAILED),
            ).label("triaged"),
            _event_agg(func.min, EventType.APPROVED).is_not(None).label("approved"),
            _event_agg(func.min, EventType.INTERVIEW_SCHEDULED).is_not(None).label("interview"),
            _event_agg(func.min, EventType.OFFER_RECEIVED).is_not(None).label("offer"),
            _event_agg(func.min, EventType.ACCEPTED).is_not(None).label("accepted"),
        )
        .where(*scope, ~duplicate)
        .cte("raw")
    )
    first_reply = (
        select(func.min(Event.occurred_at))
        .where(
            Event.job_id == raw.c.job_id,
            Event.type.in_(RESPONSE_TYPES),
            Event.occurred_at >= raw.c.applied_at,
        )
        .correlate(raw)
        .scalar_subquery()
    )
    # Acumulado: cada paso incluye a las que llegaron a uno posterior.
    accepted = raw.c.accepted
    offer = or_(raw.c.offer, accepted)
    interview = or_(raw.c.interview, offer)
    replied = or_(first_reply.is_not(None), interview)
    applied = or_(raw.c.applied_at.is_not(None), replied)
    approved = or_(raw.c.approved, applied)
    triaged = or_(raw.c.triaged, approved)

    def flag(condition: ColumnElement[bool], name: str) -> Any:
        return case((condition, 1), else_=0).label(name)

    per_job = select(
        raw.c.job_id,
        raw.c.source_id,
        raw.c.first_seen_at,
        raw.c.applied_at,
        first_reply.label("reply_at"),
        literal_column("1").label("found"),
        flag(triaged, "triaged"),
        flag(approved, "approved"),
        flag(applied, "applied"),
        flag(replied, "replied"),
        flag(interview, "interview"),
        flag(offer, "offer"),
        flag(accepted, "accepted"),
    ).cte("per_job")
    return per_job, duplicates or 0


def _sums(per_job: CTE, steps: tuple[str, ...]) -> list[Any]:
    return [func.coalesce(func.sum(per_job.c[s]), 0).label(s) for s in steps]


def _summary(row: Any) -> dict[str, Any]:
    values = {s: int(getattr(row, s)) for s in SUMMARY_STEPS}
    return values | {"reply_rate": _rate(values["replied"], values["applied"])}


def _steps(session: Session, per_job: CTE) -> list[FunnelStep]:
    row = session.execute(select(*_sums(per_job, tuple(s for s, _ in STEPS)))).one()
    counts = [int(getattr(row, s)) for s, _ in STEPS]
    return [
        FunnelStep(
            step=step,
            label=label,
            count=count,
            rate_from_previous=_rate(count, counts[i - 1]) if i else None,
            rate_from_start=_rate(count, counts[0]),
        )
        for i, ((step, label), count) in enumerate(zip(STEPS, counts, strict=True))
    ]


def _by_source(session: Session, per_job: CTE) -> list[SourceFunnel]:
    rows = session.execute(
        select(Source.id, Source.kind, Source.name, *_sums(per_job, SUMMARY_STEPS))
        .join(per_job, per_job.c.source_id == Source.id)
        .group_by(Source.id)
        .order_by(func.sum(per_job.c.found).desc(), Source.id)
    ).all()
    return [SourceFunnel(source_id=r.id, kind=r.kind, name=r.name, **_summary(r)) for r in rows]


def _by_title(session: Session, per_job: CTE, top: int) -> list[TitleFunnel]:
    latest = (
        select(JobExtraction.job_id, func.max(JobExtraction.id).label("extraction_id"))
        .group_by(JobExtraction.job_id)
        .subquery()
    )
    title = JobExtraction.data["title_normalized"].as_string()
    rows = session.execute(
        select(title.label("title"), *_sums(per_job, SUMMARY_STEPS))
        .select_from(per_job)
        .outerjoin(latest, latest.c.job_id == per_job.c.job_id)
        .outerjoin(JobExtraction, JobExtraction.id == latest.c.extraction_id)
        .group_by(title)
        .order_by(func.sum(per_job.c.found).desc(), title)
    ).all()
    titled = [r for r in rows if r.title is not None]
    out = [TitleFunnel(title=r.title, group="title", **_summary(r)) for r in titled[:top]]
    rest = titled[top:]
    if rest:
        totals = {s: sum(int(getattr(r, s)) for r in rest) for s in SUMMARY_STEPS}
        out.append(
            TitleFunnel(
                title="Otros",
                group="others",
                **totals,
                reply_rate=_rate(totals["replied"], totals["applied"]),
            )
        )
    out.extend(
        TitleFunnel(title="Sin extraer", group="not_extracted", **_summary(r))
        for r in rows
        if r.title is None
    )
    return out


def _week_start(week: str) -> date:
    return date.fromisocalendar(int(week[:4]), int(week[6:]), 1)


def _by_week(session: Session, per_job: CTE) -> list[WeekFunnel]:
    week = func.jh_iso_week(per_job.c.first_seen_at)
    rows = {
        r.week: r
        for r in session.execute(
            select(week.label("week"), *_sums(per_job, SUMMARY_STEPS)).group_by(week)
        ).all()
    }
    if not rows:
        return []
    # Semanas seguidas, con las vacías a cero, para que la gráfica no salte huecos.
    first, last = min(map(_week_start, rows)), max(map(_week_start, rows))
    out: list[WeekFunnel] = []
    monday = first
    while monday <= last:
        year, number, _ = monday.isocalendar()
        key = f"{year}-W{number:02d}"
        row = rows.get(key)
        values = _summary(row) if row else dict.fromkeys(SUMMARY_STEPS, 0) | {"reply_rate": None}
        out.append(WeekFunnel(week=key, week_start=monday, **values))
        monday += timedelta(days=7)
    return out


def _by_referral(session: Session, per_job: CTE) -> list[ReferralFunnel]:
    def marked(status: str) -> ColumnElement[bool]:
        return (
            exists()
            .where(Contact.job_id == per_job.c.job_id, Contact.referral == status)
            .correlate(per_job)
        )

    group = case((marked("given"), "given"), (marked("requested"), "requested"), else_="none")
    rows = {
        r.group: r
        for r in session.execute(
            select(group.label("group"), *_sums(per_job, SUMMARY_STEPS)).group_by(group)
        ).all()
    }
    empty = dict.fromkeys(SUMMARY_STEPS, 0) | {"reply_rate": None}
    return [
        ReferralFunnel(group=g, **(_summary(rows[g]) if g in rows else empty))
        for g in REFERRAL_GROUPS
    ]


def _response_time(session: Session, per_job: CTE) -> ResponseTime:
    sent = per_job.c.applied_at.is_not(None)
    no_reply = and_(sent, per_job.c.reply_at.is_(None))
    stage = Application.stage
    row = session.execute(
        select(
            func.count().filter(sent).label("applied"),
            func.count(per_job.c.reply_at).filter(sent).label("replied"),
            func.count().filter(no_reply, stage == Stage.APPLIED).label("awaiting"),
            func.count().filter(no_reply, stage == Stage.CLOSED).label("closed"),
        )
        .select_from(per_job)
        .outerjoin(Application, Application.job_id == per_job.c.job_id)
    ).one()
    days = session.scalars(
        select(func.julianday(per_job.c.reply_at) - func.julianday(per_job.c.applied_at)).where(
            per_job.c.reply_at.is_not(None), sent
        )
    ).all()
    return ResponseTime(
        applied=row.applied,
        replied=row.replied,
        median_days=round(statistics.median(days), 1) if days else None,
        mean_days=round(statistics.fmean(days), 1) if days else None,
        awaiting_reply=row.awaiting,
        closed_without_reply=row.closed,
    )


def _discard_reasons(session: Session, per_job: CTE) -> list[ReasonCount]:
    reason = func.coalesce(Event.payload["reason"].as_string(), "unspecified")
    count = func.count(Event.job_id.distinct())
    rows = session.execute(
        select(reason.label("reason"), count.label("count"))
        .join(per_job, per_job.c.job_id == Event.job_id)
        .where(Event.type == EventType.DISCARDED)
        .group_by(reason)
        .order_by(count.desc(), reason)
    ).all()
    return [ReasonCount(reason=r.reason, count=r.count) for r in rows]


def _hard_filter_failures(session: Session, per_job: CTE) -> list[FilterCount]:
    failures = func.json_each(Event.payload, "$.failures").table_valued("value")
    name = func.json_extract(failures.c.value, "$.filter")
    count = func.count(Event.job_id.distinct())
    rows = session.execute(
        select(name.label("filter"), count.label("count"))
        .select_from(Event)
        .join(per_job, per_job.c.job_id == Event.job_id)
        .join(failures, true())
        .where(Event.type == EventType.HARD_FILTER_FAILED, name.is_not(None))
        .group_by(name)
        .order_by(count.desc(), name)
    ).all()
    return [FilterCount(filter=r.filter, count=r.count) for r in rows]


def get_funnel_stats(
    session: Session, since: date | None = None, top_titles: int = TOP_TITLES
) -> FunnelStats:
    """Embudo, desglose por fuente, puesto y semana, tiempo hasta la primera respuesta y motivos
    de descarte de las ofertas vistas desde `since` (todas si es `None`)."""
    per_job, duplicates = _per_job(session, since)
    return FunnelStats(
        since=since,
        duplicates_excluded=duplicates,
        steps=_steps(session, per_job),
        by_source=_by_source(session, per_job),
        by_title=_by_title(session, per_job, top_titles),
        by_week=_by_week(session, per_job),
        by_referral=_by_referral(session, per_job),
        response_time=_response_time(session, per_job),
        discard_reasons=_discard_reasons(session, per_job),
        hard_filter_failures=_hard_filter_failures(session, per_job),
    )
