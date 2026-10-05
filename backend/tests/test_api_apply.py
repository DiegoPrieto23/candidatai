"""API de la candidatura asistida (fase 11.2). Sin navegador: las rutas solo encolan y leen."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.main import create_app
from app.core import migrations
from app.core.config import get_settings
from app.core.db import session_scope
from app.models import ApplicationAttempt, Task
from app.services import events
from tests.applier_support import PDF, cv_ready_job

GREENHOUSE = "https://boards.greenhouse.io/acme/jobs/1"


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


def new_job(url: str = GREENHOUSE) -> int:
    with session_scope() as session:
        return cv_ready_job(session, url)


def ready_attempt(job_id: int, **changes: Any) -> tuple[int, str]:
    """Un intento ya rellenado, como lo deja el worker. Devuelve su id y su `updated_at`."""
    with session_scope() as session:
        row = ApplicationAttempt(
            job_id=job_id,
            platform="greenhouse",
            mode="fill",
            url=GREENHOUSE,
            status="ready",
            fields=[],
            warnings=[
                {"code": "submit_button", "message": "Al confirmar se pulsará «Submit».",
                 "detail": "Submit"},
            ],
        )  # fmt: skip
        for key, value in changes.items():
            setattr(row, key, value)
        session.add(row)
        session.flush()
        return row.id, row.updated_at.isoformat()


def queued(kind: str) -> list[Task]:
    with session_scope() as session:
        stmt = select(Task).where(Task.kind == kind, Task.status == "queued")
        return list(session.scalars(stmt))


def error_code(response: Any) -> str:
    (detail,) = response.json()["error"]["details"]
    return str(detail["received"])


def test_state_says_what_prepare_would_do(client: TestClient) -> None:
    job_id = new_job()
    body = client.get(f"/jobs/{job_id}/apply").json()
    assert body["attempt"] is None and body["can_prepare"] is True
    assert (body["mode"], body["domain"], body["company"]) == (
        "fill",
        "boards.greenhouse.io",
        "Acme Analytics",
    )
    with session_scope() as session:
        linkedin = cv_ready_job(session, "https://www.linkedin.com/jobs/view/9", company="Beta")
        events.add_user_event(session, linkedin, "applied_manually")
    closed = client.get(f"/jobs/{linkedin}/apply").json()
    assert closed["mode"] == "open" and not closed["can_prepare"] and closed["reason"]
    assert client.get("/jobs/999/apply").status_code == 404


def test_prepare_queues_the_worker_and_refuses_twice(client: TestClient) -> None:
    job_id = new_job()
    response = client.post(f"/jobs/{job_id}/apply/prepare")
    assert response.status_code == 202
    attempt = response.json()
    assert (attempt["status"], attempt["platform"], attempt["domain"]) == (
        "queued",
        "greenhouse",
        "boards.greenhouse.io",
    )
    assert attempt["pending_task"]["kind"] == "apply_fill"
    again = client.post(f"/jobs/{job_id}/apply/prepare")
    assert again.status_code == 409 and error_code(again) == "busy"


def test_prepare_refuses_local_urls(client: TestClient) -> None:
    job_id = new_job("http://127.0.0.1:8000/jobs/1")
    response = client.post(f"/jobs/{job_id}/apply/prepare")
    assert response.status_code == 422 and error_code(response) == "invalid_url"
    assert not client.get(f"/jobs/{job_id}/apply").json()["can_prepare"]


def test_submit_needs_company_and_reviewed_version(client: TestClient) -> None:
    job_id = new_job()
    attempt_id, _ = ready_attempt(job_id)
    view = client.get(f"/jobs/{job_id}/apply").json()["attempt"]
    assert view["can_submit"] and view["submit_button"] == "Submit"
    reviewed_at = view["updated_at"]  # lo que manda la UI: la versión que vio

    missing = client.post(f"/apply/{attempt_id}/submit", json={"company_confirmation": "Acme"})
    assert missing.status_code == 422  # sin `reviewed_at`
    wrong = client.post(
        f"/apply/{attempt_id}/submit",
        json={"company_confirmation": "Otra", "reviewed_at": reviewed_at},
    )
    assert wrong.status_code == 422 and error_code(wrong) == "company_mismatch"
    assert queued("apply_submit") == []

    ok = client.post(
        f"/apply/{attempt_id}/submit",
        json={"company_confirmation": "acme analytics", "reviewed_at": reviewed_at},
    )
    assert ok.status_code == 202
    (task,) = queued("apply_submit")
    assert task.payload["attempt_id"] == attempt_id
    # El token no sale nunca por la API.
    assert task.payload["token"] not in ok.text
    assert ok.json()["pending_task"]["kind"] == "apply_submit"
    twice = client.post(
        f"/apply/{attempt_id}/submit",
        json={"company_confirmation": "Acme Analytics", "reviewed_at": reviewed_at},
    )
    assert twice.status_code == 409 and error_code(twice) == "busy"


def test_stale_review_is_refused(client: TestClient) -> None:
    job_id = new_job()
    attempt_id, _ = ready_attempt(job_id)
    response = client.post(
        f"/apply/{attempt_id}/submit",
        json={"company_confirmation": "Acme Analytics", "reviewed_at": "2026-01-01T00:00:00Z"},
    )
    assert response.status_code == 409 and error_code(response) == "stale"


def test_focus_rescan_and_manual_done(client: TestClient) -> None:
    job_id = new_job()
    attempt_id, _ = ready_attempt(job_id)
    assert client.post(f"/apply/{attempt_id}/rescan").status_code == 202
    assert client.post(f"/apply/{attempt_id}/focus").status_code == 202
    assert [t.kind for t in queued("apply_rescan") + queued("apply_focus")] == [
        "apply_rescan",
        "apply_focus",
    ]
    done = client.post(f"/jobs/{job_id}/apply/manual-done")
    assert done.status_code == 200 and done.json()["stage"] == "applied"
    view = client.get(f"/jobs/{job_id}/apply").json()["attempt"]
    assert view["status"] == "manual_done" and not view["can_rescan"]
    assert client.post("/apply/999/focus").status_code == 404


def test_browser_open_is_queued(client: TestClient) -> None:
    response = client.post("/browser/open")
    assert response.status_code == 202
    assert [t.kind for t in queued("browser_open")] == ["browser_open"]


def test_screenshots(client: TestClient) -> None:
    job_id = new_job()
    attempt_id, _ = ready_attempt(job_id)
    assert client.get(f"/apply/{attempt_id}/screenshot/review").status_code == 404
    relative = f"applications/{job_id}/{attempt_id}/review.png"
    path = get_settings().data_dir / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PDF)  # el contenido da igual: se sirve tal cual
    with session_scope() as session:
        row = session.get(ApplicationAttempt, attempt_id)
        assert row is not None
        row.screenshot_path = relative
    response = client.get(f"/apply/{attempt_id}/screenshot/review")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert client.get(f"/apply/{attempt_id}/screenshot/other").status_code == 422


def test_submit_refusals_never_queue(client: TestClient) -> None:
    job_id = new_job()
    empty = [{"marker": "0", "label": "Salary", "control": "text", "kind": "question",
              "required": True, "status": "empty"}]  # fmt: skip
    missing = ready_attempt(job_id, fields=empty)
    opened = ready_attempt(job_id, mode="open", status="manual")
    for (attempt_id, stamp), code in ((missing, "missing_required"), (opened, "invalid_state")):
        response = client.post(
            f"/apply/{attempt_id}/submit",
            json={"company_confirmation": "Acme Analytics", "reviewed_at": stamp},
        )
        assert error_code(response) == code
    assert queued("apply_submit") == []


def test_cannot_submit_once_the_job_is_applied(client: TestClient) -> None:
    job_id = new_job()
    attempt_id, stamp = ready_attempt(job_id)
    with session_scope() as session:
        events.add_user_event(session, job_id, "applied_manually")
    view = client.get(f"/jobs/{job_id}/apply").json()["attempt"]
    assert not view["can_submit"]
    response = client.post(
        f"/apply/{attempt_id}/submit",
        json={"company_confirmation": "Acme Analytics", "reviewed_at": stamp},
    )
    assert response.status_code == 409 and error_code(response) == "invalid_stage"


def test_token_never_leaves_and_no_rescan_after_click(client: TestClient) -> None:
    job_id = new_job()
    attempt_id, stamp = ready_attempt(job_id)
    client.post(
        f"/apply/{attempt_id}/submit",
        json={"company_confirmation": "Acme Analytics", "reviewed_at": stamp},
    )
    (task,) = queued("apply_submit")
    assert task.payload["token"] not in client.get(f"/jobs/{job_id}/apply").text
    with session_scope() as session:
        row = session.get(ApplicationAttempt, attempt_id)
        assert row is not None
        row.token_used_at, row.status = row.token_expires_at, "submit_unconfirmed"
    response = client.post(f"/apply/{attempt_id}/rescan")
    assert response.status_code == 409 and error_code(response) == "invalid_state"


def test_manual_done_waits_for_the_worker(client: TestClient) -> None:
    job_id = new_job()
    ready_attempt(job_id, status="submitting")
    response = client.post(f"/jobs/{job_id}/apply/manual-done")
    assert response.status_code == 409 and error_code(response) == "busy"


def test_screenshot_outside_applications_is_not_served(client: TestClient) -> None:
    job_id = new_job()
    secret = get_settings().data_dir / "capture_token"
    secret.write_text("secreto", encoding="utf-8")
    for bad in ("../capture_token", "capture_token", str(secret)):
        attempt_id, _ = ready_attempt(job_id, screenshot_path=bad, status="needs_user")
        assert client.get(f"/apply/{attempt_id}/screenshot/review").status_code == 404
