"""API de «Mi perfil» (fase 13): estado del contexto y abrir carpetas, solo desde la UI.

Ningún test abre el explorador de verdad: `os.startfile` se sustituye.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.config import get_settings
from app.services import application_archive, context, folders

JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Windows; registra las carpetas que se abrirían."""
    calls: list[str] = []
    monkeypatch.setattr(folders.sys, "platform", "win32")
    monkeypatch.setattr(folders.os, "startfile", calls.append, raising=False)
    return calls


def test_status_without_files(client: TestClient) -> None:
    body = client.get("/context").json()
    assert [f["section"] for f in body["files"]] == list(context.SECTIONS)
    assert all(not f["exists"] for f in body["files"])
    assert "text" not in body["files"][0]
    assert {f["name"] for f in body["folders"]} == set(context.DOCUMENT_FOLDERS)
    assert body["context_dir"].endswith("contexto")


def test_status_with_content(client: TestClient) -> None:
    context.init()
    (context.context_dir() / "criterios.md").write_text("# Criterios\n\nSin guardias.\n", "utf-8")
    files = {f["section"]: f for f in client.get("/context").json()["files"]}
    assert files["criterios"]["exists"] and not files["criterios"]["empty"]
    assert files["narrativa"]["exists"] and files["narrativa"]["empty"]


def test_open_context_folder_creates_files(client: TestClient, opened: list[str]) -> None:
    response = client.post("/folders/open", json={"folder": "contexto"}, headers=JSON)
    assert response.status_code == 200, response.text
    assert response.json() == {"path": str(context.context_dir()), "opened": True}
    assert opened == [str(context.context_dir())]
    assert (context.context_dir() / "criterios.md").is_file()
    assert (context.documents_dir() / "candidaturas").is_dir()


def test_open_documents_folder(client: TestClient, opened: list[str]) -> None:
    response = client.post("/folders/open", json={"folder": "documentos"}, headers=JSON)
    assert response.json()["path"] == str(context.documents_dir())
    assert opened == [str(context.documents_dir())]


def test_open_interviews_folder_creates_it(client: TestClient, opened: list[str]) -> None:
    """Fase 17: los dosieres de `prepare-interview`."""
    response = client.post("/folders/open", json={"folder": "entrevistas"}, headers=JSON)
    path = get_settings().data_dir / "entrevistas"
    assert response.json() == {"path": str(path), "opened": True}
    assert opened == [str(path)] and path.is_dir()


def test_open_application_folder(client: TestClient, opened: list[str]) -> None:
    body = {"folder": "candidatura", "job_id": 4}
    missing = client.post("/folders/open", json=body, headers=JSON)
    assert missing.status_code == 404
    assert opened == []

    folder = application_archive.archive_root() / "Acme_Data-Engineer_4"
    folder.mkdir(parents=True)
    response = client.post("/folders/open", json=body, headers=JSON)
    assert response.json() == {"path": str(folder), "opened": True}
    assert opened == [str(folder)]


def test_application_folder_needs_job(client: TestClient, opened: list[str]) -> None:
    response = client.post("/folders/open", json={"folder": "candidatura"}, headers=JSON)
    assert response.status_code == 422
    assert opened == []


def test_only_known_folders(client: TestClient, opened: list[str]) -> None:
    for body in ({"folder": "C:/Windows"}, {"folder": "contexto", "path": "C:/"}):
        response = client.post("/folders/open", json=body, headers=JSON)
        assert response.status_code == 422
    assert opened == []


def test_only_the_ui_can_open(client: TestClient, opened: list[str]) -> None:
    evil = client.post(
        "/folders/open",
        json={"folder": "contexto"},
        headers={"Origin": "https://evil.example.com", "Content-Type": "application/json"},
    )
    assert evil.status_code == 403
    form = client.post(
        "/folders/open",
        content='{"folder": "contexto"}',
        headers={"Origin": UI_ORIGIN, "Content-Type": "text/plain"},
    )
    assert form.status_code == 403
    assert opened == []


def test_other_systems_get_the_path(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(folders.sys, "platform", "linux")
    response = client.post("/folders/open", json={"folder": "documentos"}, headers=JSON)
    assert response.json() == {"path": str(context.documents_dir()), "opened": False}


def test_startfile_failure_returns_path(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(_path: str) -> None:
        raise OSError("sin explorador")

    monkeypatch.setattr(folders.sys, "platform", "win32")
    monkeypatch.setattr(folders.os, "startfile", fail, raising=False)
    response = client.post("/folders/open", json={"folder": "contexto"}, headers=JSON)
    assert response.json()["opened"] is False
    assert Path(response.json()["path"]) == context.context_dir()
