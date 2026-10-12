"""«En segundo plano» (fase 19, ADR-032): comando con solo las herramientas de la acción, cola de
una en una y el runner con un agente falso que imita `stream-json` (sin red ni LLM)."""

import json
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agent_interface.tools import TOOLS_BY_NAME
from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import AgentRun, SkillGapMark
from app.services import agent_launch, agent_runner, agent_runs, events
from app.services.agent_launch import ACTIONS, Headless, LaunchError, _Launcher
from app.services.matching import skills
from app.services.pipeline import Actor, EventType
from tests.test_api_triage import add_extracted, import_profile

FAKE_AGENT = Path(__file__).parent / "fixtures" / "fake_agent.py"
JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}
PREFIX = "mcp__candidatai__"
# Herramientas que escriben o salen fuera y que ninguna ejecución desatendida debe tener.
RISKY = {
    "add_event",
    "add_job_from_url",
    "add_job_from_text",
    "save_source",
    "record_source_run",
    "request_user_action",
    "save_application_answers",
    "render_cv",
}


@pytest.fixture
def db() -> None:
    migrations.upgrade()


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Un agente cuyo `headless` es el agente falso. Devuelve el fichero donde deja su registro."""
    launcher = _Launcher(
        "claude",
        ["claude", "{prompt}"],
        ["ANTHROPIC_API_KEY"],
        ["claude", "--resume", "{session_id}"],
        Headless(
            [
                sys.executable,
                str(FAKE_AGENT),
                "{prompt}",
                "--disallowedTools",
                "{denied_tools}",
                "--allowedTools",
                "{allowed_tools}",
            ],
            ["Agent"],
            "Skill({skill})",
            "claude-stream-json",
            PREFIX,
        ),
    )
    real_which = agent_launch.shutil.which

    def which(name: str) -> str | None:
        return real_which(name) if Path(name).is_absolute() else f"C:/bin/{name}.exe"

    monkeypatch.setattr(agent_launch, "_launchers", lambda: [launcher])
    monkeypatch.setattr(agent_launch.shutil, "which", which)
    monkeypatch.setattr(agent_runner, "FLUSH_SECONDS", 0.1)
    monkeypatch.setattr(agent_runner, "RESULT_GRACE_SECONDS", 1.0)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-no-debe-llegar")
    log = tmp_path / "fake-agent.json"
    monkeypatch.setenv("FAKE_AGENT_LOG", str(log))
    monkeypatch.setenv("FAKE_AGENT_MODE", "ok")
    return log


def start(action: str = "procesar-ofertas", job_id: int | None = None) -> int:
    with session_scope() as session:
        return agent_runs.start(session, action, job_id).id  # type: ignore[arg-type]


def run_row(run_id: int) -> AgentRun:
    with session_scope() as session:
        row = session.get(AgentRun, run_id)
        assert row is not None
        session.expunge(row)
        return row


def run_now(**kwargs: float) -> agent_runner.AgentRunOutcome:
    outcome = agent_runner.run_next(poll=0.05, **kwargs)
    assert outcome is not None
    return outcome


# --- Comando y herramientas --------------------------------------------------------------------


def test_only_three_actions_run_in_background() -> None:
    assert {a for a, spec in ACTIONS.items() if spec.background} == {
        "procesar-ofertas",
        "evaluar-encaje",
        "generar-cv",
    }


def test_background_tools_exist_and_are_minimal() -> None:
    for action, spec in ACTIONS.items():
        for tool in spec.background:
            assert tool in TOOLS_BY_NAME, f"{action}: {tool} no existe"
        assert not RISKY & set(spec.background), action
    assert set(ACTIONS["procesar-ofertas"].background) == {
        "get_status",
        "list_jobs",
        "get_job",
        "save_extraction",
    }
    # Solo procesar-ofertas (su subagente extractor) lee el texto de las ofertas.
    assert "get_job" not in ACTIONS["evaluar-encaje"].background
    assert "get_job" not in ACTIONS["generar-cv"].background


@pytest.mark.parametrize("action", ["procesar-ofertas", "evaluar-encaje", "generar-cv"])
def test_manifest_command_allows_only_the_action_tools(action: str) -> None:
    """El comando real de Claude Code (manifiesto): sin terminal ni web, solo el skill de la acción
    y todas las demás herramientas MCP denegadas (un deny gana a los allow de `settings.json`)."""
    launchers = {launcher.agent: launcher for launcher in agent_launch._launchers()}
    claude = launchers["claude"]
    assert claude.headless is not None and claude.headless.output == "claude-stream-json"
    assert launchers["codex"].headless is None  # Codex: sin segundo plano (ADR-032)
    spec = ACTIONS[action]
    command = agent_launch.headless_command(claude, "ORDEN", action)

    assert command[:3] == ["claude", "-p", "ORDEN"]
    assert command[command.index("--output-format") + 1] == "stream-json"
    assert command[command.index("--permission-mode") + 1] == "dontAsk"
    assert "--strict-mcp-config" in command
    assert command[command.index("--mcp-config") + 1] == ".mcp.json"
    builtin = command[command.index("--tools") + 1].split(",")
    assert set(builtin) == {"Skill", "Agent", "Read"}  # nada de Bash, PowerShell ni web
    allowed = command[command.index("--allowedTools") + 1 :]
    assert allowed == [
        "Agent",
        "Read(./docs/**)",
        f"Skill({action})",  # solo su skill, no cualquiera de los instalados
        *(PREFIX + t for t in spec.background),
    ]
    assert [tool for tool in allowed if "*" in tool] == ["Read(./docs/**)"]
    denied = command[command.index("--disallowedTools") + 1 : command.index("--allowedTools")]
    assert {"Read(./.env)", "Read(./data/**)"} <= set(denied)
    denied_mcp = {t.removeprefix(PREFIX) for t in denied if t.startswith(PREFIX)}
    assert denied_mcp == set(TOOLS_BY_NAME) - set(spec.background)
    assert denied_mcp >= RISKY
    assert claude.unset_env == ["ANTHROPIC_API_KEY"]
    assert claude.resume == ["claude", "--resume", "{session_id}"]


def test_start_rejects_actions_that_ask(db: None, fake: Path) -> None:
    with session_scope() as session, pytest.raises(LaunchError, match="En terminal"):
        agent_runs.start(session, "buscar-ofertas")


def test_start_without_headless_agent(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    launcher = _Launcher("codex", ["codex", "{prompt}"], ["OPENAI_API_KEY"])
    monkeypatch.setattr(agent_launch, "_launchers", lambda: [launcher])
    monkeypatch.setattr(agent_launch.shutil, "which", lambda name: f"C:/bin/{name}.exe")
    assert agent_launch.background_info().available is False
    with session_scope() as session, pytest.raises(LaunchError) as exc:
        agent_runs.start(session, "procesar-ofertas")
    assert exc.value.code == "unavailable" and "headless" in str(exc.value)


def test_start_queues_once_and_stores_the_command(db: None, fake: Path) -> None:
    first = start()
    assert start() == first  # misma acción en cola: no se duplica
    row = run_row(first)
    assert row.status == "queued" and row.agent == "claude"
    assert row.prompt.startswith("Usa el skill procesar-ofertas")
    assert "PREGUNTA:" in row.prompt and "segundo plano" in row.prompt
    assert row.command[-4:] == [f"{PREFIX}{t}" for t in ACTIONS["procesar-ofertas"].background]
    assert row.unset_env == ["ANTHROPIC_API_KEY"]


def _approved_job(**changes: object) -> int:
    import_profile()
    job_id = add_extracted("Data Engineer", "Acme", **changes)
    with session_scope() as session:
        events.record(session, job_id, EventType.APPROVED, actor=Actor.USER)
    return job_id


def test_generate_cv_in_background_needs_no_questions(db: None, fake: Path) -> None:
    job_id = _approved_job()  # el perfil de ejemplo cubre todas las obligatorias
    run_id = start("generar-cv", job_id)
    row = run_row(run_id)
    assert row.job_id == job_id and f"oferta {job_id}" in row.prompt
    assert "No la tengo" not in row.prompt


def test_generate_cv_with_unmarked_missing_skills_goes_to_terminal(db: None, fake: Path) -> None:
    job_id = _approved_job(must_have_skills=["Python", "Kafka", "Scala"])
    with session_scope() as session, pytest.raises(LaunchError, match="2 skills obligatorias"):
        agent_runs.start(session, "generar-cv", job_id)

    # Marcadas como «No la tengo» en la página Skills: ya no hay nada que preguntar.
    index = skills.alias_index()
    with session_scope() as session:
        for name in ("Kafka", "Scala"):
            key = skills.canonical(name, index)
            session.add(SkillGapMark(skill_key=key, skill_name=name, status="gap"))
    row = run_row(start("generar-cv", job_id))
    assert "No la tengo" in row.prompt
    assert "Kafka" not in row.prompt and "Scala" not in row.prompt  # nada de la oferta


def test_generate_cv_needs_an_approved_job(db: None, fake: Path) -> None:
    import_profile()
    job_id = add_extracted("Data Engineer", "Acme")
    with session_scope() as session, pytest.raises(LaunchError, match="aprobada"):
        agent_runs.start(session, "generar-cv", job_id)


# --- Runner con el agente falso ----------------------------------------------------------------


def test_run_ok_saves_progress_result_and_usage(db: None, fake: Path) -> None:
    run_id = start()
    outcome = run_now()
    assert outcome.status == "done" and outcome.run_id == run_id
    row = run_row(run_id)
    assert row.status == "done" and row.result == "Procesadas 2 ofertas, 0 fallidas."
    assert row.session_id == "0f7c2d1e-aaaa-bbbb-cccc-123456789abc"
    assert row.usage == {"num_turns": 4, "duration_ms": 1234, "total_cost_usd": 0.0}
    assert row.started_at and row.finished_at and row.pid
    texts = [p["text"] for p in row.progress]
    assert "list_jobs" in texts
    assert "Subagente «extractor»" in texts
    assert "↳ get_job" in texts  # lo del subagente, marcado
    assert "Voy a procesar las ofertas pendientes." in texts
    assert "TEXTO DE LA OFERTA" not in json.dumps(row.progress)  # nunca las entradas

    seen = json.loads(fake.read_text(encoding="utf-8"))
    assert seen["api_key"] is False  # `unset_env` quitada
    assert seen["argv"][0].startswith("Usa el skill procesar-ofertas")
    argv = seen["argv"]
    assert argv[argv.index("--allowedTools") + 1 :] == ["Agent", "Skill(procesar-ofertas)"] + [
        PREFIX + t for t in ACTIONS["procesar-ofertas"].background
    ]
    assert f"{PREFIX}add_event" in argv[: argv.index("--allowedTools")]  # denegada


def test_run_with_questions_needs_the_user(
    db: None, fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "question")
    run_id = start()
    assert run_now().status == "needs_user"
    with session_scope() as session:
        view = agent_runs.get_run(session, run_id)
    assert view.questions == [
        "La oferta 3 parece cerrada, ¿redacto igualmente?",
        "¿Con foto o sin foto?",
    ]
    assert view.can_resume is True


@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("error", "error_max_turns"),
        ("crash", "boom"),
        ("nomcp", "no se conectó"),
    ],
)
def test_run_failures(
    db: None, fake: Path, monkeypatch: pytest.MonkeyPatch, mode: str, message: str
) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", mode)
    run_id = start()
    began = time.monotonic()
    outcome = run_now()
    assert outcome.status == "failed"
    assert message in (outcome.error or "")
    assert time.monotonic() - began < 20  # `nomcp` no espera a que el agente acabe
    assert run_row(run_id).error == outcome.error


def test_denied_tools_are_reported(db: None, fake: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "denied")
    run_id = start()
    assert run_now().status == "done"
    row = run_row(run_id)
    assert row.usage and row.usage["denied_tools"] == ["Bash"]
    assert any("denegadas: Bash" in p["text"] for p in row.progress)


def test_run_timeout_stops_the_process(
    db: None, fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "hang")
    run_id = start()
    outcome = run_now(timeout=1.5)
    assert outcome.status == "timeout" and "tiempo máximo" in (outcome.error or "")
    row = run_row(run_id)
    assert row.session_id is not None  # el progreso de antes se conserva
    assert "list_jobs" in [p["text"] for p in row.progress]


def test_cancel_a_running_run(db: None, fake: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "hang")
    run_id = start()
    outcomes: list[agent_runner.AgentRunOutcome] = []
    worker = threading.Thread(target=lambda: outcomes.append(run_now(timeout=30)))
    worker.start()
    for _ in range(100):
        if run_row(run_id).status == "running":
            break
        time.sleep(0.05)
    with session_scope() as session:
        assert agent_runs.cancel(session, run_id).cancel_requested is True
    worker.join(timeout=20)
    assert outcomes and outcomes[0].status == "cancelled"
    assert run_row(run_id).status == "cancelled"


def test_cancel_queued_and_finished(db: None, fake: Path) -> None:
    run_id = start()
    with session_scope() as session:
        assert agent_runs.cancel(session, run_id).status == "cancelled"
    with session_scope() as session, pytest.raises(LaunchError, match="ya ha terminado"):
        agent_runs.cancel(session, run_id)
    assert agent_runner.run_next() is None  # la cancelada no se ejecuta


def test_one_run_at_a_time(db: None, fake: Path) -> None:
    first = start("procesar-ofertas")
    second = start("evaluar-encaje")
    with session_scope() as session:
        row = session.get(AgentRun, first)
        assert row is not None
        row.status = "running"
    assert agent_runner.claim_next() is None  # hay otra en curso
    assert run_row(second).status == "queued"

    assert agent_runner.recover_interrupted() == 1
    row = run_row(first)
    assert row.status == "failed" and "No se repite" in (row.error or "")
    outcomes = agent_runner.run_pending(poll=0.05)
    assert [o.run_id for o in outcomes] == [second]


def test_open_in_terminal_resumes_the_session(
    db: None, fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[tuple[str, str]] = []
    monkeypatch.setattr(agent_launch.sys, "platform", "win32")
    monkeypatch.setattr(agent_launch, "_open_terminal", lambda t, c: opened.append((t, c)))
    monkeypatch.setenv("FAKE_AGENT_MODE", "question")
    run_id = start()
    with session_scope() as session, pytest.raises(LaunchError, match="Espera"):
        agent_runs.open_in_terminal(session, run_id)
    run_now()
    with session_scope() as session:
        result = agent_runs.open_in_terminal(session, run_id)
    assert "misma sesión" in result.message
    [(title, command)] = opened
    assert title == "CandidatAI · Procesar ofertas"
    assert command.endswith("& 'claude' '--resume' '0f7c2d1e-aaaa-bbbb-cccc-123456789abc'")
    assert "Remove-Item Env:ANTHROPIC_API_KEY" in command


def test_questions_parser() -> None:
    text = "Hecho.\nPREGUNTA: ¿Sigo?\n* **Pregunta:** ¿Con foto?\nNo es una PREGUNTA: aquí"
    assert agent_runner.questions_in(text) == ["¿Sigo?", "¿Con foto?"]


# --- API ---------------------------------------------------------------------------------------


@pytest.fixture
def client(db: None) -> Iterator[TestClient]:
    with TestClient(create_app()) as client:
        yield client


def test_api_start_list_get_and_cancel(client: TestClient, fake: Path) -> None:
    status = client.get("/agent").json()
    assert status["background"] == {"available": True, "agent": "claude", "reason": None}
    actions = {a["id"]: a for a in status["actions"]}
    assert actions["procesar-ofertas"]["background"] is True
    assert actions["buscar-ofertas"]["background"] is False

    response = client.post("/agent/runs", json={"action": "procesar-ofertas"}, headers=JSON)
    assert response.status_code == 202
    run = response.json()
    assert run["status"] == "queued" and run["label"] == "Procesar ofertas"
    assert run["allowed_tools"] == list(ACTIONS["procesar-ofertas"].background)

    listed = client.get("/agent/runs").json()
    assert listed["active"] == 1 and [r["id"] for r in listed["runs"]] == [run["id"]]
    assert client.get(f"/agent/runs/{run['id']}").json()["id"] == run["id"]
    assert client.get("/agent/runs/999").status_code == 404

    cancelled = client.post(f"/agent/runs/{run['id']}/cancel", json={}, headers=JSON)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"

    asks = client.post("/agent/runs", json={"action": "buscar-ofertas"}, headers=JSON)
    assert asks.status_code == 422


def test_api_unavailable_returns_the_prompt(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(agent_launch, "_launchers", lambda: [])
    response = client.post("/agent/runs", json={"action": "evaluar-encaje"}, headers=JSON)
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["type"] == "agent_unavailable"
    assert error["details"][0]["received"].startswith("Usa el skill evaluar-encaje")


@pytest.mark.parametrize("path", ["/agent/runs", "/agent/runs/1/cancel", "/agent/runs/1/open"])
def test_only_the_ui_can_start_or_cancel(client: TestClient, fake: Path, path: str) -> None:
    headers = {"Origin": "https://example.com", "Content-Type": "application/json"}
    response = client.post(path, content='{"action": "procesar-ofertas"}', headers=headers)
    assert response.status_code == 403
    # Sin cuerpo JSON tampoco: un formulario de otra web no necesita comprobación CORS.
    assert client.post(path, headers={"Origin": UI_ORIGIN}).status_code == 403
    with session_scope() as session:
        assert session.scalars(select(AgentRun)).first() is None


def test_worker_once_runs_background_runs(db: None, fake: Path) -> None:
    from typer.testing import CliRunner

    from app import cli

    run_id = start()
    result = CliRunner().invoke(cli.app, ["worker", "--once", "--json"])
    assert result.exit_code == 0, result.stdout
    body = json.loads(result.stdout)
    assert body["agent_runs"] == [
        {
            "run_id": run_id,
            "action": "procesar-ofertas",
            "status": "done",
            "error": None,
            "questions": 0,
        }
    ]


# --- Revisión: procesos que no deben quedar vivos y carreras -----------------------------------


def _alive(pid: int) -> bool:
    import subprocess

    out = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, check=False
    ).stdout
    return str(pid) in out


windows_only = pytest.mark.skipif(sys.platform != "win32", reason="taskkill y tasklist (Windows)")


@windows_only
def test_timeout_kills_the_whole_tree(
    db: None, fake: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    child_file = tmp_path / "child.pid"
    monkeypatch.setenv("FAKE_AGENT_MODE", "child")
    monkeypatch.setenv("FAKE_AGENT_CHILD", str(child_file))
    start()
    assert run_now(timeout=3).status == "timeout"
    child = int(child_file.read_text(encoding="utf-8"))
    for _ in range(20):
        if not _alive(child):
            break
        time.sleep(0.2)
    assert not _alive(child)  # el hijo (como el cai-mcp) también se para


def test_non_json_output_is_ignored(db: None, fake: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "garbage")
    run_id = start()
    assert run_now().status == "done"
    assert run_row(run_id).result == "Procesadas 2 ofertas, 0 fallidas."


def test_agent_that_does_not_exit_after_its_result(
    db: None, fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "linger")
    run_id = start()
    began = time.monotonic()
    assert run_now(timeout=30).status == "done"  # no espera al tiempo máximo
    assert time.monotonic() - began < 15
    assert run_row(run_id).result == "Procesadas 2 ofertas, 0 fallidas."


@windows_only
def test_an_exception_never_leaves_the_agent_running(
    db: None, fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "hang")
    started: list[int] = []
    real_save = agent_runner._save

    def broken_save(run_id: int, **values: object) -> bool:
        if "pid" in values:
            started.append(int(str(values["pid"])))
            raise RuntimeError("database is locked")
        return real_save(run_id, **values)

    monkeypatch.setattr(agent_runner, "_save", broken_save)
    run_id = start()
    outcome = run_now(timeout=30)
    assert outcome.status == "failed" and "database is locked" in (outcome.error or "")
    assert started and not _alive(started[0])
    assert run_row(run_id).status == "failed"


def test_stopping_the_worker_stops_the_agent(
    db: None, fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "hang")
    run_id = start()
    outcomes: list[agent_runner.AgentRunOutcome] = []
    worker = threading.Thread(target=lambda: outcomes.append(run_now(timeout=30)))
    worker.start()
    try:
        for _ in range(100):
            if run_row(run_id).pid:
                break
            time.sleep(0.05)
        assert agent_runner.stop_active() == 1
        worker.join(timeout=20)
        assert outcomes and outcomes[0].status == "failed"
        assert "Se paró el worker" in (outcomes[0].error or "")
        assert agent_runner.run_next() is None  # parado: no empieza otra
    finally:
        agent_runner._shutdown.clear()


def test_recover_kills_an_orphan_agent(
    db: None, fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = start()
    with session_scope() as session:
        row = session.get(AgentRun, run_id)
        assert row is not None
        row.status, row.pid = "running", 4242
    killed: list[int] = []
    monkeypatch.setattr(agent_runner, "_alive_as", lambda pid, program: pid == 4242)
    monkeypatch.setattr(agent_runner, "_kill_pid_tree", killed.append)
    assert agent_runner.recover_interrupted() == 1
    assert killed == [4242]
    assert run_row(run_id).status == "failed"


def test_cancel_after_the_worker_claims_it(db: None, fake: Path) -> None:
    """Si el worker la reclama entre que la UI la lee y la cancela, queda pedida, no pisada."""
    run_id = start()
    claimed = agent_runner.claim_next()
    assert claimed is not None and claimed.id == run_id
    with session_scope() as session:
        view = agent_runs.cancel(session, run_id)
    assert view.status == "running" and view.cancel_requested is True


def test_tool_errors_do_not_leak_their_detail() -> None:
    from app.services.agent_output import ClaudeStreamParser

    parser = ClaudeStreamParser()
    use = {"type": "tool_use", "id": "t1", "name": f"{PREFIX}save_extraction", "input": {}}
    parser.feed(json.dumps({"type": "assistant", "message": {"content": [use]}}))
    error = {"type": "tool_result", "tool_use_id": "t1", "is_error": True, "content": "TEXTO"}
    parser.feed(json.dumps({"type": "user", "message": {"content": [error]}}))
    assert parser.state.progress[-1] == ("error", "Error en save_extraction")
