"""Guía de preparación de una entrevista en PDF: contenido estructurado del agente,
maquetado y escapado por la app, guardado en el hito y servido a la ficha."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models import Job
from app.schemas.interview_guide import InterviewGuideInput
from app.services import interview_guide, interviews, process
from app.services.interviews import InterviewNotAllowedError
from tests.replies_support import APPLIED, NOW, add_applied_job

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
