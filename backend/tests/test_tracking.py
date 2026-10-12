"""Fase 10.1: hitos, contactos, ficha de proceso, seguimientos, próximos, kanban y calendario."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, Job, JobExtraction, Milestone
from app.services import calendar_ics, events, process, tracking
from app.services.pipeline import InvalidTransitionError, Stage

# Lunes, 11:00 en Madrid. En el pasado: los eventos sin fecha (ahora) van después.
NOW = datetime(2026, 9, 21, 9, 0, tzinfo=UTC)


def _at(days: float, hours: float = 0) -> datetime:
    return NOW + timedelta(days=days, hours=hours)


@pytest.fixture
def job_at(session: Session, make_job: Callable[..., Job]) -> Callable[..., Job]:
    """Crea una oferta y la lleva a la etapa pedida con eventos fechados en el pasado."""

    def _make(stage: Stage, applied_days_ago: int = 1, title: str = "Data Engineer") -> Job:
        job = make_job(title)
        start = NOW - timedelta(days=applied_days_ago + 5)
        steps = ["found", "extracted", "approved"]
        if stage in (Stage.APPLIED, Stage.IN_PROCESS, Stage.CLOSED):
            steps.append("applied_manually")
        for i, step in enumerate(steps):
            when = start + timedelta(hours=i)
            if step == "applied_manually":
                when = NOW - timedelta(days=applied_days_ago)
            events.record(session, job.id, step, "user", occurred_at=when)
        if stage == Stage.IN_PROCESS:
            events.record(session, job.id, "reply_received", "user", occurred_at=_at(-0.5))
        if stage == Stage.CLOSED:
            events.record(session, job.id, "rejected", "user", occurred_at=_at(-0.5))
        if stage == Stage.PENDING_TRIAGE:
            # Deshace la aprobación: la oferta queda en triaje.
            session.execute(
                Event.__table__.delete().where(Event.job_id == job.id, Event.type == "approved")
            )
            from app.services.pipeline import rebuild_projection

            rebuild_projection(session, job.id)
        session.flush()
        return job

    return _make


def interview(**changes: object) -> process.MilestoneCreate:
    data: dict[str, object] = {"kind": "interview", "starts_at": _at(2)} | changes
    return process.MilestoneCreate.model_validate(data)


# --- Hitos ----------------------------------------------------------------------------------


def test_interview_moves_applied_to_in_process(session: Session, job_at) -> None:
    job = job_at(Stage.APPLIED)
    out = process.create_milestone(session, job.id, interview(location="Meet"))
    assert out.title == "Entrevista"
    assert events.current_stage(session, job.id) == Stage.IN_PROCESS
    event = session.get(Event, out.event_id)
    assert event is not None and event.type == "interview_scheduled"
    assert event.payload["milestone_id"] == out.id


def test_interview_before_applying_is_rejected_and_not_saved(session: Session, job_at) -> None:
    job = job_at(Stage.APPROVED)
    with pytest.raises(InvalidTransitionError):
        process.create_milestone(session, job.id, interview())
    assert session.scalars(select(Milestone)).all() == []


def test_deadline_records_no_event_and_all_day_starts_at_local_midnight(
    session: Session, job_at
) -> None:
    job = job_at(Stage.APPROVED)
    before = len(events.get_timeline(session, job.id).events)
    out = process.create_milestone(
        session,
        job.id,
        process.MilestoneCreate(kind="deadline", starts_at=_at(3, 10), all_day=True),
    )
    assert out.event_id is None
    assert len(events.get_timeline(session, job.id).events) == before
    local = out.starts_at.astimezone(process.local_zone())
    assert (local.hour, local.minute, local.date()) == (0, 0, date(2026, 9, 24))


def test_reschedule_and_cancel_leave_notes(session: Session, job_at) -> None:
    job = job_at(Stage.APPLIED)
    out = process.create_milestone(session, job.id, interview())
    moved = process.update_milestone(
        session, out.id, process.MilestoneFields(starts_at=_at(4), title="Técnica")
    )
    assert moved.title == "Técnica"
    cancelled = process.set_milestone_status(
        session, out.id, process.MilestoneStatusChange(status="cancelled", note="Lo aplazan")
    )
    assert cancelled.status == "cancelled"
    notes = [
        e.payload["note"] for e in events.get_timeline(session, job.id).events if e.type == "note"
    ]
    assert notes[0].startswith("Técnica reprogramada para el 25/09/2026")
    assert notes[1].endswith("cancelada. Lo aplazan")
    row = session.get(Milestone, out.id)
    assert row is not None and row.sequence == 2
    with pytest.raises(ValueError, match="crea otro"):
        process.set_milestone_status(session, out.id, process.MilestoneStatusChange(status="done"))


def test_interview_done_records_event(session: Session, job_at) -> None:
    job = job_at(Stage.APPLIED)
    out = process.create_milestone(session, job.id, interview(starts_at=_at(-0.1)))
    process.set_milestone_status(session, out.id, process.MilestoneStatusChange(status="done"))
    types = [e.type for e in events.get_timeline(session, job.id).events]
    assert types[-1] == "interview_done"


def test_milestone_end_must_follow_start() -> None:
    with pytest.raises(ValueError, match="posterior"):
        interview(ends_at=_at(1))


# --- Contactos y ficha ----------------------------------------------------------------------


def test_contacts_and_process_view(session: Session, job_at) -> None:
    job = job_at(Stage.APPLIED, applied_days_ago=12)
    contact = process.add_contact(
        session, job.id, process.ContactFields(name=" Ana ", role="Recruiter", email="")
    )
    assert contact.name == "Ana" and contact.email is None
    process.update_contact(
        session, contact.id, process.ContactFields(name="Ana", phone="600000000")
    )
    other = process.add_contact(session, job.id, process.ContactFields(name="Bea"))
    process.delete_contact(session, other.id)
    events.add_user_event(session, job.id, "note", note="Llamar el lunes")

    view = process.get_process(session, job.id, now=NOW)
    assert view.stage == Stage.APPLIED
    assert [c.name for c in view.contacts] == ["Ana"]
    assert view.contacts[0].phone == "600000000"
    assert [n.text for n in view.notes] == ["Llamar el lunes"]
    assert view.followup is not None
    assert (view.followup.due, view.followup.days_waiting) == (True, 12)
    assert view.documents.cv_render_id is None and not view.documents.cv_sent
    with pytest.raises(process.ContactNotFoundError):
        process.delete_contact(session, other.id)


def test_applied_by_user_keeps_channel(session: Session, job_at) -> None:
    job = job_at(Stage.APPROVED)
    events.add_user_event(session, job.id, "applied_manually", channel="email")
    view = process.get_process(session, job.id)
    assert view.channel == "email"
    with pytest.raises(ValueError, match="solo se usa"):
        events.add_user_event(session, job.id, "note", note="x", channel="email")
    with pytest.raises(ValueError, match="Canal desconocido"):
        events.add_user_event(session, job.id, "followup_sent", channel="fax")


# --- Seguimientos ---------------------------------------------------------------------------


def test_followups_due_from_last_followup(session: Session, job_at) -> None:
    old = job_at(Stage.APPLIED, applied_days_ago=15)
    recent = job_at(Stage.APPLIED, applied_days_ago=3)
    chased = job_at(Stage.APPLIED, applied_days_ago=20)
    events.record(session, chased.id, "followup_sent", "user", occurred_at=_at(-4))
    job_at(Stage.IN_PROCESS, applied_days_ago=30)  # ya respondieron

    due = tracking.list_followups_due(session, now=NOW)
    assert due.days_without_reply == 10
    assert [(f.job_id, f.days_waiting) for f in due.followups] == [(old.id, 15)]

    custom = tracking.list_followups_due(session, days_without_reply=3, now=NOW)
    assert [f.job_id for f in custom.followups] == [old.id, chased.id, recent.id]
    assert custom.followups[1].last_followup_at == _at(-4)


# --- Próximos -------------------------------------------------------------------------------


def _extraction(session: Session, job_id: int, deadline: date | None) -> None:
    from tests.agent_support import extraction

    data = extraction(application_deadline=deadline.isoformat() if deadline else None)
    session.add(JobExtraction(job_id=job_id, schema_version=1, data=data))
    session.flush()


def test_upcoming_window_and_application_deadlines(session: Session, job_at) -> None:
    applied = job_at(Stage.APPLIED)
    soon = process.create_milestone(session, applied.id, interview(starts_at=_at(1)))
    process.create_milestone(  # fuera de la ventana
        session, applied.id, process.MilestoneCreate(kind="other", starts_at=_at(9))
    )
    earlier_today = process.create_milestone(  # hoy a las 08:00 en Madrid: ya pasó, pero es hoy
        session, applied.id, process.MilestoneCreate(kind="test", starts_at=_at(0, -3))
    )
    approved = job_at(Stage.APPROVED)
    _extraction(session, approved.id, date(2026, 9, 23))
    late = job_at(Stage.APPROVED)
    _extraction(session, late.id, date(2026, 11, 30))
    closed = job_at(Stage.CLOSED)
    process.create_milestone(
        session, closed.id, process.MilestoneCreate(kind="other", starts_at=_at(1))
    )

    out = tracking.list_upcoming(session, days=7, now=NOW)
    kinds = [(i.kind, i.job_id) for i in out.items]
    assert kinds == [
        ("test", applied.id),
        ("interview", applied.id),
        ("application_deadline", approved.id),
    ]
    assert out.items[0].milestone_id == earlier_today.id
    assert out.items[1].milestone_id == soon.id
    assert out.items[2].all_day and out.items[2].milestone_id is None
    with pytest.raises(ValueError, match="`days`"):
        tracking.list_upcoming(session, days=0)


# --- Kanban ---------------------------------------------------------------------------------


def test_board_columns_and_moves(session: Session, job_at) -> None:
    approved = job_at(Stage.APPROVED)
    applied = job_at(Stage.APPLIED, applied_days_ago=11)
    in_process = job_at(Stage.IN_PROCESS)
    process.create_milestone(session, in_process.id, interview(starts_at=_at(3)))
    closed = job_at(Stage.CLOSED)
    triage = job_at(Stage.PENDING_TRIAGE)
    events.add_user_event(session, triage.id, "discarded", reason="skills")  # no se llegó a aprobar

    board = tracking.get_board(session, now=NOW)
    by_stage = {c.stage: [card.job_id for card in c.cards] for c in board.columns}
    assert by_stage == {
        Stage.APPROVED: [approved.id],
        Stage.CV_READY: [],
        Stage.APPLIED: [applied.id],
        Stage.IN_PROCESS: [in_process.id],
        Stage.CLOSED: [closed.id],
    }
    cards = {card.job_id: card for c in board.columns for card in c.cards}
    assert cards[applied.id].followup_due and cards[applied.id].days_waiting == 11
    assert cards[in_process.id].next_milestone is not None
    assert cards[closed.id].closed_by == "rejected"
    assert cards[closed.id].reopen_to == Stage.APPLIED

    moves = {m.event: m for m in board.moves}
    assert moves["applied"].from_stages == [Stage.CV_READY]
    assert moves["applied_manually"].from_stages == [Stage.APPROVED, Stage.CV_READY]
    assert moves["interview_scheduled"].from_stages == [Stage.APPLIED]
    assert moves["discarded"].to == Stage.CLOSED
    assert moves["reopened"].to is None
    assert "note" not in moves and "approved" not in moves


# --- Calendario -----------------------------------------------------------------------------


def test_escape_and_fold() -> None:
    assert calendar_ics.escape_text("a,b;c\\d\ne") == "a\\,b\\;c\\\\d\\ne"
    line = "DESCRIPTION:" + "ñ" * 80
    folded = calendar_ics.fold(line).split("\r\n")
    assert all(len(part.encode("utf-8")) <= 75 for part in folded)
    assert all(part.startswith(" ") for part in folded[1:])
    assert "".join(p[1:] if i else p for i, p in enumerate(folded)) == line


def test_milestone_ics_and_feed(session: Session, job_at) -> None:
    job = job_at(Stage.APPLIED)
    timed = process.create_milestone(
        session,
        job.id,
        interview(starts_at=datetime(2026, 9, 23, 8, 30, tzinfo=UTC), location="Calle 1, Vigo"),
    )
    body, filename = calendar_ics.milestone_ics(session, timed.id)
    assert filename == "entrevista-acme-1.ics"
    assert body.endswith("\r\n") and "\n" not in body.replace("\r\n", "")
    lines = body.split("\r\n")
    assert lines[0] == "BEGIN:VCALENDAR" and "END:VCALENDAR" in lines
    assert f"UID:milestone-{timed.id}@candidatai.local" in lines
    assert "DTSTART:20260923T083000Z" in lines and "DTEND:20260923T093000Z" in lines
    assert "LOCATION:Calle 1\\, Vigo" in lines
    assert "SUMMARY:Entrevista · Data Engineer (Acme 1)" in lines

    process.create_milestone(
        session,
        job.id,
        process.MilestoneCreate(kind="deadline", starts_at=_at(2), all_day=True, title="Docs"),
    )
    past = process.create_milestone(
        session, job.id, process.MilestoneCreate(kind="other", starts_at=_at(-3))
    )
    feed = calendar_ics.feed_ics(session, now=NOW)
    assert feed.count("BEGIN:VEVENT") == 2
    assert "DTSTART;VALUE=DATE:20260923" in feed and "DTEND;VALUE=DATE:20260924" in feed
    assert f"milestone-{past.id}@" not in feed

    path = calendar_ics.export_feed(session)
    assert path.read_bytes().startswith(b"BEGIN:VCALENDAR\r\n")
    with pytest.raises(process.MilestoneNotFoundError):
        calendar_ics.milestone_ics(session, 999)


def test_ics_filename_is_ascii(session: Session, job_at) -> None:
    job = job_at(Stage.APPLIED)
    from app.models import Company

    company = session.get(Company, job.company_id)
    assert company is not None
    company.name = "Łódź Tech 東京"
    out = process.create_milestone(session, job.id, interview())
    _, filename = calendar_ics.milestone_ics(session, out.id)
    assert filename == "entrevista-odz-tech.ics"
    filename.encode("latin-1")


def test_all_day_range_includes_last_day(session: Session, job_at) -> None:
    job = job_at(Stage.APPROVED)
    out = process.create_milestone(
        session,
        job.id,
        process.MilestoneCreate(
            kind="other", starts_at=_at(1), ends_at=_at(3), all_day=True, title="Viaje"
        ),
    )
    assert out.ends_at == process.start_of_local_day(date(2026, 9, 25))
    body, _ = calendar_ics.milestone_ics(session, out.id)
    assert "DTSTART;VALUE=DATE:20260922" in body and "DTEND;VALUE=DATE:20260925" in body


def test_upcoming_window_covers_whole_last_day(session: Session, job_at) -> None:
    job = job_at(Stage.APPLIED)
    late = process.create_milestone(  # dentro de 7 días a las 21:00 de Madrid
        session, job.id, process.MilestoneCreate(kind="other", starts_at=_at(7, 10))
    )
    process.create_milestone(  # el día siguiente: fuera
        session, job.id, process.MilestoneCreate(kind="other", starts_at=_at(8, -8))
    )
    out = tracking.list_upcoming(session, days=7, now=NOW)
    assert [i.milestone_id for i in out.items] == [late.id]
