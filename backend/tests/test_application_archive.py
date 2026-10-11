"""Archivo de candidaturas enviadas en `data/documentos/candidaturas/` (fase 13)."""

import json
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from app.cli import app
from app.core.config import get_settings
from app.models import Document, DocumentRender, Task
from app.schemas.cover_letter import CoverLetterContent
from app.services import application_archive, events, worker
from app.services.documents import cover_letter, pdf
from tests.applier_support import cv_ready_job
from tests.cv_support import LETTER, demo_content_data, fake_converter

URL = "https://jobs.example.com/acme/1"


@pytest.fixture(autouse=True)
def _no_libreoffice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf, "get_converter", lambda: fake_converter())


@pytest.fixture
def ready(session: Session) -> int:
    """Oferta en `cv_ready` con CV elegido, carta renderizada y respuestas."""
    job_id = cv_ready_job(session, URL, company="Ácme Analytics, S.L.")
    # El CV del helper no tiene contenido ni opciones: se le da contenido y la carta se hace sin
    # «a juego con el CV».
    cv_render = session.scalars(select(DocumentRender)).one()
    cv_doc = session.get(Document, cv_render.document_id)
    assert cv_doc is not None
    cv_doc.content = demo_content_data()
    cv_render.selected = False
    cover_letter.save_cover_letter(session, job_id, CoverLetterContent.model_validate(LETTER))
    cv_render.selected = True
    session.flush()
    return job_id


def _tasks(session: Session) -> list[Task]:
    return list(session.scalars(select(Task).where(Task.kind == "archive_application")))


def _payload(session: Session) -> dict[str, Any]:
    (task,) = _tasks(session)
    return dict(task.payload)


def test_folder_name_is_ascii_and_windows_safe() -> None:
    name = application_archive.folder_name("Ácme: Analytics/S.L.", "Data Engineer (H/M)", 7)
    assert name == "Acme-Analytics-S-L_Data-Engineer-H-M_7"
    assert application_archive.folder_name("", "???", 3) == "sin-nombre_sin-nombre_3"


def test_applied_manually_enqueues_and_worker_archives(session: Session, ready: int) -> None:
    events.add_user_event(session, ready, "applied_manually", channel="email")
    payload = _payload(session)
    assert payload["cv_render_id"] is not None
    assert payload["letter_document_id"] is not None
    assert payload["answers_document_id"] is not None

    result = worker._archive_application(session, payload)
    assert result["created"] is True
    folder = get_settings().data_dir / result["folder"]
    assert folder.parent == application_archive.archive_root()
    assert folder.name == f"Acme-Analytics-S-L_Data-Engineer_{ready}"
    names = sorted(p.name for p in folder.iterdir())
    assert "CV-Lucia-Varela.pdf" in names
    assert "Carta-Lucia-Varela-Otero.txt" in names
    assert any(n.startswith("Carta-") and n.endswith(".pdf") for n in names)
    assert "respuestas.json" in names and "README.md" in names
    assert sorted(result["files"]) == names

    letter_txt = (folder / "Carta-Lucia-Varela-Otero.txt").read_text(encoding="utf-8")
    assert "Hola, equipo de Acme:" in letter_txt
    answers = json.loads((folder / "respuestas.json").read_text(encoding="utf-8"))
    assert answers["answers"]
    readme = (folder / "README.md").read_text(encoding="utf-8")
    assert URL in readme
    assert "email (registrado por ti)" in readme
    assert "Versión del perfil:** 1" in readme
    assert "Europe/Madrid" in readme
    assert application_archive.relative_folder(ready) == result["folder"]


def test_archive_is_idempotent_and_ignores_later_changes(session: Session, ready: int) -> None:
    events.add_user_event(session, ready, "applied_manually")
    payload = _payload(session)
    first = application_archive.archive(session, payload)
    folder = get_settings().data_dir / first.folder
    before = {p.name: p.read_bytes() for p in folder.iterdir()}

    # Después del envío cambia la carta: lo archivado no se toca.
    letter_doc = session.scalars(select(Document).where(Document.kind == "cover_letter")).one()
    letter_doc.content = {**letter_doc.content, "letter": {**LETTER, "greeting": "Buenas:"}}
    session.flush()

    again = application_archive.archive(session, payload)
    assert again.created is False and again.files == [] and again.folder == first.folder
    assert {p.name: p.read_bytes() for p in folder.iterdir()} == before
    assert len(list(application_archive.archive_root().iterdir())) == 1


def test_archive_without_documents_writes_only_readme(session: Session, ready: int) -> None:
    payload = {
        "job_id": ready,
        "event_id": None,
        "cv_render_id": None,
        "letter_document_id": None,
        "letter_render_id": None,
        "answers_document_id": None,
    }
    result = application_archive.archive(session, payload)
    folder = get_settings().data_dir / result.folder
    assert [p.name for p in folder.iterdir()] == ["README.md"]
    assert "ninguno" in (folder / "README.md").read_text(encoding="utf-8")


def test_missing_pdf_is_skipped(session: Session, ready: int) -> None:
    events.add_user_event(session, ready, "applied_manually")
    payload = _payload(session)
    render = session.get(DocumentRender, payload["cv_render_id"])
    assert render is not None and render.pdf_path
    (get_settings().data_dir / render.pdf_path).unlink()
    result = application_archive.archive(session, payload)
    assert "CV-Lucia-Varela.pdf" not in result.files


def test_failed_archive_leaves_no_partial_folder(
    session: Session, ready: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    events.add_user_event(session, ready, "applied_manually")
    payload = _payload(session)

    def boom(*_args: object) -> str:
        raise OSError("disco lleno")

    monkeypatch.setattr(application_archive, "_readme", boom)
    with pytest.raises(OSError):
        application_archive.archive(session, payload)
    assert list(application_archive.archive_root().iterdir()) == []
    assert application_archive.find_folder(ready) is None


def test_other_events_do_not_enqueue(session: Session, ready: int) -> None:
    events.add_user_event(session, ready, "note", note="Llamar el lunes")
    assert _tasks(session) == []


def test_find_folder_matches_exact_job_id() -> None:
    root = application_archive.archive_root()
    (root / "Acme_Data_12").mkdir(parents=True)
    (root / ".tmp-2-abc").mkdir()
    assert application_archive.find_folder(2) is None
    assert application_archive.find_folder(12) == root / "Acme_Data_12"


def test_archive_existing_backfills(session: Session, ready: int) -> None:
    events.add_user_event(session, ready, "applied_manually")
    (result,) = application_archive.archive_existing(session)
    assert result.created
    (again,) = application_archive.archive_existing(session, ready)
    assert not again.created


def test_archive_existing_rejects_job_not_applied(session: Session, ready: int) -> None:
    with pytest.raises(application_archive.ArchiveError):
        application_archive.archive_existing(session, ready)


def test_cli_archive_requires_one_target() -> None:
    out = CliRunner().invoke(app, ["applications", "archive", "--json"])
    assert out.exit_code == 1
    assert json.loads(out.output)["error"]["type"] == "invalid_request"


def test_worker_describes_archive() -> None:
    outcome = worker.TaskOutcome(
        task_id=1,
        kind="archive_application",
        ok=True,
        result={"job_id": 3, "folder": "documentos/candidaturas/A_B_3", "created": True},
    )
    assert worker.describe(outcome) == (
        "Candidatura de la oferta 3 archivada en data/documentos/candidaturas/A_B_3"
    )


def test_job_view_links_the_archive(session: Session, ready: int) -> None:
    from app.services import jobs

    assert jobs.get_job_view(session, ready).archive_folder is None
    events.add_user_event(session, ready, "applied_manually")
    result = application_archive.archive(session, _payload(session))
    assert jobs.get_job_view(session, ready).archive_folder == result.folder


def test_concurrent_archive_returns_existing(
    session: Session, ready: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Si otro proceso la archiva entre la comprobación y el renombrado, no falla."""
    events.add_user_event(session, ready, "applied_manually")
    payload = _payload(session)
    other = application_archive.archive_root() / f"Otro_{ready}"
    real_find = application_archive.find_folder
    calls = {"n": 0}

    def find_late(job_id: int):  # noqa: ANN202
        calls["n"] += 1
        if calls["n"] == 1:
            other.mkdir(parents=True)  # llega «el otro proceso»
            (
                application_archive.archive_root() / f"Acme-Analytics-S-L_Data-Engineer_{ready}"
            ).mkdir()
            return None
        return real_find(job_id)

    monkeypatch.setattr(application_archive, "find_folder", find_late)
    result = application_archive.archive(session, payload)
    assert result.created is False
    assert not any(p.name.startswith(".tmp-") for p in application_archive.archive_root().iterdir())


def test_job_view_skips_disk_before_sending(
    session: Session, ready: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import jobs

    def boom(_job_id: int) -> None:
        raise AssertionError("no debería mirar el disco")

    monkeypatch.setattr(application_archive, "relative_folder", boom)
    assert jobs.get_job_view(session, ready).archive_folder is None
