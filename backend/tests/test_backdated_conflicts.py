"""Anotar con fecha pasada algo que choca con lo anotado después (p. ej. cerrar antes de un
seguimiento): qué lo impide, cómo se arregla y qué pasa al aceptarlo."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, Job, MessageDraft
from app.services import events
from app.services.events import LaterEventsConflictError, check_user_event, record
from app.services.pipeline import InvalidTransitionError, Stage, rebuild_projection

T0 = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)
MakeJob = Callable[..., Job]


def _in_process(session: Session, make_job: MakeJob) -> Job:
    """Una candidatura con entrevista hecha el día 3 y re-puntuada después."""
    job = make_job()
    record(session, job.id, "found", "system", occurred_at=T0)
    record(session, job.id, "extracted", "agent", occurred_at=T0 + timedelta(hours=1))
    record(session, job.id, "applied_manually", "user", occurred_at=T0 + timedelta(days=1))
    record(session, job.id, "interview_done", "user", occurred_at=T0 + timedelta(days=3))
    return job


def _types(session: Session, job_id: int) -> list[str]:
    return [e.type for e in events.job_events(session, job_id)]


def test_system_notices_after_a_backdated_close_do_not_block_it(
    session: Session, make_job: MakeJob
) -> None:
    job = _in_process(session, make_job)
    record(session, job.id, "scored", "system", occurred_at=T0 + timedelta(days=6))
    record(session, job.id, "fit_assessed", "agent", occurred_at=T0 + timedelta(days=6, hours=1))

    record(session, job.id, "rejected", "user", occurred_at=T0 + timedelta(days=5))

    assert events.current_stage(session, job.id) == Stage.CLOSED
    assert rebuild_projection(session, job.id) == 1  # la reproducción también los ignora
    assert events.current_stage(session, job.id) == Stage.CLOSED
    # Uno nuevo en una oferta cerrada sigue sin ser válido.
    with pytest.raises(InvalidTransitionError):
        record(session, job.id, "scored", "system")


def test_a_later_follow_up_blocks_the_close_with_a_clear_message(
    session: Session, make_job: MakeJob
) -> None:
    job = _in_process(session, make_job)
    record(session, job.id, "followup_sent", "user", occurred_at=T0 + timedelta(days=6))

    with pytest.raises(LaterEventsConflictError) as raised:
        record(session, job.id, "rejected", "user", occurred_at=T0 + timedelta(days=5))

    message = str(raised.value)
    assert "después hay anotado «followup_sent» (07/09/2026 11:00)" in message
    assert "Pon una fecha posterior al 07/09/2026 11:00" in message
    assert "allí te propone quitarlo" in message
    assert [c.type for c in raised.value.conflicts] == ["followup_sent"]
    assert events.current_stage(session, job.id) == Stage.IN_PROCESS
    assert "rejected" not in _types(session, job.id)


def test_check_proposes_removing_or_a_later_date(session: Session, make_job: MakeJob) -> None:
    job = _in_process(session, make_job)
    first = record(session, job.id, "followup_sent", "user", occurred_at=T0 + timedelta(days=6))
    second = record(
        session, job.id, "followup_sent", "user", occurred_at=T0 + timedelta(days=6, seconds=1)
    )

    found = check_user_event(session, job.id, "rejected", T0 + timedelta(days=5))

    assert [(c.id, c.type, c.removable) for c in found.conflicts] == [
        (first.id, "followup_sent", True),
        (second.id, "followup_sent", True),
    ]
    assert found.can_remove is True
    assert found.suggested_at == T0 + timedelta(days=6, minutes=1)
    # Sin nada después que choque, no hay nada que proponer.
    clean = check_user_event(session, job.id, "rejected", T0 + timedelta(days=7))
    assert clean.conflicts == [] and clean.can_remove is False and clean.suggested_at is None


def test_check_raises_when_the_event_does_not_fit_where_it_falls(
    session: Session, make_job: MakeJob
) -> None:
    job = _in_process(session, make_job)
    # Sin haber enviado la candidatura no hay entrevista hecha: no es por lo de después.
    with pytest.raises(InvalidTransitionError) as raised:
        check_user_event(session, job.id, "interview_done", T0 + timedelta(hours=2))
    assert not isinstance(raised.value, LaterEventsConflictError)


def test_accepting_removes_the_mistakes_and_closes_on_the_date_given(
    session: Session, make_job: MakeJob
) -> None:
    job = _in_process(session, make_job)
    followup = record(session, job.id, "followup_sent", "user", occurred_at=T0 + timedelta(days=6))
    draft = MessageDraft(
        job_id=job.id, kind="followup", body="Hola", status="sent", event_id=followup.id
    )
    session.add(draft)
    session.flush()
    when = T0 + timedelta(days=5)
    ids = [c.id for c in check_user_event(session, job.id, "rejected", when).conflicts]

    result = events.add_user_event(
        session, job.id, "rejected", occurred_at=when, remove_event_ids=ids
    )

    assert result.stage == Stage.CLOSED
    assert "followup_sent" not in _types(session, job.id)
    closed = session.scalars(select(Event).where(Event.type == "rejected")).one()
    assert closed.occurred_at.replace(tzinfo=UTC) == when
    session.refresh(draft)
    assert draft.event_id is None  # el borrador se queda, sin el enlace


def test_close_and_reopen_attempts_after_a_backdated_close_are_offered_for_removal(
    session: Session, make_job: MakeJob
) -> None:
    """Probar a cerrar y reabrir deja eventos que reabrirían la oferta: cerrar con fecha anterior
    los señala para quitarlos, en vez de dejarla abierta sin que nadie lo pida."""
    job = _in_process(session, make_job)
    record(session, job.id, "rejected", "user", occurred_at=T0 + timedelta(days=9))
    record(session, job.id, "reopened", "user", occurred_at=T0 + timedelta(days=9, minutes=1))
    when = T0 + timedelta(days=5)

    found = check_user_event(session, job.id, "rejected", when)

    assert [c.type for c in found.conflicts] == ["rejected", "reopened"]
    assert found.can_remove is True
    events.add_user_event(
        session,
        job.id,
        "rejected",
        occurred_at=when,
        remove_event_ids=[c.id for c in found.conflicts],
    )
    assert events.current_stage(session, job.id) == Stage.CLOSED
    assert _types(session, job.id)[-1] == "rejected"


def test_milestone_events_are_not_removable(session: Session, make_job: MakeJob) -> None:
    job = _in_process(session, make_job)
    record(
        session,
        job.id,
        "interview_scheduled",
        "user",
        {"milestone_id": 7},
        occurred_at=T0 + timedelta(days=6),
    )

    found = check_user_event(session, job.id, "rejected", T0 + timedelta(days=5))

    assert [(c.type, c.removable) for c in found.conflicts] == [("interview_scheduled", False)]
    assert found.can_remove is False
    assert found.suggested_at == T0 + timedelta(days=6, minutes=1)
    with pytest.raises(InvalidTransitionError, match="ha cambiado"):
        events.add_user_event(
            session,
            job.id,
            "rejected",
            occurred_at=T0 + timedelta(days=5),
            remove_event_ids=[c.id for c in found.conflicts],
        )
    assert "interview_scheduled" in _types(session, job.id)


def test_removal_must_match_what_was_shown(session: Session, make_job: MakeJob) -> None:
    job = _in_process(session, make_job)
    record(session, job.id, "followup_sent", "user", occurred_at=T0 + timedelta(days=6))
    note = record(session, job.id, "note", "user", {"note": "x"}, T0 + timedelta(days=7))

    with pytest.raises(InvalidTransitionError, match="ha cambiado"):
        events.add_user_event(
            session,
            job.id,
            "rejected",
            occurred_at=T0 + timedelta(days=5),
            remove_event_ids=[note.id],
        )
    assert _types(session, job.id)[-2:] == ["followup_sent", "note"]
    assert events.current_stage(session, job.id) == Stage.IN_PROCESS
