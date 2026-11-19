"""Registro de eventos: la única forma de cambiar el estado de una oferta."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, get_args
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.models import Application, Event, Job, MessageDraft, Reply
from app.models.base import utcnow
from app.services.pipeline import (
    TRANSITIONS,
    Actor,
    EventType,
    InvalidTransitionError,
    ProjectionState,
    Stage,
    apply_event,
    job_events,
    project,
    save_projection,
    tolerated,
)
from app.services.signals import set_signal


class UnknownEventTypeError(ValueError):
    pass


class UnknownActorError(ValueError):
    pass


class JobNotFoundError(LookupError):
    pass


def parse_event_type(value: str) -> EventType:
    try:
        return EventType(value)
    except ValueError:
        valid = ", ".join(t.value for t in EventType)
        raise UnknownEventTypeError(
            f"Tipo de evento desconocido: «{value}». Tipos válidos: {valid}."
        ) from None


def parse_actor(value: str) -> Actor:
    try:
        return Actor(value)
    except ValueError:
        valid = ", ".join(a.value for a in Actor)
        raise UnknownActorError(f"Actor desconocido: «{value}». Válidos: {valid}.") from None


def _after_same_minute(occurred_at: datetime, previous: list[Event]) -> datetime:
    """Una hora en minuto exacto (la UI la pide sin segundos) en el mismo minuto que el último
    evento, pero antes que él, es «ahora mismo»: va justo detrás, no antes. Sin esto, «Me han
    respondido» registrado segundos después del envío quedaba antes del envío (o del alta) y se
    rechazaba. Si de verdad fue a las 10:00 en punto y lo último es de las 10:00:30, queda a las
    10:00:30: la diferencia es de segundos y el orden es el que importa."""
    if not previous or occurred_at.second or occurred_at.microsecond:
        return occurred_at
    last = max(e.occurred_at for e in previous)
    if last.tzinfo is None:  # SQLite devuelve UTC sin zona
        last = last.replace(tzinfo=UTC)
    if occurred_at < last < occurred_at + timedelta(minutes=1):
        return last
    return occurred_at


# --- Eventos posteriores que chocan con uno anotado con fecha pasada ----------------------------

# Lo que el usuario puede haber anotado por error y quitar al anotar algo con fecha pasada (p. ej.
# un seguimiento detrás de un cierre, o cerrar y reabrir para probar). Las entrevistas y las
# pruebas no: van con su hito, que se borra desde su ficha. Una oferta recibida o aceptada, tampoco.
REMOVABLE_ON_CONFLICT = frozenset(
    {
        EventType.FOLLOWUP_SENT,
        EventType.REPLY_RECEIVED,
        EventType.REJECTED,
        EventType.WITHDRAWN,
        EventType.EXPIRED,
        EventType.REOPENED,
    }
)


class LaterEventsConflictError(InvalidTransitionError):
    """El evento encaja donde cae, pero algo anotado después deja de encajar con él."""

    def __init__(self, message: str, conflicts: list[Event]) -> None:
        super().__init__(message)
        self.conflicts = conflicts


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value  # SQLite: UTC sin zona


def _local(value: datetime) -> str:
    zone = ZoneInfo(get_policies().calendar.timezone)
    return _utc(value).astimezone(zone).strftime("%d/%m/%Y %H:%M")


def _removable(event: Event) -> bool:
    return (
        EventType(event.type) in REMOVABLE_ON_CONFLICT
        and event.actor != Actor.SYSTEM.value
        and "milestone_id" not in (event.payload or {})
    )


def _replay(previous: Sequence[Event], event: Event) -> tuple[ProjectionState, list[Event]]:
    """Proyecta `previous` con `event` en su sitio. Lanza `InvalidTransitionError` si `event` no es
    válido donde cae; si lo es, devuelve el estado y los eventos posteriores que dejan de encajar
    (se saltan para seguir buscando: así salen todos, no solo el primero).

    Un cierre con fecha pasada tampoco deja pasar un `reopened` posterior: la oferta acabaría
    abierta sin que nadie lo pidiera, porque ese `reopened` deshacía otro cierre."""
    ordered = sorted([*previous, event], key=lambda e: _utc(e.occurred_at))
    closing = TRANSITIONS[EventType(event.type)].to == Stage.CLOSED
    state: ProjectionState | None = None
    conflicts: list[Event] = []
    seen = False
    for item in ordered:
        if item is event:
            seen = True
            state = apply_event(state, item)
            continue
        if tolerated(state, item):
            continue
        if (
            seen
            and closing
            and item.type == EventType.REOPENED
            and state is not None
            and state.stage == Stage.CLOSED
        ):
            conflicts.append(item)
            continue
        try:
            state = apply_event(state, item)
        except InvalidTransitionError:
            if not seen:
                raise
            conflicts.append(item)
    assert state is not None
    return state, conflicts


def _conflict_message(event: Event, conflicts: list[Event]) -> str:
    listed = ", ".join(f"«{c.type}» ({_local(c.occurred_at)})" for c in conflicts)
    last = _local(max(_utc(c.occurred_at) for c in conflicts))
    message = (
        f"No se puede anotar «{event.type}» el {_local(event.occurred_at)}: después hay anotado "
        f"{listed}, que no encaja con eso. Pon una fecha posterior al {last}"
    )
    if all(_removable(c) for c in conflicts):
        return (
            f"{message}. Si lo anotaste por error, anótalo desde la ficha de la oferta: allí te "
            "propone quitarlo."
        )
    return f"{message}."


def record(
    session: Session,
    job_id: int,
    type: str,
    actor: str,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
    agent_name: str | None = None,
) -> Event:
    """Registra un evento y actualiza la proyección en `applications`.

    Valida tipo, actor y transición antes de escribir nada. `occurred_at` puede ser pasado (se
    anota algo que ocurrió antes): la proyección se recalcula reproduciendo los eventos de la
    oferta en orden, así que el evento debe encajar también con los posteriores.
    """
    event_type = parse_event_type(type)
    event_actor = parse_actor(actor)
    if session.get(Job, job_id) is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    if occurred_at is not None and occurred_at.tzinfo is None:
        raise ValueError("`occurred_at` debe llevar zona horaria.")
    previous = job_events(session, job_id)
    if occurred_at is not None:
        occurred_at = _after_same_minute(occurred_at, previous)

    event = Event(
        job_id=job_id,
        type=event_type.value,
        actor=event_actor.value,
        agent_name=agent_name,
        payload=payload or {},
        occurred_at=occurred_at or utcnow(),
        recorded_at=utcnow(),
    )
    # Valida contra la secuencia completa antes de persistir: si falla, no se escribe nada.
    state, conflicts = _replay(previous, event)
    if conflicts:
        raise LaterEventsConflictError(_conflict_message(event, conflicts), conflicts)
    session.add(event)
    save_projection(session, job_id, state)
    if event_type == EventType.REOPENED:
        job = session.get(Job, job_id)
        if job is not None and (job.signals or {}).get("republished_after_close"):
            set_signal(job, "republished_after_close", None)
    session.flush()
    return event


class EventOut(BaseModel):
    id: int
    type: str
    actor: str
    agent_name: str | None
    payload: dict[str, Any]
    occurred_at: datetime
    recorded_at: datetime


class Timeline(BaseModel):
    job_id: int
    stage: Stage | None
    events: list[EventOut]


def get_timeline(session: Session, job_id: int) -> Timeline:
    """Etapa actual y eventos de una oferta, en orden cronológico. Sin texto crudo."""
    if session.get(Job, job_id) is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    events = job_events(session, job_id)
    return Timeline(
        job_id=job_id,
        stage=project(events).stage if events else None,
        events=[EventOut.model_validate(e, from_attributes=True) for e in events],
    )


def current_stage(session: Session, job_id: int) -> Stage:
    """Etapa actual según la proyección. Solo para ofertas que ya tienen eventos."""
    application = session.get(Application, job_id)
    if application is None:
        raise JobNotFoundError(f"La oferta {job_id} no tiene eventos.")
    return Stage(application.stage)


# Eventos que tienen su propia herramienta o que solo registra el sistema: `add_event` no los
# acepta, para que nadie se salte la validación que hay detrás (p. ej. `extracted` sin extracción).
RESERVED_EVENTS = frozenset(
    {
        EventType.FOUND,
        EventType.DETAIL_CAPTURED,  # lo registra la captura del navegador (09b.2), con el texto
        EventType.DUPLICATE_DETECTED,
        EventType.EXTRACTED,
        EventType.HARD_FILTER_FAILED,
        EventType.SCORED,
        EventType.FIT_ASSESSED,
        EventType.CV_GENERATED,
        EventType.CV_RENDERED,
        EventType.CV_VERIFIED,
        EventType.CV_REJECTED,
        EventType.COVER_LETTER_GENERATED,
        EventType.COVER_LETTER_VERIFIED,
        EventType.APPLICATION_PREPARED,
        EventType.APPLICATION_FILLED,  # lo registra el worker al rellenar (fase 11)
    }
)


class ReservedEventError(ValueError):
    pass


class AddEventResult(BaseModel):
    ok: bool
    event_id: int
    stage: Stage


def add_event(
    session: Session,
    job_id: int,
    type: str,
    note: str | None = None,
    occurred_at: datetime | None = None,
    agent_name: str | None = None,
) -> AddEventResult:
    """Registra un evento pedido por un agente (actor `agent`). La nota va en `payload.note`."""
    event_type = parse_event_type(type)
    if event_type in RESERVED_EVENTS:
        raise ReservedEventError(
            f"El evento «{event_type}» no se registra con `add_event`: lo registra su propia "
            "herramienta o el sistema."
        )
    event = record(
        session,
        job_id,
        event_type,
        Actor.AGENT,
        payload={"note": note} if note else None,
        occurred_at=occurred_at,
        agent_name=agent_name,
    )
    return AddEventResult(ok=True, event_id=event.id, stage=current_stage(session, job_id))


# Eventos que registra el usuario desde la UI (actor `user` en el catálogo de DATA_MODEL.md).
# `cv_rendered` también admite `user`, pero solo lo registra el servicio de render al crear un
# render de verdad: un `cv_rendered` suelto podría llevar a `cv_ready` sin ficheros.
USER_EVENTS = frozenset(
    {
        EventType.APPROVED,
        EventType.DISCARDED,
        EventType.APPLIED,
        EventType.APPLIED_MANUALLY,
        EventType.REPLY_RECEIVED,
        EventType.INTERVIEW_SCHEDULED,
        EventType.INTERVIEW_DONE,
        EventType.TEST_ASSIGNED,
        EventType.FOLLOWUP_SENT,
        EventType.OFFER_RECEIVED,
        EventType.REJECTED,
        EventType.WITHDRAWN,
        EventType.EXPIRED,
        EventType.ACCEPTED,
        EventType.REOPENED,
        EventType.NOTE,
    }
)


class NotUserEventError(ValueError):
    pass


# Motivos rápidos de descarte en el triaje (para la analítica del embudo). `other` exige nota.
# `closed` (fase 16): la oferta ya no está publicada. `not_interested` (fase 27.6): el descarte
# rápido de la Bandeja antes de completar o extraer la oferta, por el título o la empresa.
DiscardReason = Literal[
    "seniority", "skills", "location", "salary", "company", "closed", "not_interested", "other"
]
DISCARD_REASONS: tuple[str, ...] = get_args(DiscardReason)

# Por dónde se envió la candidatura (`applications.channel`).
ApplicationChannel = Literal["ats_form", "email", "linkedin_manual", "portal_manual"]
APPLICATION_CHANNELS: tuple[str, ...] = get_args(ApplicationChannel)


class ConflictingEvent(BaseModel):
    id: int
    type: str
    occurred_at: datetime
    removable: bool  # se puede quitar como anotado por error (`REMOVABLE_ON_CONFLICT`)


class EventConflicts(BaseModel):
    """Qué impide anotar un evento con fecha pasada y cómo arreglarlo (solo la UI)."""

    conflicts: list[ConflictingEvent]
    # Quitar todos los `conflicts` deja anotarlo en la fecha pedida.
    can_remove: bool
    # El primer minuto después del último conflicto en que sí se puede anotar, si lo hay.
    suggested_at: datetime | None


def _probe(job_id: int, type: EventType, occurred_at: datetime) -> Event:
    return Event(
        job_id=job_id, type=type.value, actor=Actor.USER.value, payload={}, occurred_at=occurred_at
    )


def _fits(previous: Sequence[Event], probe: Event) -> bool:
    try:
        return not _replay(previous, probe)[1]
    except InvalidTransitionError:
        return False


def check_user_event(
    session: Session, job_id: int, type: str, occurred_at: datetime
) -> EventConflicts:
    """Los eventos posteriores que no dejarían anotar `type` en `occurred_at`, si quitarlos lo
    arregla y la primera fecha en que sí se puede. No escribe nada. Si el evento no es válido ni
    siquiera donde cae (no por lo de después), lanza `InvalidTransitionError`."""
    event_type = parse_event_type(type)
    if session.get(Job, job_id) is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    if occurred_at.tzinfo is None:
        raise ValueError("`occurred_at` debe llevar zona horaria.")
    previous = job_events(session, job_id)
    occurred_at = _after_same_minute(occurred_at, previous)
    _, conflicts = _replay(previous, _probe(job_id, event_type, occurred_at))
    if not conflicts:
        return EventConflicts(conflicts=[], can_remove=False, suggested_at=None)
    ids = {c.id for c in conflicts}
    can_remove = all(_removable(c) for c in conflicts) and _fits(
        [e for e in previous if e.id not in ids], _probe(job_id, event_type, occurred_at)
    )
    last = max(_utc(c.occurred_at) for c in conflicts)
    suggested: datetime | None = last.replace(second=0, microsecond=0) + timedelta(minutes=1)
    if suggested is not None and (
        suggested > utcnow() or not _fits(previous, _probe(job_id, event_type, suggested))
    ):
        suggested = None
    return EventConflicts(
        conflicts=[
            ConflictingEvent(
                id=c.id, type=c.type, occurred_at=_utc(c.occurred_at), removable=_removable(c)
            )
            for c in conflicts
        ],
        can_remove=can_remove,
        suggested_at=suggested,
    )


def _remove_conflicts(
    session: Session, job_id: int, type: EventType, occurred_at: datetime, ids: list[int]
) -> None:
    """Quita los eventos anotados por error que impiden anotar `type` en `occurred_at`. Tienen que
    ser justo los que salen en `check_user_event`: si algo cambió desde entonces, no se quita nada.
    Lo que apuntaba a ellos (un borrador, un correo aceptado) se queda, sin el enlace."""
    found = check_user_event(session, job_id, type, occurred_at)
    if not found.can_remove or {c.id for c in found.conflicts} != set(ids):
        raise InvalidTransitionError(
            "Lo que impedía anotarlo ha cambiado desde que lo viste: vuelve a intentarlo."
        )
    for model in (Reply, MessageDraft):
        session.execute(update(model).where(model.event_id.in_(ids)).values(event_id=None))
    for event in job_events(session, job_id):
        if event.id in ids:
            session.delete(event)
    session.flush()


def add_user_event(
    session: Session,
    job_id: int,
    type: str,
    note: str | None = None,
    occurred_at: datetime | None = None,
    reason: str | None = None,
    channel: str | None = None,
    remove_event_ids: list[int] | None = None,
) -> AddEventResult:
    """Registra un evento del usuario (actor `user`). La nota va en `payload.note`.

    `discarded` exige un motivo (`reason`, uno de `DISCARD_REASONS`); con `other`, también nota.
    `applied` y `applied_manually` admiten el canal (`channel`) y apuntan en `payload.render_id`
    el render seleccionado del último CV de la oferta, si lo hay (el CV enviado), y encolan el
    archivo de la candidatura en `data/documentos/candidaturas/` (`archive_application`).

    `remove_event_ids` (solo la UI, tras confirmarlo el usuario): los eventos posteriores anotados
    por error que impiden anotar este en `occurred_at` (`check_user_event`). Se quitan y se anota
    en la misma transacción; si algo falla, no cambia nada.
    """
    event_type = parse_event_type(type)
    if event_type not in USER_EVENTS:
        raise NotUserEventError(f"El evento «{event_type}» no lo registra el usuario desde la UI.")
    note = note.strip() if note and note.strip() else None
    if event_type == EventType.NOTE and not note:
        raise ValueError("Una nota necesita texto.")
    if reason is not None and event_type != EventType.DISCARDED:
        raise ValueError("`reason` solo se usa al descartar.")
    if event_type == EventType.DISCARDED:
        if reason not in DISCARD_REASONS:
            valid = ", ".join(DISCARD_REASONS)
            raise ValueError(f"Descartar necesita un motivo (`reason`): {valid}.")
        if reason == "other" and not note:
            raise ValueError("Con el motivo «other», explica el motivo en la nota.")
    applied = event_type in (EventType.APPLIED, EventType.APPLIED_MANUALLY)
    if channel is not None and channel not in APPLICATION_CHANNELS:
        valid = ", ".join(APPLICATION_CHANNELS)
        raise ValueError(f"Canal desconocido: «{channel}». Válidos: {valid}.")
    if channel is not None and not applied:
        raise ValueError("`channel` solo se usa al registrar el envío de la candidatura.")
    payload: dict[str, Any] = {}
    if reason:
        payload["reason"] = reason
    if note:
        payload["note"] = note
    if applied:
        # Import diferido: el servicio de documentos ya importa este módulo.
        from app.services.documents.service import selected_render_id

        if channel:
            payload["channel"] = channel
        render_id = selected_render_id(session, job_id)
        if render_id is not None:
            payload["render_id"] = render_id
    if remove_event_ids and occurred_at is None:
        raise ValueError("Para quitar eventos posteriores hace falta la fecha (`occurred_at`).")
    with session.begin_nested():
        if remove_event_ids and occurred_at is not None:
            _remove_conflicts(session, job_id, event_type, occurred_at, remove_event_ids)
        event = record(
            session,
            job_id,
            event_type,
            Actor.USER,
            payload=payload or None,
            occurred_at=occurred_at,
        )
    if applied:
        # Import diferido: el archivo usa los servicios de documentos, que importan este módulo.
        from app.services import application_archive

        application_archive.enqueue(session, job_id, event.id)
    return AddEventResult(ok=True, event_id=event.id, stage=current_stage(session, job_id))
