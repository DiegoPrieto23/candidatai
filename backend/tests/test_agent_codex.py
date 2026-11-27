"""Fase 46: el asistente con Codex en segundo plano (techo en un perfil propio de cada ejecución,
escrito en la carpeta de Codex) y en una terminal aparte para los agentes sin segundo plano.
Sin red ni LLM: una salida grabada de codex-cli 0.163.0 sobre la demo y terminales simuladas."""
# ruff: noqa: F811 - los fixtures importados se usan como parámetros

import json
import tomllib
from datetime import timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core.db import session_scope
from app.models import AgentRun, AssistantRequest
from app.models.base import utcnow
from app.services import agent_launch, agent_registry, agent_run_config, agent_runner, assistant
from app.services.agent_actions import ACTIONS
from app.services.agent_launch import Headless, LaunchError, _Launcher
from app.services.agent_output import PARSERS, CodexJsonParser
from app.services.agent_prefs import Resolution
from app.services.agent_registry import APPROVE_ALL_FLAGS, RunConfigSpec
from tests.test_agent_runs import db  # noqa: F401

RECORDED = Path(__file__).parent / "fixtures" / "agent_output" / "codex_ok.jsonl"
PREFIX = "mcp__candidatai__"
PROFILE = RunConfigSpec(
    format="codex", env="CODEX_HOME", value="profile", home="~/.codex", agent="cai-run-{run_id}"
)


@pytest.fixture
def codex_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "codex-home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    return home


# --- Manifiesto --------------------------------------------------------------------------------


def test_manifest_codex_headless_only_without_raw_job_text() -> None:
    """Fase 48.1a: las acciones que no leen el texto crudo de una oferta (Codex es de nivel B) y
    cuyo techo cabe en un perfil (sin roles que lean ficheros: las políticas, con
    `get_policies`)."""
    spec = agent_registry.get("codex")
    assert spec is not None and spec.headless is not None
    headless = spec.headless
    assert headless.ceiling == "config" and headless.output == "codex-json"
    assert headless.actions == [
        "assistant",
        "assess-fit",
        "assess-fit-job",
        "translate-summary",
        "generate-cv",
        "correct-cv",
        "verify-cv",
        "generate-cover-letter",
    ]
    for action in headless.actions:
        assert "get_job" not in ACTIONS[action].background  # type: ignore[index]
        assert agent_run_config.ceiling_problem(action) is None  # type: ignore[arg-type]
    assert headless.config is not None and headless.config.value == "profile"
    assert headless.config.agent in headless.command  # `-p cai-run-{run_id}`
    assert "{run_id}" in headless.config.agent  # uno por ejecución
    assert not APPROVE_ALL_FLAGS & set(headless.command)
    assert "--ignore-user-config" not in headless.command  # con ella no carga el perfil
    assert spec.launch is not None and "{session_id}" in spec.launch.resume
    assert "codex-json" in PARSERS


def test_profile_needs_a_home() -> None:
    with pytest.raises(ValueError, match="home"):
        RunConfigSpec(format="codex", env="CODEX_HOME", value="profile", agent="x")


def codex_launcher() -> _Launcher:
    headless = Headless(
        ["codex", "exec", "-p", "cai-run-{run_id}", "{prompt}"],
        [],
        "",
        "codex-json",
        PREFIX,
        "config",
        PROFILE,
        ("assistant",),
    )
    return _Launcher("codex", ["codex", "{prompt}"], [], headless=headless)


@pytest.mark.parametrize("action", sorted(name for name in ACTIONS if ACTIONS[name].background))
def test_only_the_listed_actions_go_to_the_background(action: str) -> None:
    res = Resolution(agent="codex", display_name="Codex", reason="explicit", reason_text="")
    problem = agent_launch._no_background(codex_launcher(), res, action)
    if action == "assistant":
        assert problem is None
    else:
        assert problem is not None and "segundo plano" in problem
    # Sin acción (el estado general), tiene segundo plano.
    assert agent_launch._no_background(codex_launcher(), res, None) is None


# --- El perfil de la ejecución -----------------------------------------------------------------


def test_profile_enables_only_the_action_tools() -> None:
    config = agent_run_config.codex_config("assistant", PROFILE.agent, PREFIX)
    server = config["mcp_servers"]["candidatai"]
    assert server["enabled_tools"] == list(ACTIONS["assistant"].background)
    assert server["command"] and server["args"]  # completo, aunque no se cargue `.codex/`
    assert server["required"] is True
    assert set(server["omit_tools_from"]) == {"deferred", "code_mode"}
    assert config["approval_policy"] == "never" and config["sandbox_mode"] == "read-only"
    assert config["web_search"] == "disabled"
    features = config["features"]
    for name in ("shell_tool", "multi_agent", "apps", "plugins", "browser_use", "computer_use"):
        assert features[name] is False
    assert features["code_mode"] == {"enabled": False}


def test_toml_round_trip() -> None:
    config = agent_run_config.codex_config("assistant", PROFILE.agent, PREFIX)
    config["mcp_servers"]["con espacio"] = {
        "enabled": False,
        "args": ['a "b"', "ñ", r"C:\ruta\uv.exe", "dos\nlíneas"],
    }
    assert tomllib.loads(agent_run_config.to_toml(config)) == config


def test_write_profile_in_codex_home_and_remove(codex_home: Path) -> None:
    (codex_home / "config.toml").write_text(
        '[mcp_servers.github]\ncommand = "gh"\n\n[mcp_servers.candidatai]\ncommand = "uv"\n',
        encoding="utf-8",
    )
    assert agent_run_config.write(12, "assistant", PROFILE, PREFIX) == {}
    path = codex_home / "cai-run-12.config.toml"
    profile = tomllib.loads(path.read_text(encoding="utf-8"))
    assert profile["mcp_servers"]["github"] == {"enabled": False}  # los tuyos, apagados
    assert profile["mcp_servers"]["candidatai"]["enabled_tools"]
    agent_run_config.remove(12)
    assert not path.exists() and not agent_run_config.run_dir(12).exists()
    assert (codex_home / "config.toml").exists()  # tu configuración no se toca
    agent_run_config.remove(12)  # no falla si ya no está


def test_without_codex_home_nothing_is_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "no-existe"))
    with pytest.raises(agent_run_config.RunConfigError, match="carpeta"):
        agent_run_config.write(3, "assistant", PROFILE, PREFIX)


def test_remove_only_deletes_profiles(tmp_path: Path) -> None:
    folder = agent_run_config.run_dir(5)
    folder.mkdir(parents=True)
    other = tmp_path / "importante.txt"
    other.write_text("x", encoding="utf-8")
    (folder / agent_run_config.EXTERNAL_FILE).write_text(str(other), encoding="utf-8")
    near = tmp_path / "otra.config.toml"
    near.write_text("x", encoding="utf-8")
    own = tmp_path / "cai-run-5.config.toml"
    own.write_text("x", encoding="utf-8")
    listed = "\n".join(str(path) for path in (other, near, tmp_path / "config.toml", own))
    (tmp_path / "config.toml").write_text("x", encoding="utf-8")
    (folder / agent_run_config.EXTERNAL_FILE).write_text(listed, encoding="utf-8")
    agent_run_config.remove(5)
    assert other.exists() and near.exists() and (tmp_path / "config.toml").exists()
    assert not own.exists()  # solo el perfil de esta ejecución


def test_project_servers_are_switched_off_too(
    codex_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = tmp_path / "repo"
    (repo / ".codex").mkdir(parents=True)
    (repo / ".codex" / "config.toml").write_text(
        '[mcp_servers.candidatai]\ncommand = "uv"\n\n[mcp_servers.extra]\ncommand = "x"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(agent_run_config, "REPO_ROOT", repo)
    agent_run_config.write(13, "assistant", PROFILE, PREFIX)
    try:
        path = codex_home / "cai-run-13.config.toml"
        profile = tomllib.loads(path.read_text(encoding="utf-8"))
        assert profile["mcp_servers"]["extra"] == {"enabled": False}
    finally:
        agent_run_config.remove(13)


def test_runner_names_the_profile_of_each_run(codex_home: Path) -> None:
    run = AgentRun(
        id=21,
        action="assistant",
        agent="codex",
        command=["codex", "exec", "-p", "cai-run-{run_id}", "orden"],
        run_config={**PROFILE.model_dump(), "mcp_prefix": PREFIX},
    )
    try:
        env, clear, command = agent_runner._write_config(run)
        assert env == {} and clear == []
        assert command == ["codex", "exec", "-p", "cai-run-21", "orden"]
        assert (codex_home / "cai-run-21.config.toml").is_file()
    finally:
        agent_run_config.remove(21)
    assert not (codex_home / "cai-run-21.config.toml").exists()


# --- Lector de la salida -----------------------------------------------------------------------


def feed(lines: list[str]) -> CodexJsonParser:
    parser = CodexJsonParser(PREFIX)
    for line in lines:
        parser.feed(line)
    return parser


def test_recorded_ok_run() -> None:
    state = feed(RECORDED.read_text(encoding="utf-8").splitlines()).state
    assert state.finished and not state.is_error
    assert state.session_id == "01a1f505-5616-7cf3-a616-e6cd53fc081d"
    assert state.result and state.result.startswith("He respondido a la petición 1")
    tools = [text for kind, text in state.progress if kind == "tool"]
    assert tools == [
        "get_assistant_request",
        "get_status",
        "list_jobs",
        "list_jobs",
        "save_assistant_answer",
    ]
    assert state.usage["input_tokens"] == 161876 and state.usage["output_tokens"] == 549 + 89
    # Nunca las entradas de las herramientas (pueden llevar texto de una oferta).
    assert not any("request_id" in text for _, text in state.progress)


def test_denied_tool_and_failed_turn() -> None:
    denied = {
        "type": "item.completed",
        "item": {
            "type": "mcp_tool_call",
            "server": "candidatai",
            "tool": "add_event",
            "status": "failed",
            "error": {"message": "tool rejected: not allowed"},
        },
    }
    failed = {"type": "turn.failed", "error": {"message": "usage limit reached"}}
    state = feed(["no es json", json.dumps(denied), json.dumps(failed)]).state
    assert ("error", "Denegada: add_event") in state.progress
    assert state.usage["denied_tools"] == ["add_event"]
    assert state.finished and state.is_error and state.result == "usage limit reached"


# --- El asistente en una terminal ---------------------------------------------------------------


@pytest.fixture
def terminal(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Un agente sin segundo plano que se abre en una terminal (simulada)."""
    launcher = _Launcher("antigravity", ["agy", "-i", "{prompt}"], [])
    opened: list[str] = []

    def open_terminal(title: str, command: str) -> None:
        # Cuando se abre la ventana, la petición ya está guardada: el agente la lee desde otro
        # proceso en cuanto arranca.
        with session_scope() as other:
            assert other.scalar(select(func.count()).select_from(AssistantRequest)) > 0
        opened.append(command)

    monkeypatch.setattr(agent_launch, "_launchers", lambda: [launcher])
    monkeypatch.setattr(agent_launch.shutil, "which", lambda name: f"C:/bin/{name}.exe")
    monkeypatch.setattr(agent_launch, "_open_terminal", open_terminal)
    # Hay dónde abrirla también en una CI de Linux sin entorno gráfico.
    monkeypatch.setattr(agent_launch, "no_terminal", lambda: None)
    return opened


def test_terminal_mode_opens_the_agent_and_waits_for_the_answer(
    db: None, terminal: list[str]
) -> None:
    with session_scope() as session:
        view = assistant.create(session, "¿Qué tengo hoy?", "terminal")
    assert view.status == "terminal" and view.run_id is None and view.agent == "antigravity"
    assert view.finished_at is None
    order = f"Usa el skill assistant de CandidatAI para la petición {view.id}."
    assert len(terminal) == 1 and order in terminal[0]
    assert "¿Qué tengo hoy?" not in terminal[0]  # el texto no va en la orden
    with session_scope() as session:
        assert assistant.pending(session, view.id).open
        assistant.save_answer(session, view.id, "Nada pendiente.")
        done = assistant.get(session, view.id)
    assert done.status == "done" and done.answer == "Nada pendiente." and done.finished_at


def test_terminal_mode_cancel_closes_it(db: None, terminal: list[str]) -> None:
    with session_scope() as session:
        view = assistant.create(session, "¿Qué tengo hoy?", "terminal")
        assert assistant.cancel(session, view.id).status == "cancelled"
        with pytest.raises(assistant.AssistantClosedError):
            assistant.save_answer(session, view.id, "Tarde.")
        with pytest.raises(LaunchError, match="ya ha terminado"):
            assistant.cancel(session, view.id)


def test_terminal_mode_without_agent_saves_nothing(
    db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(agent_launch, "_launchers", lambda: [])
    with session_scope() as session:
        with pytest.raises(LaunchError):
            assistant.create(session, "¿Qué tengo hoy?", "terminal")
        assert assistant.list_conversations(session).conversations == []


def test_terminal_mode_stops_waiting_after_a_while(db: None, terminal: list[str]) -> None:
    with session_scope() as session:
        view = assistant.create(session, "¿Qué tengo hoy?", "terminal")
        listed = assistant.list_conversations(session).conversations
        assert [c.active for c in listed] == [True]  # trabajando, también en la barra
        row = session.get(AssistantRequest, view.id)
        assert row is not None
        row.created_at = utcnow() - timedelta(hours=assistant.TERMINAL_HOURS, minutes=1)
        session.flush()
        old = assistant.get(session, view.id)
        assert old.status == "failed" and old.error == assistant.TERMINAL_EXPIRED
        assert old.finished_at is not None
        assert not assistant.pending(session, view.id).open
        with pytest.raises(assistant.AssistantClosedError):
            assistant.save_answer(session, view.id, "Tarde.")
        assert [c.active for c in assistant.list_conversations(session).conversations] == [False]


def test_at_most_three_terminals_at_once(db: None, terminal: list[str]) -> None:
    with session_scope() as session:
        for _ in range(assistant.MAX_ACTIVE):
            assistant.create(session, "Hola", "terminal")
        with pytest.raises(LaunchError, match="abiertas en la terminal"):
            assistant.create(session, "Hola", "terminal")
    assert len(terminal) == assistant.MAX_ACTIVE
