"""API de «Mi CV» (fase 08.3): subidas, plantilla por defecto y vistas del original y del perfil."""

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core import migrations
from app.core.config import get_settings
from app.core.db import session_scope
from app.services import profile
from app.services.documents import pdf, uploads
from app.services.documents.importer import build
from tests.cv_support import fake_converter
from tests.template_support import MAPPING, make_cv

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(pdf, "get_converter", lambda: fake_converter())
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture
def real_profile(client: TestClient) -> Path:
    """`data/profile.yaml` (copia del demo, con sus comentarios) importado."""
    path = profile.default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(profile.EXAMPLE_PATH, path)
    with session_scope() as session:
        profile.import_profile(session, path)
    return path


def _upload(client: TestClient, name: str, data: bytes, kind: str = DOCX_TYPE) -> dict:  # type: ignore[type-arg]
    response = client.post("/uploads", files={"file": (name, data, kind)})
    return {"status": response.status_code, **response.json()} if response.content else {}


def _cv_bytes(tmp_path: Path) -> bytes:
    return make_cv(tmp_path / "cv.docx").read_bytes()


# --- Subidas --------------------------------------------------------------------------------


def test_upload_saves_with_safe_name_and_never_overwrites(
    client: TestClient, tmp_path: Path
) -> None:
    data = _cv_bytes(tmp_path)
    first = _upload(client, "Mi CV (versión 2).docx", data)
    assert first["status"] == 201
    assert first["name"] == "mi-cv-version-2.docx"
    assert first["path"] == "data/uploads/mi-cv-version-2.docx"
    assert first["supported"] and first["template_id"] is None
    assert first["agent_command"] == "importar-plantilla-cv data/uploads/mi-cv-version-2.docx"
    second = _upload(client, "Mi CV (versión 2).docx", data)
    assert second["name"] == "mi-cv-version-2-2.docx"
    assert (uploads.paths.uploads_dir() / "mi-cv-version-2.docx").read_bytes() == data


def test_upload_rejects_format_size_and_path_tricks(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert _upload(client, "cv.exe", b"MZ")["status"] == 422
    monkeypatch.setattr(uploads, "MAX_BYTES", 10)
    too_big = _upload(client, "cv.docx", b"x" * 11)
    assert too_big["status"] == 413 and too_big["error"]["type"] == "too_large"
    monkeypatch.setattr(uploads, "MAX_BYTES", 10 * 1024 * 1024)
    tricky = _upload(client, "..\\..\\fuera.pdf", b"%PDF-1.4")
    assert tricky["status"] == 201 and tricky["name"] == "fuera.pdf"
    assert tricky["supported"]  # PDF: motor html (fase 08b)
    assert client.delete("/uploads/..%5Cprofile.yaml").status_code == 404


def test_list_marks_imported_uploads_and_delete(client: TestClient, tmp_path: Path) -> None:
    saved = _upload(client, "mi-cv.docx", _cv_bytes(tmp_path))
    listed = client.get("/uploads").json()
    assert [u["template_id"] for u in listed] == [None]

    build.build_docx(uploads.paths.uploads_dir() / saved["name"], MAPPING, "mi-cv")
    listed = client.get("/uploads").json()
    assert listed[0]["template_id"] == "mi-cv"
    by_id = {t["id"]: t for t in client.get("/templates").json()["templates"]}
    assert by_id["mi-cv"]["from_user_cv"] and by_id["mi-cv"]["has_source_preview"]
    assert not by_id["ats-simple"]["from_user_cv"]

    source = client.get("/templates/mi-cv/source.png")
    assert source.status_code == 200 and source.headers["content-type"] == "image/png"
    assert client.get("/templates/ats-simple/source.png").status_code == 404

    assert client.delete(f"/uploads/{saved['name']}").status_code == 204
    assert client.get("/uploads").json() == []


# --- Plantilla por defecto ------------------------------------------------------------------


def test_set_default_keeps_comments_and_creates_version(
    client: TestClient, real_profile: Path, tmp_path: Path
) -> None:
    build.build_docx(make_cv(_uploads_file(tmp_path)), MAPPING, "mi-cv")
    before = real_profile.read_text(encoding="utf-8")
    assert client.get("/templates/default").json() == {"template_id": "clasica-foto"}

    response = client.post("/templates/mi-cv/default")
    assert response.status_code == 200
    body = response.json()
    assert body["template_id"] == "mi-cv" and body["created"]
    assert any("ATS workday" in c and "ats-simple" in c for c in body["conflicts"])

    after = real_profile.read_text(encoding="utf-8")
    changed = [
        (a, b) for a, b in zip(before.splitlines(), after.splitlines(), strict=True) if a != b
    ]
    assert len(changed) == 1 and "default_template: mi-cv" in changed[0][1]
    assert "# integrada o tuya" in changed[0][1]  # el comentario de la línea sigue
    assert yaml.safe_load(after)["preferences"]["cv"]["default_template"] == "mi-cv"
    assert client.get("/templates/default").json() == {"template_id": "mi-cv"}


def test_set_default_errors(client: TestClient, real_profile: Path) -> None:
    assert client.post("/templates/no-existe/default").status_code == 404
    real_profile.unlink()
    response = client.post("/templates/ats-simple/default")
    assert (
        response.status_code == 404 and "actualizar-perfil" in response.json()["error"]["message"]
    )


def test_real_preview_is_cached(client: TestClient, real_profile: Path) -> None:
    first = client.get("/templates/ats-simple/preview-real.png")
    assert first.status_code == 200 and first.headers["content-type"] == "image/png"
    cached = list((get_settings().data_dir / "cache" / "previews").glob("ats-simple-real-*-v*.png"))
    assert len(cached) == 1
    assert client.get("/templates/ats-simple/preview-real.png").content == first.content


def _uploads_file(tmp_path: Path) -> Path:
    folder = uploads.paths.uploads_dir()
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "mi-cv.docx"


def test_upload_checks_content_and_reserved_names(client: TestClient, tmp_path: Path) -> None:
    fake = _upload(client, "cv.docx", b"esto no es un Word")
    assert fake["status"] == 422 and fake["error"]["type"] == "invalid_file"
    reserved = _upload(client, "CON.docx", _cv_bytes(tmp_path))
    assert reserved["status"] == 201 and reserved["name"] == "cv-con.docx"


def test_set_default_keeps_lf_line_endings(
    client: TestClient, real_profile: Path, tmp_path: Path
) -> None:
    real_profile.write_bytes(real_profile.read_bytes().replace(b"\r\n", b"\n"))
    assert client.post("/templates/ats-simple/default").status_code == 200
    assert b"\r\n" not in real_profile.read_bytes()
