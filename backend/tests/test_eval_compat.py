"""Matriz automatizada (fase 24.6): `cai eval compat` recorre el flujo entero con un agente falso
(sin red ni LLM), mide y escribe el resultado y el informe; con un paso sin segundo plano, da los
pasos manuales y `--import` completa la medida."""

import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select

from app import cli
from app.core.db import session_scope
from app.models import AgentRun, SkillGapMark
from app.models.base import utcnow
from app.schemas.cv import CvRenderOptions, CvVerification
from app.schemas.llm_io import FitAssessment, JobExtraction
from app.services import agent_launch, agent_runner, demo, extractions
from app.services.agent_launch import Headless, _Launcher
from app.services.documents import pdf
from app.services.documents import service as cv_service
from app.services.evals import compat
from app.services.evals import cv as cv_eval
from app.services.matching import service as matching
from tests.agent_support import runner
from tests.cv_support import fake_converter
from tests.test_eval_cv import _content

FAKE_AGENT = Path(__file__).parent / "fixtures" / "fake_agent.py"


@pytest.fixture
def agent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Claude Code «instalado», con segundo plano; resultados e informe en `tmp_path`."""
    launcher = _Launcher(
        "claude",
        ["claude", "{prompt}"],
        ["ANTHROPIC_API_KEY"],
        [],
        Headless(
            [sys.executable, str(FAKE_AGENT), "{prompt}", "{denied_tools}", "{allowed_tools}"],
            ["Agent"],
            "Skill({skill})",
            "claude-stream-json",
            "mcp__candidatai__",
        ),
    )
    real_which = agent_launch.shutil.which
    monkeypatch.setattr(agent_launch, "_launchers", lambda: [launcher])
    monkeypatch.setattr(
        agent_launch.shutil,
        "which",
        lambda name: real_which(name) if Path(name).is_absolute() else f"C:/bin/{name}.exe",
    )
    monkeypatch.setattr(pdf, "converter_name", lambda: "Conversor de prueba")
    monkeypatch.setattr(pdf, "get_converter", lambda: fake_converter())
    monkeypatch.setattr(compat, "RESULTS_DIR", tmp_path / "results")
    monkeypatch.setattr(compat, "REPORT_PATH", tmp_path / "REPORT.md")
    monkeypatch.setattr(agent_runner, "FLUSH_SECONDS", 0.1)
    monkeypatch.setattr(agent_runner, "RESULT_GRACE_SECONDS", 1.0)


CASES = {c.id: c for c in cv_eval.load_compat_cases()}


def fake_execute(timeout: float | None) -> None:
    """Un agente «perfecto» en el mismo proceso: hace lo que pide cada acción con los servicios y
    deja la ejecución terminada con su uso. Se equivoca a propósito en un campo de un caso."""
    run = agent_runner.claim_next()
    assert run is not None, "no había nada en cola"
    with session_scope() as session:
        by_job = {job_id: case for case, job_id in compat._case_jobs(session).items() if job_id}
        if run.action == "process-jobs":
            for job_id, case_id in by_job.items():
                data = CASES[case_id].extraction.model_dump()
                if case_id == "cv09-etl-migracion":
                    data["title_normalized"] = "Desarrollador/a ETL"
                extractions.save_extraction(
                    session, job_id, JobExtraction.model_validate(data), agent_name="claude"
                )
        elif run.action == "assess-fit":
            for job_id in by_job:
                assessment = FitAssessment(
                    verdict="strong", rationale="Encaja.", risks=[], questions_for_user=[]
                )
                matching.save_fit_assessment(session, job_id, assessment, "claude")
        elif run.action == "generate-cv":
            assert run.job_id is not None
            saved = cv_service.save_content(
                session, run.job_id, _content(), CvRenderOptions(template_id="ats-simple"), "claude"
            )
            cv_service.save_verification(
                session, saved.document_id, CvVerification(passed=True), "claude"
            )
    usage = {"num_turns": 3, "input_tokens": 1000, "output_tokens": 200, "total_cost_usd": 0.0}
    agent_runner._save(run.id, status="done", result="Hecho.", usage=usage, finished_at=utcnow())


@pytest.fixture
def target(tmp_path: Path) -> Iterator[Path]:
    yield tmp_path / "data-demo-compat-claude-default"


def test_full_flow_with_fake_agent(agent: None, target: Path) -> None:
    messages: list[str] = []
    result = compat.run("claude", target=target, execute=fake_execute, progress=messages.append)

    assert [(s.action, s.mode) for s in result.steps] == [
        ("process-jobs", "background"),
        ("assess-fit", "background"),
        ("generate-cv", "background"),
    ]
    assert [len(s.runs) for s in result.steps] == [1, 1, 5]
    assert all(r.status == "done" for s in result.steps for r in s.runs)
    assert (result.fields_equal, result.fields_total) == (54, 55)
    assert [s.different for s in result.extraction if s.different] == [["title_normalized"]]
    assert (result.assessed, result.verdicts) == (5, {"strong": 5})
    assert result.cv.evaluated == 5 and result.cv.checks_passed["verified"] == 5
    assert (result.turns, result.tokens) == (21, 8400)
    assert result.complete and not result.imported and result.manual_steps == []
    assert any("Aprobadas" in m for m in messages)

    with demo.use_data_dir(target), session_scope() as session:
        # Las obligatorias que faltaban, marcadas «No la tengo» solo en la demo.
        assert session.scalars(select(SkillGapMark)).all() is not None
        commands = [r.command for r in session.scalars(select(AgentRun))]
    assert len(commands) == 7

    path = compat.save(result)
    assert path.name.endswith("-claude-default.json")
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["fields_equal"] == 54
    report = compat.REPORT_PATH.read_text(encoding="utf-8")
    assert "Claude Code · modelo por defecto" in report
    assert "| Extracción (campos iguales) | 54/55 |" in report
    assert "`cv09-etl-migracion`: title_normalized" in report


def test_single_case_run(agent: None, tmp_path: Path) -> None:
    """`--cases 1`: solo la primera oferta, con su demo, su resultado y su columna."""
    target = compat.data_dir("claude", None, None, 1)
    assert target.name == "data-demo-compat-claude-default-1-oferta"
    result = compat.run("claude", target=tmp_path / target.name, execute=fake_execute, cases=1)
    assert [len(s.runs) for s in result.steps] == [1, 1, 1]
    assert [s.case for s in result.extraction] == ["cv01-de-snowflake"]
    assert (result.fields_equal, result.fields_total, result.assessed) == (11, 11, 1)
    assert result.cv.evaluated == 1 and result.complete and result.cases == 1
    path = compat.save(result)
    assert path.name.endswith("-claude-default-1-oferta.json")
    report = compat.REPORT_PATH.read_text(encoding="utf-8")
    assert "Claude Code · modelo por defecto · 1 oferta" in report and "| 1/1 " in report
    with pytest.raises(compat.CompatError, match="--cases"):
        compat.run("claude", target=tmp_path / "x", cases=9)


def test_step_without_background_gives_manual_steps(
    agent: None, target: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real = compat._blocked
    monkeypatch.setattr(
        compat,
        "_blocked",
        lambda action, *a: "Sin segundo plano." if action == "generate-cv" else real(action, *a),
    )
    result = compat.run("claude", target=target, execute=fake_execute)
    assert [(s.action, s.mode) for s in result.steps][-1] == ("generate-cv", "manual")
    assert not result.complete and result.cv.evaluated == 0
    steps = "\n".join(result.manual_steps)
    assert f'CAI_DATA_DIR = "{target.name}"' in steps
    assert "/generate-cv " in steps and "--import" in steps and "--approve" not in steps

    # Un agente sin sintaxis propia (`invoke: natural`) recibe una frase con las ofertas.
    real = compat._spec("claude")
    spec = real.model_copy(update={"info": real.info.model_copy(update={"invoke": "natural"})})
    monkeypatch.setattr(compat, "_spec", lambda _: spec)
    steps = "\n".join(compat.manual_steps("claude", None, None, target, 2))
    assert "«usa el skill generate-cv con las ofertas " in steps and "natural" not in steps
    monkeypatch.setattr(compat, "_spec", lambda _: real)

    # El usuario genera los CVs a mano; `--import` mide lo que hay.
    with demo.use_data_dir(target), session_scope() as session:
        for job_id in compat._case_jobs(session).values():
            assert job_id is not None
            saved = cv_service.save_content(
                session, job_id, _content(), CvRenderOptions(template_id="ats-simple"), "claude"
            )
            cv_service.save_verification(
                session, saved.document_id, CvVerification(passed=True), "claude"
            )
    imported = compat.import_results("claude", target=target)
    assert imported.imported and imported.complete and imported.cv.evaluated == 5
    assert len(next(s for s in imported.steps if s.action == "process-jobs").runs) == 1


def test_first_step_manual_from_the_start(
    agent: None, target: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(compat, "_blocked", lambda *a: "Nivel C.")
    result = compat.run("claude", target=target, execute=fake_execute)
    assert [s.mode for s in result.steps] == ["manual", "not_run", "not_run"]
    steps = "\n".join(result.manual_steps)
    assert "/process-jobs" in steps and "--approve" in steps
    notes = compat.approve(target)  # aún sin extraer: lo dice, sin error
    assert len(notes) == 5 and "pending_extraction" in notes[0]


def test_cli_end_to_end(
    agent: None, target: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(agent_runner, "run_next", fake_execute)
    monkeypatch.setattr(compat, "data_dir", lambda *a: target)
    result = runner.invoke(cli.app, ["eval", "compat", "--agent", "claude"])
    assert result.exit_code == 0, result.output
    assert "extracción 54/55 campos, 5/5 valoraciones, CVs 2/5 pasan" in result.output
    assert len(list((tmp_path / "results").glob("*.json"))) == 1
    as_json = runner.invoke(cli.app, ["eval", "compat", "--agent", "claude", "--import", "--json"])
    assert as_json.exit_code == 0, as_json.output
    assert json.loads(as_json.output)["imported"] is True


def test_real_runner_with_fake_agent_process(
    agent: None, target: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El camino de verdad (`agent_runner.run_next` lanza un proceso): el agente falso no guarda
    nada, así que la medida sale vacía, pero el flujo no se rompe ni deja ejecuciones en cola. Y el
    agente (con su servidor MCP) recibe la carpeta de la demo, nunca la de tus datos."""
    log = tmp_path / "fake-agent.json"
    monkeypatch.setenv("FAKE_AGENT_LOG", str(log))
    result = compat.run("claude", target=target, timeout=30)
    assert Path(json.loads(log.read_text(encoding="utf-8"))["data_dir"]) == target
    assert result.steps[0].runs[0].status == "done"
    assert result.steps[0].runs[0].turns == 4  # del `result` del agente falso
    assert result.fields_equal == 0 and not result.complete
    with demo.use_data_dir(target), session_scope() as session:
        assert not [
            r for r in session.scalars(select(AgentRun)) if r.status in ("queued", "running")
        ]


def test_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(compat.CompatError, match="ningún agente"):
        compat.run("nadie", target=tmp_path / "x")
    with pytest.raises(compat.CompatError, match="no tiene el formato"):
        compat.run("opencode", model="sin-proveedor", target=tmp_path / "x")
    with pytest.raises(compat.CompatError, match="No hay una demo"):
        compat.import_results("claude", target=tmp_path / "vacia")
    (tmp_path / "real").mkdir()
    with pytest.raises(compat.CompatError, match="no es una demo"):
        compat.approve(tmp_path / "real")


def test_compare_extraction_normalizes() -> None:
    case = CASES["cv01-de-snowflake"]
    data: dict[str, Any] = case.extraction.model_dump()
    data["must_have_skills"] = [s.upper() for s in reversed(data["must_have_skills"])]
    data["locations"] = [loc.upper() for loc in data["locations"]]
    data["seniority"] = "lead" if data["seniority"] != "lead" else "junior"
    equal, different = compat.compare_extraction(
        case.extraction, JobExtraction.model_validate(data)
    )
    assert different == ["seniority"] and equal == len(compat.COMPARED_FIELDS) - 1


def test_dir_names() -> None:
    assert compat.data_dir("opencode", "ollama/gpt-oss:20b", None).name == (
        "data-demo-compat-opencode-ollama-gpt-oss-20b"
    )
    assert compat.data_dir("codex", None, "local").name == "data-demo-compat-codex-preset-local"


def test_report_without_results(tmp_path: Path) -> None:
    assert "Todavía no hay resultados" in compat.to_markdown(compat.load_results(tmp_path))
