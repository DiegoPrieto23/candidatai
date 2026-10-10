"""Avisos al usuario (captcha, login…): pop-up en la UI y espera limitada del agente."""

import threading
import time
from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import ApplicationAttempt, Task, UserPrompt
from app.schemas.sources import AgentBrowseSource
from app.services import prompts
from app.services.ingestion import browse
from tests.applier_support import cv_ready_job

PLATFORM = {
    "name": "Tecnoempleo",
    "platform": "tecnoempleo",
    "search_urls": ["https://www.tecnoempleo.com/ofertas-trabajo/?te=data"],
}


@pytest.fixture
def db() -> Iterator[None]:
    migrations.upgrade()
    with session_scope() as session:
        browse.save_source(session, AgentBrowseSource.model_validate(PLATFORM))
    yield


def test_request_answer_and_supersede(db: None) -> None:
    with session_scope() as session:
        first = prompts.request(session, "captcha", "Completa el captcha.", source_id=1)
        assert (first.status, first.seconds_left, first.source_name) == (
            "pending",
            300,
            "Tecnoempleo",
        )
        second = prompts.request(session, "captcha", "Otra vez el captcha.", source_id=1)
        assert prompts.get(session, first.id).status == "expired"  # solo vale el último
        assert [p.id for p in prompts.list_pending(session).prompts] == [second.id]
        done = prompts.answer(session, second.id, "skipped")
        assert done.status == "skipped" and done.answered_at is not None
        with pytest.raises(ValueError, match="ya no está pendiente"):
            prompts.answer(session, second.id, "done")
        assert prompts.list_pending(session).prompts == []


def test_unanswered_prompt_expires(db: None) -> None:
    with session_scope() as session:
        view = prompts.request(session, "login_required", "Inicia sesión.", timeout_seconds=60)
        row = session.get(UserPrompt, view.id)
        assert row is not None
        row.expires_at = row.created_at - timedelta(seconds=1)
    with session_scope() as session:
        assert prompts.list_pending(session).prompts == []
        assert prompts.get(session, view.id).status == "expired"


def test_wait_returns_as_soon_as_the_user_answers(db: None) -> None:
    with session_scope() as session:
        prompt_id = prompts.request(session, "captcha", "Completa el captcha.").id

    def answer_later() -> None:
        time.sleep(0.5)
        with session_scope() as session:
            prompts.answer(session, prompt_id, "done")

    thread = threading.Thread(target=answer_later)
    started = time.monotonic()
    thread.start()
    view = prompts.wait(prompt_id, max_seconds=20)
    thread.join()
    assert view.status == "done" and time.monotonic() - started < 10
    with session_scope() as session:
        pending = prompts.request(session, "captcha", "Otro.").id
    assert prompts.wait(pending, max_seconds=0).status == "pending"  # vuelve enseguida


def test_done_on_an_assisted_application_fills_the_page_again(db: None) -> None:
    with session_scope() as session:
        job_id = cv_ready_job(session, "https://empresa.example.com/empleo")
        row = ApplicationAttempt(
            job_id=job_id, platform="generic", mode="fill", url="https://empresa.example.com",
            status="needs_user", fields=[], warnings=[],
        )  # fmt: skip
        session.add(row)
        session.flush()
        prompt_id = prompts.request(session, "captcha", "Captcha.", attempt_id=row.id).id
        prompts.answer(session, prompt_id, "done")
        tasks = [t.kind for t in session.query(Task).all()]
        assert "apply_fill_page" in tasks
        assert session.get(ApplicationAttempt, row.id).status == "queued"


def test_api_lists_and_answers(db: None) -> None:
    with session_scope() as session:
        prompt_id = prompts.request(session, "anti_bot", "Comprueba que eres una persona.").id
    with TestClient(create_app()) as client:
        pending = client.get("/prompts/pending").json()["prompts"]
        assert [(p["id"], p["title"]) for p in pending] == [
            (prompt_id, "La web pide comprobar que eres una persona")
        ]
        answered = client.post(f"/prompts/{prompt_id}/answer", json={"outcome": "done"})
        assert answered.status_code == 200 and answered.json()["status"] == "done"
        assert client.get("/prompts/pending").json()["prompts"] == []
        again = client.post(f"/prompts/{prompt_id}/answer", json={"outcome": "skipped"})
        assert again.status_code in (400, 409, 422)
        missing = client.post("/prompts/99/answer", json={"outcome": "done"})
        assert missing.status_code == 404
