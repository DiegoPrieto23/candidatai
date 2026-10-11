"""Fase 15.3: borradores de seguimiento y agradecimiento, tope de seguimientos y `thanks_due`.

Criterio de aceptación: nada se envía (no hay código que envíe: solo se guarda texto) y el tercer
seguimiento se rechaza.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import Event, Job, MessageDraft
from app.services import drafts, events, process, tracking
from app.services.drafts import DraftNotAllowedError, MessageDraftInput
from tests.replies_support import APPLIED, NOW, add_applied_job

JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}
FOLLOWUP = MessageDraftInput(kind="followup", subject="Mi candidatura", body="Hola: ¿novedades?")
THANKS = MessageDraftInput(kind="thank_you", subject="Gracias", body="Gracias por la entrevista.")


def _events(session: Session, job_id: int) -> int:
    return session.scalar(select(func.count()).select_from(Event).where(Event.job_id == job_id))


def _followup_sent(session: Session, job: Job, when: datetime) -> None:
    events.record(session, job.id, "followup_sent", "user", occurred_at=when)


def _interview_done(session: Session, job: Job, when: datetime) -> int:
    created = process.create_milestone(
        session,
        job.id,
        process.MilestoneCreate(
            kind="interview", starts_at=when, occurred_at=APPLIED + timedelta(hours=1)
        ),
    )
    process.set_milestone_status(
        session, created.id, process.MilestoneStatusChange(status="done", occurred_at=when)
    )
    return created.id


# --- Guardar borradores ---------------------------------------------------------------------


def test_followup_draft_is_saved_and_replaced_without_events(session: Session) -> None:
    job = add_applied_job(session, "Brétema Analytics")
    before = _events(session, job.id)

    first = drafts.save_message_draft(session, job.id, FOLLOWUP, agent_name="claude-code")
    again = drafts.save_message_draft(
        session, job.id, FOLLOWUP.model_copy(update={"body": "Otra versión."})
    )

    assert first.replaced is False and again.replaced is True
    assert again.draft_id == first.draft_id
    listed = drafts.list_drafts(session, job.id)
    assert [d.body for d in listed.drafts] == ["Otra versión."]
    assert listed.followups_sent == 0 and listed.max_followups == 2
    # Guardar un borrador no envía ni registra nada.
    assert _events(session, job.id) == before


def test_third_followup_is_rejected(session: Session) -> None:
    job = add_applied_job(session, "Néboa Data")
    _followup_sent(session, job, APPLIED + timedelta(days=10))
    drafts.save_message_draft(session, job.id, FOLLOWUP)  # el segundo, aún se puede
    _followup_sent(session, job, APPLIED + timedelta(days=20))

    with pytest.raises(DraftNotAllowedError, match="máximo 2"):
        drafts.save_message_draft(session, job.id, FOLLOWUP)


def test_marking_a_draft_sent_respects_the_cap(session: Session) -> None:
    """Si el usuario registró seguimientos a mano entretanto, el borrador ya no suma un tercero."""
    job = add_applied_job(session, "Néboa Data")
    draft = drafts.save_message_draft(session, job.id, FOLLOWUP)
    _followup_sent(session, job, APPLIED + timedelta(days=10))
    _followup_sent(session, job, APPLIED + timedelta(days=20))
    with pytest.raises(DraftNotAllowedError, match="descarta este borrador"):
        drafts.mark_draft_sent(session, draft.draft_id)


def test_capped_application_has_no_followup_notice(session: Session) -> None:
    job = add_applied_job(session, "Castro Labs", applied_at=NOW - timedelta(days=35))
    for days in (30, 20):
        _followup_sent(session, job, NOW - timedelta(days=days))
    assert process.get_process(session, job.id, now=NOW).followup.due is False  # type: ignore[union-attr]
    board = tracking.get_board(session, now=NOW)
    card = next(c for col in board.columns for c in col.cards if c.job_id == job.id)
    assert card.followup_due is False and card.days_waiting == 20


def test_drafts_only_for_open_sent_applications(session: Session) -> None:
    job = add_applied_job(session, "Castro Labs")
    with pytest.raises(ValueError, match="solo va en un agradecimiento"):
        drafts.save_message_draft(session, job.id, FOLLOWUP.model_copy(update={"milestone_id": 1}))
    events.record(session, job.id, "rejected", "user")
    with pytest.raises(DraftNotAllowedError, match="enviada y abierta"):
        drafts.save_message_draft(session, job.id, FOLLOWUP)
    with pytest.raises(events.JobNotFoundError):
        drafts.save_message_draft(session, 999, FOLLOWUP)


def test_thank_you_needs_an_interview_done(session: Session) -> None:
    job = add_applied_job(session, "Rías Software S.L.")
    other = add_applied_job(session, "Lonxa Retail Tech")
    with pytest.raises(DraftNotAllowedError, match="ninguna entrevista hecha"):
        drafts.save_message_draft(session, job.id, THANKS)

    scheduled = process.create_milestone(
        session, job.id, process.MilestoneCreate(kind="interview", starts_at=NOW)
    )
    with pytest.raises(DraftNotAllowedError, match="márcala como hecha"):
        drafts.save_message_draft(
            session, job.id, THANKS.model_copy(update={"milestone_id": scheduled.id})
        )
    done = _interview_done(session, job, NOW - timedelta(days=1))
    with pytest.raises(ValueError, match="no es de la oferta"):
        drafts.save_message_draft(
            session, other.id, THANKS.model_copy(update={"milestone_id": done})
        )

    saved = drafts.save_message_draft(session, job.id, THANKS)  # la última entrevista hecha
    assert saved.milestone_id == done and saved.kind == "thank_you"
    drafts.mark_draft_sent(session, saved.draft_id)
    with pytest.raises(DraftNotAllowedError, match="Ya enviaste el agradecimiento"):
        drafts.save_message_draft(session, job.id, THANKS)


# --- Seguimientos y agradecimientos pendientes ----------------------------------------------


def test_followups_due_carry_count_contacts_and_draft(session: Session) -> None:
    long_ago = NOW - timedelta(days=40)
    job = add_applied_job(session, "Brétema Analytics", applied_at=long_ago)
    capped = add_applied_job(session, "Néboa Data", applied_at=long_ago)
    process.add_contact(
        session,
        job.id,
        process.ContactFields(name="Laura Pazos", role="Talento", email="laura@bretema.example"),
    )
    _followup_sent(session, job, NOW - timedelta(days=12))
    draft = drafts.save_message_draft(session, job.id, FOLLOWUP)
    for days in (25, 12):
        _followup_sent(session, capped, NOW - timedelta(days=days))

    due = tracking.list_followups_due(session, now=NOW)

    assert [f.job_id for f in due.followups] == [job.id]  # la del tope no sale
    item = due.followups[0]
    assert item.followups_sent == 1 and item.draft_id == draft.draft_id
    assert item.contacts == ["Laura Pazos (Talento)"]  # sin el correo
    assert "laura@" not in due.model_dump_json()


def test_thanks_due_lists_recent_interviews_until_thanked(session: Session) -> None:
    job = add_applied_job(session, "Rías Software S.L.")
    old = add_applied_job(session, "Castro Labs")
    recent = _interview_done(session, job, NOW - timedelta(days=1))
    _interview_done(session, old, NOW - timedelta(days=5))  # fuera de los 3 días

    due = tracking.list_followups_due(session, now=NOW)
    assert [(t.job_id, t.milestone_id) for t in due.thanks_due] == [(job.id, recent)]
    assert due.thank_you_days == 3 and due.thanks_due[0].draft_id is None

    saved = drafts.save_message_draft(session, job.id, THANKS)
    assert tracking.list_followups_due(session, now=NOW).thanks_due[0].draft_id == saved.draft_id
    drafts.mark_draft_sent(session, saved.draft_id)
    assert tracking.list_followups_due(session, now=NOW).thanks_due == []


# --- API: marcar y descartar, solo desde la UI ----------------------------------------------


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


def _seed_draft() -> tuple[int, int]:
    with session_scope() as session:
        job = add_applied_job(session, "Brétema Analytics")
        draft = drafts.save_message_draft(session, job.id, FOLLOWUP)
        return job.id, draft.draft_id


def test_mark_sent_records_followup_sent(client: TestClient) -> None:
    job_id, draft_id = _seed_draft()
    listed = client.get(f"/jobs/{job_id}/drafts").json()
    assert [d["id"] for d in listed["drafts"]] == [draft_id] and listed["followups_sent"] == 0

    outside = client.post(
        f"/drafts/{draft_id}/sent",
        json={},
        headers={"Origin": "https://evil.example", "Content-Type": "application/json"},
    )
    assert outside.status_code == 403

    response = client.post(f"/drafts/{draft_id}/sent", json={}, headers=JSON)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "sent"
    with session_scope() as session:
        event = session.get(Event, response.json()["event_id"])
        assert event is not None and event.type == "followup_sent"
        assert event.actor == "user" and event.payload == {"draft_id": draft_id}
    after = client.get(f"/jobs/{job_id}/drafts").json()
    assert after["drafts"] == [] and after["followups_sent"] == 1
    again = client.post(f"/drafts/{draft_id}/sent", json={}, headers=JSON)
    assert again.status_code == 403 and again.json()["error"]["type"] == "not_allowed"


def test_discard_records_nothing(client: TestClient) -> None:
    job_id, draft_id = _seed_draft()
    assert client.post(f"/drafts/{draft_id}/discard", content="{}").status_code == 403
    response = client.post(f"/drafts/{draft_id}/discard", json={}, headers=JSON)
    assert response.status_code == 200 and response.json()["event_id"] is None
    with session_scope() as session:
        assert session.get(MessageDraft, draft_id).status == "discarded"  # type: ignore[union-attr]
        sent = session.scalars(
            select(Event).where(Event.job_id == job_id, Event.type == "followup_sent")
        ).all()
        assert sent == []
    assert client.post("/drafts/999/discard", json={}, headers=JSON).status_code == 404
