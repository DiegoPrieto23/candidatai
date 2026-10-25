"""Eval de CV (fase 12.2): casos, comprobaciones y `cai eval cv`."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from app import cli
from app.core.db import session_scope
from app.schemas.cv import CvContent, CvRenderOptions, CvVerification
from app.services import demo, events
from app.services.demo_text import posting_text
from app.services.documents import pdf
from app.services.documents import service as cv_service
from app.services.evals import cv as cv_eval
from app.services.pipeline import Stage
from app.services.profile import EXAMPLE_PATH, load_from_yaml
from tests.cv_support import fake_converter

runner = CliRunner()
NOW = datetime(2026, 10, 5, 9, 30, tzinfo=UTC)


def _case(case_id: str = "cv01-de-snowflake") -> cv_eval.CvEvalCase:
    return next(c for c in cv_eval.load_cases() if c.id == case_id)


def _content(**changes: Any) -> CvContent:
    """Un CV correcto para `cv01-de-snowflake` (Python, SQL, Snowflake; valora Power BI)."""
    data: dict[str, Any] = {
        "language": "es",
        "subtitle": "Data Engineer · Python · SQL · Snowflake",
        "summary": "Data Engineer con tres años de pipelines ETL en Python sobre Snowflake.",
        "experience": [
            {
                "experience_id": "exp-norteconsulting",
                "bullets": [
                    {
                        "text": "Migré 40 procesos ETL de SSIS a Python sobre Snowflake.",
                        "evidence": ["exp-norteconsulting/a1"],
                    }
                ],
            },
            {
                "experience_id": "exp-datagal",
                "bullets": [
                    {
                        "text": "Automaticé informes semanales en Power BI.",
                        "evidence": ["exp-datagal/a1"],
                    }
                ],
            },
        ],
        "skills": [
            {"group": "Lenguajes", "items": ["Python", "SQL"]},
            {"group": "Datos", "items": ["Snowflake", "ETL", "Power BI"]},
        ],
        "education_ids": ["edu-grado"],
        "languages": [{"language": "Español", "level": "Nativo"}],
        "keywords_targeted": ["Python", "SQL", "Snowflake"],
    }
    data.update(changes)
    return CvContent.model_validate(data)


def _check(
    content: CvContent, pages: int | None = 1, passed: bool = True, case: str = "cv01-de-snowflake"
) -> dict[str, cv_eval.CheckResult]:
    results = cv_eval.check_cv(
        _case(case), content, load_from_yaml(EXAMPLE_PATH), pages, {"passed": passed}
    )
    return {r.name: r for r in results}


# --- Casos ---------------------------------------------------------------------------------


def test_cases_file_has_ten_valid_cases() -> None:
    cases = cv_eval.load_cases()
    assert len(cases) == 10
    assert len({c.id for c in cases}) == 10
    assert all(c.expect.keywords for c in cases)


def test_invalid_cases_file(tmp_path: Path) -> None:
    path = tmp_path / "casos.jsonl"
    path.write_text('{"id": "x"}\n', encoding="utf-8")
    with pytest.raises(cv_eval.CvEvalFileError, match="línea 1: job: Campo obligatorio"):
        cv_eval.load_cases(path)


# --- Comprobaciones ------------------------------------------------------------------------


def test_a_good_cv_passes_every_check() -> None:
    results = _check(_content())
    assert {name: r.passed for name, r in results.items()} == dict.fromkeys(cv_eval.CHECKS, True)


def test_invented_evidence_fails() -> None:
    content = _content()
    content.experience[0].bullets[0].evidence = ["exp-norteconsulting/a9"]
    result = _check(content)["evidence"]
    assert result.passed is False
    assert "exp-norteconsulting/a9" in (result.detail or "")


def test_two_pages_fails_and_no_pdf_is_not_measured() -> None:
    assert _check(_content(), pages=2)["one_page"].passed is False
    assert _check(_content(), pages=None)["one_page"].passed is None


def test_layout_warnings_fail_the_layout_check() -> None:
    # Fase 25.5: los avisos de maquetación del render que se enviaría; los demás no cuentan.
    profile = load_from_yaml(EXAMPLE_PATH)
    case, content = _case("cv01-de-snowflake"), _content()

    def layout(warnings: list[dict[str, object]] | None, pages: int | None = 1) -> object:
        results = cv_eval.check_cv(
            case, content, profile, pages, {"passed": True}, warnings=warnings
        )
        return next(r for r in results if r.name == "layout")

    assert layout([{"code": "pdf_only", "message": "Solo PDF."}]).passed is True
    hole = layout([{"code": "large_gap", "message": "Hay un hueco.", "page": 1}])
    assert hole.passed is False and hole.detail == "Hay un hueco."
    assert layout(None, pages=None).passed is None  # sin PDF: no se mide


def test_low_coverage_fails() -> None:
    content = _content(
        subtitle="Data Engineer",
        summary="Data Engineer con tres años de experiencia.",
        skills=[{"group": "Lenguajes", "items": ["Python"]}],
    )
    content.experience = content.experience[1:]  # sin el bullet de Snowflake y SQL
    result = _check(content)["coverage"]
    assert result.passed is False
    assert "Snowflake" in (result.detail or "")


def test_unrequested_basic_skill_fails() -> None:
    content = _content(
        skills=[{"group": "Datos", "items": ["Python", "SQL", "Snowflake", "Docker"]}]
    )
    result = _check(content)["basic_skills"]
    assert result.passed is False
    assert "Docker" in (result.detail or "")
    # En un caso que sí pide Docker, puede salir.
    assert _check(content, case="cv05-de-orquestacion")["basic_skills"].passed is True


def test_invented_and_forbidden_skills_fail() -> None:
    content = _content(
        skills=[{"group": "Datos", "items": ["Python", "SQL", "Snowflake", "Spark"]}]
    )
    result = _check(content)["skills"]
    assert result.passed is False
    assert "no están en el perfil: Spark" in (result.detail or "")
    assert "no las tiene y aparecen: Spark" in (result.detail or "")


def test_language_and_verification() -> None:
    results = _check(_content(), passed=False, case="cv07-english")
    assert results["language"].passed is False
    assert results["verified"].passed is False


# --- Sobre la demo -------------------------------------------------------------------------


@pytest.fixture
def demo_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(pdf, "converter_name", lambda: "Conversor de prueba")
    monkeypatch.setattr(pdf, "get_converter", lambda: fake_converter())
    target = tmp_path / "data-demo"
    demo.seed(target, now=NOW, eval_cv=True)
    return target


def test_eval_cv_on_the_demo(demo_dir: Path) -> None:
    with demo.use_data_dir(demo_dir), session_scope() as session:
        report = cv_eval.evaluate(session)
        assert report.pending == 10
        assert {c.status for c in report.cases} == {"pending"}
        job_id = report.cases[0].job_id
        assert job_id is not None
        assert events.current_stage(session, job_id) == Stage.APPROVED

        saved = cv_service.save_content(
            session, job_id, _content(), CvRenderOptions(template_id="ats-simple"), "claude-code"
        )
        cv_service.save_verification(
            session, saved.document_id, CvVerification(passed=True), "claude-code"
        )

    with demo.use_data_dir(demo_dir), session_scope() as session:
        report = cv_eval.evaluate(session)
        first = report.cases[0]
        assert (first.status, first.agent_name) == ("passed", "claude-code")
        assert (report.evaluated, report.passed, report.pending) == (1, 1, 9)
        assert report.checks_passed["evidence"] == 1
        # Otro agente aún no ha hecho ninguno.
        assert cv_eval.evaluate(session, agent="codex").evaluated == 0
        markdown = cv_eval.to_markdown(report)
        assert "| `cv01-de-snowflake` | pasa | claude-code |" in markdown


def _save_cv(session: Session, job_id: int, agent: str, passed: bool = True) -> int:
    saved = cv_service.save_content(
        session, job_id, _content(), CvRenderOptions(template_id="ats-simple"), agent
    )
    verification = CvVerification(passed=passed)
    cv_service.save_verification(session, saved.document_id, verification, agent)
    return saved.document_id


def test_adding_eval_cases_again_keeps_what_the_agent_did(demo_dir: Path) -> None:
    with demo.use_data_dir(demo_dir), session_scope() as session:
        job_id = cv_eval.evaluate(session).cases[0].job_id
        assert job_id is not None
        document_id = _save_cv(session, job_id, "claude-code")
        before = len(events.get_timeline(session, job_id).events)

    summary = demo.seed(demo_dir, eval_cv=True)  # sin --force: solo añade lo que falte
    assert summary.jobs == 75

    with demo.use_data_dir(demo_dir), session_scope() as session:
        assert events.current_stage(session, job_id) == Stage.CV_READY
        assert len(events.get_timeline(session, job_id).events) == before
        assert cv_service.latest_document(session, job_id).id == document_id  # type: ignore[union-attr]


def test_agent_filter_picks_that_agents_cv_and_missing_cases(demo_dir: Path) -> None:
    with demo.use_data_dir(demo_dir), session_scope() as session:
        job_id = cv_eval.evaluate(session).cases[0].job_id
        assert job_id is not None
        _save_cv(session, job_id, "codex", passed=False)
        _save_cv(session, job_id, "claude-code")

    with demo.use_data_dir(demo_dir), session_scope() as session:
        # El último es de claude-code; con --agent codex se mide el de codex, aunque sea anterior.
        assert cv_eval.evaluate(session).cases[0].status == "passed"
        codex = cv_eval.evaluate(session, agent="codex").cases[0]
        assert (codex.status, codex.agent_name) == ("failed", "codex")
        unknown = cv_eval.CvEvalCase.model_validate(
            {**_case().model_dump(mode="json"), "id": "cv99-sin-alta"}
        )
        assert cv_eval.evaluate(session, cases=[unknown]).cases[0].status == "missing"


def test_a_case_that_fails_the_hard_filters_is_a_file_error(demo_dir: Path) -> None:
    data = _case().model_dump(mode="json")
    data["id"] = "cv99-senior"
    data["job"]["company"] = "Empresa de prueba"
    data["extraction"]["seniority"] = "lead"
    with (
        demo.use_data_dir(demo_dir),
        pytest.raises(cv_eval.CvEvalFileError, match="cv99-senior"),
        session_scope() as session,
    ):
        cv_eval.add_cases(session, [cv_eval.CvEvalCase.model_validate(data)])


def test_unrequested_basic_skill_in_the_summary_fails() -> None:
    result = _check(_content(summary="Data Engineer con Python, Snowflake y Docker."))
    assert result["basic_skills"].passed is False
    assert "Docker" in (result["basic_skills"].detail or "")


def test_eval_cv_outside_the_demo_is_refused(session) -> None:  # noqa: ANN001
    with pytest.raises(cv_eval.CvEvalNotDemoError):
        cv_eval.evaluate(session)


def test_cli_eval_cv(demo_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAI_DATA_DIR", str(demo_dir))
    from app.core.config import get_settings
    from app.core.db import get_engine

    get_settings.cache_clear()
    get_engine.cache_clear()
    result = runner.invoke(cli.app, ["eval", "cv"])
    assert result.exit_code == 0, result.output
    assert "evaluados 0, pasan 0, pendientes 10" in result.stdout
    as_json = runner.invoke(cli.app, ["eval", "cv", "--json", "--agent", "codex"])
    out = json.loads(as_json.stdout)
    assert out["agent"] == "codex"
    assert len(out["report_paths"]) == 2


# --- Matriz de compatibilidad (fase 12.3) ----------------------------------------------------


def test_compat_cases_enter_with_text_only(demo_dir: Path) -> None:
    ids = [c.id for c in cv_eval.load_compat_cases()]
    assert len(ids) == 5
    target = demo_dir.parent / "otra-demo"
    demo.seed(target, now=NOW, compat=True)
    with demo.use_data_dir(target), session_scope() as session:
        report = cv_eval.evaluate(session)
        compat = [c for c in report.cases if c.id in ids]
        assert {c.status for c in compat} == {"pending"}
        for case in compat:
            assert case.job_id is not None
            assert events.current_stage(session, case.job_id) == Stage.PENDING_EXTRACTION
        # Los demás casos del eval de CV no se dan de alta sin --eval-cv.
        assert {c.status for c in report.cases if c.id not in ids} == {"missing"}


def test_compat_file_with_unknown_case(tmp_path: Path) -> None:
    path = tmp_path / "jobs.txt"
    path.write_text("# comentario\ncv01-de-snowflake\ncv99-no-existe\n", encoding="utf-8")
    with pytest.raises(cv_eval.CvEvalFileError, match="cv99-no-existe"):
        cv_eval.load_compat_cases(path)


def test_posting_text_follows_the_posting_language() -> None:
    english = _case("cv07-english")
    text = posting_text("Data Engineer", "Caiño Analytics", "retail", "Europa", english.extraction)
    assert "Requirements" in text
    assert "fully remote" in text
    assert "- Experience with Snowflake." in text
    spanish = posting_text("Data Engineer", "X", "retail", "Vigo", _case().extraction)
    assert "Requisitos" in spanish
    assert "de nivel intermedio" in spanish
