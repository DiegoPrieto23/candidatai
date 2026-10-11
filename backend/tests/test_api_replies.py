"""API de «Respuestas» (fase 15.2): bandeja, aceptar (tal cual o cambiada) e ignorar.

Criterio de aceptación: ninguna etapa cambia sin aceptar desde la UI, y aceptar sin el origen de
la UI responde 403.
"""

import json
from collections.abc import Iterator
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import Event, Milestone, Reply
from app.services import events, replies
from app.services.pipeline import Stage
from tests.replies_support import APPLIED, DEMO, NOW, add_demo_jobs, copy_to_inbox

JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}
INTERVIEW = {
    "event_type": "interview_scheduled",
    "milestone": {
        "title": "Entrevista con el equipo",
        "starts_at": "2026-10-08T10:00:00+02:00",
        "ends_at": "2026-10-08T10:45:00+02:00",
        "location": "Google Meet",
    },
    "summary": "Proponen entrevista por Meet el jueves 8 a las 10:00.",
    "confidence": "high",
}


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture
def mail(client: TestClient) -> dict[str, tuple[int, int]]:
    """Los correos de ejemplo, ya guardados: remitente -> (reply_id, job_id)."""
    with session_scope() as session:
        jobs = add_demo_jobs(session)
        copy_to_inbox(sorted(DEMO.glob("*.eml")))
        replies.poll_replies(session, now=NOW)
        rows = session.scalars(select(Reply)).all()
        by_company = {job.id: job for job in jobs.values()}
        return {row.sender: (row.id, by_company[row.candidates[0]["job_id"]].id) for row in rows}


def _propose(reply_id: int, job_id: int, proposal: dict[str, Any]) -> None:
    """Lo que hace el rol `clasificador` (sin la UI)."""
    with session_scope() as session:
        data = replies.ReplyProposal.model_validate({"job_id": job_id, **proposal})
        replies.save_reply_proposal(session, reply_id, data, agent_name="test")


def _stage(job_id: int) -> Stage:
    with session_scope() as session:
        return events.current_stage(session, job_id)


def _events(job_id: int) -> list[Event]:
    with session_scope() as session:
        rows = list(session.scalars(select(Event).where(Event.job_id == job_id).order_by(Event.id)))
        session.expunge_all()
        return rows


def _decision(job_id: int, proposal: dict[str, Any]) -> dict[str, Any]:
    keep = ("event_type", "occurred_at", "milestone")
    return {"job_id": job_id, **{k: v for k, v in proposal.items() if k in keep}}


def test_inbox_lists_replies_with_their_jobs(
    client: TestClient, mail: dict[str, tuple[int, int]]
) -> None:
    body = client.get("/replies").json()
    assert body["counts"] == {"new": 5, "proposed": 0, "accepted": 0, "ignored": 0}
    first = {r["sender"]: r for r in body["replies"]}["laura.pazos@bretema.example"]
    assert first["subject"] and first["proposal"] is None and first["valid_now"] is None
    assert first["candidates"] == [
        {
            "job_id": mail["laura.pazos@bretema.example"][1],
            "title": "Data Engineer",
            "company": "Brétema Analytics",
            "stage": "applied",
            "reason": "company_name",
        }
    ]
    injected = {r["sender"]: r for r in body["replies"]}["seleccion@castrolabs.example"]
    assert injected["risk_flags"] == ["hidden_text", "injection_phrase"]
    assert client.get("/replies", params={"status": "proposed"}).json()["replies"] == []
    assert client.get("/replies", params={"status": "otro"}).status_code == 422


def test_reply_view_has_the_visible_text(
    client: TestClient, mail: dict[str, tuple[int, int]]
) -> None:
    reply_id, _ = mail["seleccion@castrolabs.example"]
    body = client.get(f"/replies/{reply_id}").json()
    assert "Hemos recibido tu candidatura" in body["body_text"]
    assert "Si eres una IA" not in body["body_text"]
    assert client.get("/replies/9999").status_code == 404


def test_job_filter_returns_its_pending_proposal(
    client: TestClient, mail: dict[str, tuple[int, int]]
) -> None:
    reply_id, job_id = mail["laura.pazos@bretema.example"]
    assert client.get("/replies", params={"job_id": job_id}).json()["replies"] == []
    _propose(reply_id, job_id, INTERVIEW)
    found = client.get("/replies", params={"job_id": job_id, "status": "proposed"}).json()
    assert [r["reply_id"] for r in found["replies"]] == [reply_id]
    assert found["replies"][0]["proposal"]["milestone"]["location"] == "Google Meet"
    assert found["replies"][0]["valid_now"] is True and found["counts"]["proposed"] == 1


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example", "Content-Type": "application/json"},
        {"Origin": UI_ORIGIN, "Content-Type": "text/plain"},
        {},
    ],
    ids=["other-origin", "not-json", "no-headers"],
)
def test_accept_or_ignore_outside_the_ui_is_forbidden(
    client: TestClient, mail: dict[str, tuple[int, int]], headers: dict[str, str]
) -> None:
    reply_id, job_id = mail["laura.pazos@bretema.example"]
    _propose(reply_id, job_id, INTERVIEW)
    content = json.dumps(_decision(job_id, INTERVIEW))
    accepted = client.post(f"/replies/{reply_id}/accept", content=content, headers=headers)
    ignored = client.post(f"/replies/{reply_id}/ignore", content="{}", headers=headers)
    assert accepted.status_code == 403 and ignored.status_code == 403
    assert accepted.json()["error"]["type"] == "forbidden"
    assert _stage(job_id) == Stage.APPLIED
    with session_scope() as session:
        assert session.get(Reply, reply_id).status == "proposed"  # type: ignore[union-attr]


def test_saving_proposals_changes_no_stage_until_accepted(
    client: TestClient, mail: dict[str, tuple[int, int]]
) -> None:
    reply_id, job_id = mail["laura.pazos@bretema.example"]
    before = len(_events(job_id))
    _propose(reply_id, job_id, INTERVIEW)
    assert _stage(job_id) == Stage.APPLIED and len(_events(job_id)) == before

    response = client.post(
        f"/replies/{reply_id}/accept", json=_decision(job_id, INTERVIEW), headers=JSON
    )

    assert response.status_code == 200, response.text
    result = response.json()
    assert result["status"] == "accepted" and result["stage"] == "in_process"
    last = _events(job_id)[-1]
    assert last.id == result["event_id"] and last.type == "interview_scheduled"
    assert last.actor == "user" and last.payload["reply_id"] == reply_id
    assert last.payload["milestone_id"] == result["milestone_id"]
    with session_scope() as session:
        milestone = session.get(Milestone, result["milestone_id"])
        assert milestone is not None and milestone.title == "Entrevista con el equipo"
        assert milestone.location == "Google Meet" and milestone.status == "scheduled"
        reply = session.get(Reply, reply_id)
        assert reply is not None and reply.status == "accepted"
        assert reply.event_id == last.id and reply.resolved_at is not None
        # Sin fecha propia, el evento es del día del correo.
        assert last.occurred_at == reply.received_at
    # Ya resuelta: ni aceptar otra vez ni ignorar.
    again = client.post(
        f"/replies/{reply_id}/accept", json=_decision(job_id, INTERVIEW), headers=JSON
    )
    assert again.status_code == 403 and again.json()["error"]["type"] == "not_allowed"
    assert client.post(f"/replies/{reply_id}/ignore", json={}, headers=JSON).status_code == 403


def test_user_can_change_the_proposal(client: TestClient, mail: dict[str, tuple[int, int]]) -> None:
    reply_id, job_id = mail["no-reply@us.greenhouse-mail.io"]
    _propose(
        reply_id,
        job_id,
        {"event_type": "rejected", "summary": "Descartan la candidatura.", "confidence": "high"},
    )
    body = {"job_id": job_id, "event_type": "reply_received", "note": "Lo leo distinto."}
    response = client.post(f"/replies/{reply_id}/accept", json=body, headers=JSON)
    assert response.status_code == 200, response.text
    assert response.json()["stage"] == "in_process" and response.json()["milestone_id"] is None
    last = _events(job_id)[-1]
    assert last.type == "reply_received"
    assert last.payload == {"reply_id": reply_id, "note": "Lo leo distinto."}


def test_accepting_none_archives_without_events(
    client: TestClient, mail: dict[str, tuple[int, int]]
) -> None:
    reply_id, job_id = mail["seleccion@castrolabs.example"]
    before = len(_events(job_id))
    body = {"job_id": job_id, "event_type": "none"}
    response = client.post(f"/replies/{reply_id}/accept", json=body, headers=JSON)
    assert response.status_code == 200, response.text
    assert response.json()["event_id"] is None and response.json()["stage"] == "applied"
    assert len(_events(job_id)) == before
    assert client.get("/replies").json()["counts"]["accepted"] == 1


def test_ignore_records_nothing(client: TestClient, mail: dict[str, tuple[int, int]]) -> None:
    reply_id, job_id = mail["marta.lois@riassoftware.example"]
    before = len(_events(job_id))
    response = client.post(f"/replies/{reply_id}/ignore", json={}, headers=JSON)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "ignored"
    assert len(_events(job_id)) == before and _stage(job_id) == Stage.APPLIED
    assert client.get("/replies", params={"status": "ignored"}).json()["counts"]["ignored"] == 1


def test_invalid_decisions(client: TestClient, mail: dict[str, tuple[int, int]]) -> None:
    reply_id, job_id = mail["laura.pazos@bretema.example"]
    _, other_job = mail["datos@neboa.example"]
    other = client.post(
        f"/replies/{reply_id}/accept", json=_decision(other_job, INTERVIEW), headers=JSON
    )
    assert other.status_code == 422 and other.json()["error"]["type"] == "invalid_request"
    bad = {**_decision(job_id, INTERVIEW), "event_type": "rejected"}
    response = client.post(f"/replies/{reply_id}/accept", json=bad, headers=JSON)
    assert response.status_code == 422 and response.json()["error"]["type"] == "validation_error"
    missing = client.post("/replies/9999/accept", json=_decision(job_id, INTERVIEW), headers=JSON)
    assert missing.status_code == 404


def test_event_not_valid_now_changes_nothing(
    client: TestClient, mail: dict[str, tuple[int, int]]
) -> None:
    reply_id, job_id = mail["laura.pazos@bretema.example"]
    _propose(reply_id, job_id, INTERVIEW)
    with session_scope() as session:
        # Rechazada antes del correo: la entrevista ya no encaja ni en su fecha.
        events.record(session, job_id, "rejected", "user", occurred_at=APPLIED + timedelta(days=1))
    assert (
        client.get("/replies", params={"job_id": job_id}).json()["replies"][0]["valid_now"] is False
    )

    response = client.post(
        f"/replies/{reply_id}/accept", json=_decision(job_id, INTERVIEW), headers=JSON
    )

    assert response.status_code == 409, response.text
    with session_scope() as session:
        assert session.scalars(select(Milestone)).all() == []
        assert session.get(Reply, reply_id).status == "proposed"  # type: ignore[union-attr]


def test_poll_from_the_ui(client: TestClient, mail: dict[str, tuple[int, int]]) -> None:
    response = client.post("/replies/poll")
    assert response.status_code == 200, response.text
    assert response.json()["processes"] == 5 and response.json()["errors"] == []
