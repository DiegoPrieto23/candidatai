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


def test_interview_type_and_prep_instructions(client: TestClient) -> None:
    job_id = _job(client)
    _event(client, job_id, type="applied_manually")
    hr = client.post(
        f"/jobs/{job_id}/milestones",
        json={"kind": "interview", "starts_at": _soon(), "interview_type": "hr"},
    ).json()
    technical = client.post(
        f"/jobs/{job_id}/milestones",
        json={"kind": "interview", "starts_at": _soon(5), "interview_type": "technical"},
    ).json()
    assert (hr["interview_type"], technical["interview_type"]) == ("hr", "technical")
    assert hr["prep_instructions"] is None

    # Editar sin mandar el tipo no lo borra; mandarlo vacío, sí.
    kept = client.post(f"/milestones/{hr['id']}", json={"starts_at": _soon(), "title": "RR. HH."})
    assert kept.json()["interview_type"] == "hr"
    changed = client.post(
        f"/milestones/{hr['id']}", json={"starts_at": _soon(), "interview_type": "case"}
    )
    assert changed.json()["interview_type"] == "case"

    # Las indicaciones son de cada entrevista y no registran evento.
    before = len(client.get(f"/jobs/{job_id}/process").json()["notes"])
    saved = client.post(
        f"/milestones/{technical['id']}/prep-instructions",
        json={"instructions": "  Más peso a SQL y a modelado de datos.  "},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["prep_instructions"] == "Más peso a SQL y a modelado de datos."
    sheet = client.get(f"/jobs/{job_id}/process").json()
    by_id = {m["id"]: m for m in sheet["milestones"]}
    assert by_id[hr["id"]]["prep_instructions"] is None
    assert by_id[technical["id"]]["prep_instructions"].startswith("Más peso")
    assert len(sheet["notes"]) == before
    cleared = client.post(
        f"/milestones/{technical['id']}/prep-instructions", json={"instructions": ""}
    )
    assert cleared.json()["prep_instructions"] is None

    # Solo en entrevistas programadas, y el tipo solo se guarda en entrevistas.
    deadline = client.post(
        f"/jobs/{job_id}/milestones",
        json={"kind": "deadline", "starts_at": _soon(), "interview_type": "hr"},
    ).json()
    assert deadline["interview_type"] is None
    refused = client.post(
        f"/milestones/{deadline['id']}/prep-instructions", json={"instructions": "x"}
    )
    assert refused.status_code == 422
    client.post(f"/milestones/{hr['id']}/status", json={"status": "cancelled"})
    late = client.post(f"/milestones/{hr['id']}/prep-instructions", json={"instructions": "x"})
    assert late.status_code == 422


def _milestone_events(job_id: int) -> list[str]:
    from sqlalchemy import select

    from app.models import Event

    with session_scope() as session:
        rows = session.scalars(select(Event).where(Event.job_id == job_id)).all()
        return [e.type for e in rows if "milestone_id" in (e.payload or {})]


def test_delete_milestone_removes_its_events_and_recalculates_stage(client: TestClient) -> None:
    from app.models import MessageDraft, Milestone
    from app.services.interview_guide import guide_path

    job_id = _job(client)
    _event(client, job_id, type="applied_manually")
    wrong = client.post(
        f"/jobs/{job_id}/milestones", json={"kind": "interview", "starts_at": _soon()}
    ).json()
    client.post(f"/milestones/{wrong['id']}", json={"starts_at": _soon(3)})  # deja una nota
    right = client.post(
        f"/jobs/{job_id}/milestones", json={"kind": "interview", "starts_at": _soon(4)}
    ).json()
    guide = guide_path(f"{job_id}-{wrong['id']}-acme-guia.pdf")
    guide.parent.mkdir(parents=True, exist_ok=True)
    guide.write_bytes(b"%PDF")
    with session_scope() as session:
        session.get(Milestone, wrong["id"]).prep_guide = {"file": guide.name}
        draft = MessageDraft(job_id=job_id, kind="thank_you", milestone_id=wrong["id"], body="x")
        session.add(draft)
        session.flush()
        draft_id = draft.id
    assert _milestone_events(job_id).count("interview_scheduled") == 2

    # La anotada por error se va con su evento y su nota; la otra entrevista sigue.
    deleted = client.post(f"/milestones/{wrong['id']}/delete")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["deleted_events"] == 2 and deleted.json()["stage"] == "in_process"
    assert _milestone_events(job_id) == ["interview_scheduled"]
    assert not guide.exists()
    with session_scope() as session:
        assert session.get(MessageDraft, draft_id).milestone_id is None  # el borrador se queda
    sheet = client.get(f"/jobs/{job_id}/process").json()
    assert [m["id"] for m in sheet["milestones"]] == [right["id"]]
    assert not any("reprogramada" in n["text"] for n in sheet["notes"])

    # Sin entrevistas, la oferta vuelve a «Enviada».
    assert client.post(f"/milestones/{right['id']}/delete").json()["stage"] == "applied"
    assert client.post(f"/milestones/{right['id']}/delete").status_code == 404


def test_delete_milestone_refuses_when_later_events_depend_on_it(client: TestClient) -> None:
    job_id = _job(client)
    _event(client, job_id, type="applied_manually")
    interview = client.post(
        f"/jobs/{job_id}/milestones", json={"kind": "interview", "starts_at": _soon()}
    ).json()
    _event(client, job_id, type="accepted")  # solo vale «En proceso», que da la entrevista
    refused = client.post(f"/milestones/{interview['id']}/delete")
    assert refused.status_code == 409, refused.text
    assert "cancélalo" in refused.json()["error"]["message"]
    assert _milestone_events(job_id) == ["interview_scheduled"]  # no se ha tocado nada
    sheet = client.get(f"/jobs/{job_id}/process").json()
    assert [m["id"] for m in sheet["milestones"]] == [interview["id"]]
    assert sheet["stage"] == "closed"

    # Un plazo no tiene eventos: se borra sin más.
    deadline = client.post(
        f"/jobs/{job_id}/milestones", json={"kind": "deadline", "starts_at": _soon()}
    ).json()
    gone = client.post(f"/milestones/{deadline['id']}/delete").json()
    assert gone["deleted_events"] == 0 and gone["stage"] == "closed"


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


def test_calendar_range(client: TestClient) -> None:
    job_id = _job(client)
    _event(client, job_id, type="applied_manually")
    client.post(f"/jobs/{job_id}/milestones", json={"kind": "interview", "starts_at": _soon(1)})
    today = datetime.now(UTC).date()
    start, end = (today - timedelta(days=1)).isoformat(), (today + timedelta(days=5)).isoformat()
    params = {"start": start, "end": end}
    out = client.get("/calendar", params=params).json()
    assert [(i["kind"], i["status"]) for i in out["items"]] == [("interview", "scheduled")]
    assert client.get("/calendar", params={"start": end, "end": start}).status_code == 422
    assert client.get("/calendar", params={"start": "ayer", "end": end}).status_code == 422


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
    assert download.headers["content-disposition"] == 'attachment; filename="candidatai.ics"'


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
