"""«En segundo plano» con varios agentes (fase 24.5): techo por configuración (OpenCode), el
lector `opencode-json`, la configuración temporal de cada ejecución y una cola con agentes
distintos. Sin red ni LLM: un agente falso y salidas grabadas de OpenCode 1.19.3 sobre la demo."""

import json
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import AgentRun
from app.services import agent_launch, agent_registry, agent_run_config, agent_runner, agent_runs
from app.services.agent_launch import ACTIONS, Headless, LaunchError, _Launcher
from app.services.agent_output import PARSERS, OpenCodeJsonParser
from app.services.agent_prefs import ActionPref, Preferences
from app.services.agent_registry import HeadlessSpec, RunConfigSpec

FIXTURES = Path(__file__).parent / "fixtures"
FAKE_AGENT = FIXTURES / "fake_agent.py"
RECORDED = FIXTURES / "agent_output"
OC_PREFIX = "candidatai_"
RUN_CONFIG = RunConfigSpec(
    format="opencode",
    env="OPENCODE_CONFIG_CONTENT",
    value="content",
    agent="cai-run",
    clear_env=["OPENCODE_CONFIG", "OPENCODE_CONFIG_DIR", "OPENCODE_PERMISSION"],
)
# Herramientas nativas de OpenCode que ninguna ejecución debe tener.
NATIVE = {"bash", "read", "edit", "write", "glob", "grep", "list", "webfetch", "websearch"}


def opencode_launcher() -> _Launcher:
    return _Launcher(
        "opencode",
        ["opencode", "--prompt", "{prompt}"],
        [],
        headless=Headless(
            [sys.executable, str(FAKE_AGENT), "run", "--agent", "cai-run", "{model}", "{prompt}"],
            [],
            "",
            "opencode-json",
            OC_PREFIX,
            "config",
            RUN_CONFIG,
        ),
    )


def claude_launcher() -> _Launcher:
    return _Launcher(
        "claude",
        ["claude", "{prompt}"],
        ["ANTHROPIC_API_KEY"],
        headless=Headless(
            [sys.executable, str(FAKE_AGENT), "{prompt}", "{denied_tools}", "{allowed_tools}"],
            ["Agent"],
            "Skill({skill})",
            "claude-stream-json",
            "mcp__candidatai__",
        ),
    )


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> None:
    migrations.upgrade()
    # Sin ofertas, «Evaluar encaje» no se lanzaría (umbral de la fase 25.4): aquí da igual cuáles.
    monkeypatch.setattr(agent_runs, "_assess_prompt", lambda *_a: "Usa el skill assess-fit con 1.")


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Claude Code y OpenCode, los dos con el agente falso. Devuelve su registro."""
    launchers = [claude_launcher(), opencode_launcher()]
    real_which = agent_launch.shutil.which

    def which(name: str) -> str | None:
        return real_which(name) if Path(name).is_absolute() else f"C:/bin/{name}.exe"

    monkeypatch.setattr(agent_launch, "_launchers", lambda: launchers)
    monkeypatch.setattr(agent_launch.shutil, "which", which)
    monkeypatch.setattr(agent_runner, "FLUSH_SECONDS", 0.1)
    monkeypatch.setattr(agent_runner, "RESULT_GRACE_SECONDS", 1.0)
    monkeypatch.setenv("OPENCODE_CONFIG_CONTENT", '{"agent": {"cai-run": {"permission": "allow"}}}')
    monkeypatch.setenv("OPENCODE_PERMISSION", '{"*": "allow"}')
    monkeypatch.setenv("OPENCODE_CONFIG_DIR", "C:/otra-config")
    log = tmp_path / "fake-agent.json"
    monkeypatch.setenv("FAKE_AGENT_LOG", str(log))
    monkeypatch.setenv("FAKE_AGENT_MODE", "ok")
    return log


def start(action: str = "process-jobs", agent: str = "opencode", **kwargs: str) -> int:
    with session_scope() as session:
        return agent_runs.start(session, action, agent=agent, **kwargs).id  # type: ignore[arg-type]


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


def wait_for(condition, seconds: float = 15.0) -> None:  # type: ignore[no-untyped-def]
    deadline = time.monotonic() + seconds
    while not condition():
        assert time.monotonic() < deadline, "no llegó a tiempo"
        time.sleep(0.05)


# --- La configuración de la ejecución ----------------------------------------------------------


@pytest.mark.parametrize("action", ["process-jobs", "assess-fit"])
def test_run_config_enables_only_the_action_tools(action: str) -> None:
    spec = ACTIONS[action]
    config = agent_run_config.build(action, RUN_CONFIG, OC_PREFIX)  # type: ignore[arg-type]
    agent = config["agent"]["cai-run"]
    assert set(config["agent"]) == {"cai-run"}
    assert agent["mode"] == "primary"
    permission = agent["permission"]
    # La última regla que coincide manda: el «todo denegado» va primero.
    assert next(iter(permission.items())) == ("*", "deny")
    mcp = {key.removeprefix(OC_PREFIX) for key in permission if key.startswith(OC_PREFIX)}
    assert mcp == set(spec.background)
    assert all(permission[OC_PREFIX + tool] == "allow" for tool in spec.background)
    assert permission["skill"] == {"*": "deny", spec.skill or action: "allow"}
    assert list(permission["task"].items()) == [
        ("*", "deny"),
        *((role, "allow") for role in spec.roles),
    ]
    assert not NATIVE & set(permission)
    assert set(permission) == {"*", "skill", "task"} | {OC_PREFIX + t for t in spec.background}
    assert config["share"] == "disabled"


def test_roles_never_have_more_tools_than_their_action() -> None:
    """Un subagente no puede tener más que la ejecución: los roles que se lanzan caben enteros en
    las herramientas MCP de su acción."""
    for action in ("process-jobs", "assess-fit"):
        assert agent_run_config.ceiling_problem(action) is None  # type: ignore[arg-type]
        allowed = {f"mcp:{tool}" for tool in ACTIONS[action].background}
        for role in ACTIONS[action].roles:
            assert agent_run_config.role_tools(role) <= allowed


def test_generate_cv_cannot_be_capped_by_config() -> None:
    """`writer` y `verifier` leen ficheros (POLICIES.md) y OpenCode no los acota como la
    ejecución: con techo por configuración, `generate-cv` no tiene segundo plano."""
    problem = agent_run_config.ceiling_problem("generate-cv")
    assert problem is not None and "«writer»" in problem and "read" in problem
    with pytest.raises(agent_run_config.RunConfigError):
        agent_run_config.build("generate-cv", RUN_CONFIG, OC_PREFIX)


def test_write_and_remove(tmp_path: Path) -> None:
    env = agent_run_config.write(7, "process-jobs", RUN_CONFIG, OC_PREFIX)
    path = agent_run_config.run_dir(7) / agent_run_config.CONFIG_FILE
    assert path.is_file()
    assert json.loads(env["OPENCODE_CONFIG_CONTENT"]) == json.loads(path.read_text("utf-8"))
    by_path = agent_run_config.write(
        7, "process-jobs", RUN_CONFIG.model_copy(update={"value": "path"}), OC_PREFIX
    )
    assert by_path == {"OPENCODE_CONFIG_CONTENT": str(path)}
    agent_run_config.remove(7)
    assert not agent_run_config.run_dir(7).exists()
    agent_run_config.remove(7)  # no falla si ya no está


# --- Manifiesto y lanzador ---------------------------------------------------------------------


def test_manifest_opencode_headless() -> None:
    spec = agent_registry.get("opencode")
    assert spec is not None and spec.headless is not None
    headless = spec.headless
    assert headless.ceiling == "config" and headless.output == "opencode-json"
    assert headless.config is not None and headless.config.agent in headless.command
    assert headless.config.env == "OPENCODE_CONFIG_CONTENT"  # la que se carga la última
    assert "--pure" in headless.command
    assert "--auto" not in headless.command  # aprobaría solo lo que quede en `ask`
    assert spec.launch is not None and "{session_id}" in spec.launch.resume
    # Codex y Qwen Code, sin segundo plano (docs/AGENTS_COMPAT.md).
    assert agent_registry.get("codex").headless is None  # type: ignore[union-attr]
    assert agent_registry.get("qwen").headless is None  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "changes",
    [
        {"allow": ["read"]},  # lo que se permite lo decide la configuración
        {"config": RUN_CONFIG.model_copy(update={"format": "otro"})},
        {"config": RUN_CONFIG.model_copy(update={"agent": "otro"})},  # la orden no lo nombra
        {"config": None},
        {"output": "desconocido"},
        {"command": ["opencode", "run", "--auto", "--agent", "cai-run", "{prompt}"]},
        {"command": ["opencode", "run", "--agent", "cai-run", "{prompt}", "{denied_tools}"]},
    ],
)
def test_incomplete_config_ceiling_has_no_background(changes: dict[str, object]) -> None:
    base = {
        "ceiling": "config",
        "command": ["opencode", "run", "--agent", "cai-run", "{prompt}"],
        "output": "opencode-json",
        "config": RUN_CONFIG,
    }
    assert HeadlessSpec.model_validate(base).complete
    assert not HeadlessSpec.model_validate({**base, **changes}).complete


def test_args_ceiling_still_needs_the_denied_tools() -> None:
    spec = HeadlessSpec(
        command=["claude", "-p", "{prompt}", "{allowed_tools}"],
        skill_rule="Skill({skill})",
        output="claude-stream-json",
    )
    assert not spec.complete
    assert spec.model_copy(update={"command": [*spec.command, "{denied_tools}"]}).complete


def test_model_goes_where_the_command_says() -> None:
    parts = ["opencode", "run", "--agent", "cai-run", "{model}", "{prompt}"]
    assert agent_launch._with_model(parts, ["-m", "ollama/qwen3:8b"]) == [
        "opencode", "run", "--agent", "cai-run", "-m", "ollama/qwen3:8b", "{prompt}",
    ]  # fmt: skip
    assert agent_launch._with_model(parts, []) == [
        "opencode",
        "run",
        "--agent",
        "cai-run",
        "{prompt}",
    ]
    # Sin `{model}`, detrás del programa (Claude Code, como en la 24.4).
    assert agent_launch._with_model(["claude", "-p"], ["--model", "haiku"]) == [
        "claude", "--model", "haiku", "-p",
    ]  # fmt: skip


def test_start_stores_command_and_run_config(db: None, fake: Path) -> None:
    run_id = start(model="ollama/qwen3:8b")
    row = run_row(run_id)
    assert row.agent == "opencode" and row.output_format == "opencode-json"
    assert row.command[2:6] == ["run", "--agent", "cai-run", "-m"]
    assert row.command[6] == "ollama/qwen3:8b"
    assert "{model}" not in row.command and "{prompt}" not in row.command
    assert row.run_config == {**RUN_CONFIG.model_dump(), "mcp_prefix": OC_PREFIX}
    # Sin herramientas en la orden: el techo va en la configuración.
    assert not any(OC_PREFIX in part for part in row.command)


def test_generate_cv_with_opencode_offers_terminal(db: None, fake: Path) -> None:
    with session_scope() as session:
        launcher, res = agent_launch.choose(
            session, "generate-cv", agent="opencode", mode="background"
        )
        assert launcher is None and res.blocked_code == "no_headless"
        assert res.blocked is not None and "«writer»" in res.blocked
        # Con Claude Code, sí.
        launcher, res = agent_launch.choose(
            session, "generate-cv", agent="claude", mode="background"
        )
        assert launcher is not None


def test_headless_command_refuses_an_uncappable_action() -> None:
    with pytest.raises(LaunchError):
        agent_launch.headless_command(opencode_launcher(), "orden", "generate-cv")


# --- El runner con OpenCode --------------------------------------------------------------------


def test_opencode_run_ok(db: None, fake: Path) -> None:
    run_id = start()
    outcome = run_now()
    assert outcome.status == "done", outcome.error
    row = run_row(run_id)
    assert row.result == "Procesadas 2 ofertas, 0 fallidas."
    assert row.session_id == "ses_0f7c2d1eaaaaBBBBcccc12"
    texts = [line["text"] for line in row.progress]
    assert "Skill «process-jobs»" in texts
    assert "list_jobs" in texts
    assert "Subagente «extractor»" in texts
    assert "↳ get_job" in texts
    assert not any("TEXTO DE LA OFERTA" in text for text in texts)
    assert row.usage is not None
    assert row.usage["turns"] == 2  # los pasos de la sesión principal
    assert row.usage["input_tokens"] == 300 and row.usage["output_tokens"] == 60
    assert row.usage["cost_usd"] == pytest.approx(0.03)
    seen = json.loads(fake.read_text("utf-8"))
    assert seen["client_name"] == "opencode"
    # Recibe la configuración de la ejecución, no la que hubiera en el entorno.
    config = json.loads(seen["opencode_config"])
    assert config["agent"]["cai-run"]["permission"]["*"] == "deny"
    assert seen["opencode_env"] == []  # ni otra configuración ni permisos por variable
    assert not agent_run_config.run_dir(run_id).exists()


def test_config_exists_while_running_and_is_removed_on_cancel(
    db: None, fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "hang")
    run_id = start()
    worker = threading.Thread(target=run_now)
    worker.start()
    config = agent_run_config.run_dir(run_id) / agent_run_config.CONFIG_FILE
    wait_for(lambda: run_row(run_id).pid is not None and config.is_file())
    with session_scope() as session:
        agent_runs.cancel(session, run_id)
    worker.join(timeout=30)
    assert run_row(run_id).status == "cancelled"
    assert not config.parent.exists()


@pytest.mark.parametrize("mode", ["crash", "error"])
def test_config_is_removed_when_the_run_fails(
    db: None, fake: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", mode)
    run_id = start()
    outcome = run_now()
    assert outcome.status == "failed"
    if mode == "error":
        assert "El proveedor rechaza el modelo" in (outcome.error or "")
    assert not agent_run_config.run_dir(run_id).exists()


def test_config_is_removed_on_timeout_and_on_an_exception(
    db: None, fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "hang")
    run_id = start()
    assert run_now(timeout=1.0).status == "timeout"
    assert not agent_run_config.run_dir(run_id).exists()

    def boom(*args: object, **kwargs: object) -> None:
        assert agent_run_config.run_dir(run_id + 1).is_dir()  # ya estaba escrita
        raise RuntimeError("fallo inesperado")

    monkeypatch.setattr(agent_runner, "_popen", boom)
    second = start("assess-fit")
    assert run_now().status == "failed"
    assert not agent_run_config.run_dir(second).exists()


def test_unwritable_config_never_launches(
    db: None, fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = start()
    with session_scope() as session:
        row = session.get(AgentRun, run_id)
        assert row is not None
        row.run_config = {**(row.run_config or {}), "format": "desconocido"}
    outcome = run_now()
    assert outcome.status == "failed" and "configuración" in (outcome.error or "")
    assert not fake.exists()  # el agente no llegó a arrancar


def test_denied_tool_stops_opencode(db: None, fake: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "denied")
    run_id = start()
    outcome = run_now()
    assert outcome.status == "failed"
    row = run_row(run_id)
    assert "Denegada: add_event" in [line["text"] for line in row.progress]
    assert row.usage is not None and row.usage["denied_tools"] == ["add_event"]
    assert "auto-rejecting" in (row.error or "") and "\x1b" not in (row.error or "")


def test_opencode_question_needs_the_user(
    db: None, fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "question")
    start()
    outcome = run_now()
    assert outcome.status == "needs_user" and outcome.questions == 1


# --- Cola con agentes distintos ----------------------------------------------------------------


def test_queue_runs_different_agents_one_at_a_time(db: None, fake: Path) -> None:
    first = start("process-jobs", agent="opencode")
    second = start("assess-fit", agent="claude")
    with session_scope() as session:
        listed = agent_runs.list_runs(session)
        assert listed.active == 2
        assert {run.agent for run in listed.runs} == {"opencode", "claude"}
    outcomes = agent_runner.run_pending(poll=0.05)
    assert [o.run_id for o in outcomes] == [first, second]
    assert all(o.status == "done" for o in outcomes), outcomes
    assert run_row(first).output_format == "opencode-json"
    assert run_row(second).output_format == "claude-stream-json"
    assert run_row(second).run_config is None


def test_recover_after_restart_with_different_agents(db: None, fake: Path) -> None:
    ids = [start("process-jobs", agent="opencode"), start("assess-fit", agent="claude")]
    with session_scope() as session:
        for run_id in ids:
            row = session.get(AgentRun, run_id)
            assert row is not None
            row.status = "running"
    agent_run_config.write(ids[0], "process-jobs", RUN_CONFIG, OC_PREFIX)  # quedó a medias
    assert agent_runner.recover_interrupted() == 2
    assert {run_row(run_id).status for run_id in ids} == {"failed"}
    assert not agent_run_config.run_dir(ids[0]).exists()
    # La cola sigue: una nueva con cualquiera de los dos se ejecuta.
    start("process-jobs", agent="claude")
    assert run_now().status == "done"


# --- El lector, sobre salidas grabadas de OpenCode 1.19.3 --------------------------------------


def feed(name: str) -> OpenCodeJsonParser:
    parser = OpenCodeJsonParser(OC_PREFIX)
    for line in (RECORDED / name).read_text("utf-8").splitlines():
        parser.feed(line)
    return parser


def test_recorded_ok_run() -> None:
    state = feed("opencode_ok.jsonl").state
    assert state.finished and not state.is_error
    assert state.result == "Hay 8 ofertas pendientes de extraer."
    assert state.session_id is not None and state.session_id.startswith("ses_")
    assert ("tool", "get_status") in state.progress
    assert not any('"total"' in text for _, text in state.progress)  # nada de su salida
    assert state.usage["turns"] == 2
    assert state.usage["input_tokens"] == 35268 + 196
    assert state.usage["cost_usd"] == 0


def test_recorded_denied_run() -> None:
    state = feed("opencode_denied.jsonl").state
    assert not state.finished  # OpenCode se paró tras rechazarlas, sin paso final
    assert state.usage["denied_tools"] == ["add_event", "list_jobs"]
    assert ("error", "Denegada: list_jobs") in state.progress


def test_recorded_provider_error() -> None:
    state = feed("opencode_error.jsonl").state
    assert state.finished and state.is_error and state.subtype == "APIError"
    assert state.result is not None and "free tier" in state.result


def test_parsers_cover_the_manifest_outputs() -> None:
    assert set(PARSERS) == agent_registry.HEADLESS_OUTPUTS


def test_api_suggests_an_agent_that_can_run_in_background(db: None, fake: Path) -> None:
    """`GET /agent`: si el agente de la acción no puede en segundo plano, propone otro (24.5)."""
    with session_scope() as session:
        prefs = Preferences(
            actions={
                "generate-cv": ActionPref(agent="opencode"),
                "process-jobs": ActionPref(agent="opencode"),
            }
        )
        agent_launch.save_preferences(session, prefs)
    with TestClient(create_app()) as client:
        actions = {a["id"]: a for a in client.get("/agent").json()["actions"]}
    cv = actions["generate-cv"]["background_agent"]
    assert cv["available"] is False and "«writer»" in cv["reason"]
    assert cv["suggested"] == "claude" and cv["suggested_name"] == "Claude Code"
    jobs = actions["process-jobs"]["background_agent"]
    assert jobs == {
        "available": True,
        "agent": "opencode",
        "reason": None,
        "suggested": None,
        "suggested_name": None,
    }


def test_config_is_removed_when_the_worker_stops(
    db: None, fake: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "hang")
    run_id = start()
    worker = threading.Thread(target=lambda: run_now(timeout=30))
    worker.start()
    try:
        wait_for(lambda: run_row(run_id).pid is not None)
        assert agent_run_config.run_dir(run_id).is_dir()
        assert agent_runner.stop_active() == 1
        worker.join(timeout=20)
        assert run_row(run_id).status == "failed"
        assert not agent_run_config.run_dir(run_id).exists()
    finally:
        agent_runner._shutdown.clear()


def test_recover_removes_orphan_config_folders(db: None) -> None:
    """Carpetas que quedaron de un worker que murió, aunque su fila ya no esté `running`."""
    agent_run_config.write(41, "process-jobs", RUN_CONFIG, OC_PREFIX)
    other = agent_run_config.runs_dir() / "no-es-de-una-ejecucion"
    other.mkdir()
    assert agent_runner.recover_interrupted() == 0
    assert not agent_run_config.run_dir(41).exists()
    assert other.is_dir()  # solo se tocan las de una ejecución


def test_roles_match_what_each_skill_delegates_to() -> None:
    """`Action.roles` es lo que el skill dice delegar («delega en el rol `x`»): si no
    coincidieran, `task` denegaría un rol que el skill necesita, o se bloquearía por nada."""
    import re

    skills_dir = Path(__file__).parents[2] / ".agents" / "skills"
    for action, spec in ACTIONS.items():
        if not spec.background:
            continue
        text = (skills_dir / (spec.skill or action) / "SKILL.md").read_text("utf-8")
        named = set(re.findall(r"delega en el rol `([a-z-]+)`", text))
        assert named == set(spec.roles), action
