"""Guía de preparación de una entrevista en PDF: contenido estructurado del agente,
maquetado y escapado por la app, guardado en el hito y servido a la ficha."""

from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models import Company, Job
from app.schemas.interview_guide import (
    GuideCorrectionInput,
    InterviewGuideInput,
    ParagraphBlock,
)
from app.services import events, guide_diff, interview_guide, interviews, process
from app.services.documents.pdf import PdfConverterUnavailableError
from app.services.interviews import InterviewNotAllowedError
from tests.applied_support import APPLIED, NOW, add_applied_job

GUIDE: dict[str, Any] = {
    "language": "es",
    "title": "Data Engineer",
    "subtitle": "Entrevista técnica",
    "accent_color": "#e30613",
    "sections": [
        {
            "title": "El rol en una frase",
            "blocks": [{"type": "paragraph", "text": "De la fuente al **insight** con `dbt`."}],
        },
        {
            "title": "Responsabilidades",
            "blocks": [
                {"type": "heading", "text": "Técnicas"},
                {"type": "bullets", "items": [{"label": "ELT", "text": "con Airflow."}]},
                {
                    "type": "table",
                    "headers": ["Aspecto", "Ingeniería", "Ciencia"],
                    "rows": [["Pregunta", "¿Llega el dato?", "¿Qué pasará?"]],
                },
            ],
        },
        {
            "title": "Posibles preguntas",
            "blocks": [
                {
                    "type": "qa",
                    "items": [
                        {
                            "question": "¿Un pipeline en producción?",
                            "answer": "Historia st-migracion.",
                            "caution": "No inventes volúmenes.",
                        }
                    ],
                },
                {"type": "callout", "tone": "warning", "text": "No has usado ClickHouse."},
                {
                    "type": "code",
                    "columns": [
                        {"label": "SQL", "code": "SELECT 1;"},
                        {"label": "PySpark", "code": "df.select(lit(1))"},
                    ],
                },
            ],
        },
    ],
    "sources": [{"title": "Web de la empresa", "url": "https://example.com/acme"}],
}


def _guide(**changes: Any) -> InterviewGuideInput:
    return InterviewGuideInput.model_validate(GUIDE | changes)


def _interview(session: Session, job: Job, starts_at: datetime, kind: str = "interview") -> int:
    return process.create_milestone(
        session,
        job.id,
        process.MilestoneCreate(kind=kind, starts_at=starts_at, occurred_at=APPLIED),  # type: ignore[arg-type]
    ).id


@pytest.fixture
def fake_pdf(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Sin Chromium: escribe un PDF falso y guarda el HTML que se habría impreso."""
    printed: list[str] = []

    def html_to_pdf(html: str, _resolve: object, output: Path, *_a: object, **_k: object) -> Path:
        printed.append(html)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"%PDF-1.7 falso")
        return output

    monkeypatch.setattr(interview_guide, "html_to_pdf", html_to_pdf)
    return printed


# --- Esquema y formato ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "changes",
    [
        {"accent_color": "red"},
        {"accent_color": "#12345"},
        {"language": "fr"},
        {"sections": GUIDE["sections"][:2]},  # mínimo tres secciones
        {"sources": [{"title": "Malo", "url": "javascript:alert(1)"}]},
        {"sources": [{"title": "Malo", "url": "file:///C:/data/profile.yaml"}]},
    ],
)
def test_schema_rejects_bad_guides(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        _guide(**changes)


def test_table_rows_must_match_headers() -> None:
    bad = {"type": "table", "headers": ["A", "B"], "rows": [["1", "2"], ["solo una"]]}
    sections = [*GUIDE["sections"][:2], {"title": "Tabla", "blocks": [bad]}]
    with pytest.raises(ValidationError, match="Las filas 2"):
        _guide(sections=sections)


def test_inline_escapes_html_and_keeps_only_simple_marks() -> None:
    html = interview_guide.inline('<script>x</script> **negrita** *cursiva* `a < b` <a href="x">')
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert "<strong>negrita</strong>" in html and "<em>cursiva</em>" in html
    assert "<code>a &lt; b</code>" in html
    assert "<a " not in html
    # Dentro del código no se interpreta nada.
    assert interview_guide.inline("`**no**`") == "<code>**no**</code>"


def test_ink_darkens_light_brand_colors_until_readable() -> None:
    assert interview_guide.ink("#0082C3") != "#FFFFFF"
    for color in ("#FFD100", "#7FFF00", "#E30613", "#003B71"):
        assert interview_guide._contrast_with_white(interview_guide.ink(color)) >= 4.5
    assert interview_guide.ink("#003B71") == "#003B71"  # ya se lee: no cambia


def test_render_numbers_sections_and_uses_the_guide_language() -> None:
    starts = datetime(2026, 10, 26, 9, 0, tzinfo=UTC)  # 10:00 en Madrid (horario de invierno)
    es = interview_guide.render_html(_guide(), "Acme", starts, False, date(2026, 10, 23))
    assert "1. El rol en una frase" in es and "3. Posibles preguntas" in es
    assert "Preparación de entrevista" in es and "Idea de respuesta:" in es
    assert "Lunes, 26 de octubre de 2026 · 10:00 (hora de Madrid)" in es
    assert "--accent: #E30613" in es
    en = interview_guide.render_html(
        _guide(language="en"), "Acme", starts, False, date(2026, 10, 23)
    )
    assert "Interview preparation" in en and "Answer outline:" in en and "Q:" in en
    assert "Monday, 26 October 2026 · 10:00 (Madrid time)" in en


# --- Guardar --------------------------------------------------------------------------------


def test_save_prints_the_pdf_and_links_it_in_the_interview(
    session: Session, fake_pdf: list[str]
) -> None:
    job = add_applied_job(session, "Brétema Analytics")
    milestone_id = _interview(session, job, NOW + timedelta(days=3))

    result = interview_guide.save_interview_guide(
        session, milestone_id, _guide(), agent_name="codex", now=NOW
    )

    assert result.file == f"{job.id}-{milestone_id}-bretema-analytics-guia.pdf"
    assert result.sections == 3 and result.replaced is False
    assert interview_guide.guide_path(result.file).read_bytes().startswith(b"%PDF")
    [html] = fake_pdf
    assert "Brétema Analytics" in html
    view = interviews.get_interviews(session, job.id, now=NOW)
    guide = view.interviews[0].guide
    assert guide is not None and guide.file == result.file and guide.agent_name == "codex"
    assert interview_guide.guide_file(session, milestone_id).name == result.file
    stored = interview_guide.get_interview_guide(session, milestone_id)
    assert stored.guide is not None and stored.guide.sections[2].title == "Posibles preguntas"

    again = interview_guide.save_interview_guide(session, milestone_id, _guide(), now=NOW)
    assert again.replaced is True


def test_only_for_an_upcoming_interview(session: Session, fake_pdf: list[str]) -> None:
    job = add_applied_job(session, "Brétema Analytics")
    test_id = _interview(session, job, NOW + timedelta(days=3), kind="test")
    past_id = _interview(session, job, NOW - timedelta(days=1))
    for milestone_id in (test_id, past_id):
        with pytest.raises(InterviewNotAllowedError):
            interview_guide.save_interview_guide(session, milestone_id, _guide(), now=NOW)
    assert fake_pdf == []


def test_guide_file_is_404_without_guide(session: Session) -> None:
    job = add_applied_job(session, "Brétema Analytics")
    milestone_id = _interview(session, job, NOW + timedelta(days=3))
    with pytest.raises(FileNotFoundError, match="no tiene guía"):
        interview_guide.guide_file(session, milestone_id)


def test_api_serves_the_pdf_inline(fake_pdf: list[str]) -> None:
    from app.api.main import create_app
    from app.core import migrations
    from app.core.db import session_scope

    migrations.upgrade()
    with session_scope() as session:
        job = add_applied_job(session, "Brétema Analytics")
        milestone_id = _interview(session, job, datetime.now(UTC) + timedelta(days=3))
        interview_guide.save_interview_guide(session, milestone_id, _guide())
    with TestClient(create_app()) as client:
        response = client.get(f"/milestones/{milestone_id}/guide.pdf")
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["content-disposition"].startswith("inline")
        assert client.get("/milestones/999/guide.pdf").status_code == 404


def test_api_serves_the_cover_and_redoes_it_when_the_guide_changes(fake_pdf: list[str]) -> None:
    """La miniatura de la ficha: la portada en PNG, en caché, y nueva si se vuelve a preparar."""
    import pypdfium2

    from app.api.main import create_app
    from app.core import migrations
    from app.core.db import session_scope

    def real_pdf(path: Path, width: float) -> None:
        document = pypdfium2.PdfDocument.new()
        document.new_page(width, 842)
        document.save(path)
        document.close()

    migrations.upgrade()
    with session_scope() as session:
        job = add_applied_job(session, "Brétema Analytics")
        milestone_id = _interview(session, job, datetime.now(UTC) + timedelta(days=3))
        interview_guide.save_interview_guide(session, milestone_id, _guide())
        pdf = interview_guide.guide_file(session, milestone_id)
    real_pdf(pdf, 595)
    with TestClient(create_app()) as client:
        response = client.get(f"/milestones/{milestone_id}/guide.png")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.content.startswith(b"\x89PNG")
        first = client.get(f"/milestones/{milestone_id}/guide.png").content
        assert first == response.content  # de la caché
        real_pdf(pdf, 842)  # otra guía (apaisada): otra portada
        assert client.get(f"/milestones/{milestone_id}/guide.png").content != first
        assert client.get("/milestones/999/guide.png").status_code == 404


# --- Pedir cambios a una guía ya hecha ----------------------------------------------------------


def _with_guide(session: Session, fake_pdf: list[str]) -> tuple[Job, int]:
    """Una entrevista con guía, hecha cuando aún no había empezado."""
    job = add_applied_job(session, "Brétema Analytics")
    milestone_id = _interview(session, job, NOW + timedelta(days=3))
    interview_guide.save_interview_guide(session, milestone_id, _guide(), now=NOW)
    return job, milestone_id


def test_changes_are_kept_until_the_new_guide_is_saved(
    session: Session, fake_pdf: list[str]
) -> None:
    job, milestone_id = _with_guide(session, fake_pdf)
    out = interview_guide.request_correction(
        session, milestone_id, GuideCorrectionInput(instruction="  Quita el código.  ")
    )
    assert out.guide is not None and out.guide.correction == "Quita el código."
    stored = interview_guide.get_interview_guide(session, milestone_id)
    assert stored.info is not None and stored.info.correction == "Quita el código."
    assert stored.guide is not None  # el contenido sigue ahí, para aplicarlo encima

    interview_guide.save_interview_guide(session, milestone_id, _guide(), now=NOW)
    view = interviews.get_interviews(session, job.id, now=NOW)
    assert view.interviews[0].guide is not None and view.interviews[0].guide.correction is None


def test_changes_can_be_saved_after_the_interview_only_if_requested(
    session: Session, fake_pdf: list[str]
) -> None:
    _, milestone_id = _with_guide(session, fake_pdf)
    after = NOW + timedelta(days=5)
    with pytest.raises(InterviewNotAllowedError):
        interview_guide.save_interview_guide(session, milestone_id, _guide(), now=after)

    interview_guide.request_correction(
        session, milestone_id, GuideCorrectionInput(instruction="Quita el código.")
    )
    result = interview_guide.save_interview_guide(session, milestone_id, _guide(), now=after)
    assert result.replaced is True
    # Ya atendida, vuelve a la regla de siempre.
    with pytest.raises(InterviewNotAllowedError):
        interview_guide.save_interview_guide(session, milestone_id, _guide(), now=after)


def test_cancelling_keeps_the_guide(session: Session, fake_pdf: list[str]) -> None:
    _, milestone_id = _with_guide(session, fake_pdf)
    interview_guide.request_correction(
        session, milestone_id, GuideCorrectionInput(instruction="Quita el código.")
    )
    out = interview_guide.cancel_correction(session, milestone_id)
    assert out.guide is not None and out.guide.correction is None
    assert interview_guide.get_interview_guide(session, milestone_id).guide is not None
    # Cancelar lo que ya no está no falla.
    interview_guide.cancel_correction(session, milestone_id)


def test_changes_need_a_guide_and_an_open_interview(session: Session, fake_pdf: list[str]) -> None:
    job = add_applied_job(session, "Otra Empresa")
    without_guide = _interview(session, job, NOW + timedelta(days=3))
    data = GuideCorrectionInput(instruction="Quita el código.")
    with pytest.raises(InterviewNotAllowedError, match="no tiene guía"):
        interview_guide.request_correction(session, without_guide, data)

    _, milestone_id = _with_guide(session, fake_pdf)
    row = process.milestone_row(session, milestone_id)
    row.status = "cancelled"
    with pytest.raises(InterviewNotAllowedError, match="cancelada"):
        interview_guide.request_correction(session, milestone_id, data)


def test_instruction_cannot_be_blank() -> None:
    with pytest.raises(ValidationError):
        GuideCorrectionInput(instruction="   ")


# --- Versión anterior -----------------------------------------------------------------------


def _changed_guide() -> InterviewGuideInput:
    data = deepcopy(GUIDE)
    data["sections"][0]["blocks"] = [{"type": "paragraph", "text": "Más corto."}]
    return InterviewGuideInput.model_validate(data)


def _corrected(session: Session, fake_pdf: list[str]) -> tuple[Job, int]:
    """Una guía con otra versión, la que el usuario pidió cambiar."""
    job, milestone_id = _with_guide(session, fake_pdf)
    interview_guide.request_correction(
        session, milestone_id, GuideCorrectionInput(instruction="Más corto.")
    )
    interview_guide.save_interview_guide(
        session, milestone_id, _changed_guide(), now=NOW + timedelta(hours=1)
    )
    return job, milestone_id


def _current_text(session: Session, milestone_id: int) -> str:
    guide = interview_guide.get_interview_guide(session, milestone_id).guide
    assert guide is not None
    block = guide.sections[0].blocks[0]
    assert isinstance(block, ParagraphBlock)
    return block.text


def _stored(session: Session, milestone_id: int) -> dict[str, Any]:
    stored = process.milestone_row(session, milestone_id).prep_guide
    assert stored is not None
    return stored


def test_saving_keeps_only_the_previous_version(session: Session, fake_pdf: list[str]) -> None:
    _, milestone_id = _with_guide(session, fake_pdf)
    assert _stored(session, milestone_id)["previous"] is None
    for hours, guide in ((1, _changed_guide()), (2, _guide())):
        interview_guide.save_interview_guide(
            session, milestone_id, guide, now=NOW + timedelta(hours=hours)
        )

    previous = _stored(session, milestone_id)["previous"]
    assert previous["saved_at"] == (NOW + timedelta(hours=1)).isoformat()
    # Solo esa, sin encadenar más versiones y sin PDF, que se rehace al volver.
    assert set(previous) == {"saved_at", "agent_name", "guide", "instruction"}


def test_changes_say_what_was_asked_and_what_changed(session: Session, fake_pdf: list[str]) -> None:
    _, milestone_id = _corrected(session, fake_pdf)
    out = interview_guide.guide_changes(session, milestone_id)
    assert out.instruction == "Más corto."
    assert out.older_saved_at < out.newer_saved_at
    [change] = out.changes
    assert change.section == "El rol en una frase"
    assert change.removed == ["De la fuente al **insight** con `dbt`."]
    assert change.added == ["Más corto."]


def test_a_single_version_has_nothing_to_compare_or_restore(
    session: Session, fake_pdf: list[str]
) -> None:
    _, milestone_id = _with_guide(session, fake_pdf)
    with pytest.raises(FileNotFoundError, match="no tiene otra versión"):
        interview_guide.guide_changes(session, milestone_id)
    with pytest.raises(InterviewNotAllowedError, match="no tiene otra versión"):
        interview_guide.restore_guide(session, milestone_id)


def test_restoring_goes_back_and_can_be_undone(session: Session, fake_pdf: list[str]) -> None:
    _, milestone_id = _corrected(session, fake_pdf)
    printed = len(fake_pdf)

    out = interview_guide.restore_guide(session, milestone_id)
    assert out.guide is not None and out.guide.restored is True
    assert out.guide.saved_at == NOW and out.guide.other_saved_at == NOW + timedelta(hours=1)
    assert "insight" in _current_text(session, milestone_id)
    assert len(fake_pdf) == printed + 1 and "insight" in fake_pdf[-1]
    # Se sigue comparando de la antigua a la nueva, con lo que pidió el usuario.
    changes = interview_guide.guide_changes(session, milestone_id)
    assert changes.instruction == "Más corto."
    assert changes.changes[0].added == ["Más corto."]

    undone = interview_guide.restore_guide(session, milestone_id)
    assert undone.guide is not None and undone.guide.restored is False
    assert _current_text(session, milestone_id) == "Más corto."


def test_saving_after_restoring_is_the_new_latest(session: Session, fake_pdf: list[str]) -> None:
    _, milestone_id = _corrected(session, fake_pdf)
    interview_guide.restore_guide(session, milestone_id)
    interview_guide.save_interview_guide(
        session, milestone_id, _changed_guide(), now=NOW + timedelta(hours=2)
    )
    stored = _stored(session, milestone_id)
    assert not stored.get("restored")
    assert stored["previous"]["saved_at"] == NOW.isoformat()


def test_restoring_without_chromium_changes_nothing(
    session: Session, fake_pdf: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, milestone_id = _corrected(session, fake_pdf)

    def no_chromium(*_a: object, **_k: object) -> Path:
        raise PdfConverterUnavailableError("Sin Chromium.")

    monkeypatch.setattr(interview_guide, "html_to_pdf", no_chromium)
    with pytest.raises(PdfConverterUnavailableError):
        interview_guide.restore_guide(session, milestone_id)
    assert _current_text(session, milestone_id) == "Más corto."
    assert _stored(session, milestone_id).get("restored") is None


@pytest.mark.parametrize(
    ("reason", "message"), [("pending", "cambios pedidos"), ("cancelled", "cancelada")]
)
def test_restoring_is_not_allowed(
    session: Session, fake_pdf: list[str], reason: str, message: str
) -> None:
    _, milestone_id = _corrected(session, fake_pdf)
    if reason == "pending":
        interview_guide.request_correction(
            session, milestone_id, GuideCorrectionInput(instruction="Otra cosa.")
        )
    else:
        process.milestone_row(session, milestone_id).status = "cancelled"
    with pytest.raises(InterviewNotAllowedError, match=message):
        interview_guide.restore_guide(session, milestone_id)
    assert _current_text(session, milestone_id) == "Más corto."


def test_restoring_works_after_the_interview(session: Session, fake_pdf: list[str]) -> None:
    """Como pedir cambios: la guía sigue sirviendo para repasar o para la siguiente ronda."""
    _, milestone_id = _corrected(session, fake_pdf)
    process.milestone_row(session, milestone_id).starts_at = NOW - timedelta(days=5)
    interview_guide.restore_guide(session, milestone_id)
    assert "insight" in _current_text(session, milestone_id)


def test_restoring_records_no_event(session: Session, fake_pdf: list[str]) -> None:
    job, milestone_id = _corrected(session, fake_pdf)
    before = len(events.get_timeline(session, job.id).events)
    interview_guide.restore_guide(session, milestone_id)
    assert len(events.get_timeline(session, job.id).events) == before


def test_restoring_after_renaming_the_company_replaces_the_pdf(
    session: Session, fake_pdf: list[str]
) -> None:
    job, milestone_id = _corrected(session, fake_pdf)
    old_file = _stored(session, milestone_id)["file"]
    assert job.company_id is not None
    company = session.get(Company, job.company_id)
    assert company is not None
    company.name = "Nombre Nuevo"

    interview_guide.restore_guide(session, milestone_id)

    new_file = _stored(session, milestone_id)["file"]
    assert new_file != old_file and "nombre-nuevo" in new_file
    assert interview_guide.guide_path(new_file).is_file()
    assert not interview_guide.guide_path(old_file).exists()


def test_a_guide_saved_before_versions_still_works(session: Session, fake_pdf: list[str]) -> None:
    _, milestone_id = _with_guide(session, fake_pdf)
    row = process.milestone_row(session, milestone_id)
    assert row.prep_guide is not None
    row.prep_guide = {
        key: row.prep_guide[key] for key in ("file", "saved_at", "agent_name", "guide")
    }
    info = interview_guide.get_interview_guide(session, milestone_id).info
    assert info is not None and info.other_saved_at is None and info.restored is False

    interview_guide.save_interview_guide(
        session, milestone_id, _changed_guide(), now=NOW + timedelta(hours=1)
    )
    assert interview_guide.guide_changes(session, milestone_id).instruction is None
    interview_guide.restore_guide(session, milestone_id)
    assert "insight" in _current_text(session, milestone_id)


def test_diff_ignores_what_is_not_text() -> None:
    assert guide_diff.diff(_guide(), _guide(accent_color="#123456")) == []


def test_diff_of_guides() -> None:
    old = _guide()
    data = deepcopy(GUIDE)
    data["title"] = "Analytics Engineer"
    data["sections"].reverse()
    data["sources"] = []
    changes = guide_diff.diff(old, InterviewGuideInput.model_validate(data))
    assert [(c.part, c.section, c.reordered) for c in changes] == [
        ("cover", None, False),
        ("section", None, True),
        ("sources", None, False),
    ]
    assert changes[0].removed == ["Data Engineer"]
    assert changes[0].added == ["Analytics Engineer"]
    assert guide_diff.diff(old, old) == []


def test_diff_covers_every_block_type() -> None:
    """Cada tipo de bloque se compara: si se quita la guía entera de una sección, salen todos."""
    empty = deepcopy(GUIDE)
    for section in empty["sections"]:
        section["blocks"] = [{"type": "paragraph", "text": "Nada."}]
    changes = guide_diff.diff(_guide(), InterviewGuideInput.model_validate(empty))
    removed = [text for change in changes for text in change.removed]
    for text in (
        "Técnicas",
        "ELT: con Airflow.",
        "Pregunta | ¿Llega el dato? | ¿Qué pasará?",
        "¿Un pipeline en producción? — Historia st-migracion. — No inventes volúmenes.",
        "No has usado ClickHouse.",
        "SQL: SELECT 1;",
    ):
        assert text in removed


def test_api_changes_and_restore(fake_pdf: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.main import create_app
    from app.core import migrations
    from app.core.db import session_scope

    migrations.upgrade()
    with session_scope() as session:
        job = add_applied_job(session, "Brétema Analytics")
        milestone_id = _interview(session, job, datetime.now(UTC) + timedelta(days=3))
        interview_guide.save_interview_guide(session, milestone_id, _guide())
    with TestClient(create_app(), raise_server_exceptions=False) as client:
        changes = f"/milestones/{milestone_id}/guide/changes"
        restore = f"/milestones/{milestone_id}/guide/restore"
        assert client.get(changes).status_code == 404
        assert client.post(restore).status_code == 403
        assert client.get("/milestones/999/guide/changes").status_code == 404
        assert client.post("/milestones/999/guide/restore").status_code == 404

        with session_scope() as session:
            interview_guide.save_interview_guide(session, milestone_id, _changed_guide())
        body = client.get(changes).json()
        assert body["changes"][0]["added"] == ["Más corto."]

        restored = client.post(restore)
        assert restored.status_code == 200
        assert restored.json()["guide"]["restored"] is True
        assert restored.json()["guide"]["other_saved_at"] is not None

        def no_chromium(*_a: object, **_k: object) -> Path:
            raise PdfConverterUnavailableError("Sin Chromium.")

        monkeypatch.setattr(interview_guide, "html_to_pdf", no_chromium)
        response = client.post(restore)
        assert response.status_code == 503
        assert response.json()["error"]["type"] == "pdf_unavailable"
