"""Registro de eventos y proyección persistida en `applications`."""

import random
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Event, Job
from app.services import events
from app.services.events import (
    JobNotFoundError,
    UnknownActorError,
    UnknownEventTypeError,
    get_timeline,
    record,
)
from app.services.pipeline import InvalidTransitionError, Stage, rebuild_projection
from app.services.status import get_status

T0 = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
MakeJob = Callable[..., Job]


def _snapshot(session: Session) -> list[tuple[object, ...]]:
    rows = session.scalars(select(Application).order_by(Application.job_id))
    return [
        (a.job_id, a.stage, a.channel, a.document_id, a.applied_at, a.last_event_at) for a in rows
    ]


def test_record_creates_event_and_projection(session: Session, make_job: MakeJob) -> None:
    job = make_job()
    event = record(session, job.id, "found", "system", occurred_at=T0)
    assert event.id is not None
    assert event.payload == {}
    app = session.get(Application, job.id)
    assert app is not None
    assert app.stage == Stage.PENDING_EXTRACTION
    assert app.last_event_at == T0

    record(session, job.id, "extracted", "agent", {"schema_version": 1}, agent_name="codex")
    assert app.stage == Stage.PENDING_TRIAGE
    stored = session.scalars(select(Event).where(Event.type == "extracted")).one()
    assert stored.agent_name == "codex"
    assert stored.recorded_at.tzinfo is UTC


def test_invalid_transition_writes_nothing(session: Session, make_job: MakeJob) -> None:
    job = make_job()
    record(session, job.id, "found", "system")
    with pytest.raises(InvalidTransitionError, match="«applied» no es válido"):
        record(session, job.id, "applied", "user")
    session.flush()
    assert [e.type for e in session.scalars(select(Event))] == ["found"]
    app = session.get(Application, job.id)
    assert app is not None and app.stage == Stage.PENDING_EXTRACTION


def test_record_validates_inputs(session: Session, make_job: MakeJob) -> None:
    job = make_job()
    with pytest.raises(UnknownEventTypeError, match="Tipos válidos: found"):
        record(session, job.id, "teleported", "system")
    with pytest.raises(UnknownActorError, match="Válidos: system, user, agent"):
        record(session, job.id, "found", "robot")
    with pytest.raises(JobNotFoundError, match="No existe la oferta 999"):
        record(session, 999, "found", "system")
    with pytest.raises(ValueError, match="zona horaria"):
        record(session, job.id, "found", "system", occurred_at=datetime(2026, 9, 1))


def test_backdated_event_is_placed_in_order(session: Session, make_job: MakeJob) -> None:
    job = make_job()
    record(session, job.id, "found", "system", occurred_at=T0)
    record(session, job.id, "extracted", "agent", occurred_at=T0 + timedelta(hours=1))
    record(session, job.id, "approved", "user", occurred_at=T0 + timedelta(hours=3))
    # Anotado después, pero ocurrió antes de aprobar: no cambia la etapa ni `last_event_at`.
    record(session, job.id, "note", "user", {"text": "llamada"}, T0 + timedelta(hours=2))
    app = session.get(Application, job.id)
    assert app is not None
    assert app.stage == Stage.APPROVED
    assert app.last_event_at == T0 + timedelta(hours=3)

    # Un evento pasado que rompería la secuencia se rechaza.
    with pytest.raises(InvalidTransitionError):
        record(session, job.id, "discarded", "user", occurred_at=T0 + timedelta(minutes=30))


# Guiones de eventos (tipo, payload) que recorren el catálogo.
SCRIPTS: list[list[tuple[str, dict[str, object] | None]]] = [
    [("found", None), ("duplicate_detected", {"duplicate_of": 1})],
    [("found", None), ("extraction_failed", None), ("extracted", None), ("scored", None)],
    [("found", None), ("extracted", None), ("hard_filter_failed", None), ("reopened", None)],
    [
        ("found", None),
        ("injection_suspected", {"flags": ["hidden_text"]}),
        ("extracted", None),
        ("fit_assessed", None),
        ("approved", None),
        ("cv_generated", None),
        ("cv_rejected", None),
        ("cv_verified", {"passed": True}),
        ("application_prepared", None),
        ("applied", {"channel": "ats_form"}),
        ("followup_sent", None),
        ("interview_scheduled", None),
        ("interview_done", None),
        ("offer_received", None),
        ("accepted", None),
    ],
    [
        ("found", None),
        ("extracted", None),
        ("applied_manually", {"channel": "email"}),
        ("test_assigned", None),
        ("rejected", None),
        ("note", {"text": "feedback"}),
    ],
    [("found", None), ("extracted", None), ("approved", None), ("withdrawn", None)],
    [("found", None), ("expired", None), ("reopened", None), ("discarded", None)],
]


def test_rebuild_matches_incremental_projection(session: Session, make_job: MakeJob) -> None:
    rng = random.Random(42)
    jobs = [make_job() for _ in SCRIPTS]
    # Intercala los eventos de todas las ofertas, con algunas fechas repetidas o pasadas.
    cursors = [0] * len(SCRIPTS)
    clock = T0
    while any(c < len(s) for c, s in zip(cursors, SCRIPTS, strict=True)):
        i = rng.choice([i for i, s in enumerate(SCRIPTS) if cursors[i] < len(s)])
        event_type, payload = SCRIPTS[i][cursors[i]]
        clock += timedelta(minutes=rng.choice([0, 1, 5]))
        record(session, jobs[i].id, event_type, "user", payload, occurred_at=clock)
        cursors[i] += 1

    incremental = _snapshot(session)
    session.query(Application).delete()
    session.flush()
    assert _snapshot(session) == []

    assert rebuild_projection(session) == len(SCRIPTS)
    assert _snapshot(session) == incremental
    stages = [row[1] for row in incremental]
    assert stages == ["closed", "pending_triage", "pending_triage", "closed"] + ["closed"] * 3


def test_rebuild_single_job_and_cleans_orphans(session: Session, make_job: MakeJob) -> None:
    job, other = make_job(), make_job()
    record(session, job.id, "found", "system")
    app = session.get(Application, job.id)
    assert app is not None
    app.stage = "approved"  # proyección corrompida a mano
    assert rebuild_projection(session, job.id) == 1
    assert app.stage == Stage.PENDING_EXTRACTION

    # Una fila de proyección sin eventos desaparece al recalcular.
    session.add(Application(job_id=other.id, stage="approved", last_event_at=T0))
    session.flush()
    assert rebuild_projection(session, other.id) == 0
    assert session.get(Application, other.id) is None
    session.add(Application(job_id=other.id, stage="approved", last_event_at=T0))
    session.flush()
    assert rebuild_projection(session) == 1
    assert session.get(Application, other.id) is None


def test_get_timeline(session: Session, make_job: MakeJob) -> None:
    job = make_job()
    assert get_timeline(session, job.id).stage is None
    record(session, job.id, "found", "system", occurred_at=T0)
    record(session, job.id, "extracted", "agent", occurred_at=T0 + timedelta(hours=1))
    timeline = get_timeline(session, job.id)
    assert timeline.stage == Stage.PENDING_TRIAGE
    assert [e.type for e in timeline.events] == ["found", "extracted"]
    assert timeline.events[0].occurred_at == T0
    with pytest.raises(JobNotFoundError):
        get_timeline(session, 999)


def test_get_status_counts_every_stage(session: Session, make_job: MakeJob) -> None:
    empty = get_status(session)
    assert empty.total == 0
    assert set(empty.by_stage) == set(Stage)

    a, b, c = make_job(), make_job(), make_job()
    for job in (a, b, c):
        record(session, job.id, "found", "system")
    record(session, b.id, "extracted", "agent")
    record(session, c.id, "discarded", "user", {"reason": "sin encaje"})
    status = get_status(session)
    assert status.total == 3
    assert status.by_stage[Stage.PENDING_EXTRACTION] == 1
    assert status.by_stage[Stage.PENDING_TRIAGE] == 1
    assert status.by_stage[Stage.CLOSED] == 1
    assert status.by_stage[Stage.APPROVED] == 0


def test_events_module_exposes_record() -> None:
    # La regla de AGENTS.md cita `services.events.record()`: la firma debe existir tal cual.
    assert events.record is record
