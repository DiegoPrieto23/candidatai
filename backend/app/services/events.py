"""Registro de eventos: la única forma de cambiar el estado de una oferta."""

from datetime import datetime
from typing import Any, Literal, get_args

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import Application, Event, Job
from app.models.base import utcnow
from app.services.pipeline import (
    Actor,
    EventType,
    Stage,
    job_events,
    project,
    save_projection,
)


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
    state = project([*job_events(session, job_id), event])
    session.add(event)
    save_projection(session, job_id, state)
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


def add_user_event(
    session: Session,
    job_id: int,
    type: str,
    note: str | None = None,
    occurred_at: datetime | None = None,
    reason: str | None = None,
    channel: str | None = None,
) -> AddEventResult:
    """Registra un evento del usuario (actor `user`). La nota va en `payload.note`.

    `discarded` exige un motivo (`reason`, uno de `DISCARD_REASONS`); con `other`, también nota.
    `applied` y `applied_manually` admiten el canal (`channel`) y apuntan en `payload.render_id`
    el render seleccionado del último CV de la oferta, si lo hay (el CV enviado), y encolan el
    archivo de la candidatura en `data/documentos/candidaturas/` (`archive_application`).
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
