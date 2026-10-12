"""Fase 17: plan de preparación y repaso de entrevistas, guardados en el hito.

Criterios: `save_interview_notes` guarda las notas en el hito y aparecen en la ficha; nada de esto
registra eventos, cambia el estado del hito ni toca el perfil.
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Event, Job, Milestone, ProfileVersion
from app.schemas.interviews import InterviewPlanInput
from app.services import events, interviews, process
from app.services.interviews import InterviewNotAllowedError, InterviewNotesInput
from app.services.process import MilestoneNotFoundError
from tests.replies_support import APPLIED, NOW, add_applied_job

TODAY = date(2026, 10, 11)  # NOW en Europe/Madrid
NOTES = InterviewNotesInput(notes="Preguntaron por dbt.", next_steps="Prueba técnica.")


def _events(session: Session, job_id: int) -> int:
    return session.scalar(select(func.count()).select_from(Event).where(Event.job_id == job_id))


def _milestone(session: Session, job: Job, starts_at: datetime, kind: str = "interview") -> int:
    return process.create_milestone(
        session,
        job.id,
        process.MilestoneCreate(
            kind=kind, title=f"{kind} {starts_at:%d}", starts_at=starts_at, occurred_at=APPLIED
        ),  # type: ignore[arg-type]
    ).id


def _plan(*days: date, dossier: str | None = "1-bretema.md") -> InterviewPlanInput:
    return InterviewPlanInput.model_validate(
        {
            "dossier": dossier,
            "blocks": [{"date": d, "minutes": 45, "topic": f"Bloque {d}"} for d in days],
        }
    )


# --- get_interviews -------------------------------------------------------------------------


def test_get_interviews_lists_only_interviews_with_contacts_and_offer(session: Session) -> None:
    job = add_applied_job(session, "Brétema Analytics")
    second = _milestone(session, job, NOW + timedelta(days=5))
    first = _milestone(session, job, NOW - timedelta(days=2))
    _milestone(session, job, NOW + timedelta(days=1), kind="test")
    process.add_contact(
        session, job.id, process.ContactFields(name="Uxía Rey", role="Talento", email="u@x.es")
    )

    view = interviews.get_interviews(session, job.id, now=NOW)

    assert [m.id for m in view.interviews] == [first, second]
    assert view.company == "Brétema Analytics" and view.stage == "in_process"
    assert view.today == TODAY and view.offer_received is False
    assert [c.model_dump() for c in view.contacts] == [{"name": "Uxía Rey", "role": "Talento"}]

    events.record(session, job.id, "offer_received", "user")
    assert interviews.get_interviews(session, job.id, now=NOW).offer_received is True


def test_get_interviews_unknown_job(session: Session) -> None:
    with pytest.raises(events.JobNotFoundError):
        interviews.get_interviews(session, 999)


# --- save_interview_plan --------------------------------------------------------------------


def test_plan_is_saved_sorted_in_the_milestone_without_events(session: Session) -> None:
    job = add_applied_job(session, "Néboa Data")
    milestone_id = _milestone(session, job, NOW + timedelta(days=3))
    before = _events(session, job.id)
    day = TODAY + timedelta(days=3)

    result = interviews.save_interview_plan(
        session, milestone_id, _plan(day, TODAY), agent_name="claude-code", now=NOW
    )

    assert result.blocks == 2 and result.replaced is False
    assert "90 minutos" in result.message
    saved = process.get_process(session, job.id, now=NOW).milestones[0].prep_plan
    assert saved is not None and saved.dossier == "1-bretema.md"
    assert [b.date for b in saved.blocks] == [TODAY, day]
    assert saved.agent_name == "claude-code"
    assert _events(session, job.id) == before
    assert process.get_milestone(session, milestone_id).status == "scheduled"

    again = interviews.save_interview_plan(session, milestone_id, _plan(TODAY), now=NOW)
    assert again.replaced is True
    replaced = process.get_milestone(session, milestone_id).prep_plan
    assert replaced is not None and len(replaced.blocks) == 1


@pytest.mark.parametrize("offset", [-1, 4])
def test_plan_blocks_must_fall_between_today_and_the_interview(
    session: Session, offset: int
) -> None:
    job = add_applied_job(session, "Lonxa Retail Tech")
    milestone_id = _milestone(session, job, NOW + timedelta(days=3))
    with pytest.raises(InterviewNotAllowedError, match="fuera de plazo"):
        interviews.save_interview_plan(
            session, milestone_id, _plan(TODAY, TODAY + timedelta(days=offset)), now=NOW
        )


def test_plan_only_for_upcoming_scheduled_interviews(session: Session) -> None:
    job = add_applied_job(session, "Castro Labs")
    test_id = _milestone(session, job, NOW + timedelta(days=2), kind="test")
    past_id = _milestone(session, job, NOW - timedelta(hours=1))
    done_id = _milestone(session, job, NOW + timedelta(days=2))
    process.set_milestone_status(session, done_id, process.MilestoneStatusChange(status="done"))

    with pytest.raises(InterviewNotAllowedError, match="no es una entrevista"):
        interviews.save_interview_plan(session, test_id, _plan(TODAY), now=NOW)
    for milestone_id in (past_id, done_id):
        with pytest.raises(InterviewNotAllowedError, match="programada"):
            interviews.save_interview_plan(session, milestone_id, _plan(TODAY), now=NOW)
    with pytest.raises(MilestoneNotFoundError):
        interviews.save_interview_plan(session, 999, _plan(TODAY), now=NOW)


def test_plan_rejected_when_the_process_is_closed(session: Session) -> None:
    job = add_applied_job(session, "Rías Software S.L.")
    milestone_id = _milestone(session, job, NOW + timedelta(days=2))
    events.record(session, job.id, "rejected", "user")
    with pytest.raises(InterviewNotAllowedError, match="cerrado"):
        interviews.save_interview_plan(session, milestone_id, _plan(TODAY), now=NOW)


@pytest.mark.parametrize(
    "changes",
    [
        {"dossier": "../perfil.md"},
        {"dossier": "entrevistas/1.md"},
        {"dossier": "dosier.txt"},
        {"blocks": []},
        {"blocks": [{"date": "2026-10-11", "minutes": 10, "topic": "x"}]},
        {"blocks": [{"date": "2026-10-11", "minutes": 45, "topic": ""}]},
        {"extra": 1},
    ],
)
def test_plan_input_validation(changes: dict[str, object]) -> None:
    data = {"dossier": "1-a.md", "blocks": [{"date": "2026-10-11", "minutes": 45, "topic": "x"}]}
    with pytest.raises(ValidationError):
        InterviewPlanInput.model_validate({**data, **changes})


# --- save_interview_notes -------------------------------------------------------------------


def test_notes_are_saved_in_the_milestone_and_shown_in_the_process(session: Session) -> None:
    job = add_applied_job(session, "Brétema Analytics")
    milestone_id = _milestone(session, job, NOW - timedelta(days=1))
    process.set_milestone_status(
        session, milestone_id, process.MilestoneStatusChange(status="done")
    )
    before = _events(session, job.id)

    result = interviews.save_interview_notes(session, milestone_id, NOTES, now=NOW)

    assert result.replaced is False and result.milestone_status == "done"
    assert "marque como hecha" not in result.message
    shown = process.get_process(session, job.id, now=NOW).milestones[0]
    assert shown.debrief_notes == "Preguntaron por dbt."
    assert shown.next_steps == "Prueba técnica."
    assert shown.debriefed_at == NOW
    assert _events(session, job.id) == before

    again = interviews.save_interview_notes(
        session, milestone_id, InterviewNotesInput(notes="Otra versión."), now=NOW
    )
    assert again.replaced is True
    assert process.get_milestone(session, milestone_id).next_steps is None


def test_notes_keep_a_scheduled_interview_scheduled_and_say_so(session: Session) -> None:
    job = add_applied_job(session, "Néboa Data")
    milestone_id = _milestone(session, job, NOW - timedelta(hours=2))

    result = interviews.save_interview_notes(session, milestone_id, NOTES, now=NOW)

    assert result.milestone_status == "scheduled"
    assert "marque como hecha" in result.message
    assert process.get_milestone(session, milestone_id).status == "scheduled"


def test_notes_rejected_for_future_cancelled_or_other_milestones(session: Session) -> None:
    job = add_applied_job(session, "Lonxa Retail Tech")
    future = _milestone(session, job, NOW + timedelta(hours=1))
    cancelled = _milestone(session, job, NOW - timedelta(days=1))
    process.set_milestone_status(
        session, cancelled, process.MilestoneStatusChange(status="cancelled")
    )
    test_id = _milestone(session, job, NOW - timedelta(days=1), kind="test")

    with pytest.raises(InterviewNotAllowedError, match="aún no ha empezado"):
        interviews.save_interview_notes(session, future, NOTES, now=NOW)
    with pytest.raises(InterviewNotAllowedError, match="cancelada"):
        interviews.save_interview_notes(session, cancelled, NOTES, now=NOW)
    with pytest.raises(InterviewNotAllowedError, match="no es una entrevista"):
        interviews.save_interview_notes(session, test_id, NOTES, now=NOW)


def test_nothing_here_touches_the_profile(session: Session) -> None:
    """Las historias nuevas de un repaso solo entran con `update-profile`."""
    job = add_applied_job(session, "Castro Labs")
    milestone_id = _milestone(session, job, NOW - timedelta(days=1))
    versions = session.scalar(select(func.count()).select_from(ProfileVersion))

    interviews.save_interview_notes(
        session,
        milestone_id,
        InterviewNotesInput(notes="Conté cómo migré el ETL a Airflow y bajó un 40 % el coste."),
        now=NOW,
    )

    assert session.scalar(select(func.count()).select_from(ProfileVersion)) == versions


# --- Fechas: todo el día y zona horaria (revisión) ------------------------------------------


def test_all_day_interview_is_prepared_that_day_and_debriefed_after(session: Session) -> None:
    """Un hito de todo el día se guarda a las 00:00 de Madrid: no cuenta como empezado hasta que
    acaba ese día."""
    job = add_applied_job(session, "Brétema Analytics")
    milestone_id = process.create_milestone(
        session,
        job.id,
        process.MilestoneCreate(kind="interview", starts_at=NOW, all_day=True, occurred_at=APPLIED),
    ).id
    row = session.get(Milestone, milestone_id)
    assert row is not None
    evening = datetime(2026, 10, 11, 21, 0, tzinfo=UTC)  # 23:00 en Madrid, aún ese día
    next_day = datetime(2026, 10, 11, 22, 30, tzinfo=UTC)  # 00:30 en Madrid del día siguiente

    assert not interviews.has_started(row, evening) and interviews.has_started(row, next_day)
    plan = interviews.save_interview_plan(session, milestone_id, _plan(TODAY), now=evening)
    assert plan.blocks == 1
    with pytest.raises(InterviewNotAllowedError, match="aún no ha empezado"):
        interviews.save_interview_notes(session, milestone_id, NOTES, now=evening)
    assert interviews.save_interview_notes(session, milestone_id, NOTES, now=next_day).ok


def test_plan_dates_use_madrid_not_utc(session: Session) -> None:
    """A las 22:30 UTC ya es el día siguiente en Madrid: ese es «hoy» para el plan."""
    job = add_applied_job(session, "Néboa Data")
    late = datetime(2026, 10, 11, 22, 30, tzinfo=UTC)  # 00:30 del 12 en Madrid
    milestone_id = _milestone(session, job, datetime(2026, 10, 13, 8, 0, tzinfo=UTC))

    assert interviews.get_interviews(session, job.id, now=late).today == date(2026, 10, 12)
    with pytest.raises(InterviewNotAllowedError, match="fuera de plazo"):
        interviews.save_interview_plan(session, milestone_id, _plan(date(2026, 10, 11)), now=late)
    saved = interviews.save_interview_plan(
        session, milestone_id, _plan(date(2026, 10, 12), date(2026, 10, 13)), now=late
    )
    assert saved.blocks == 2
