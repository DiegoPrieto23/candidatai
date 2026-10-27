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

Solo SQLite: la semana usa `cai_iso_week` (registrada en `app/core/db.py`) y los filtros duros,
`json_each`.

**Calibración** (fase 20, `get_calibration`): ¿predicen el score y el veredicto las respuestas?
Sobre las ofertas **enviadas** (con `applied` o `applied_manually`), tasa de respuesta y de
entrevista por tramo de score, veredicto, fuente, portal, plantilla, carta, referencia y días entre
el alta y el envío, con intervalo de Wilson al 95 % y `low_data` por debajo de `min_cases`. Todo
se mide **en el momento del primer envío**:

- **Score**: el del último match calculado antes del envío; si no hay ninguno, el primero después
  (el score lo calcula código y no sabe del resultado). Sin match: `none`.
- **Veredicto**: el del último `fit_assessed` antes del envío. Uno posterior no cuenta (pudo
  escribirse sabiendo cómo fue).
- **Plantilla**: la del render de `payload.render_id` del primer envío (el CV enviado).
- **Carta**: algún documento `cover_letter` creado antes del envío.
- **Referencia**: como en el embudo (dada, pedida o ninguna, sin fecha de corte).
- `since` filtra por la fecha del **primer envío**, desde las 00:00 de ese día en Europe/Madrid.
"""

import math
import statistics
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import (
    Column,
    ColumnElement,
    Float,
    Integer,
    MetaData,
    Select,
    Table,
    and_,
    case,
    exists,
    func,
    insert,
    literal_column,
    or_,
    select,
    true,
    tuple_,
    type_coerce,
)
from sqlalchemy.orm import Session, aliased
from sqlalchemy.sql.expression import FromClause
from sqlalchemy.types import NullType

from app.models import (
    Application,
    Contact,
    Document,
    DocumentRender,
    Event,
    Job,
    JobExtraction,
    Match,
    Source,
)
from app.services.documents.cover_letter import LETTER_KIND
from app.services.pipeline import EventType, Stage
from app.services.process import local_zone, start_of_local_day

TOP_TITLES = 8

FunnelStepName = Literal[
    "found", "triaged", "approved", "applied", "replied", "interview", "offer", "accepted"
]
STEPS: tuple[tuple[FunnelStepName, str], ...] = (
    ("found", "Encontradas"),
    ("triaged", "Pasan filtros"),
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
# Los eventos que mira `_job_events`: el resto (notas, scores…) ni se leen.
FUNNEL_TYPES = (
    *APPLIED_TYPES,
    EventType.EXTRACTED,
    EventType.HARD_FILTER_FAILED,
    EventType.DUPLICATE_DETECTED,
    EventType.APPROVED,
    EventType.INTERVIEW_SCHEDULED,
    EventType.OFFER_RECEIVED,
    EventType.ACCEPTED,
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
    # Fase 25.4: lo que han gastado sus ofertas en segundo plano (`agent_costs`).
    tokens: int  # entrada + salida
    cost_usd: float | None  # `None` si ningún agente dio coste


class FunnelCost(BaseModel):
    """Lo que han gastado en segundo plano las ofertas del periodo (fase 25.4). Lo de una terminal
    no cuenta: el agente no devuelve su uso."""

    runs: int  # ejecuciones con alguna oferta del periodo
    tokens: int
    cost_usd: float | None
    applied: int
    interview: int
    tokens_per_applied: float | None
    cost_per_applied_usd: float | None
    tokens_per_interview: float | None
    cost_per_interview_usd: float | None


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
    agent_cost: FunnelCost


# --- Consultas ------------------------------------------------------------------------------


def _first(*types: str) -> Any:
    """Agregado: fecha del primer evento de esos tipos (NULL si no hay)."""
    return func.min(case((Event.type.in_(types), Event.occurred_at)))


def _has(*types: str) -> Any:
    """Agregado: 1 si hay algún evento de esos tipos, 0 si no."""
    return func.max(case((Event.type.in_(types), 1), else_=0))


def _job_events() -> Select[Any]:
    """Una fila por oferta con lo que el embudo necesita de sus eventos, en una sola pasada por
    `events` agrupada por oferta (con 5000 ofertas, una subconsulta por oferta y paso tardaba
    segundos). Solo salen las ofertas con alguno de `FUNNEL_TYPES`: se une con `outerjoin`."""
    return (
        select(
            Event.job_id.label("job_id"),
            _first(*APPLIED_TYPES).label("applied_at"),
            _has(EventType.EXTRACTED).label("extracted"),
            _has(EventType.HARD_FILTER_FAILED).label("filtered"),
            _has(EventType.DUPLICATE_DETECTED).label("duplicated"),
            _has(EventType.APPROVED).label("approved"),
            _has(EventType.INTERVIEW_SCHEDULED).label("interview"),
            _has(EventType.OFFER_RECEIVED).label("offer"),
            _has(EventType.ACCEPTED).label("accepted"),
        )
        .where(Event.type.in_(FUNNEL_TYPES))
        .group_by(Event.job_id)
    )


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


@contextmanager
def _materialized(session: Session, name: str, query: Select[Any]) -> Iterator[Table]:
    """El resultado de `query` en una tabla temporal de SQLite mientras dura el bloque.

    El embudo y la calibración hacen una decena de agregados (`GROUP BY`) sobre las mismas filas
    por oferta; como subconsulta, SQLite las recalculaba en cada uno. La tabla es de la conexión
    (no se ve desde otras ni toca los datos) y se borra al salir. El nombre es fijo: no se anidan
    dos llamadas de analítica sobre la misma sesión.
    """
    columns = []
    for column in query.selected_columns:
        if isinstance(column.type, NullType):
            raise TypeError(f"Columna sin tipo en «{name}»: {column.name}.")
        # Una fila por oferta en todas: `job_id` es la clave (y su índice, para los `JOIN`).
        columns.append(Column(column.name, column.type, primary_key=column.name == "job_id"))
    table = Table(name, MetaData(), *columns, prefixes=["TEMPORARY"])
    connection = session.connection()
    # pysqlite confirma el `CREATE` por su cuenta y abre la transacción en el `INSERT`: el `DROP`
    # quedaría dentro y un rollback (lo normal en una lectura) lo desharía, dejando la tabla en la
    # conexión del pool. Con la transacción abierta antes, crear y borrar van juntos.
    if not connection.connection.driver_connection.in_transaction:  # type: ignore[union-attr]
        connection.exec_driver_sql("BEGIN")
    drop = f'DROP TABLE IF EXISTS temp."{name}"'
    connection.exec_driver_sql(drop)  # por si una llamada anterior no llegó a borrarla
    table.create(connection)
    try:
        session.execute(insert(table).from_select([c.name for c in columns], query))
        yield table
    finally:
        connection.exec_driver_sql(drop)


@contextmanager
def _per_job(session: Session, since: date | None) -> Iterator[tuple[Table, int]]:
    """Tabla con una fila por oferta del periodo y sus pasos (0/1, acumulados) y fechas de envío y
    primera respuesta. Da también cuántas se excluyen por duplicadas."""
    scope = []
    if since is not None:
        scope.append(Job.first_seen_at >= start_of_local_day(since))
    # Por pasos, cada uno en su tabla temporal: así cada subconsulta por oferta (la primera
    # respuesta, si sigue cerrada) se evalúa una vez y no en cada columna que la usa.
    with _materialized(session, "cai_job_events", _job_events()) as flags:
        query, duplicates = _raw_query(session, flags, scope)
        with (
            _materialized(session, "cai_raw", query) as raw,
            _materialized(session, "cai_per_job", _cumulative(raw)) as per_job,
        ):
            yield per_job, duplicates


def _raw_query(
    session: Session, flags: FromClause, scope: list[ColumnElement[bool]]
) -> tuple[Select[Any], int]:
    """Las ofertas del periodo (sin duplicadas) con sus pasos sin acumular y la primera respuesta.
    Da también cuántas duplicadas se excluyen."""

    def still_closed_by(has: Any, event_type: EventType) -> ColumnElement[bool]:
        # La subconsulta (por oferta) solo se evalúa en las que tienen ese evento: `CASE` en
        # SQLite no calcula las ramas que no tocan.
        return case((has == 1, _still_closed_by(event_type)), else_=False)

    duplicate = still_closed_by(flags.c.duplicated, EventType.DUPLICATE_DETECTED)
    duplicates = session.scalar(
        select(func.count())
        .select_from(Job)
        .join(flags, flags.c.job_id == Job.id)
        .where(*scope, duplicate)
    )

    def flag_of(column: Any) -> ColumnElement[bool]:
        return func.coalesce(column, 0) == 1

    first_reply = case(
        (
            flags.c.applied_at.is_not(None),
            select(func.min(Event.occurred_at))
            .where(
                Event.job_id == Job.id,
                Event.type.in_(RESPONSE_TYPES),
                Event.occurred_at >= flags.c.applied_at,
            )
            .correlate(Job, flags)
            .scalar_subquery(),
        ),
    )
    query = (
        select(
            Job.id.label("job_id"),
            Job.source_id,
            Job.first_seen_at,
            flags.c.applied_at,
            type_coerce(first_reply, Event.occurred_at.type).label("reply_at"),
            and_(
                flag_of(flags.c.extracted),
                ~still_closed_by(flags.c.filtered, EventType.HARD_FILTER_FAILED),
            ).label("triaged"),
            flag_of(flags.c.approved).label("approved"),
            flag_of(flags.c.interview).label("interview"),
            flag_of(flags.c.offer).label("offer"),
            flag_of(flags.c.accepted).label("accepted"),
        )
        .outerjoin(flags, flags.c.job_id == Job.id)
        .where(*scope, ~duplicate)
    )
    return query, duplicates or 0


def _cumulative(raw: FromClause) -> Select[Any]:
    """Los pasos de cada oferta, acumulados."""
    # Acumulado: cada paso incluye a las que llegaron a uno posterior.
    accepted = raw.c.accepted
    offer = or_(raw.c.offer, accepted)
    interview = or_(raw.c.interview, offer)
    replied = or_(raw.c.reply_at.is_not(None), interview)
    applied = or_(raw.c.applied_at.is_not(None), replied)
    approved = or_(raw.c.approved, applied)
    triaged = or_(raw.c.triaged, approved)

    def flag(condition: ColumnElement[bool], name: str) -> Any:
        return case((condition, 1), else_=0).label(name)

    return select(
        raw.c.job_id,
        raw.c.source_id,
        raw.c.first_seen_at,
        raw.c.applied_at,
        raw.c.reply_at,
        literal_column("1", Integer).label("found"),
        flag(triaged, "triaged"),
        flag(approved, "approved"),
        flag(applied, "applied"),
        flag(replied, "replied"),
        flag(interview, "interview"),
        flag(offer, "offer"),
        flag(accepted, "accepted"),
    )


def _sums(per_job: FromClause, steps: tuple[str, ...]) -> list[Any]:
    return [func.coalesce(func.sum(per_job.c[s]), 0).label(s) for s in steps]


def _summary(row: Any) -> dict[str, Any]:
    values = {s: int(getattr(row, s)) for s in SUMMARY_STEPS}
    return values | {"reply_rate": _rate(values["replied"], values["applied"])}


def _steps(session: Session, per_job: FromClause) -> list[FunnelStep]:
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


_Spend = tuple[float, float | None]  # tokens y dólares (`None`: ningún agente dio coste)


def _job_spend(session: Session) -> tuple[dict[int, _Spend], dict[int, set[int]]]:
    """Tokens y coste de cada oferta (su parte de cada ejecución) y las ejecuciones de cada una."""
    from app.services import agent_costs  # evita la importación circular

    spend: dict[int, _Spend] = {}
    runs: dict[int, set[int]] = {}
    for job_id, items in agent_costs.attributed(session).items():
        tokens = sum(
            i.usage.get("input_tokens", 0) + i.usage.get("output_tokens", 0) for i in items
        )
        costs = [i.usage["cost_usd"] for i in items if "cost_usd" in i.usage]
        spend[job_id] = (tokens, sum(costs) if costs else None)
        runs[job_id] = {i.run_id for i in items}
    return spend, runs


def _add_spend(a: _Spend, b: _Spend) -> _Spend:
    cost = None if a[1] is None and b[1] is None else (a[1] or 0) + (b[1] or 0)
    return a[0] + b[0], cost


def _per(value: float | None, count: int, digits: int) -> float | None:
    return round(value / count, digits) if value is not None and count else None


def _spent(spend: dict[int, _Spend], sources_of: dict[int, int]) -> list[int]:
    """Las ofertas del periodo con gasto en segundo plano, por id: solo ellas suman algo."""
    return sorted(job_id for job_id in spend if job_id in sources_of)


def _agent_cost(
    session: Session,
    per_job: FromClause,
    spend: dict[int, _Spend],
    job_runs: dict[int, set[int]],
    sources_of: dict[int, int],
) -> FunnelCost:
    row = session.execute(select(*_sums(per_job, ("applied", "interview")))).one()
    total: _Spend = (0, None)
    runs: set[int] = set()
    for job_id in _spent(spend, sources_of):
        total = _add_spend(total, spend[job_id])
        runs |= job_runs.get(job_id, set())
    applied, interview = int(row.applied), int(row.interview)
    tokens, cost = total
    return FunnelCost(
        runs=len(runs),
        tokens=round(tokens),
        cost_usd=round(cost, 6) if cost is not None else None,
        applied=applied,
        interview=interview,
        tokens_per_applied=_per(tokens, applied, 1),
        cost_per_applied_usd=_per(cost, applied, 6),
        tokens_per_interview=_per(tokens, interview, 1),
        cost_per_interview_usd=_per(cost, interview, 6),
    )


def _by_source(
    session: Session, per_job: FromClause, spend: dict[int, _Spend], sources_of: dict[int, int]
) -> list[SourceFunnel]:
    rows = session.execute(
        select(Source.id, Source.kind, Source.name, *_sums(per_job, SUMMARY_STEPS))
        .join(per_job, per_job.c.source_id == Source.id)
        .group_by(Source.id)
        .order_by(func.sum(per_job.c.found).desc(), Source.id)
    ).all()
    by_source: dict[int, _Spend] = {}
    for job_id in _spent(spend, sources_of):
        source_id = sources_of[job_id]
        by_source[source_id] = _add_spend(by_source.get(source_id, (0, None)), spend[job_id])
    out = []
    for r in rows:
        tokens, cost = by_source.get(r.id, (0, None))
        out.append(
            SourceFunnel(
                source_id=r.id,
                kind=r.kind,
                name=r.name,
                tokens=round(tokens),
                cost_usd=round(cost, 6) if cost is not None else None,
                **_summary(r),
            )
        )
    return out


def _by_title(session: Session, per_job: FromClause, top: int) -> list[TitleFunnel]:
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


def _by_week(session: Session, per_job: FromClause) -> list[WeekFunnel]:
    week = func.cai_iso_week(per_job.c.first_seen_at)
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


def _referral_group(per_job: FromClause) -> Any:
    """`given`, `requested` o `none` según la marca de referencia de los contactos del proceso."""

    def marked(status: str) -> ColumnElement[bool]:
        return (
            exists()
            .where(Contact.job_id == per_job.c.job_id, Contact.referral == status)
            .correlate(per_job)
        )

    return case((marked("given"), "given"), (marked("requested"), "requested"), else_="none")


def _by_referral(session: Session, per_job: FromClause) -> list[ReferralFunnel]:
    group = _referral_group(per_job)
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


def _response_time(session: Session, per_job: FromClause) -> ResponseTime:
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


def _discard_reasons(session: Session, per_job: FromClause) -> list[ReasonCount]:
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


def _hard_filter_failures(session: Session, per_job: FromClause) -> list[FilterCount]:
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
    spend, job_runs = _job_spend(session)
    with _per_job(session, since) as (per_job, duplicates):
        rows = session.execute(select(per_job.c.job_id, per_job.c.source_id))
        sources_of = {job_id: source_id for job_id, source_id in rows}
        return FunnelStats(
            since=since,
            duplicates_excluded=duplicates,
            steps=_steps(session, per_job),
            by_source=_by_source(session, per_job, spend, sources_of),
            by_title=_by_title(session, per_job, top_titles),
            by_week=_by_week(session, per_job),
            by_referral=_by_referral(session, per_job),
            response_time=_response_time(session, per_job),
            discard_reasons=_discard_reasons(session, per_job),
            hard_filter_failures=_hard_filter_failures(session, per_job),
            agent_cost=_agent_cost(session, per_job, spend, job_runs, sources_of),
        )


# --- Calibración (fase 20) -------------------------------------------------------------------

MIN_CASES = 10  # por debajo, el grupo lleva `low_data`
CONFIDENCE = 0.95
_Z = 1.959964  # cuantil normal del 97,5 %: intervalo bilateral al 95 %

SCORE_BANDS: tuple[tuple[str, str], ...] = (
    ("lt60", "< 60"),
    ("60_74", "60-74"),
    ("75_84", "75-84"),
    ("gte85", "≥ 85"),
    ("none", "Sin score"),
)
VERDICTS: tuple[tuple[str, str], ...] = (
    ("strong", "Fuerte"),
    ("possible", "Posible"),
    ("weak", "Débil"),
    ("none", "Sin valorar"),
)
LETTER_GROUPS: tuple[tuple[str, str], ...] = (("with", "Con carta"), ("without", "Sin carta"))
REFERRAL_LABELS: tuple[tuple[str, str], ...] = (
    ("given", "Con referencia"),
    ("requested", "Referencia pedida"),
    ("none", "Sin referencia"),
)
# Días entre el alta (`first_seen_at`) y el primer envío: menos de `limit` días.
DAY_BUCKETS: tuple[tuple[str, str, float], ...] = (
    ("0_1", "0-1 días", 2),
    ("2_3", "2-3 días", 4),
    ("4_7", "4-7 días", 8),
    ("8_plus", "8 días o más", math.inf),
)
# Señales de oferta dudosa (fase 25.3). Una oferta cuenta en cada señal que tenga; «Sin señales»
# son las que no tienen ninguna. Son las señales de ahora, no las que tenía al enviarla.
SIGNAL_LABELS: tuple[tuple[str, str], ...] = (
    ("salary_range_wide", "Rango salarial muy amplio"),
    ("employer_hidden", "Empresa oculta o agencia"),
    ("fixed_term", "Temporal"),
    ("stale_repost", "Publicada hace meses"),
    ("ai_screening", "Cribado con IA"),
    ("none", "Sin señales"),
)
# Grupos sin dato. Una plantilla del usuario con id «none» se sumaría a «Sin CV de la app».
NO_PLATFORM = "none"
NO_TEMPLATE = "none"


class RateInterval(BaseModel):
    rate: float | None  # 0-1; `null` sin envíos
    low: float | None  # intervalo de Wilson al 95 %
    high: float | None


class CalibrationGroup(BaseModel):
    key: str  # estable: tramo, veredicto, id de fuente, portal, id de plantilla…
    label: str
    applied: int  # enviadas
    replied: int  # con respuesta (la que sea, también un rechazo)
    interview: int  # con entrevista
    awaiting: int  # enviadas sin respuesta y aún en `applied`: bajan la tasa sin ser un «no»
    reply_rate: RateInterval
    interview_rate: RateInterval
    low_data: bool  # `applied < min_cases`: no saques conclusiones


class Calibration(BaseModel):
    since: date | None  # fecha del primer envío
    min_cases: int
    confidence: float
    total: CalibrationGroup
    by_score: list[CalibrationGroup]  # siempre los cinco tramos, en orden
    by_verdict: list[CalibrationGroup]  # strong, possible, weak, none
    by_source: list[CalibrationGroup]  # las que tienen envíos; `key` = id de la fuente
    by_platform: list[CalibrationGroup]  # `jobs.platform`; `none` sin portal
    by_template: list[CalibrationGroup]  # plantilla del CV enviado; `none` sin CV de la app
    by_cover_letter: list[CalibrationGroup]  # with, without
    by_referral: list[CalibrationGroup]  # given, requested, none
    by_days_to_apply: list[CalibrationGroup]  # 0_1, 2_3, 4_7, 8_plus
    # Fase 25.3: una oferta cuenta en cada señal de oferta dudosa que tenga; `none`, sin ninguna.
    by_signal: list[CalibrationGroup]


def wilson_interval(successes: int, n: int, z: float = _Z) -> RateInterval:
    """Tasa e intervalo de Wilson: no se sale de [0, 1] y no colapsa con 0 o n éxitos."""
    if n == 0:
        return RateInterval(rate=None, low=None, high=None)
    p = successes / n
    denominator = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    low, high = max(0.0, centre - margin), min(1.0, centre + margin)
    return RateInterval(rate=round(p, 4), low=round(low, 4), high=round(high, 4))


def _calibration_rows(per_job: FromClause, since: date | None) -> Select[Any]:
    """Una fila por oferta enviada con su resultado y lo que se sabía al enviarla."""
    applied_at, job_id = per_job.c.applied_at, per_job.c.job_id

    def nearest_score(before: bool) -> Any:
        if before:
            when = Match.created_at <= applied_at
            order = (Match.created_at.desc(), Match.id.desc())
        else:
            when = Match.created_at > applied_at
            order = (Match.created_at, Match.id)
        query = select(Match.score).where(Match.job_id == job_id, when).order_by(*order).limit(1)
        return query.correlate(per_job).scalar_subquery()

    verdict = (
        select(Event.payload["verdict"].as_string())
        .where(
            Event.job_id == job_id,
            Event.type == EventType.FIT_ASSESSED,
            Event.occurred_at <= applied_at,
        )
        .order_by(Event.occurred_at.desc(), Event.id.desc())
        .limit(1)
        .correlate(per_job)
        .scalar_subquery()
    )
    render_id = (
        select(Event.payload["render_id"].as_integer())
        .where(Event.job_id == job_id, Event.type.in_(APPLIED_TYPES))
        .order_by(Event.occurred_at, Event.id)
        .limit(1)
        .correlate(per_job)
        .scalar_subquery()
    )
    template = (
        select(DocumentRender.template_id)
        .where(DocumentRender.id == render_id)
        .correlate(per_job)
        .scalar_subquery()
    )
    letter = (
        exists()
        .where(
            Document.job_id == job_id,
            Document.kind == LETTER_KIND,
            Document.created_at <= applied_at,
        )
        .correlate(per_job)
    )
    # Como el paso «Con respuesta» del embudo: una entrevista anterior al envío cuenta como
    # respuesta aunque no tenga `reply_at`.
    awaiting = and_(per_job.c.replied == 0, Application.stage == Stage.APPLIED)
    scope = [applied_at.is_not(None)]
    if since is not None:
        scope.append(applied_at >= start_of_local_day(since))
    return (
        select(
            job_id,
            per_job.c.source_id,
            func.coalesce(Job.platform, NO_PLATFORM).label("platform"),
            per_job.c.replied,
            per_job.c.interview,
            case((awaiting, 1), else_=0).label("awaiting"),
            func.coalesce(nearest_score(True), nearest_score(False)).label("score"),
            func.coalesce(verdict, "none").label("verdict"),
            func.coalesce(template, NO_TEMPLATE).label("template"),
            case((letter, "with"), else_="without").label("letter"),
            _referral_group(per_job).label("referral"),
            type_coerce(
                func.julianday(applied_at) - func.julianday(per_job.c.first_seen_at), Float
            ).label("days"),
            *(
                case((func.json_extract(Job.signals, f"$.{code}").is_not(None), 1), else_=0).label(
                    f"signal_{code}"
                )
                for code, _ in SIGNAL_LABELS[:-1]
            ),
        )
        .select_from(per_job)
        .join(Job, Job.id == job_id)
        .outerjoin(Application, Application.job_id == job_id)
        .where(*scope)
    )


def _group(key: str, label: str, row: Any | None, min_cases: int) -> CalibrationGroup:
    applied, replied, interview, awaiting = (
        (int(row.applied), int(row.replied), int(row.interview), int(row.awaiting))
        if row is not None
        else (0, 0, 0, 0)
    )
    return CalibrationGroup(
        key=key,
        label=label,
        applied=applied,
        replied=replied,
        interview=interview,
        awaiting=awaiting,
        reply_rate=wilson_interval(replied, applied),
        interview_rate=wilson_interval(interview, applied),
        low_data=applied < min_cases,
    )


def _counts(session: Session, cal: FromClause, key: Any = None) -> list[Any]:
    """Enviadas, con respuesta, con entrevista y esperando; agrupadas por `key` si se da."""
    sums = [
        func.count().label("applied"),
        func.coalesce(func.sum(cal.c.replied), 0).label("replied"),
        func.coalesce(func.sum(cal.c.interview), 0).label("interview"),
        func.coalesce(func.sum(cal.c.awaiting), 0).label("awaiting"),
    ]
    if key is None:
        return [session.execute(select(*sums).select_from(cal)).one()]
    return list(session.execute(select(key.label("key"), *sums).group_by(key)).all())


def _by_signal(session: Session, cal: FromClause, min_cases: int) -> list[CalibrationGroup]:
    """Un grupo por señal (una oferta puede estar en varios) y «Sin señales»."""
    columns = [cal.c[f"signal_{code}"] for code, _ in SIGNAL_LABELS[:-1]]
    sums = [
        func.count().label("applied"),
        func.coalesce(func.sum(cal.c.replied), 0).label("replied"),
        func.coalesce(func.sum(cal.c.interview), 0).label("interview"),
        func.coalesce(func.sum(cal.c.awaiting), 0).label("awaiting"),
    ]
    out = []
    for (code, label), column in zip(SIGNAL_LABELS, [*columns, None], strict=True):
        where = column == 1 if column is not None else and_(*(c == 0 for c in columns))
        row = session.execute(select(*sums).select_from(cal).where(where)).one()
        out.append(_group(code, label, row, min_cases))
    return out


def _fixed(
    session: Session, cal: FromClause, key: Any, groups: tuple[tuple[str, str], ...], min_cases: int
) -> list[CalibrationGroup]:
    """Siempre los mismos grupos y en ese orden, a cero si no tienen envíos."""
    rows = {r.key: r for r in _counts(session, cal, key)}
    return [_group(k, label, rows.get(k), min_cases) for k, label in groups]


def _open(
    session: Session, cal: FromClause, key: Any, labels: dict[str, str], min_cases: int
) -> list[CalibrationGroup]:
    """Los grupos que salen de los datos, de más a menos envíos y por etiqueta."""
    out = [
        _group(str(r.key), labels.get(str(r.key), str(r.key)), r, min_cases)
        for r in _counts(session, cal, key)
    ]
    return sorted(out, key=lambda g: (-g.applied, g.label.casefold(), g.key))


def get_calibration(
    session: Session, since: date | None = None, min_cases: int = MIN_CASES
) -> Calibration:
    """Tasa de respuesta y de entrevista de las candidaturas enviadas desde `since` (todas si es
    `None`) por tramo de score, veredicto, fuente, portal, plantilla, carta, referencia y días
    entre el alta y el envío. Orientativa: con pocos casos, el intervalo lo dice."""
    with (
        _per_job(session, None) as (per_job, _),
        _materialized(session, "cai_calibration", _calibration_rows(per_job, since)) as cal,
    ):
        return _calibration(session, cal, since, min_cases)


def _calibration(
    session: Session, cal: FromClause, since: date | None, min_cases: int
) -> Calibration:
    score = cal.c.score
    band = case(
        (score.is_(None), "none"),
        (score < 60, "lt60"),
        (score < 75, "60_74"),
        (score < 85, "75_84"),
        else_="gte85",
    )
    days = case(
        *((cal.c.days < limit, key) for key, _, limit in DAY_BUCKETS[:-1]),
        else_=DAY_BUCKETS[-1][0],
    )
    sources = {str(s.id): s.name for s in session.scalars(select(Source))}
    day_groups = tuple((key, label) for key, label, _ in DAY_BUCKETS)
    return Calibration(
        since=since,
        min_cases=min_cases,
        confidence=CONFIDENCE,
        total=_group("total", "Total", _counts(session, cal)[0], min_cases),
        by_score=_fixed(session, cal, band, SCORE_BANDS, min_cases),
        by_verdict=_fixed(session, cal, cal.c.verdict, VERDICTS, min_cases),
        by_source=_open(session, cal, cal.c.source_id, sources, min_cases),
        by_platform=_open(session, cal, cal.c.platform, {NO_PLATFORM: "Sin portal"}, min_cases),
        by_template=_open(
            session, cal, cal.c.template, {NO_TEMPLATE: "Sin CV de la app"}, min_cases
        ),
        by_cover_letter=_fixed(session, cal, cal.c.letter, LETTER_GROUPS, min_cases),
        by_referral=_fixed(session, cal, cal.c.referral, REFERRAL_LABELS, min_cases),
        by_days_to_apply=_fixed(session, cal, days, day_groups, min_cases),
        by_signal=_by_signal(session, cal, min_cases),
    )


# --- La historia con números (fase 25.6) -----------------------------------------------------

_MONTHS = {
    "es": ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"),
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
}
# La línea para el README: campo, singular y plural, en el orden en que se cuenta.
_STORY_WORDS: dict[str, dict[str, Any]] = {
    "es": {
        "head": "Mi búsqueda con CandidatAI",
        "week": "semana",
        "weeks": "semanas",
        "last": " y ",
        "counts": (
            ("evaluated", "oferta evaluada", "ofertas evaluadas"),
            ("approved", "aprobada", "aprobadas"),
            ("applied", "candidatura", "candidaturas"),
            ("replied", "respuesta", "respuestas"),
            ("interviews", "entrevista", "entrevistas"),
            ("offers", "oferta", "ofertas"),
        ),
    },
    "en": {
        "head": "My search with CandidatAI",
        "week": "week",
        "weeks": "weeks",
        "last": ", ",
        "counts": (
            ("evaluated", "posting evaluated", "postings evaluated"),
            ("approved", "approved", "approved"),
            ("applied", "application", "applications"),
            ("replied", "reply", "replies"),
            ("interviews", "interview", "interviews"),
            ("offers", "offer", "offers"),
        ),
    },
}


class SearchStory(BaseModel):
    """Toda la búsqueda en números agregados, para contarla (p. ej. en el README).

    Solo recuentos y fechas: ni empresas, ni puestos, ni fuentes, ni importes. Es lo que el usuario
    puede publicar si quiere; la app no lo publica nunca.
    """

    started_on: date | None  # día (Europe/Madrid) de la primera oferta vista
    first_applied_on: date | None
    last_activity_on: date | None  # día del último evento
    weeks: int | None  # semanas entre `started_on` y `last_activity_on`, redondeando hacia arriba
    found: int
    evaluated: int  # con extracción: pasaran o no los filtros duros
    approved: int
    applied: int
    replied: int
    interviews: int
    offers: int
    accepted: int
    reply_rate: float | None  # con respuesta / enviadas
    interview_rate: float | None  # con entrevista / enviadas
    median_days_to_reply: float | None
    markdown: dict[Literal["es", "en"], str]  # una línea para pegar, en cada idioma del README


def _local_day(value: datetime | None) -> date | None:
    return value.astimezone(local_zone()).date() if value is not None else None


def _number(value: int, lang: str) -> str:
    grouped = f"{value:,}"
    return grouped.replace(",", " ") if lang == "es" else grouped


def _day(value: date, lang: str) -> str:
    return f"{value.day} {_MONTHS[lang][value.month - 1]} {value.year}"


def _story_markdown(story: SearchStory, lang: Literal["es", "en"]) -> str:
    words = _STORY_WORDS[lang]
    parts = []
    for field, singular, plural in words["counts"]:
        value = getattr(story, field)
        parts.append(f"{_number(value, lang)} {singular if value == 1 else plural}")
    counts = ", ".join(parts[:-1]) + f"{words['last']}{parts[-1]}"
    when = ""
    if story.started_on and story.last_activity_on:
        week = words["week"] if story.weeks == 1 else words["weeks"]
        when = (
            f" ({_day(story.started_on, lang)} → {_day(story.last_activity_on, lang)}, "
            f"{story.weeks} {week})"
        )
    return f"**{words['head']}**{when}: {counts}."


def get_search_story(session: Session) -> SearchStory:
    """La búsqueda entera, desde la primera oferta, en números agregados (sin duplicadas)."""
    with _per_job(session, None) as (per_job, _):
        return _search_story(session, per_job)


def _search_story(session: Session, per_job: FromClause) -> SearchStory:
    steps = ("found", "approved", "applied", "replied", "interview", "offer", "accepted")
    row = session.execute(
        select(
            *_sums(per_job, steps),
            func.min(per_job.c.first_seen_at).label("started"),
            func.min(per_job.c.applied_at).label("first_applied"),
        )
    ).one()
    evaluated = session.scalar(
        select(func.count(Event.job_id.distinct())).where(
            Event.type == EventType.EXTRACTED,
            Event.job_id.in_(select(per_job.c.job_id)),
        )
    )
    last = session.scalar(
        select(func.max(Event.occurred_at)).where(Event.job_id.in_(select(per_job.c.job_id)))
    )
    started, last_day = _local_day(row.started), _local_day(last)
    weeks = None
    if started is not None and last_day is not None:
        weeks = max(1, math.ceil(((last_day - started).days + 1) / 7))
    applied = int(row.applied)
    story = SearchStory(
        started_on=started,
        first_applied_on=_local_day(row.first_applied),
        last_activity_on=last_day,
        weeks=weeks,
        found=int(row.found),
        evaluated=evaluated or 0,
        approved=int(row.approved),
        applied=applied,
        replied=int(row.replied),
        interviews=int(row.interview),
        offers=int(row.offer),
        accepted=int(row.accepted),
        reply_rate=_rate(int(row.replied), applied),
        interview_rate=_rate(int(row.interview), applied),
        median_days_to_reply=_response_time(session, per_job).median_days,
        markdown={"es": "", "en": ""},
    )
    story.markdown = {"es": _story_markdown(story, "es"), "en": _story_markdown(story, "en")}
    return story
