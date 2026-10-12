"""API del seguimiento (fase 10.1): kanban, ficha de proceso, hitos, contactos y calendario."""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.schemas.llm_io import JobExtraction
from app.services import extractions
from tests.agent_support import POSTING_TEXT, extraction


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


def _job(client: TestClient, company: str = "Acme Analytics") -> int:
    body = {"title": "Data Engineer", "company": company, "text": POSTING_TEXT}
    job_id = client.post("/jobs/text", json=body).json()["job_id"]
    with session_scope() as session:
        extractions.save_extraction(session, job_id, JobExtraction.model_validate(extraction()))
    assert client.post(f"/jobs/{job_id}/events", json={"type": "approved"}).status_code == 201
    return job_id


def _event(client: TestClient, job_id: int, **body: Any) -> dict[str, Any]:
    response = client.post(f"/jobs/{job_id}/events", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _soon(days: int = 2) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).replace(microsecond=0).isoformat()


def _stages(board: dict[str, Any]) -> dict[str, list[int]]:
    return {c["stage"]: [card["job_id"] for card in c["cards"]] for c in board["columns"]}


def test_board_moves_only_with_events(client: TestClient) -> None:
    job_id = _job(client)
    board = client.get("/board").json()
    assert _stages(board)["approved"] == [job_id]
    assert {m["event"] for m in board["moves"]} >= {"applied_manually", "discarded", "reopened"}

    # Enviar → `applied`; programar entrevista → `in_process`, con su hito.
    assert _event(client, job_id, type="applied_manually", channel="email")["stage"] == "applied"
    milestone = client.post(
        f"/jobs/{job_id}/milestones",
        json={"kind": "interview", "starts_at": _soon(), "location": "https://meet.example/x"},
    )
    assert milestone.status_code == 201, milestone.text
    board = client.get("/board").json()
    assert _stages(board)["in_process"] == [job_id]
    card = board["columns"][3]["cards"][0]
    assert card["next_milestone"]["milestone_id"] == milestone.json()["id"]

    # Cerrar y reabrir: vuelve a la etapa anterior al cierre.
    assert _event(client, job_id, type="rejected", note="Otro perfil")["stage"] == "closed"
    closed = client.get("/board").json()["columns"][4]
    assert closed["total"] == 1 and closed["cards"][0]["reopen_to"] == "in_process"
    assert closed["cards"][0]["closed_by"] == "rejected"
    assert _event(client, job_id, type="reopened")["stage"] == "in_process"


def test_milestone_errors(client: TestClient) -> None:
    job_id = _job(client)
    early = client.post(
        f"/jobs/{job_id}/milestones", json={"kind": "interview", "starts_at": _soon()}
    )
    assert early.status_code == 409
    assert early.json()["error"]["type"] == "invalid_transition"
    assert client.get(f"/jobs/{job_id}/process").json()["milestones"] == []

    naive = client.post(
        f"/jobs/{job_id}/milestones", json={"kind": "deadline", "starts_at": "2026-10-10T10:00:00"}
    )
    assert naive.status_code == 422
    missing = client.post("/milestones/99/status", json={"status": "done"})
    assert missing.status_code == 404 and missing.json()["error"]["type"] == "not_found"
    assert client.get("/milestones/99/ics").status_code == 404


def test_process_sheet_contacts_and_milestone_lifecycle(client: TestClient) -> None:
    job_id = _job(client)
    _event(client, job_id, type="applied_manually")
    created = client.post(
        f"/jobs/{job_id}/milestones",
        json={"kind": "test", "starts_at": _soon(3), "title": "Prueba de SQL"},
    ).json()
    edited = client.post(
        f"/milestones/{created['id']}",
        json={"starts_at": _soon(4), "title": "Prueba de SQL", "notes": "En casa"},
    )
    assert edited.status_code == 200 and edited.json()["notes"] == "En casa"
    done = client.post(f"/milestones/{created['id']}/status", json={"status": "done"})
    assert done.json()["status"] == "done"
    again = client.post(f"/milestones/{created['id']}/status", json={"status": "cancelled"})
    assert again.status_code == 422

    contact = client.post(
        f"/jobs/{job_id}/contacts", json={"name": "Ana", "role": "Recruiter"}
    ).json()
    client.post(f"/contacts/{contact['id']}", json={"name": "Ana López", "role": "Recruiter"})
    sheet = client.get(f"/jobs/{job_id}/process").json()
    assert [c["name"] for c in sheet["contacts"]] == ["Ana López"]
    assert sheet["stage"] == "in_process"
    assert any("reprogramada" in n["text"] for n in sheet["notes"])
    assert client.post(f"/contacts/{contact['id']}/delete").json() == {"ok": True}
    assert client.get(f"/jobs/{job_id}/process").json()["contacts"] == []


def test_followups_and_upcoming(client: TestClient) -> None:
    job_id = _job(client)
    _event(client, job_id, type="applied_manually")
    assert client.get("/followups").json() == {
        "days_without_reply": 10,
        "max_followups": 2,
        "followups": [],
        "thank_you_days": 3,
        "thanks_due": [],
    }
    client.post(
        f"/jobs/{job_id}/milestones",
        json={"kind": "deadline", "starts_at": _soon(1), "all_day": True},
    )
    upcoming = client.get("/upcoming", params={"days": 3}).json()
    assert [i["kind"] for i in upcoming["items"]] == ["deadline"]
    assert client.get("/upcoming", params={"days": 0}).status_code == 422


def test_calendar_endpoints(client: TestClient) -> None:
    job_id = _job(client, company="Beta, S.L.")
    _event(client, job_id, type="applied_manually")
    milestone = client.post(
        f"/jobs/{job_id}/milestones", json={"kind": "interview", "starts_at": _soon()}
    ).json()

    single = client.get(f"/milestones/{milestone['id']}/ics")
    assert single.status_code == 200
    assert single.headers["content-type"].startswith("text/calendar")
    assert 'filename="entrevista-beta-s-l.ics"' in single.headers["content-disposition"]
    assert "SUMMARY:Entrevista · Data Engineer (Beta\\, S.L.)" in single.text

    feed = client.get("/calendar.ics")
    assert feed.status_code == 200 and "content-disposition" not in feed.headers
    assert feed.text.count("BEGIN:VEVENT") == 1
    download = client.get("/calendar.ics", params={"download": True})
    assert download.headers["content-disposition"] == 'attachment; filename="jobhunter.ics"'


def test_process_shows_interview_debrief_and_offer(client: TestClient) -> None:
    """Fase 17: el repaso que guarda el agente aparece en la ficha; y si hay propuesta, se dice."""
    from app.services import interviews

    job_id = _job(client)
    _event(client, job_id, type="applied_manually", channel="email")
    past = (datetime.now(UTC) - timedelta(days=1)).replace(microsecond=0).isoformat()
    created = client.post(
        f"/jobs/{job_id}/milestones", json={"kind": "interview", "starts_at": past}
    ).json()
    with session_scope() as session:
        interviews.save_interview_notes(
            session,
            created["id"],
            interviews.InterviewNotesInput(notes="Preguntaron por dbt.", next_steps="Prueba."),
        )

    body = client.get(f"/jobs/{job_id}/process").json()
    [shown] = body["milestones"]
    assert shown["debrief_notes"] == "Preguntaron por dbt." and shown["next_steps"] == "Prueba."
    assert shown["status"] == "scheduled" and body["offer_received"] is False

    _event(client, job_id, type="offer_received")
    assert client.get(f"/jobs/{job_id}/process").json()["offer_received"] is True
