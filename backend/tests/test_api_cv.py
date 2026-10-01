"""API del CV (fase 08.2): plantillas, CV de la oferta, renders y ficheros."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core import migrations
from app.core.config import get_settings
from app.core.db import session_scope
from app.models import DocumentRender
from app.services import events, extractions, profile
from app.services.documents import pdf, service
from tests.agent_support import POSTING_TEXT
from tests.cv_support import demo_content, fake_converter, write_template
from tests.matching_support import demo_extraction


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(pdf, "get_converter", lambda: fake_converter())
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


def _approved_job(client: TestClient) -> int:
    body = {"title": "Data Engineer", "company": "Acme Analytics", "text": POSTING_TEXT}
    job_id = client.post("/jobs/text", json=body).json()["job_id"]
    with session_scope() as session:
        profile.import_profile(session, profile.EXAMPLE_PATH)
        extractions.save_extraction(session, job_id, demo_extraction())
        events.record(session, job_id, "approved", "user")
    return job_id


@pytest.fixture
def job_with_cv(client: TestClient) -> dict[str, Any]:
    job_id = _approved_job(client)
    with session_scope() as session:
        saved = service.save_content(session, job_id, demo_content())
    return {"job_id": job_id, "document_id": saved.document_id, "render_id": saved.render.render_id}


# --- Plantillas -----------------------------------------------------------------------------


def test_list_templates_with_previews(client: TestClient) -> None:
    response = client.get("/templates")
    assert response.status_code == 200
    by_id = {t["id"]: t for t in response.json()["templates"]}
    assert {"ats-simple", "clasica-foto"} <= set(by_id)
    assert by_id["clasica-foto"]["photo_supported"] is True
    assert len(by_id["clasica-foto"]["accent_colors"]["choices"]) == 4
    assert by_id["ats-simple"]["has_preview"] is True

    preview = client.get("/templates/clasica-foto/preview.png")
    assert preview.status_code == 200 and preview.headers["content-type"] == "image/png"
    assert preview.content.startswith(b"\x89PNG")


def test_template_preview_errors(client: TestClient) -> None:
    assert client.get("/templates/no-existe/preview.png").status_code == 404
    write_template(get_settings().user_templates_dir, "sin-preview")
    response = client.get("/templates/sin-preview/preview.png")
    assert response.status_code == 404
    assert response.json()["error"]["type"] == "not_found"


# --- CV de la oferta ------------------------------------------------------------------------


def test_job_without_cv(client: TestClient) -> None:
    job_id = _approved_job(client)
    body = client.get(f"/jobs/{job_id}/cv").json()
    assert body == {"job_id": job_id, "stage": "approved", "can_render": True, "cv": None}
    assert client.get("/jobs/999/cv").status_code == 404


def test_job_cv_with_renders(client: TestClient, job_with_cv: dict[str, Any]) -> None:
    body = client.get(f"/jobs/{job_with_cv['job_id']}/cv").json()
    cv = body["cv"]
    assert cv["document_id"] == job_with_cv["document_id"]
    assert cv["verification"] is None
    [render] = cv["renders"]
    assert render["template_id"] == "clasica-foto"
    assert render["selected"] is True and render["template_changed"] is False
    assert render["pages"] == 1 and "present" in render["keyword_coverage"]


def test_render_from_ui_and_select(client: TestClient, job_with_cv: dict[str, Any]) -> None:
    response = client.post(
        f"/documents/{job_with_cv['document_id']}/renders",
        json={"template_id": "ats-simple", "photo": "exclude", "hidden_sections": ["projects"]},
    )
    assert response.status_code == 201, response.text
    new = response.json()
    assert new["template_id"] == "ats-simple" and new["selected"] is False
    assert new["options"]["hidden_sections"] == ["projects"]

    selected = client.post(f"/renders/{new['render_id']}/select")
    assert selected.status_code == 200 and selected.json()["selected"] is True
    renders = client.get(f"/jobs/{job_with_cv['job_id']}/cv").json()["cv"]["renders"]
    assert [r["selected"] for r in renders] == [False, True]

    timeline = client.get(f"/jobs/{job_with_cv['job_id']}").json()["events"]
    last = [e for e in timeline if e["type"] == "cv_rendered"][-1]
    assert last["actor"] == "user"


def test_render_validation_errors(client: TestClient, job_with_cv: dict[str, Any]) -> None:
    url = f"/documents/{job_with_cv['document_id']}/renders"
    bad_color = client.post(url, json={"accent_color": "#000000"})
    assert bad_color.status_code == 422
    assert "admite estos colores" in bad_color.json()["error"]["message"]
    assert client.post(url, json={"photo": "a veces"}).status_code == 422
    assert client.post("/documents/999/renders", json={}).status_code == 404
    assert client.post("/renders/999/select").status_code == 404


def test_render_files(client: TestClient, job_with_cv: dict[str, Any]) -> None:
    render_id = job_with_cv["render_id"]
    pdf_response = client.get(f"/renders/{render_id}/pdf")
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert pdf_response.headers["content-disposition"].startswith("inline")
    assert pdf_response.content.startswith(b"%PDF")

    docx_response = client.get(f"/renders/{render_id}/docx")
    assert docx_response.status_code == 200
    assert docx_response.headers["content-disposition"].startswith("attachment")
    assert "CV-Lucia-Varela-Otero.docx" in docx_response.headers["content-disposition"]
    assert client.get("/renders/999/pdf").status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "../fuera.pdf",
        "../../secreto.pdf",
        "C:/Windows/win.ini",
        "/etc/passwd",
        "capture_token",  # dentro de data/, pero fuera de data/cvs/
        "cvs/../capture_token",
    ],
)
def test_render_files_never_leave_data(
    client: TestClient, job_with_cv: dict[str, Any], path: str
) -> None:
    outside = get_settings().data_dir.parent / "fuera.pdf"
    outside.write_bytes(b"%PDF-1.4 fuera de data")
    (get_settings().data_dir / "capture_token").write_bytes(b"fuera de data/cvs")
    with session_scope() as session:
        row = session.get(DocumentRender, job_with_cv["render_id"])
        assert row is not None
        row.pdf_path = path
    response = client.get(f"/renders/{job_with_cv['render_id']}/pdf")
    assert response.status_code == 404
    assert b"fuera de data" not in response.content
