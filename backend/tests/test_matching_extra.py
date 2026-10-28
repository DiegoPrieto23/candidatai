"""Instalar desde la UI la similitud semántica (extra `matching`): la elección se guarda, la
instala el worker sin tocar lo instalado y, si falta tras actualizar, se reinstala al arrancar."""

import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import Task
from app.services import container, worker
from app.services.matching import embeddings, extra

UI = {"Origin": "http://127.0.0.1:5173"}


@pytest.fixture(autouse=True)
def db(isolated_env: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    migrations.upgrade()
    monkeypatch.setattr(embeddings, "is_installed", lambda: False)
    monkeypatch.setattr(container, "in_docker", lambda: False)
    monkeypatch.setenv("UV_PATH", __file__)  # existe: basta para `_uv()`
    yield


def _kinds() -> list[tuple[str, str]]:
    with session_scope() as session:
        return [(t.kind, t.status) for t in session.scalars(select(Task).order_by(Task.id))]


def test_status_starts_not_wanted() -> None:
    with session_scope() as session:
        view = extra.status(session)
    assert not view.installed and not view.wanted and not view.installing and view.error is None


def test_install_from_the_ui_queues_the_worker_task() -> None:
    client = TestClient(create_app())
    other = {"Origin": "https://evil.example.com"}
    assert client.post("/matching/semantic/install", json={}, headers=other).status_code == 403
    response = client.post("/matching/semantic/install", json={}, headers=UI)
    assert response.status_code == 200
    assert response.json()["wanted"] and response.json()["installing"]
    # Pedirla dos veces no encola dos instalaciones.
    client.post("/matching/semantic/install", json={}, headers=UI)
    assert _kinds() == [("install_matching", "queued")]
    assert client.get("/matching/semantic").json()["wanted"]


def test_not_in_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(container, "in_docker", lambda: True)
    with session_scope() as session, pytest.raises(ValueError, match="Docker"):
        extra.request_install(session)
    assert _kinds() == []


def test_worker_installs_only_adding_packages_and_rescores(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        monkeypatch.setattr(embeddings, "is_installed", lambda: True)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(extra.subprocess, "run", fake_run)
    with session_scope() as session:
        extra.request_install(session)
    outcome = worker.run_one()
    assert outcome is not None and outcome.ok, outcome
    (command,) = calls
    # Solo añade: ni quita lo instalado, ni toca uv.lock, ni reinstala la app en uso.
    for flag in ("--extra", "matching", "--inexact", "--frozen", "--no-install-project"):
        assert flag in command
    assert _kinds() == [("install_matching", "done"), ("rescore_all", "queued")]


def test_failed_install_is_shown_and_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 2, "", "error: sin conexión")

    monkeypatch.setattr(extra.subprocess, "run", fake_run)
    with session_scope() as session:
        extra.request_install(session)
    outcome = worker.run_one()
    assert outcome is not None and not outcome.ok
    with session_scope() as session:
        view = extra.status(session)
    assert view.wanted and not view.installing
    assert view.error is not None and "sin conexión" in view.error


def test_reinstalled_on_start_if_wanted_and_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    with session_scope() as session:
        assert not extra.ensure_installed(session)  # no la pediste
        extra.request_install(session)
        assert not extra.ensure_installed(session)  # ya está en cola
    with session_scope() as session:
        for task in session.scalars(select(Task)):
            task.status = "done"
    with session_scope() as session:
        assert extra.ensure_installed(session)  # tras actualizar, falta: se reinstala
    monkeypatch.setattr(embeddings, "is_installed", lambda: True)
    with session_scope() as session:
        assert not extra.ensure_installed(session)
