"""Respuestas de screening y paquete de candidatura (fase 10.3)."""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import Document, DocumentRender, Event, Job
from app.schemas.llm_io import ApplicationAnswers, JobExtraction
from app.services import answers, events, extractions, process
from app.services import profile as profile_service
from app.services.pipeline import EventType, InvalidTransitionError
from tests.agent_support import POSTING_TEXT, extraction

GOOD = {
    "question": "¿Has migrado procesos ETL a Python?",
    "answer": "Sí: migré las cargas de SSIS a Python.",
    "evidence": ["exp-norteconsulting/a1", "st-migracion"],
    "needs_user_input": False,
}
SALARY = {
    "question": "Expectativa salarial",
    "answer": "",
    "evidence": [],
    "needs_user_input": True,
}


def _answers(*items: dict[str, Any]) -> ApplicationAnswers:
    return ApplicationAnswers.model_validate({"answers": list(items)})


@pytest.fixture
def approved(session: Session, make_job: Callable[..., Job]) -> int:
    profile_service.import_profile(session, profile_service.EXAMPLE_PATH)
    job = make_job()
    events.record(session, job.id, "found", "system")
    extractions.save_extraction(
        session, job.id, JobExtraction.model_validate(extraction(locations=["Vigo"]))
    )
    events.record(session, job.id, "approved", "user")
    return job.id


def _prepared(session: Session, job_id: int) -> list[Event]:
    stmt = select(Event).where(Event.job_id == job_id, Event.type == EventType.APPLICATION_PREPARED)
    return list(session.scalars(stmt.order_by(Event.id)))


# --- Esquema --------------------------------------------------------------------------------


def test_schema_needs_one_answer_and_all_keys() -> None:
    with pytest.raises(ValidationError):
        ApplicationAnswers.model_validate({"answers": []})
    with pytest.raises(ValidationError):
        ApplicationAnswers.model_validate({"answers": [{"question": "¿Y?", "answer": "Sí"}]})
    with pytest.raises(ValidationError):  # la carta es un documento propio (08c)
        ApplicationAnswers.model_validate({"answers": [GOOD], "cover_letter": "Hola"})


# --- Servicio -------------------------------------------------------------------------------


def test_save_stores_document_and_records_event(session: Session, approved: int) -> None:
    result = answers.save_application_answers(
        session, approved, _answers(GOOD, SALARY), agent_name="claude-code"
    )
    assert result.ok and result.needs_user_input == 1

    doc = session.get(Document, result.document_id)
    assert doc is not None
    assert doc.kind == "answers" and doc.language == "es" and not doc.edited_by_user
    assert doc.profile_version_id == profile_service.current(session).profile_version_id
    assert doc.content["answers"][1]["needs_user_input"] is True

    (event,) = _prepared(session, approved)
    assert event.actor == "agent" and event.agent_name == "claude-code"
    assert event.payload == {"document_id": doc.id, "edited_by_user": False}
    assert events.current_stage(session, approved) == "approved"  # no cambia la etapa
    assert process.get_process(session, approved).documents.answers_document_id == doc.id


def test_get_application_answers_returns_the_latest(session: Session, approved: int) -> None:
    """`prepare-interview` las lee para no contradecir lo que se envió."""
    assert answers.get_application_answers(session, approved).answers is None
    result = answers.save_application_answers(session, approved, _answers(GOOD, SALARY))
    info = answers.get_application_answers(session, approved)
    assert info.answers is not None and info.answers.document_id == result.document_id
    assert len(info.answers.answers) == 2


def test_evidence_must_exist_and_nothing_is_saved(session: Session, approved: int) -> None:
    bad = {**GOOD, "evidence": ["exp-inventada/a9", "extraction", "user", "st-nada"]}
    with pytest.raises(answers.AnswersContentError) as info:
        answers.save_application_answers(session, approved, _answers(bad, {**SALARY}))
    issues = info.value.issues
    assert [(i.field, i.received) for i in issues] == [
        ("answers[0].evidence[0]", "exp-inventada/a9"),
        ("answers[0].evidence[3]", "st-nada"),
    ]
    assert session.scalars(select(Document)).all() == []
    assert _prepared(session, approved) == []


def test_empty_answer_only_with_needs_user_input(session: Session, approved: int) -> None:
    empty = {**SALARY, "answer": "   ", "needs_user_input": False}
    no_evidence = {**GOOD, "evidence": []}
    with pytest.raises(answers.AnswersContentError) as info:
        answers.save_application_answers(session, approved, _answers(empty, no_evidence))
    assert [i.field for i in info.value.issues] == ["answers[0].answer", "answers[1].evidence"]


def test_only_in_approved_or_cv_ready(session: Session, approved: int) -> None:
    events.record(session, approved, "applied_manually", "user")
    with pytest.raises(InvalidTransitionError):
        answers.save_application_answers(session, approved, _answers(GOOD))
    with pytest.raises(InvalidTransitionError):
        answers.save_user_answers(session, approved, _answers(GOOD))


def test_user_edit_creates_new_document_and_keeps_previous(session: Session, approved: int) -> None:
    first = answers.save_application_answers(session, approved, _answers(GOOD, SALARY))
    edited = {**SALARY, "answer": "45.000 € brutos al año", "needs_user_input": False}
    second = answers.save_user_answers(session, approved, _answers(GOOD, edited))
    assert second.document_id != first.document_id and second.needs_user_input == 0

    assert session.get(Document, first.document_id) is not None  # se conserva
    doc = session.get(Document, second.document_id)
    assert doc is not None and doc.edited_by_user
    assert [e.actor for e in _prepared(session, approved)] == ["agent", "user"]

    package = answers.get_package(session, approved)
    assert package.answers is not None
    assert package.answers.document_id == second.document_id
    assert package.answers.edited_by_user
    assert package.answers.answers[1].answer == "45.000 € brutos al año"
    assert package.answers.evidence["st-migracion"].startswith("Historia «Migración")


def test_user_edit_still_rejects_unknown_evidence(session: Session, approved: int) -> None:
    with pytest.raises(answers.AnswersContentError):
        answers.save_user_answers(session, approved, _answers({**GOOD, "evidence": ["exp-x"]}))
    # Sin evidencias sí vale: manda el usuario.
    result = answers.save_user_answers(session, approved, _answers({**GOOD, "evidence": []}))
    assert result.ok


def test_user_edit_validates_against_the_version_it_edits(
    session: Session, approved: int, tmp_path: Path
) -> None:
    """Si el perfil cambia entre medias, la edición cita la versión de las respuestas que edita."""
    first = answers.save_application_answers(session, approved, _answers(GOOD))
    old_version = profile_service.current(session).profile_version_id
    text = profile_service.EXAMPLE_PATH.read_text(encoding="utf-8")
    changed = tmp_path / "profile.yaml"
    renamed = text.replace("  - id: st-migracion", "  - id: st-migracion-v2")
    changed.write_text(renamed, encoding="utf-8")
    assert profile_service.import_profile(session, changed).created

    edited = answers.save_user_answers(session, approved, _answers({**GOOD, "answer": "Sí."}))
    doc = session.get(Document, edited.document_id)
    assert doc is not None and doc.profile_version_id == old_version
    assert first.document_id != edited.document_id
    # El agente, en cambio, valida con la versión vigente: `st-migracion` ya no existe.
    with pytest.raises(answers.AnswersContentError):
        answers.save_application_answers(session, approved, _answers(GOOD))


def test_package_without_anything(session: Session, approved: int) -> None:
    package = answers.get_package(session, approved)
    assert package.can_edit and package.stage == "approved"
    assert package.cv is None and package.answers is None and package.cover_letter is None


def test_package_uses_selected_render_then_sent_one(session: Session, approved: int) -> None:
    version = profile_service.current(session).profile_version_id
    cv = Document(
        job_id=approved,
        profile_version_id=version,
        kind="cv",
        language="es",
        content={},
        verification={"passed": True, "issues": []},
    )
    session.add(cv)
    session.flush()
    renders = [
        DocumentRender(
            document_id=cv.id,
            template_id=template,
            template_hash="h",
            options={},
            pdf_path=f"cvs/{approved}/{cv.id}/{n}/CV.pdf",
            pages=1,
            selected=selected,
        )
        for n, (template, selected) in enumerate((("ats-simple", False), ("clasica", True)))
    ]
    session.add_all(renders)
    session.flush()

    package = answers.get_package(session, approved)
    assert package.cv is not None
    assert package.cv.render_id == renders[1].id and package.cv.template_id == "clasica"
    assert package.cv.pdf_url == f"/renders/{renders[1].id}/pdf"
    assert package.cv.verified and not package.cv.sent

    sent = {"render_id": renders[0].id}
    events.record(session, approved, "applied_manually", "user", payload=sent)
    package = answers.get_package(session, approved)
    assert package.cv is not None and package.cv.render_id == renders[0].id and package.cv.sent
    assert not package.can_edit


# --- API ------------------------------------------------------------------------------------


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


def _api_job(client: TestClient) -> int:
    with session_scope() as session:
        profile_service.import_profile(session, profile_service.EXAMPLE_PATH)
    body = {"title": "Data Engineer", "company": "Acme Analytics", "text": POSTING_TEXT}
    job_id: int = client.post("/jobs/text", json=body).json()["job_id"]
    with session_scope() as session:
        extractions.save_extraction(
            session, job_id, JobExtraction.model_validate(extraction(locations=["Vigo"]))
        )
    assert client.post(f"/jobs/{job_id}/events", json={"type": "approved"}).status_code == 201
    return job_id


def test_api_package_and_user_edit(client: TestClient) -> None:
    job_id = _api_job(client)
    empty = client.get(f"/jobs/{job_id}/package")
    assert empty.status_code == 200
    assert empty.json()["answers"] is None and empty.json()["cover_letter"] is None

    with session_scope() as session:
        answers.save_application_answers(session, job_id, _answers(GOOD, SALARY))
    edited = {**SALARY, "answer": "Incorporación en 15 días", "needs_user_input": False}
    saved = client.post(f"/jobs/{job_id}/answers", json={"answers": [GOOD, edited]})
    assert saved.status_code == 201, saved.text

    package = client.get(f"/jobs/{job_id}/package").json()
    assert package["answers"]["edited_by_user"] is True
    assert package["answers"]["answers"][1]["answer"] == "Incorporación en 15 días"
    with session_scope() as session:
        assert [e.actor for e in _prepared(session, job_id)] == ["agent", "user"]


def test_api_errors(client: TestClient) -> None:
    job_id = _api_job(client)
    bad = client.post(
        f"/jobs/{job_id}/answers",
        json={"answers": [{**SALARY, "needs_user_input": False}]},
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["type"] == "validation_error"
    assert bad.json()["error"]["details"][0]["field"] == "answers.0.answer"

    assert client.get("/jobs/999/package").status_code == 404
    applied = client.post(f"/jobs/{job_id}/events", json={"type": "applied_manually"})
    assert applied.status_code == 201
    late = client.post(f"/jobs/{job_id}/answers", json={"answers": [GOOD]})
    assert late.status_code == 409
