"""Corregir un CV ya generado: correcciones, versiones, qué cambió, «Volver» y edición directa."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.main import create_app
from app.core import migrations
from app.core.config import get_settings
from app.core.db import session_scope
from app.models import AgentRequest, Document, DocumentRender
from app.schemas.cv import CvContent, CvVerification
from app.services import agent_launch, agent_requests, events, extractions, profile
from app.services.documents import corrections, cv_diff, pdf, service
from app.services.pipeline import Stage
from tests.agent_support import POSTING_TEXT
from tests.cv_support import demo_content, demo_content_data, fake_converter
from tests.matching_support import demo_extraction

SHORTER = "Data Engineer con experiencia en Snowflake."


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setattr(pdf, "get_converter", lambda: fake_converter())
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture
def job_id(client: TestClient) -> int:
    body = {"title": "Data Engineer", "company": "Acme Analytics", "text": POSTING_TEXT}
    created = client.post("/jobs/text", json=body).json()["job_id"]
    with session_scope() as session:
        profile.import_profile(session, profile.EXAMPLE_PATH)
        extractions.save_extraction(session, created, demo_extraction())
        events.record(session, created, "approved", "user")
        service.save_content(session, created, demo_content())
    return created


def _correct(client: TestClient, job_id: int, text: str = "El resumen más corto") -> dict[str, Any]:
    response = client.post(f"/jobs/{job_id}/cv/corrections", json={"instruction": text})
    assert response.status_code == 201
    return response.json()


def _apply(job_id: int, correction_id: int, note: str | None = None, **changes: Any) -> int:
    with session_scope() as session:
        result = corrections.save_corrected(
            session,
            job_id,
            correction_id,
            demo_content(**(changes or {"summary": SHORTER})),
            note=note,
        )
    return result.document_id


def _history(client: TestClient, job_id: int) -> dict[str, Any]:
    response = client.get(f"/jobs/{job_id}/cv/history")
    assert response.status_code == 200
    return response.json()


def _current_id(client: TestClient, job_id: int) -> int:
    return client.get(f"/jobs/{job_id}/cv").json()["cv"]["document_id"]


def _edit(client: TestClient, job_id: int, base: int, **changes: Any) -> Any:
    return client.post(
        f"/jobs/{job_id}/cv/edit",
        json={"base_document_id": base, "content": demo_content_data(**changes)},
    )


# --- Corrección -----------------------------------------------------------------------------


def test_action_exists_and_needs_a_pending_correction(client: TestClient, job_id: int) -> None:
    assert {"correct-cv", "verify-cv"} <= set(agent_launch.ACTIONS)
    with session_scope() as session, pytest.raises(agent_launch.LaunchError, match="qué quieres"):
        agent_launch.check_target(session, "correct-cv", job_id)
    _correct(client, job_id, "cambia «lideré» por «participé»")
    with session_scope() as session:
        prompt, _, _ = agent_launch.check_target(session, "correct-cv", job_id)
    # La orden no lleva el texto del usuario: lo lee el skill.
    assert "lideré" not in prompt and str(job_id) in prompt


def test_verify_needs_a_cv(client: TestClient, job_id: int) -> None:
    with session_scope() as session:
        prompt, _, _ = agent_launch.check_target(session, "verify-cv", job_id)
    assert "verify-cv" in prompt
    body = {"title": "Sin CV", "company": "Acme", "text": POSTING_TEXT}
    other = client.post("/jobs/text", json=body).json()["job_id"]
    with session_scope() as session:
        extractions.save_extraction(session, other, demo_extraction())
        events.record(session, other, "approved", "user")
    with session_scope() as session, pytest.raises(agent_launch.LaunchError, match="aún no tiene"):
        agent_launch.check_target(session, "verify-cv", other)


@pytest.mark.parametrize("text", ["", "   ", "x" * (corrections.MAX_INSTRUCTION + 1)])
def test_instruction_is_bounded(client: TestClient, job_id: int, text: str) -> None:
    response = client.post(f"/jobs/{job_id}/cv/corrections", json={"instruction": text})
    assert response.status_code == 422


def test_correction_needs_a_cv_and_a_cv_stage(client: TestClient, job_id: int) -> None:
    assert client.post("/jobs/9999/cv/corrections", json={"instruction": "x"}).status_code == 404
    with session_scope() as session:
        events.record(session, job_id, "applied_manually", "user", {"channel": "other"})
        assert events.current_stage(session, job_id) == Stage.APPLIED
    response = client.post(f"/jobs/{job_id}/cv/corrections", json={"instruction": "x"})
    assert response.status_code == 409


def test_a_new_request_replaces_the_pending_one(client: TestClient, job_id: int) -> None:
    first = _correct(client, job_id, "primera")
    second = _correct(client, job_id, "segunda")
    assert second["id"] == first["id"] and second["instruction"] == "segunda"
    with session_scope() as session:
        pending = corrections.get_pending(session, job_id)
    assert pending.correction is not None and pending.correction.instruction == "segunda"


def test_applied_correction_keeps_both_versions_and_inherits_style(
    client: TestClient, job_id: int
) -> None:
    original = _current_id(client, job_id)
    with session_scope() as session:
        styled = service.render(
            session, original, service.CvRenderOptions(template_id="clasica-foto", photo="exclude")
        )
        service.select_render(session, styled.render_id)
    correction = _correct(client, job_id)
    new_id = _apply(job_id, correction["id"], note="No quité el proyecto: no lo pediste.")

    history = _history(client, job_id)
    assert [v["document_id"] for v in history["versions"]] == [new_id, original]
    newest, older = history["versions"]
    assert newest["current"] and not older["current"]
    assert newest["origin"] == "correction" and older["origin"] == "generated"
    assert newest["instruction"] == "El resumen más corto"
    assert newest["note"].startswith("No quité")
    assert newest["render"]["template_id"] == "clasica-foto"
    assert newest["changes"] == [
        {
            "section": "summary",
            "item": None,
            "removed": [demo_content().summary],
            "added": [SHORTER],
            "reordered": False,
        }
    ]
    assert history["correction"]["status"] == "applied"


def test_correction_retry_compares_against_the_version_before_correcting(
    client: TestClient, job_id: int
) -> None:
    original = _current_id(client, job_id)
    correction = _correct(client, job_id)
    _apply(job_id, correction["id"], summary="Primer intento de resumen.")
    second = _apply(job_id, correction["id"], summary=SHORTER)
    newest = _history(client, job_id)["versions"][0]
    assert newest["document_id"] == second and newest["instruction"]
    assert newest["changes"][0]["removed"] == [demo_content().summary]
    with session_scope() as session:
        assert session.get(Document, second).base_document_id == original


def test_correction_of_other_job_or_closed_is_rejected(client: TestClient, job_id: int) -> None:
    correction = _correct(client, job_id)
    with session_scope() as session, pytest.raises(corrections.CorrectionNotFoundError):
        corrections.save_corrected(session, job_id + 1, correction["id"], demo_content())
    client.post(f"/cv-corrections/{correction['id']}/cancel")
    with session_scope() as session, pytest.raises(corrections.CorrectionClosedError):
        corrections.save_corrected(session, job_id, correction["id"], demo_content())


def test_decline_leaves_no_new_version_and_shows_why(client: TestClient, job_id: int) -> None:
    correction = _correct(client, job_id, "añade que hablo japonés")
    with session_scope() as session:
        result = corrections.decline(session, correction["id"], "  Tu perfil no lo respalda.  ")
    assert result.status == "declined"
    history = _history(client, job_id)
    assert len(history["versions"]) == 1
    assert history["correction"]["status"] == "declined"
    assert history["correction"]["note"] == "Tu perfil no lo respalda."
    with session_scope() as session, pytest.raises(corrections.CorrectionClosedError):
        corrections.decline(session, correction["id"], "otra vez")


def test_cancel_correction_cancels_its_request_and_vice_versa(
    client: TestClient, job_id: int
) -> None:
    correction = _correct(client, job_id)
    with session_scope() as session:
        request = agent_requests.create(session, "correct-cv", job_id)
    assert client.post(f"/cv-corrections/{correction['id']}/cancel").status_code == 200
    with session_scope() as session:
        assert session.get(AgentRequest, request.id).status == "cancelled"
    # Cancelar dos veces no vale.
    assert client.post(f"/cv-corrections/{correction['id']}/cancel").status_code == 403
    assert client.post("/cv-corrections/9999/cancel").status_code == 404
    assert _history(client, job_id)["correction"] is None

    _correct(client, job_id, "otra")
    with session_scope() as session:
        request = agent_requests.create(session, "correct-cv", job_id)
        agent_requests.cancel(session, request.id)
    with session_scope() as session:
        assert corrections.get_pending(session, job_id).correction is None


def test_agent_does_not_overwrite_an_edit_made_while_it_worked(
    client: TestClient, job_id: int
) -> None:
    original = _current_id(client, job_id)
    correction = _correct(client, job_id)
    with session_scope() as session:
        assert corrections.get_pending(session, job_id).document_id == original
    edited = _edit(client, job_id, original, subtitle="Editado a mano").json()["document_id"]
    with session_scope() as session, pytest.raises(corrections.CvVersionConflictError):
        corrections.save_corrected(session, job_id, correction["id"], demo_content())
    assert _current_id(client, job_id) == edited
    # Al volver a leer, parte de la edición y ya puede guardar.
    with session_scope() as session:
        assert corrections.get_pending(session, job_id).document_id == edited
    assert _apply(job_id, correction["id"]) > edited


def test_rewriting_after_the_agent_read_it_rejects_the_old_one(
    client: TestClient, job_id: int
) -> None:
    first = _correct(client, job_id, "primera")
    with session_scope() as session:
        corrections.get_pending(session, job_id)
    second = _correct(client, job_id, "segunda")
    assert second["id"] != first["id"]
    with session_scope() as session, pytest.raises(corrections.CorrectionClosedError):
        corrections.save_corrected(session, job_id, first["id"], demo_content())
    with session_scope() as session:
        pending = corrections.get_pending(session, job_id).correction
    assert pending is not None and pending.instruction == "segunda"


def test_retry_needs_the_current_version_to_be_its_own(client: TestClient, job_id: int) -> None:
    original = _current_id(client, job_id)
    correction = _correct(client, job_id)
    _apply(job_id, correction["id"], summary="Primer intento de resumen.")
    client.post(f"/documents/{original}/restore")
    with session_scope() as session, pytest.raises(corrections.CvVersionConflictError):
        corrections.save_corrected(session, job_id, correction["id"], demo_content())


def test_render_cover_is_a_png_of_the_pdf(client: TestClient, job_id: int) -> None:
    import pypdfium2

    from app.core.config import get_settings

    with session_scope() as session:
        render_id = service.selected_render_id(session, job_id)
        assert render_id is not None
        pdf = service.render_file(session, render_id, "pdf")
    assert pdf.is_relative_to(get_settings().data_dir.resolve())
    document = pypdfium2.PdfDocument.new()
    document.new_page(595, 842)
    document.save(pdf)
    document.close()

    response = client.get(f"/renders/{render_id}/cover.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")
    assert client.get("/renders/999999/cover.png").status_code == 404


# --- Volver ---------------------------------------------------------------------------------


def test_restore_makes_an_older_version_current_without_deleting(
    client: TestClient, job_id: int
) -> None:
    original = _current_id(client, job_id)
    newer = _apply(job_id, _correct(client, job_id)["id"])
    with session_scope() as session:
        documents = session.scalar(select(func.count()).select_from(Document))
        renders = session.scalar(select(func.count()).select_from(DocumentRender))

    response = client.post(f"/documents/{original}/restore")
    assert response.status_code == 200
    assert response.json()["cv"]["document_id"] == original
    assert _current_id(client, job_id) == original
    with session_scope() as session:
        assert session.scalar(select(func.count()).select_from(Document)) == documents
        assert session.scalar(select(func.count()).select_from(DocumentRender)) == renders
        # Lo que se enviaría es el render de la versión a la que se ha vuelto.
        selected = service.selected_render_id(session, job_id)
        assert session.get(DocumentRender, selected).document_id == original

    # Se puede volver a la más nueva y, tras otra corrección, manda esa.
    assert client.post(f"/documents/{newer}/restore").json()["cv"]["document_id"] == newer
    client.post(f"/documents/{original}/restore")
    latest = _apply(job_id, _correct(client, job_id, "otra")["id"], summary="Otra versión del CV.")
    assert _current_id(client, job_id) == latest
    with session_scope() as session:
        assert session.get(Document, latest).base_document_id == original


def test_restore_of_a_version_where_nothing_fits_selects_nothing(
    client: TestClient, job_id: int
) -> None:
    original = _current_id(client, job_id)
    _apply(job_id, _correct(client, job_id)["id"])
    with session_scope() as session:
        for row in session.scalars(
            select(DocumentRender).where(DocumentRender.document_id == original)
        ):
            row.selected = False
            row.warnings = [{"code": "too_long", "message": "Demasiado largo."}]
    assert client.post(f"/documents/{original}/restore").status_code == 200
    with session_scope() as session:
        assert service.selected_render_id(session, job_id) is None


def test_restore_errors(client: TestClient, job_id: int) -> None:
    original = _current_id(client, job_id)
    assert client.post("/documents/9999/restore").status_code == 404
    with session_scope() as session:
        events.record(session, job_id, "applied_manually", "user", {"channel": "other"})
    assert client.post(f"/documents/{original}/restore").status_code == 409


def test_restore_does_not_change_the_stage(client: TestClient, job_id: int) -> None:
    original = _current_id(client, job_id)
    with session_scope() as session:
        service.save_verification(session, original, CvVerification(passed=True, issues=[]))
        assert events.current_stage(session, job_id) == Stage.CV_READY
    _apply(job_id, _correct(client, job_id)["id"])
    client.post(f"/documents/{original}/restore")
    with session_scope() as session:
        assert events.current_stage(session, job_id) == Stage.CV_READY


# --- Edición directa ------------------------------------------------------------------------


def test_edit_creates_unverified_version_with_same_style(client: TestClient, job_id: int) -> None:
    original = _current_id(client, job_id)
    with session_scope() as session:
        styled = service.render(
            session, original, service.CvRenderOptions(template_id="clasica-foto", photo="exclude")
        )
        service.select_render(session, styled.render_id)
        service.save_verification(session, original, CvVerification(passed=True, issues=[]))

    response = _edit(client, job_id, original, summary=SHORTER)
    assert response.status_code == 201
    body = response.json()
    assert body["warnings"] == []
    assert body["render"]["template_id"] == "clasica-foto"
    assert body["render"]["options"]["template_source"] == "option"

    newest, older = _history(client, job_id)["versions"]
    assert newest["origin"] == "edit" and newest["verified"] is None and newest["current"]
    assert older["verified"] is True
    assert newest["changes"][0]["section"] == "summary"
    with session_scope() as session:
        doc = session.get(Document, body["document_id"])
        assert doc.edited_by_user and doc.base_document_id == original


def _changed_bullet(text: str) -> dict[str, Any]:
    data = demo_content_data()
    data["experience"][0]["bullets"][0]["text"] = text
    return data


def test_edit_warns_about_what_the_profile_does_not_back_but_saves(
    client: TestClient, job_id: int
) -> None:
    original = _current_id(client, job_id)
    data = _changed_bullet("Migré 40 procesos ETL (-97 % en tiempo de carga).")
    data["skills"][0]["items"][0] = "Cobol"
    response = _edit(
        client,
        job_id,
        original,
        experience=data["experience"],
        skills=data["skills"],
    )
    assert response.status_code == 201
    warnings = {(w["code"], w["field"], w["value"]) for w in response.json()["warnings"]}
    assert ("skill", "skills.0.items.0", "Cobol") in warnings
    assert ("number", "experience.0.bullets.0", "97") in warnings
    # El 40 ya estaba y lo que no se ha tocado no avisa.
    assert not any(value == "40" for _, _, value in warnings)
    assert len(warnings) == 2
    assert _current_id(client, job_id) == response.json()["document_id"]


def test_edit_keeps_numbers_that_are_in_the_profile_quiet(client: TestClient, job_id: int) -> None:
    original = _current_id(client, job_id)
    data = _changed_bullet("Reduje un 35 % el tiempo de carga nocturna.")
    response = _edit(client, job_id, original, experience=data["experience"])
    assert response.status_code == 201
    assert response.json()["warnings"] == []


@pytest.mark.parametrize(
    "changes",
    [
        {"education_ids": []},
        {"certification_ids": []},
        {"projects": []},
        {"language": "en"},
        {"keywords_targeted": ["Otra"]},
        {"languages": [{"language": "Español", "level": "Nativo"}]},
    ],
)
def test_edit_cannot_change_the_structure(
    client: TestClient, job_id: int, changes: dict[str, Any]
) -> None:
    response = _edit(client, job_id, _current_id(client, job_id), **changes)
    assert response.status_code == 422
    assert "solo se cambian textos" in response.json()["error"]["message"]


def test_edit_cannot_change_blocks_evidence_or_counts(client: TestClient, job_id: int) -> None:
    original = _current_id(client, job_id)
    reordered = demo_content_data()
    reordered["experience"].reverse()
    evidence = demo_content_data()
    evidence["experience"][0]["bullets"][0]["evidence"] = ["exp-norteconsulting/a2"]
    fewer = demo_content_data()
    fewer["experience"][0]["bullets"].pop()
    skills = demo_content_data()
    skills["skills"][0]["items"].pop()
    for data in (reordered, evidence, fewer, skills):
        response = _edit(client, job_id, original, **data)
        assert response.status_code == 422


def test_edit_rejects_blank_text_and_no_changes(client: TestClient, job_id: int) -> None:
    original = _current_id(client, job_id)
    assert "vacíos" in _edit(client, job_id, original, summary="   ").json()["error"]["message"]
    assert "No hay cambios" in _edit(client, job_id, original).json()["error"]["message"]
    assert _edit(client, job_id, original, summary="x" * 1201).status_code == 422


def test_edit_of_an_outdated_version_conflicts(client: TestClient, job_id: int) -> None:
    original = _current_id(client, job_id)
    _apply(job_id, _correct(client, job_id)["id"])
    response = _edit(client, job_id, original, summary="Otra cosa.")
    assert response.status_code == 409
    assert response.json()["error"]["type"] == "conflict"


def test_edit_errors(client: TestClient, job_id: int) -> None:
    original = _current_id(client, job_id)
    assert _edit(client, 9999, original, summary="Otra cosa.").status_code == 404
    with session_scope() as session:
        events.record(session, job_id, "applied_manually", "user", {"channel": "other"})
    assert _edit(client, job_id, original, summary="Otra cosa.").status_code == 409


def test_failed_render_leaves_nothing(
    client: TestClient, job_id: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(*_args: Any, **_kwargs: Any) -> None:
        raise pdf.PdfConversionError("no")

    monkeypatch.setattr(pdf, "get_converter", lambda: broken)
    original = _current_id(client, job_id)
    edit = corrections.CvEditInput(
        base_document_id=original, content=demo_content(summary="Otra cosa.")
    )
    with session_scope() as session, pytest.raises(pdf.PdfConversionError):
        corrections.save_user_edit(session, job_id, edit)
    assert _current_id(client, job_id) == original
    staging = get_settings().tmp_dir / "renders"
    assert not staging.exists() or not list(Path(staging).iterdir())


# --- Qué cambió -----------------------------------------------------------------------------


def _bullets(data: dict[str, Any]) -> CvContent:
    return CvContent.model_validate(data)


def test_diff_nothing_changed() -> None:
    assert cv_diff.diff(demo_content(), demo_content(), {}) == []


def test_diff_by_section_with_labels() -> None:
    new = demo_content_data(subtitle="Data Engineer")
    new["experience"][0]["bullets"][0]["text"] = "Migré 40 procesos."
    new["projects"] = []
    new["skills"][1]["items"].remove("ETL")
    new["education_ids"] = []
    new["languages"] = [{"language": "Español", "level": "Nativo"}]
    labels = {"exp-norteconsulting": "Data Engineer · Norte", "prj-tfg": "TFG"}
    changes = {(c.section, c.item): c for c in cv_diff.diff(demo_content(), _bullets(new), labels)}

    assert changes[("subtitle", None)].added == ["Data Engineer"]
    bullet = changes[("experience", "Data Engineer · Norte")]
    assert bullet.added == ["Migré 40 procesos."] and len(bullet.removed) == 1
    assert len(changes[("projects", "TFG")].removed) == 1
    assert changes[("skills", "Datos")].removed == ["ETL"]
    assert changes[("education", None)].removed == ["edu-grado"]
    assert changes[("languages", None)].removed == ["Inglés: B2"]
    assert len(changes) == 6


def test_diff_detects_reorder_and_new_block() -> None:
    new = demo_content_data()
    new["experience"].reverse()
    new["experience"][0]["bullets"].append({"text": "Otra viñeta.", "evidence": ["exp-datagal/a1"]})
    new["skills"].append({"group": "Nube", "items": ["AWS"]})
    changes = cv_diff.diff(demo_content(), _bullets(new), {})
    assert any(c.section == "experience" and c.reordered for c in changes)
    assert any(c.section == "experience" and c.added == ["Otra viñeta."] for c in changes)
    assert any(c.item == "Nube" and c.added == ["AWS"] for c in changes)


def test_diff_repeated_text_counts_once_each() -> None:
    old = demo_content_data()
    old["experience"][0]["bullets"][1]["text"] = old["experience"][0]["bullets"][0]["text"]
    new = demo_content_data()
    new["experience"][0]["bullets"].pop()
    changes = cv_diff.diff(_bullets(old), _bullets(new), {})
    assert changes[0].removed == [old["experience"][0]["bullets"][1]["text"]]
    assert changes[0].added == []


# --- Etiquetas para la UI -------------------------------------------------------------------


def test_cv_view_names_experience_and_projects(client: TestClient, job_id: int) -> None:
    labels = client.get(f"/jobs/{job_id}/cv").json()["cv"]["labels"]
    assert " · " in labels["exp-norteconsulting"] and labels["prj-tfg"]
