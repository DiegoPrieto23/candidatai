"""Etapas de una oferta y su proyección a partir de los eventos (ver `docs/DATA_MODEL.md`).

La etapa nunca se guarda sin más: se calcula reproduciendo los eventos en orden cronológico. Cada
tipo de evento declara desde qué etapas es válido y a cuál lleva; un evento fuera de lugar
lanza `InvalidTransitionError` con un mensaje que explica qué se esperaba.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Any, Protocol

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Application, Event


class Stage(StrEnum):
    PENDING_DETAIL = "pending_detail"  # oferta «resumen» de una alerta (fase 09b)
    PENDING_EXTRACTION = "pending_extraction"
    PENDING_TRIAGE = "pending_triage"
    APPROVED = "approved"
    CV_READY = "cv_ready"
    APPLIED = "applied"
    IN_PROCESS = "in_process"
    CLOSED = "closed"


class EventType(StrEnum):
    FOUND = "found"
    DETAIL_CAPTURED = "detail_captured"
    DUPLICATE_DETECTED = "duplicate_detected"
    EXTRACTED = "extracted"
    HARD_FILTER_FAILED = "hard_filter_failed"
    EXTRACTION_FAILED = "extraction_failed"
    INJECTION_SUSPECTED = "injection_suspected"
    SCORED = "scored"
    FIT_ASSESSED = "fit_assessed"
    APPROVED = "approved"
    DISCARDED = "discarded"
    CV_GENERATED = "cv_generated"
    CV_RENDERED = "cv_rendered"
    CV_VERIFIED = "cv_verified"
    CV_REJECTED = "cv_rejected"
    APPLICATION_PREPARED = "application_prepared"
    APPLIED = "applied"
    APPLIED_MANUALLY = "applied_manually"
    REPLY_RECEIVED = "reply_received"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_DONE = "interview_done"
    TEST_ASSIGNED = "test_assigned"
    FOLLOWUP_SENT = "followup_sent"
    OFFER_RECEIVED = "offer_received"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    ACCEPTED = "accepted"
    REOPENED = "reopened"
    NOTE = "note"


class Actor(StrEnum):
    SYSTEM = "system"
    USER = "user"
    AGENT = "agent"


OPEN_STAGES = frozenset(Stage) - {Stage.CLOSED}
# Una oferta resumen (`pending_detail`) solo admite completarse, descartarse, caducar, quedar como
# duplicado, avisos de riesgo y notas: aún no hay descripción que valorar.
WORKING_STAGES = OPEN_STAGES - {Stage.PENDING_DETAIL}
BEFORE_APPLIED = frozenset(
    {Stage.PENDING_EXTRACTION, Stage.PENDING_TRIAGE, Stage.APPROVED, Stage.CV_READY}
)
AFTER_APPLIED = frozenset({Stage.APPLIED, Stage.IN_PROCESS})
CV_STAGES = frozenset({Stage.APPROVED, Stage.CV_READY})
ALL_STAGES = frozenset(Stage)


@dataclass(frozen=True)
class Transition:
    """Desde qué etapas es válido un evento y a qué etapa lleva (`None`: no cambia)."""

    allowed_from: frozenset[Stage]
    to: Stage | None
    hint: str | None = None


_IN_PROCESS = Transition(AFTER_APPLIED, Stage.IN_PROCESS)

# `found` (primer evento; lleva a `pending_detail` si `payload.detail_level` es `summary`),
# `reopened` (vuelve a la etapa previa al cierre), `cv_verified` y `cv_rendered` (llevan a
# `cv_ready` cuando un mismo documento está verificado con `passed` y tiene un render sin
# `too_long`) tienen además un tratamiento especial en `apply_event`.
TRANSITIONS: dict[EventType, Transition] = {
    EventType.FOUND: Transition(frozenset(), Stage.PENDING_EXTRACTION),
    EventType.DETAIL_CAPTURED: Transition(
        frozenset({Stage.PENDING_DETAIL}), Stage.PENDING_EXTRACTION
    ),
    EventType.DUPLICATE_DETECTED: Transition(
        frozenset({Stage.PENDING_DETAIL, Stage.PENDING_EXTRACTION, Stage.PENDING_TRIAGE}),
        Stage.CLOSED,
    ),
    EventType.EXTRACTED: Transition(
        frozenset({Stage.PENDING_EXTRACTION, Stage.PENDING_TRIAGE}), Stage.PENDING_TRIAGE
    ),
    EventType.EXTRACTION_FAILED: Transition(frozenset({Stage.PENDING_EXTRACTION}), None),
    EventType.HARD_FILTER_FAILED: Transition(frozenset({Stage.PENDING_TRIAGE}), Stage.CLOSED),
    EventType.INJECTION_SUSPECTED: Transition(OPEN_STAGES, None),
    EventType.SCORED: Transition(WORKING_STAGES, None),
    EventType.FIT_ASSESSED: Transition(WORKING_STAGES, None),
    EventType.APPROVED: Transition(frozenset({Stage.PENDING_TRIAGE}), Stage.APPROVED),
    EventType.DISCARDED: Transition(BEFORE_APPLIED | {Stage.PENDING_DETAIL}, Stage.CLOSED),
    EventType.CV_GENERATED: Transition(CV_STAGES, None),
    EventType.CV_RENDERED: Transition(CV_STAGES, None),
    EventType.CV_VERIFIED: Transition(CV_STAGES, None),
    EventType.CV_REJECTED: Transition(CV_STAGES, None),
    EventType.APPLICATION_PREPARED: Transition(WORKING_STAGES, None),
    EventType.APPLIED: Transition(
        frozenset({Stage.CV_READY}),
        Stage.APPLIED,
        hint="Si enviaste la candidatura por tu cuenta, registra `applied_manually`.",
    ),
    EventType.APPLIED_MANUALLY: Transition(BEFORE_APPLIED, Stage.APPLIED),
    EventType.REPLY_RECEIVED: _IN_PROCESS,
    EventType.INTERVIEW_SCHEDULED: _IN_PROCESS,
    EventType.INTERVIEW_DONE: _IN_PROCESS,
    EventType.TEST_ASSIGNED: _IN_PROCESS,
    EventType.OFFER_RECEIVED: _IN_PROCESS,
    EventType.FOLLOWUP_SENT: Transition(AFTER_APPLIED, None),
    EventType.REJECTED: Transition(WORKING_STAGES, Stage.CLOSED),
    EventType.WITHDRAWN: Transition(WORKING_STAGES, Stage.CLOSED),
    EventType.EXPIRED: Transition(OPEN_STAGES, Stage.CLOSED),
    EventType.ACCEPTED: Transition(frozenset({Stage.IN_PROCESS}), Stage.CLOSED),
    EventType.REOPENED: Transition(frozenset({Stage.CLOSED}), None),
    EventType.NOTE: Transition(ALL_STAGES, None),
}


class InvalidTransitionError(ValueError):
    """El evento no es válido en la etapa actual de la oferta."""


class EventLike(Protocol):
    """Lo mínimo que necesita la proyección de un evento (el modelo `Event` lo cumple)."""

    @property
    def type(self) -> str: ...
    @property
    def payload(self) -> dict[str, Any] | None: ...
    @property
    def occurred_at(self) -> datetime: ...


@dataclass(frozen=True)
class ProjectionState:
    """Estado proyectado de una oferta; lo que se guarda en `applications` y algo más."""

    stage: Stage
    last_event_at: datetime
    # Se fija en cada cierre y no se limpia al reabrir: solo se lee en `reopened` (desde
    # `closed`), y un cierre posterior lo sobrescribe con la etapa de ese momento.
    stage_before_close: Stage | None = None
    channel: str | None = None
    render_id: int | None = None
    applied_at: datetime | None = None
    # Documentos (CV) verificados con `passed` y documentos con algún render sin `too_long`.
    verified_documents: frozenset[int] = frozenset()
    fitting_documents: frozenset[int] = frozenset()


def _invalid(event_type: EventType, stage: Stage | None, transition: Transition) -> str:
    current = f"la etapa «{stage}»" if stage else "una oferta sin eventos"
    if event_type == EventType.FOUND:
        expected = "solo puede ser el primer evento de una oferta"
    else:
        allowed = ", ".join(s.value for s in Stage if s in transition.allowed_from)
        expected = f"solo es válido en: {allowed}"
    msg = f"El evento «{event_type}» no es válido en {current}; {expected}."
    return f"{msg} {transition.hint}" if transition.hint else msg


def _track_cv(
    state: ProjectionState, event_type: EventType, payload: dict[str, Any]
) -> ProjectionState:
    document_id = payload.get("document_id")
    if not isinstance(document_id, int):
        return state
    # Una verificación que pasa no se retira: un `cv_rejected` o un `cv_verified` fallido
    # posteriores del mismo documento son informativos y no sacan la oferta de `cv_ready`.
    if event_type == EventType.CV_VERIFIED and payload.get("passed") is True:
        return replace(state, verified_documents=state.verified_documents | {document_id})
    if event_type == EventType.CV_RENDERED and payload.get("too_long") is False:
        return replace(state, fitting_documents=state.fitting_documents | {document_id})
    return state


def apply_event(state: ProjectionState | None, event: EventLike) -> ProjectionState:
    """Aplica un evento al estado. Lanza `InvalidTransitionError` si no es válido."""
    event_type = EventType(event.type)
    transition = TRANSITIONS[event_type]
    payload = event.payload or {}

    if state is None:
        if event_type != EventType.FOUND:
            raise InvalidTransitionError(
                f"El primer evento de una oferta debe ser «found», no «{event_type}»."
            )
        summary = payload.get("detail_level") == "summary"
        stage = Stage.PENDING_DETAIL if summary else Stage.PENDING_EXTRACTION
        return ProjectionState(stage=stage, last_event_at=event.occurred_at)

    if event_type == EventType.FOUND or state.stage not in transition.allowed_from:
        raise InvalidTransitionError(_invalid(event_type, state.stage, transition))

    new = replace(state, last_event_at=event.occurred_at)
    target = transition.to
    if event_type == EventType.REOPENED:
        target = state.stage_before_close or Stage.PENDING_EXTRACTION
    elif event_type in (EventType.CV_VERIFIED, EventType.CV_RENDERED):
        new = _track_cv(new, event_type, payload)
        document_id = payload.get("document_id")
        if document_id in new.verified_documents and document_id in new.fitting_documents:
            target = Stage.CV_READY

    if event_type in (EventType.APPLIED, EventType.APPLIED_MANUALLY):
        new = replace(
            new,
            applied_at=event.occurred_at,
            channel=payload.get("channel"),
            render_id=payload.get("render_id"),
        )

    if target is None:
        return new
    if target == Stage.CLOSED:
        return replace(new, stage=Stage.CLOSED, stage_before_close=state.stage)
    return replace(new, stage=target)


def project(events: Iterable[EventLike]) -> ProjectionState:
    """Reproduce los eventos en orden cronológico.

    La ordenación es estable: a igual `occurred_at` se respeta el orden de entrada (el de
    registro), así que los eventos deben llegar ordenados por `id`.
    """
    state: ProjectionState | None = None
    for event in sorted(events, key=lambda e: e.occurred_at):
        state = apply_event(state, event)
    if state is None:
        raise ValueError("No hay eventos: la oferta no tiene etapa.")
    return state


def stage_for(events: Iterable[EventLike]) -> Stage:
    return project(events).stage


def job_events(session: Session, job_id: int) -> list[Event]:
    """Eventos de una oferta en orden cronológico (y de registro, a igual fecha)."""
    stmt = select(Event).where(Event.job_id == job_id).order_by(Event.occurred_at, Event.id)
    return list(session.scalars(stmt))


def save_projection(session: Session, job_id: int, state: ProjectionState) -> Application:
    app = session.get(Application, job_id)
    if app is None:
        app = Application(job_id=job_id)
        session.add(app)
    app.stage = state.stage.value
    app.channel = state.channel
    app.render_id = state.render_id
    app.applied_at = state.applied_at
    app.last_event_at = state.last_event_at
    return app


def rebuild_projection(session: Session, job_id: int | None = None) -> int:
    """Recalcula `applications` desde cero para una oferta o para todas. Devuelve cuántas."""
    if job_id is None:
        job_ids: Sequence[int] = session.scalars(select(Event.job_id).distinct()).all()
        session.execute(delete(Application).where(Application.job_id.not_in(job_ids)))
    else:
        job_ids = [job_id]

    rebuilt = 0
    for jid in job_ids:
        events = job_events(session, jid)
        if not events:
            session.execute(delete(Application).where(Application.job_id == jid))
            continue
        save_projection(session, jid, project(events))
        rebuilt += 1
    session.flush()
    return rebuilt
