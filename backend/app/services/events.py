"""Registro de eventos: la única forma de cambiar el estado de una oferta."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.models import Event, Job
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
