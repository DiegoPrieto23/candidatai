"""Cartas de presentación (fase 08c.1): indicaciones, contenido, verificación, render y texto."""

import copy
from collections.abc import Callable
from typing import Any

import pytest
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Document, DocumentRender, Event, Job
from app.schemas.cover_letter import CoverLetterBriefInput, CoverLetterContent
from app.schemas.cover_letter import CoverLetterRenderOptions as Options
from app.schemas.cv import CvRenderOptions, CvVerification, VerificationIssue
from app.services import events, extractions, profile
from app.services.documents import cover_letter as letter
from app.services.documents import pdf, service, templates
from app.services.documents.options import InvalidRenderOptionsError
from app.services.pipeline import InvalidTransitionError, Stage
from tests.cv_support import LETTER, demo_content, fake_converter, write_template
from tests.matching_support import demo_extraction

PASSED = CvVerification(passed=True, issues=[])


def letter_data(**changes: Any) -> dict[str, Any]:
    data = copy.deepcopy(LETTER)
    data.update(changes)
    return data


def content(**changes: Any) -> CoverLetterContent:
    return CoverLetterContent.model_validate(letter_data(**changes))


def paragraph(text: str, *evidence: str) -> dict[str, Any]:
    return {"text": text, "evidence": list(evidence)}


@pytest.fixture(autouse=True)
def converter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin LibreOffice: un conversor falso que escribe el texto del DOCX en un PDF mínimo."""
    monkeypatch.setattr(pdf, "get_converter", lambda: fake_converter())


@pytest.fixture
def approved_job(session: Session, make_job: Callable[..., Job]) -> Job:
    """Oferta aprobada con la extracción demo y el perfil demo (con `preferences.cover_letter`)."""
    profile.import_profile(session, profile.EXAMPLE_PATH)
    job = make_job("Data Engineer")
    job.location_raw = "Santiago de Compostela"
    events.record(session, job.id, "found", "system")
    extractions.save_extraction(session, job.id, demo_extraction())
    events.record(session, job.id, "approved", "user")
    session.flush()
    return job


def import_profile_without_letter_prefs(session: Session, tmp_path: Any) -> None:
    data = yaml.safe_load(profile.EXAMPLE_PATH.read_text(encoding="utf-8"))
    data["preferences"].pop("cover_letter")
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    assert profile.import_profile(session, path).created


def letter_events(session: Session, job: Job) -> list[Event]:
    stmt = select(Event).where(Event.job_id == job.id, Event.type.like("cover_letter_%"))
    return list(session.scalars(stmt.order_by(Event.id)))


def issues_of(exc: pytest.ExceptionInfo[letter.CoverLetterContentError]) -> list[tuple[str, str]]:
    return [(i.field, i.received or "") for i in exc.value.issues]


# --- Guardar --------------------------------------------------------------------------------


def test_save_stores_document_with_instructions_and_first_render(
    session: Session, approved_job: Job
) -> None:
    letter.save_brief(
        session,
        approved_job.id,
        CoverLetterBriefInput(instructions="Menciona que uso su producto desde 2023."),
    )
    result = letter.save_cover_letter(session, approved_job.id, content(), agent_name="codex")

    doc = session.get(Document, result.document_id)
    assert doc is not None and doc.kind == "cover_letter" and not doc.edited_by_user
    used = doc.content["instructions"]
    assert used["brief"]["instructions"] == "Menciona que uso su producto desde 2023."
    assert used["preferences"]["tone"] == "cercano y directo"
    assert used["max_words"] == 170  # perfil demo; el brief no pone límite
    assert result.word_count == letter.word_count(content())

    (event,) = letter_events(session, approved_job)
    assert event.type == "cover_letter_generated" and event.actor == "agent"
    assert event.agent_name == "codex"
    assert event.payload == {"document_id": doc.id, "edited_by_user": False}
    assert events.current_stage(session, approved_job.id) == Stage.APPROVED


def test_rejects_unknown_evidence_user_without_instructions_and_too_many_words(
    session: Session, approved_job: Job, tmp_path: Any
) -> None:
    import_profile_without_letter_prefs(session, tmp_path)
    long_text = " ".join(["palabra"] * 181)
    bad = content(
        paragraphs=[
            paragraph("Lideré la migración a la nube.", "exp-inventada/a9"),
            paragraph("Uso vuestro producto desde 2023.", "user"),
            paragraph(long_text, "exp-norteconsulting"),
        ]
    )
    with pytest.raises(letter.CoverLetterContentError) as exc:
        letter.save_cover_letter(session, approved_job.id, bad)
    assert issues_of(exc) == [
        ("paragraphs[0].evidence[0]", "exp-inventada/a9"),
        ("paragraphs[1].evidence[0]", "user"),
        ("paragraphs", str(letter.word_count(bad))),
    ]
    assert session.scalars(select(Document).where(Document.kind == "cover_letter")).all() == []
    assert letter_events(session, approved_job) == []


def test_offer_instructions_win_over_profile(session: Session, approved_job: Job) -> None:
    info = letter.get_cover_letter(session, job_id=approved_job.id)
    assert info.max_words == 170 and info.letter is None  # perfil demo
    saved = letter.save_brief(
        session, approved_job.id, CoverLetterBriefInput(instructions="Breve.", max_words=60)
    )
    assert saved.max_words == 60
    # 61 palabras: valen con el perfil (170), no con la oferta (60).
    with pytest.raises(letter.CoverLetterContentError) as exc:
        letter.save_cover_letter(
            session,
            approved_job.id,
            content(paragraphs=[paragraph(" ".join(["dato"] * 61), "exp-norteconsulting")]),
        )
    assert issues_of(exc) == [("paragraphs", "61")]


def test_max_words_falls_back_to_policies(
    session: Session, approved_job: Job, tmp_path: Any
) -> None:
    import_profile_without_letter_prefs(session, tmp_path)
    assert letter.get_cover_letter(session, job_id=approved_job.id).max_words == 180


def test_skills_out_of_profile_and_basic_not_requested(
    session: Session, approved_job: Job, make_job: Callable[..., Job]
) -> None:
    job = make_job("Data Engineer")
    events.record(session, job.id, "found", "system")
    must = ["Python", "SQL", "Kafka"]
    extraction = demo_extraction(must_have_skills=must, nice_to_have_skills=[])
    extractions.save_extraction(session, job.id, extraction)
    events.record(session, job.id, "approved", "user")
    bad = content(
        paragraphs=[
            paragraph("He trabajado con Kafka y con Airflow en producción.", "exp-datagal"),
            # Hablar del puesto citando la oferta sí vale.
            paragraph("Vuestro equipo trabaja con Kafka.", "extraction"),
            # Citar la oferta junto al perfil no vale: se la estaría atribuyendo.
            paragraph("Llevo tres años con Kafka.", "extraction", "exp-datagal"),
        ],
        keywords_targeted=["Python", "Kafka", "Docker"],
    )
    with pytest.raises(letter.CoverLetterContentError) as exc:
        letter.save_cover_letter(session, job.id, bad)
    assert issues_of(exc) == [
        ("keywords_targeted[1]", "Kafka"),
        ("keywords_targeted[2]", "Docker"),  # básica y ya no la pide la oferta
        ("paragraphs[0]", "Kafka"),
        ("paragraphs[0]", "Apache Airflow"),
        ("paragraphs[2]", "Kafka"),
    ]


def test_only_in_approved_or_cv_ready(session: Session, approved_job: Job) -> None:
    events.record(session, approved_job.id, "applied_manually", "user")
    with pytest.raises(InvalidTransitionError):
        letter.save_cover_letter(session, approved_job.id, content())


# --- Render ---------------------------------------------------------------------------------


def sin_carta() -> None:
    """Plantilla de CV del usuario sin diseño de carta (copia del CV de `ats-simple`)."""
    write_template(
        get_settings().user_templates_dir,
        "sin-carta",
        templates.BUILTIN_TEMPLATES_DIR / "ats-simple" / "template.docx",
    )


def test_without_cv_uses_profile_rules(session: Session, approved_job: Job) -> None:
    render = letter.save_cover_letter(session, approved_job.id, content()).render
    # Perfil demo: `clasica-foto` por defecto, que trae su carta (08c.2).
    assert render.template_id == "clasica-foto" and not render.options.letter_fallback
    assert render.options.template_source == "default_template"
    assert render.options.cv_render_id is None and render.warnings == []
    assert render.options.accent_color == "#1F4E79"
    assert render.pages == 1 and render.selected
    assert render.pdf_path.endswith(f"/{render.render_id}/Carta-Lucia-Varela-Otero.pdf")
    assert render.docx_path and render.docx_path.startswith(f"cvs/{approved_job.id}/")
    assert (get_settings().data_dir / render.pdf_path).is_file()
    # Los renders no registran eventos.
    assert [e.type for e in letter_events(session, approved_job)] == ["cover_letter_generated"]


def test_cv_template_without_letter_falls_back_to_carta_simple(
    session: Session, approved_job: Job
) -> None:
    sin_carta()
    cv = service.save_content(session, approved_job.id, demo_content())
    chosen = service.render(session, cv.document_id, CvRenderOptions(template_id="sin-carta"))
    service.select_render(session, chosen.render_id)
    render = letter.save_cover_letter(session, approved_job.id, content()).render
    assert render.template_id == "carta-simple"
    assert render.options.base_template_id == "sin-carta"
    assert render.options.template_source == "cv" and render.options.letter_fallback
    assert [w.code for w in render.warnings] == ["letter_fallback"]
    assert render.options.accent_color == "#1F4E79"  # `sin-carta` no tiene color: el suyo


def test_matches_selected_cv_render_color(session: Session, approved_job: Job) -> None:
    cv = service.save_content(session, approved_job.id, demo_content())
    green = service.render(session, cv.document_id, CvRenderOptions(accent_color="#2E5E4E"))
    service.select_render(session, green.render_id)

    render = letter.save_cover_letter(session, approved_job.id, content()).render
    assert render.options.template_source == "cv"
    assert render.options.cv_render_id == green.render_id
    assert render.options.accent_color == "#2E5E4E"  # `carta-simple` admite cualquier color

    docx = get_settings().data_dir / (render.docx_path or "")
    assert b"2E5E4E" in _document_xml(docx)


def _document_xml(docx: Any) -> bytes:
    import zipfile

    with zipfile.ZipFile(docx) as z:
        return z.read("word/document.xml")


def test_template_with_letter_is_used_and_options_validated(
    session: Session, approved_job: Job
) -> None:
    builtin = templates.BUILTIN_TEMPLATES_DIR
    folder = write_template(
        get_settings().user_templates_dir,
        "con-carta",
        builtin / "ats-simple" / "template.docx",
        letter={"file": "letter.docx"},
    )
    (folder / "letter.docx").write_bytes((builtin / "carta-simple" / "letter.docx").read_bytes())
    doc = letter.save_cover_letter(session, approved_job.id, content()).document_id
    render = letter.render_cover_letter(session, doc, Options(template_id="con-carta"))
    assert render.template_id == "con-carta" and not render.options.letter_fallback
    assert render.options.template_source == "option"
    sin_carta()
    with pytest.raises(templates.TemplateNotFoundError, match="diseño de carta"):
        letter.render_cover_letter(session, doc, Options(template_id="sin-carta"))
    with pytest.raises(InvalidRenderOptionsError):
        # `con-carta` no declara color de acento: no admite uno.
        letter.render_cover_letter(
            session, doc, Options(template_id="con-carta", accent_color="#123456")
        )


def test_too_long_when_more_than_one_page(
    session: Session, approved_job: Job, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(pdf, "get_converter", lambda: fake_converter(lines_per_page=3))
    render = letter.save_cover_letter(session, approved_job.id, content()).render
    assert "too_long" in [w.code for w in render.warnings]
    assert render.pages > 1 and not render.selected


def test_select_render(session: Session, approved_job: Job) -> None:
    saved = letter.save_cover_letter(session, approved_job.id, content())
    other = letter.render_cover_letter(session, saved.document_id, Options(accent_color="#7A2E39"))
    assert not other.selected
    assert letter.select_render(session, other.render_id).selected
    rows = session.scalars(
        select(DocumentRender).where(DocumentRender.document_id == saved.document_id)
    )
    assert [r.selected for r in rows] == [False, True]


def test_carta_simple_is_not_a_cv_template() -> None:
    cv_ids = [t.id for t in templates.list_templates()[0]]
    assert "carta-simple" not in cv_ids
    assert "carta-simple" in [t.id for t in templates.list_templates(kind="letter")[0]]
    with pytest.raises(templates.TemplateNotFoundError, match="de CV"):
        templates.get("carta-simple")
    templates.validate("carta-simple", kind="letter")
    # `jh templates validate` acepta también las de solo carta.
    from app.services.documents import authoring

    assert authoring.validate("carta-simple").template_id == "carta-simple"


# --- Ver, verificar, editar y texto ---------------------------------------------------------


def test_get_cover_letter_resolves_evidence(session: Session, approved_job: Job) -> None:
    saved = letter.save_cover_letter(session, approved_job.id, content())
    info = letter.get_cover_letter(session, document_id=saved.document_id)
    assert info.job_id == approved_job.id and info.letter is not None
    view = info.letter
    assert view.evidence["extraction"] == "La oferta (su extracción)"
    assert view.evidence["user"] == "Tus indicaciones para la carta"
    assert view.evidence["st-migracion"].startswith("Historia «Migración de SSIS")
    assert view.verification is None and len(view.renders) == 1


def test_verification_records_event_without_stage_change(
    session: Session, approved_job: Job
) -> None:
    saved = letter.save_cover_letter(session, approved_job.id, content())
    failed = CvVerification(
        passed=False,
        issues=[VerificationIssue(severity="blocker", location="p2", problem="Cifra inflada")],
    )
    assert not letter.save_verification(session, saved.document_id, failed).passed
    letter.save_verification(session, saved.document_id, PASSED, agent_name="claude-code")
    *_, event = letter_events(session, approved_job)
    assert event.type == "cover_letter_verified"
    assert event.payload == {"document_id": saved.document_id, "passed": True, "blockers": 0}
    assert letter_events(session, approved_job)[1].payload["blockers"] == 1
    assert events.current_stage(session, approved_job.id) == Stage.APPROVED


def test_user_edit_creates_unverified_document(session: Session, approved_job: Job) -> None:
    first = letter.save_cover_letter(session, approved_job.id, content())
    letter.save_verification(session, first.document_id, PASSED)
    edited = letter.save_user_letter(session, approved_job.id, content(greeting="Hola:"))
    doc = session.get(Document, edited.document_id)
    assert doc is not None and doc.edited_by_user and doc.verification is None
    assert session.get(Document, first.document_id) is not None
    *_, event = letter_events(session, approved_job)
    assert event.actor == "user" and event.payload["edited_by_user"] is True
    info = letter.get_cover_letter(session, job_id=approved_job.id)
    assert info.letter is not None and info.letter.document_id == edited.document_id
    # Siguen las comprobaciones del código.
    with pytest.raises(letter.CoverLetterContentError):
        letter.save_user_letter(
            session, approved_job.id, content(paragraphs=[paragraph("Hola.", "exp-x")])
        )


def test_plain_text_keeps_accents_and_windows_line_breaks(
    session: Session, approved_job: Job
) -> None:
    saved = letter.save_cover_letter(session, approved_job.id, content())
    text = letter.plain_text(session, saved.document_id)
    assert text.startswith("Hola, equipo de Acme:\r\n\r\nOs escribo por el puesto")
    assert "migré" in text and "\n" not in text.replace("\r\n", "")
    assert text.endswith("Un saludo,\r\nLucía Varela Otero\r\n")
    assert text.encode("utf-8").decode("utf-8") == text


def test_word_count_counts_body_only() -> None:
    assert letter.word_count(content(paragraphs=[paragraph("Uno, dos-tres  C++.", "user")])) == 4
