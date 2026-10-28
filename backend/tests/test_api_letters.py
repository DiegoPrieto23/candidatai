"""API de la carta de presentación (fase 08c.3): ficha, indicaciones, renders, TXT y edición."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from app.agent_interface.tools import TOOLS_BY_NAME, JobIdInput
from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import Document
from app.schemas.cover_letter import CoverLetterContent
from app.schemas.llm_io import JobExtraction
from app.services import extractions, profile
from app.services.documents import cover_letter, pdf
from tests.agent_support import POSTING_TEXT, extraction
from tests.cv_support import LETTER, fake_converter


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(pdf, "get_converter", lambda: fake_converter())
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


def approved_job(client: TestClient) -> int:
    with session_scope() as session:
        profile.import_profile(session, profile.EXAMPLE_PATH)
    body = {"title": "Data Engineer", "company": "Acme Analytics", "text": POSTING_TEXT}
    job_id: int = client.post("/jobs/text", json=body).json()["job_id"]
    with session_scope() as session:
        data = extraction(locations=["Vigo"])
        extractions.save_extraction(session, job_id, JobExtraction.model_validate(data))
    assert client.post(f"/jobs/{job_id}/events", json={"type": "approved"}).status_code == 201
    return job_id


def with_letter(job_id: int) -> int:
    with session_scope() as session:
        content = CoverLetterContent.model_validate(LETTER)
        return cover_letter.save_cover_letter(session, job_id, content).document_id


def test_job_cover_letter_without_and_with_letter(client: TestClient) -> None:
    job_id = approved_job(client)
    empty = client.get(f"/jobs/{job_id}/cover-letter").json()
    assert empty["info"]["letter"] is None and empty["plain_text"] is None
    assert empty["can_edit"] and empty["info"]["max_words"] == 170  # perfil demo
    ids = [t["id"] for t in empty["templates"]]
    assert {"carta-simple", "clasica-foto", "ats-simple", "moderna-2col"} <= set(ids)
    simple = next(t for t in empty["templates"] if t["id"] == "carta-simple")
    assert simple["letter_only"] and simple["accent_colors"]["free"]

    doc = with_letter(job_id)
    data = client.get(f"/jobs/{job_id}/cover-letter").json()
    assert data["info"]["letter"]["document_id"] == doc
    assert data["plain_text"].startswith("Hola, equipo de Acme:\r\n\r\n")


def test_brief_and_errors(client: TestClient) -> None:
    job_id = approved_job(client)
    saved = client.post(
        f"/jobs/{job_id}/cover-letter/brief",
        json={"instructions": "Menciona que uso su producto desde 2023.", "max_words": 150},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["max_words"] == 150
    info = client.get(f"/jobs/{job_id}/cover-letter").json()["info"]
    assert info["brief"]["instructions"] == "Menciona que uso su producto desde 2023."
    bad = client.post(f"/jobs/{job_id}/cover-letter/brief", json={"max_words": 5})
    assert bad.status_code == 422
    assert client.get("/jobs/999/cover-letter").status_code == 404


def test_cv_brief_is_saved_per_job_and_read_by_the_agent(client: TestClient) -> None:
    """Las indicaciones del CV de la ficha: sustituyen a las anteriores y las lee el agente."""
    job_id = approved_job(client)
    assert client.get(f"/jobs/{job_id}/cv/brief").json()["instructions"] == ""
    saved = client.post(f"/jobs/{job_id}/cv/brief", json={"instructions": "  Destaca Airflow. "})
    assert saved.status_code == 200 and saved.json()["instructions"] == "Destaca Airflow."
    with session_scope() as session:
        view = TOOLS_BY_NAME["get_cv_brief"].handler(session, JobIdInput(job_id=job_id), None)
    assert view.instructions == "Destaca Airflow."  # type: ignore[attr-defined]
    assert client.post(f"/jobs/{job_id}/cv/brief", json={}).json()["instructions"] == ""
    too_long = client.post(f"/jobs/{job_id}/cv/brief", json={"instructions": "x" * 4001})
    assert too_long.status_code == 422
    assert client.get("/jobs/999/cv/brief").status_code == 404


def test_render_select_and_files(client: TestClient) -> None:
    job_id = approved_job(client)
    doc = with_letter(job_id)
    render = client.post(f"/cover-letters/{doc}/renders", json={"accent_color": "#7A2E39"})
    assert render.status_code == 201, render.text
    render_id = render.json()["render_id"]
    assert render.json()["options"]["accent_color"] == "#7A2E39"
    assert not render.json()["selected"]

    selected = client.post(f"/renders/{render_id}/select")
    assert selected.status_code == 200 and selected.json()["selected"]
    letter = client.get(f"/jobs/{job_id}/cover-letter").json()["info"]["letter"]
    assert [r["selected"] for r in letter["renders"]] == [False, True]

    pdf_file = client.get(f"/renders/{render_id}/pdf")
    assert pdf_file.status_code == 200 and pdf_file.headers["content-type"] == "application/pdf"
    assert client.get(f"/renders/{render_id}/docx").status_code == 200

    unknown = client.post(f"/cover-letters/{doc}/renders", json={"template_id": "nada"})
    assert unknown.status_code == 404


def test_plain_text_download(client: TestClient) -> None:
    job_id = approved_job(client)
    doc = with_letter(job_id)
    response = client.get(f"/cover-letters/{doc}/text")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/plain; charset=utf-8"
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="Carta-Lucia-Varela-Otero.txt"'
    )
    text = response.content.decode("utf-8")
    assert "migré" in text and "\r\n" in text and "\n" not in text.replace("\r\n", "")
    assert client.get("/cover-letters/999/text").status_code == 404


def test_user_edit_creates_unverified_document(client: TestClient) -> None:
    job_id = approved_job(client)
    first = with_letter(job_id)
    edited: dict[str, Any] = {**LETTER, "greeting": "Hola:"}
    saved = client.post(f"/jobs/{job_id}/cover-letter", json=edited)
    assert saved.status_code == 201, saved.text
    doc_id = saved.json()["document_id"]
    assert doc_id != first
    with session_scope() as session:
        doc = session.get(Document, doc_id)
        assert doc is not None and doc.edited_by_user and doc.verification is None
        assert session.get(Document, first) is not None
    letter = client.get(f"/jobs/{job_id}/cover-letter").json()["info"]["letter"]
    assert letter["edited_by_user"] and letter["content"]["greeting"] == "Hola:"

    bad = client.post(
        f"/jobs/{job_id}/cover-letter",
        json={**LETTER, "paragraphs": [{"text": "Hola.", "evidence": ["exp-x"]}]},
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["details"][0]["field"] == "paragraphs.0.evidence.0"


def test_user_edit_without_instructions_marks_changed_paragraphs(
    client: TestClient, tmp_path: Path
) -> None:
    """Sin indicaciones guardadas, el retoque también se guarda: el autor es el usuario."""
    job_id = approved_job(client)
    data = yaml.safe_load(profile.EXAMPLE_PATH.read_text(encoding="utf-8"))
    data["preferences"].pop("cover_letter")
    plain = tmp_path / "profile.yaml"
    plain.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with session_scope() as session:
        profile.import_profile(session, plain)
    # La carta del agente, sin `user` (no hay indicaciones que lo respalden).
    agent_letter = {**LETTER, "paragraphs": LETTER["paragraphs"][:2]}
    with session_scope() as session:
        content = CoverLetterContent.model_validate(agent_letter)
        doc = cover_letter.save_cover_letter(session, job_id, content).document_id

    paragraphs = [dict(p) for p in agent_letter["paragraphs"]]
    paragraphs[1] = {**paragraphs[1], "text": "Reescrito por mí: migré las cargas a Python."}
    saved = client.post(
        f"/jobs/{job_id}/cover-letter", json={**agent_letter, "paragraphs": paragraphs}
    )
    assert saved.status_code == 201, saved.text
    letter = client.get(f"/jobs/{job_id}/cover-letter").json()["info"]["letter"]
    assert letter["document_id"] != doc and letter["edited_by_user"]
    evidence = [p["evidence"] for p in letter["content"]["paragraphs"]]
    assert evidence == [["extraction"], ["exp-norteconsulting/a1", "st-migracion", "user"]]


def test_letter_in_package_and_process(client: TestClient) -> None:
    job_id = approved_job(client)
    assert client.get(f"/jobs/{job_id}/package").json()["cover_letter"] is None
    doc = with_letter(job_id)
    package = client.get(f"/jobs/{job_id}/package").json()["cover_letter"]
    assert package["document_id"] == doc and package["text"].startswith("Hola, equipo")
    assert package["pdf_url"] == f"/renders/{package['render_id']}/pdf"
    assert not package["verified"] and not package["edited_by_user"]
    process = client.get(f"/jobs/{job_id}/process").json()
    assert process["documents"]["cover_letter_document_id"] == doc
