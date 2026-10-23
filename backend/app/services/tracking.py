"""Seguimiento de los procesos (fase 10): seguimientos vencidos, próximos hitos y kanban."""

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.models import Application, Company, Contact, Event, Job, Match, Milestone
from app.models.base import utcnow
from app.schemas.llm_io import JobExtraction
from app.services import drafts, extractions
from app.services.events import USER_EVENTS
from app.services.jobs import last_match_subquery
from app.services.pipeline import (
    TRANSITIONS,
    EventType,
    Stage,
    project,
)
from app.services.process import followup_status, local_zone, start_of_local_day

MAX_DAYS = 365

# --- Seguimientos ---------------------------------------------------------------------------


class FollowupItem(BaseModel):
    job_id: int
    title: str
    company: str
    url: str
    channel: str | None
    applied_at: datetime | None
    last_followup_at: datetime | None
    days_waiting: int  # días desde el envío o el último seguimiento
    followups_sent: int  # como mucho `followups.max_followups` - 1: con el tope, no sale
    contacts: list[str]  # nombres (y cargo) de los contactos de la ficha, sin datos de contacto
    draft_id: int | None  # borrador de seguimiento vigente, si ya lo hay


class ThanksItem(BaseModel):
    """Entrevista hecha hace poco sin agradecimiento enviado (fase 15)."""

    job_id: int
    title: str
    company: str
    milestone_id: int
    interview_title: str
    interview_at: datetime
    contacts: list[str]
    draft_id: int | None  # borrador de agradecimiento vigente, si ya lo hay


class FollowupList(BaseModel):
    days_without_reply: int
    max_followups: int
    followups: list[FollowupItem]
    thank_you_days: int
    thanks_due: list[ThanksItem]


def _last_followups(session: Session, job_ids: Iterable[int]) -> dict[int, datetime]:
    rows = session.execute(
        select(Event.job_id, func.max(Event.occurred_at))
        .where(Event.type == EventType.FOLLOWUP_SENT, Event.job_id.in_(list(job_ids)))
        .group_by(Event.job_id)
    ).all()
    return {job_id: value for job_id, value in rows if value is not None}


def _contact_names(session: Session, job_ids: list[int]) -> dict[int, list[str]]:
    """«Nombre (cargo)» de los contactos: lo justo para el saludo, sin emails ni teléfonos."""
    names: dict[int, list[str]] = defaultdict(list)
    for contact in session.scalars(
        select(Contact).where(Contact.job_id.in_(job_ids)).order_by(Contact.id)
    ):
        names[contact.job_id].append(
            f"{contact.name} ({contact.role})" if contact.role else contact.name
        )
    return names


def _draft_ids(session: Session, job_ids: list[int]) -> dict[tuple[int, str, int | None], int]:
    return {
        (row.job_id, row.kind, row.milestone_id): row.id
        for row in reversed(drafts.active_drafts(session, job_ids))
    }


def _thanks_due(session: Session, now: datetime, days: int) -> list[ThanksItem]:
    rows = session.execute(
        select(Milestone, Job.title, Company.name)
        .join(Job, Job.id == Milestone.job_id)
        .join(Company, Company.id == Job.company_id)
        .join(Application, Application.job_id == Job.id)
        .where(
            Milestone.kind == "interview",
            Milestone.status == "done",
            Milestone.starts_at >= now - timedelta(days=days),
            Milestone.starts_at <= now,
            Application.stage.in_(drafts.DRAFT_STAGES),
        )
        .order_by(Milestone.starts_at.desc())
    ).all()
    thanked = drafts.thanked_milestones(session, [m.id for m, _, _ in rows])
    rows = [row for row in rows if row[0].id not in thanked]
    job_ids = [m.job_id for m, _, _ in rows]
    contacts = _contact_names(session, job_ids)
    draft_ids = _draft_ids(session, job_ids)
    return [
        ThanksItem(
            job_id=milestone.job_id,
            title=title,
            company=company,
            milestone_id=milestone.id,
            interview_title=milestone.title,
            interview_at=milestone.starts_at,
            contacts=contacts.get(milestone.job_id, []),
            draft_id=draft_ids.get((milestone.job_id, "thank_you", milestone.id)),
        )
        for milestone, title, company in rows
    ]


def list_followups_due(
    session: Session, days_without_reply: int | None = None, now: datetime | None = None
) -> FollowupList:
    """Candidaturas en `applied` sin respuesta desde hace `days_without_reply` días o más,
    contando desde el envío o el último `followup_sent`. La que más espera, primero. Sin las que
    ya llevan `followups.max_followups` seguimientos. Con `thanks_due`: entrevistas hechas en los
    últimos `followups.thank_you_days` días sin agradecimiento enviado."""
    policy = get_policies().followups
    threshold = days_without_reply or policy.days_without_reply
    now = now or utcnow()
    rows = session.execute(
        select(Application, Job, Company.name)
        .join(Job, Job.id == Application.job_id)
        .join(Company, Company.id == Job.company_id)
        .where(Application.stage == Stage.APPLIED)
    ).all()
    job_ids = [app.job_id for app, _, _ in rows]
    last = _last_followups(session, job_ids)
    sent = drafts.followups_sent(session, job_ids)
    due: list[tuple[Application, Job, str, int]] = []
    for application, job, company in rows:
        if sent.get(job.id, 0) >= policy.max_followups:
            continue
        status = followup_status(application, last.get(job.id), threshold, now)
        if status is None or not status.due or status.days_waiting is None:
            continue
        due.append((application, job, company, status.days_waiting))
    due_ids = [job.id for _, job, _, _ in due]
    contacts = _contact_names(session, due_ids)
    draft_ids = _draft_ids(session, due_ids)
    items = [
        FollowupItem(
            job_id=job.id,
            title=job.title,
            company=company,
            url=job.url,
            channel=application.channel,
            applied_at=application.applied_at,
            last_followup_at=last.get(job.id),
            days_waiting=days_waiting,
            followups_sent=sent.get(job.id, 0),
            contacts=contacts.get(job.id, []),
            draft_id=draft_ids.get((job.id, "followup", None)),
        )
        for application, job, company, days_waiting in due
    ]
    items.sort(key=lambda i: (-i.days_waiting, i.job_id))
    return FollowupList(
        days_without_reply=threshold,
        max_followups=policy.max_followups,
        followups=items,
        thank_you_days=policy.thank_you_days,
        thanks_due=_thanks_due(session, now, policy.thank_you_days),
    )


# --- Próximos hitos -------------------------------------------------------------------------

UpcomingKind = Literal["interview", "test", "deadline", "other", "application_deadline"]
# Plazos de la oferta que aún importan: todavía no se ha enviado la candidatura.
DEADLINE_STAGES = (Stage.PENDING_TRIAGE, Stage.APPROVED, Stage.CV_READY)


class UpcomingItem(BaseModel):
    kind: UpcomingKind
    job_id: int
    job_title: str
    company: str
    stage: Stage
    milestone_id: int | None  # `null` en el plazo de la oferta (`application_deadline`)
    title: str
    starts_at: datetime
    ends_at: datetime | None
    all_day: bool
    location: str | None


class UpcomingList(BaseModel):
    days: int
    items: list[UpcomingItem]


def upcoming_items(session: Session, start: datetime, end: datetime | None) -> list[UpcomingItem]:
    """Hitos programados de ofertas abiertas y plazos de las ofertas sin enviar desde `start`
    hasta `end` excluido (sin límite si es `None`), por fecha."""
    query = (
        select(Milestone, Job.title, Company.name, Application.stage)
        .join(Job, Job.id == Milestone.job_id)
        .join(Company, Company.id == Job.company_id)
        .join(Application, Application.job_id == Job.id)
        .where(
            Milestone.status == "scheduled",
            Milestone.starts_at >= start,
            Application.stage != Stage.CLOSED,
        )
    )
    if end is not None:
        query = query.where(Milestone.starts_at < end)
    items = [
        UpcomingItem(
            kind=m.kind,  # type: ignore[arg-type]
            job_id=m.job_id,
            job_title=job_title,
            company=company,
            stage=Stage(stage),
            milestone_id=m.id,
            title=m.title,
            starts_at=m.starts_at,
            ends_at=m.ends_at,
            all_day=m.all_day,
            location=m.location,
        )
        for m, job_title, company, stage in session.execute(query).all()
    ]
    items.extend(_application_deadlines(session, start, end))
    items.sort(key=lambda i: (i.starts_at, i.job_id, i.milestone_id or 0))
    return items


MilestoneStatus = Literal["scheduled", "done", "cancelled"]


class CalendarItem(UpcomingItem):
    status: MilestoneStatus  # el plazo de la oferta siempre es `scheduled`


class CalendarRange(BaseModel):
    start: date
    end: date  # incluido
    items: list[CalendarItem]


def calendar_items(session: Session, start: date, end: date) -> CalendarRange:
    """Página «Calendario»: todos los hitos (programados, hechos y cancelados, también de procesos
    cerrados) y los plazos de las ofertas sin enviar, del día `start` al `end` incluidos, en hora
    de Madrid."""
    if end < start:
        raise ValueError("`end` no puede ser anterior a `start`.")
    if (end - start).days >= MAX_DAYS:
        raise ValueError(f"El rango no puede pasar de {MAX_DAYS} días.")
    first = start_of_local_day(start)
    after = start_of_local_day(end + timedelta(days=1))
    rows = session.execute(
        select(Milestone, Job.title, Company.name, Application.stage)
        .join(Job, Job.id == Milestone.job_id)
        .join(Company, Company.id == Job.company_id)
        .join(Application, Application.job_id == Job.id)
        .where(Milestone.starts_at >= first, Milestone.starts_at < after)
    ).all()
    items = [
        CalendarItem(
            kind=m.kind,  # type: ignore[arg-type]
            job_id=m.job_id,
            job_title=job_title,
            company=company,
            stage=Stage(stage),
            milestone_id=m.id,
            title=m.title,
            starts_at=m.starts_at,
            ends_at=m.ends_at,
            all_day=m.all_day,
            location=m.location,
            status=m.status,  # type: ignore[arg-type]
        )
        for m, job_title, company, stage in rows
    ]
    items.extend(
        CalendarItem(**i.model_dump(), status="scheduled")
        for i in _application_deadlines(session, first, after)
    )
    items.sort(key=lambda i: (i.starts_at, i.job_id, i.milestone_id or 0))
    return CalendarRange(start=start, end=end, items=items)


def _application_deadlines(
    session: Session, start: datetime, end: datetime | None
) -> list[UpcomingItem]:
    rows = session.execute(
        select(Job.id, Job.title, Company.name, Application.stage)
        .join(Company, Company.id == Job.company_id)
        .join(Application, Application.job_id == Job.id)
        .where(Application.stage.in_(DEADLINE_STAGES))
    ).all()
    latest = extractions.latest_rows(session, [row[0] for row in rows])
    first_day = start.astimezone(local_zone()).date()
    items: list[UpcomingItem] = []
    for job_id, title, company, stage in rows:
        row = latest.get(job_id)
        deadline = JobExtraction.model_validate(row.data).application_deadline if row else None
        if deadline is None or deadline < first_day:
            continue
        starts_at = start_of_local_day(deadline)
        if end is not None and starts_at >= end:
            continue
        items.append(
            UpcomingItem(
                kind="application_deadline",
                job_id=job_id,
                job_title=title,
                company=company,
                stage=Stage(stage),
                milestone_id=None,
                title="Plazo de la oferta",
                starts_at=starts_at,
                ends_at=None,
                all_day=True,
                location=None,
            )
        )
    return items


def list_upcoming(session: Session, days: int = 7, now: datetime | None = None) -> UpcomingList:
    """Entrevistas, pruebas y plazos desde las 00:00 de hoy (Europe/Madrid) hasta el final del día
    de dentro de `days` días (`days=7`: hoy y los 7 días siguientes, enteros)."""
    if not 1 <= days <= MAX_DAYS:
        raise ValueError(f"`days` debe estar entre 1 y {MAX_DAYS}.")
    now = now or utcnow()
    start = start_of_local_day(now)
    return UpcomingList(
        days=days,
        items=upcoming_items(session, start, start_of_local_day(now + timedelta(days=days + 1))),
    )


# --- Kanban ---------------------------------------------------------------------------------

BOARD_STAGES = (Stage.APPROVED, Stage.CV_READY, Stage.APPLIED, Stage.IN_PROCESS, Stage.CLOSED)
CLOSED_LIMIT = 50
# Las cerradas que entran en el tablero: las que llegaron a aprobarse o a enviarse.
_REACHED_BOARD = (EventType.APPROVED, EventType.APPLIED_MANUALLY)
CLOSING_EVENTS = frozenset(e for e, t in TRANSITIONS.items() if t.to == Stage.CLOSED)


class NextMilestone(BaseModel):
    milestone_id: int
    kind: str
    title: str
    starts_at: datetime
    all_day: bool


class BoardCard(BaseModel):
    job_id: int
    title: str
    company: str
    stage: Stage
    score: int | None
    applied_at: datetime | None
    last_event_at: datetime
    next_milestone: NextMilestone | None
    followup_due: bool
    days_waiting: int | None  # solo en `applied`
    closed_by: str | None  # evento de cierre (solo en `closed`)
    reopen_to: Stage | None  # etapa a la que vuelve si se reabre (solo en `closed`)


class BoardColumn(BaseModel):
    stage: Stage
    cards: list[BoardCard]
    total: int  # en `closed`, puede haber más que las mostradas


class BoardMove(BaseModel):
    """Un evento del usuario que mueve una tarjeta entre columnas.

    `to` es `null` en `reopened`: vuelve a la etapa de `reopen_to` de cada tarjeta.
    """

    event: EventType
    from_stages: list[Stage]
    to: Stage | None


class Board(BaseModel):
    columns: list[BoardColumn]
    moves: list[BoardMove]
    days_without_reply: int


def board_moves() -> list[BoardMove]:
    moves: list[BoardMove] = []
    for event in EventType:
        if event not in USER_EVENTS:
            continue
        transition = TRANSITIONS[event]
        if event == EventType.REOPENED:
            moves.append(BoardMove(event=event, from_stages=[Stage.CLOSED], to=None))
            continue
        target = transition.to
        if target is None or target not in BOARD_STAGES:
            continue
        sources = [s for s in BOARD_STAGES if s in transition.allowed_from and s != target]
        if sources:
            moves.append(BoardMove(event=event, from_stages=sources, to=target))
    return moves


def get_board(
    session: Session, closed_limit: int = CLOSED_LIMIT, now: datetime | None = None
) -> Board:
    """Tarjetas por columna (de `approved` a `closed`) y los movimientos posibles."""
    now = now or utcnow()
    threshold = get_policies().followups.days_without_reply
    last = last_match_subquery()
    base = (
        select(Application, Job.title, Company.name, Match.score)
        .join(Job, Job.id == Application.job_id)
        .join(Company, Company.id == Job.company_id)
        .outerjoin(last, last.c.job_id == Job.id)
        .outerjoin(Match, Match.id == last.c.match_id)
    )
    open_rows = session.execute(
        base.where(Application.stage.in_([s for s in BOARD_STAGES if s != Stage.CLOSED]))
    ).all()
    reached = exists().where(Event.job_id == Application.job_id, Event.type.in_(_REACHED_BOARD))
    closed_filter = (Application.stage == Stage.CLOSED, reached)
    closed_total = session.scalar(
        select(func.count()).select_from(Application).where(*closed_filter)
    )
    closed_rows = session.execute(
        base.where(*closed_filter)
        .order_by(Application.last_event_at.desc(), Application.job_id.desc())
        .limit(closed_limit)
    ).all()
    rows = [*open_rows, *closed_rows]
    job_ids = [app.job_id for app, *_ in rows]
    followups = _last_followups(session, job_ids)
    sent = drafts.followups_sent(session, job_ids)
    next_milestones = _next_milestones(session, job_ids, start_of_local_day(now))
    closings = _closings(session, [app.job_id for app, *_ in closed_rows])

    cards: dict[Stage, list[BoardCard]] = {s: [] for s in BOARD_STAGES}
    for application, title, company, score in rows:
        stage = Stage(application.stage)
        status = followup_status(
            application,
            followups.get(application.job_id),
            threshold,
            now,
            sent.get(application.job_id, 0),
        )
        closed_by = reopen_to = None
        if stage == Stage.CLOSED:
            closed_by, reopen_to = closings.get(application.job_id, (None, None))
        cards[stage].append(
            BoardCard(
                job_id=application.job_id,
                title=title,
                company=company,
                stage=stage,
                score=score,
                applied_at=application.applied_at,
                last_event_at=application.last_event_at,
                next_milestone=next_milestones.get(application.job_id),
                followup_due=bool(status and status.due),
                days_waiting=status.days_waiting if status else None,
                closed_by=closed_by,
                reopen_to=reopen_to,
            )
        )
    for stage in BOARD_STAGES:
        if stage != Stage.CLOSED:
            cards[stage].sort(key=lambda c: (c.last_event_at, c.job_id), reverse=True)
    columns = [
        BoardColumn(
            stage=s,
            cards=cards[s],
            total=(closed_total or 0) if s == Stage.CLOSED else len(cards[s]),
        )
        for s in BOARD_STAGES
    ]
    return Board(columns=columns, moves=board_moves(), days_without_reply=threshold)


def _next_milestones(
    session: Session, job_ids: list[int], start: datetime
) -> dict[int, NextMilestone]:
    if not job_ids:
        return {}
    rows = session.scalars(
        select(Milestone)
        .where(
            Milestone.job_id.in_(job_ids),
            Milestone.status == "scheduled",
            Milestone.starts_at >= start,
        )
        .order_by(Milestone.starts_at.desc(), Milestone.id.desc())
    )
    # Orden descendente: el último que se escribe para cada oferta es el más próximo.
    return {
        m.job_id: NextMilestone(
            milestone_id=m.id, kind=m.kind, title=m.title, starts_at=m.starts_at, all_day=m.all_day
        )
        for m in rows
    }


def _closings(session: Session, job_ids: list[int]) -> dict[int, tuple[str | None, Stage | None]]:
    """Evento que cerró cada oferta y etapa a la que volvería al reabrirla (una sola consulta)."""
    if not job_ids:
        return {}
    by_job: dict[int, list[Event]] = defaultdict(list)
    stmt = (
        select(Event)
        .where(Event.job_id.in_(job_ids))
        .order_by(Event.job_id, Event.occurred_at, Event.id)
    )
    for event in session.scalars(stmt):
        by_job[event.job_id].append(event)
    result: dict[int, tuple[str | None, Stage | None]] = {}
    for job_id, events in by_job.items():
        closed_by = next((e.type for e in reversed(events) if e.type in CLOSING_EVENTS), None)
        result[job_id] = (closed_by, project(events).stage_before_close)
    return result
