"""Un CV que no cabe no se publica: se mide antes y, al corregir, la app no lo deja pasar."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent_interface.tools import TOOLS_BY_NAME
from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import Document, DocumentRender
from app.services import events, extractions, profile
from app.services.documents import corrections, pdf, service
from tests.agent_support import POSTING_TEXT
from tests.cv_support import demo_content, fake_converter
from tests.matching_support import demo_extraction


@pytest.fixture
def pages(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[int]]:
    """Cuántas páginas devuelve la conversión: la lista se puede cambiar dentro del test."""
    count = [1]
    monkeypatch.setattr(pdf, "get_converter", lambda: fake_converter())
    real = service.prepare_files

    def measured(*args: object, **kwargs: object) -> object:
        files = real(*args, **kwargs)  # type: ignore[arg-type]
        files.pages = count[0]
        return files

    monkeypatch.setattr(service, "prepare_files", measured)
    migrations.upgrade()
    yield count


@pytest.fixture
def job_id(pages: list[int]) -> int:
    body = {"title": "Data Engineer", "company": "Acme Analytics", "text": POSTING_TEXT}
    with TestClient(create_app()) as client:
        created = client.post("/jobs/text", json=body).json()["job_id"]
    with session_scope() as session:
        profile.import_profile(session, profile.EXAMPLE_PATH)
        extractions.save_extraction(session, created, demo_extraction())
        events.record(session, created, "approved", "user")
        service.save_content(session, created, demo_content())
    return created


def _correction(session: Session, job_id: int, text: str) -> int:
    row = corrections.request_correction(
        session, job_id, corrections.CorrectionInput(instruction=text)
    )
    corrections.get_pending(session, job_id)
    return row.id


def _versions(session: Session, job_id: int) -> int:
    stmt = select(func.count()).select_from(Document).where(Document.job_id == job_id)
    return session.scalar(stmt) or 0


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Quiero que lo acortes para que ocupe solo 1 página", 1),
        ("de un CV de 2 hojas pásalo a 1 página", 1),
        ("déjalo en una sola página", 1),
        ("que quepa en una hoja", 1),
        ("máximo dos páginas", 2),
        ("make it a one-page CV", 1),
        ("I want a one pager", 1),
        ("2 pages at most", 2),
        ("quita el proyecto de la página 2", None),
        ("el resumen más corto", None),
        ("una página web en proyectos", 1),
    ],
)
def test_requested_pages(text: str, expected: int | None) -> None:
    assert corrections.requested_pages(text) == expected


def test_checking_writes_nothing(job_id: int, pages: list[int]) -> None:
    pages[0] = 2
    with session_scope() as session:
        before = _versions(session, job_id)
        renders = session.scalar(select(func.count()).select_from(DocumentRender))
        result = service.check_fit(session, job_id, demo_content())
        assert result.pages == 2
        assert _versions(session, job_id) == before
        assert session.scalar(select(func.count()).select_from(DocumentRender)) == renders


def test_too_long_correction_creates_no_version_and_stays_pending(
    job_id: int, pages: list[int]
) -> None:
    pages[0] = 2
    with session_scope() as session:
        correction = _correction(session, job_id, "que ocupe solo 1 página")
        before = _versions(session, job_id)
        current = service.latest_document(session, job_id)
        with pytest.raises(service.CvTooLongError) as error:
            corrections.save_corrected(session, job_id, correction, demo_content())
        assert (error.value.pages, error.value.max_pages) == (2, 1)

        assert _versions(session, job_id) == before
        assert service.latest_document(session, job_id) == current
        pending = corrections.get_pending(session, job_id)
        assert pending.correction is not None
        assert pending.correction.status == "pending"


def test_pages_the_user_asked_for_win_over_what_the_agent_passes(
    job_id: int, pages: list[int]
) -> None:
    pages[0] = 2
    options = service.CvRenderOptions(max_pages=3)
    with session_scope() as session:
        correction = _correction(session, job_id, "que ocupe 1 página")
        with pytest.raises(service.CvTooLongError):
            corrections.save_corrected(
                session, job_id, correction, demo_content(), render_options=options
            )
        check = corrections.check_fit(session, job_id, correction, demo_content(), options)
        assert (check.fits, check.max_pages) == (False, 1)


def test_once_it_fits_it_is_saved_selected_and_closes_the_correction(
    job_id: int, pages: list[int]
) -> None:
    pages[0] = 2
    with session_scope() as session:
        correction = _correction(session, job_id, "que ocupe solo 1 página")
        with pytest.raises(service.CvTooLongError):
            corrections.save_corrected(session, job_id, correction, demo_content())

        pages[0] = 1
        check = corrections.check_fit(session, job_id, correction, demo_content())
        assert (check.fits, check.pages, check.max_pages) == (True, 1, 1)
        result = corrections.save_corrected(session, job_id, correction, demo_content())

        assert result.render.selected is True
        assert (result.render.pages, result.render.max_pages) == (1, 1)
        assert corrections.get_pending(session, job_id).correction is None


def test_the_next_correction_knows_the_length(job_id: int) -> None:
    with session_scope() as session:
        _correction(session, job_id, "que ocupe solo 1 página")
        pending = corrections.get_pending(session, job_id)
        assert pending.max_pages == 1
        assert pending.current_pages == 1


def test_generating_without_a_correction_still_saves(job_id: int, pages: list[int]) -> None:
    """Al generar, el aviso `too_long` lo devuelve al redactor: se queda sin elegir para enviar."""
    pages[0] = 9
    with session_scope() as session:
        result = service.save_content(session, job_id, demo_content())
        assert result.render.selected is False
        assert any(warning.code == "too_long" for warning in result.render.warnings)


def test_the_command_keeps_its_input_file_so_it_can_be_adjusted() -> None:
    spec = TOOLS_BY_NAME["check_cv_fit"]
    assert spec.cli.keep_file is True
    assert TOOLS_BY_NAME["save_cv_content"].cli.keep_file is False
