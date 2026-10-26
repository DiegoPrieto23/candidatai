"""Elegir agente y modelo (fase 24.4): precedencia, comprobaciones por capacidad y por
nivel, el modelo en el comando de cada agente, `CAI_CLIENT_NAME` y la API de extremo a extremo con
agentes falsos. Ningún test abre una terminal ni lanza un agente de verdad."""

import base64
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.config import get_settings
from app.core.db import session_scope
from app.models import AgentRun
from app.services import agent_launch, agent_prefs, agent_registry, agent_runs
from app.services.agent_launch import LaunchError
from app.services.agent_prefs import ActionPref, ModelPref, PreferenceError, Preferences

JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}
LAUNCHABLE = ["claude", "codex", "opencode", "qwen"]


@pytest.fixture
def db() -> None:
    migrations.upgrade()


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Todos los agentes instalados y la terminal de Windows (PowerShell); devuelve lo que
    ejecutaría cada terminal. Sin simular `win32` en todo el proceso: en macOS y Linux, la
    detección de los agentes usaría opciones que solo existen en Windows (fase 26.2)."""
    commands: list[str] = []
    monkeypatch.setattr(agent_launch, "no_terminal", lambda: None)
    monkeypatch.setattr(agent_launch, "terminal_command", agent_launch.powershell_command)
    monkeypatch.setattr(agent_launch.shutil, "which", lambda name: f"C:/bin/{name}.exe")
    monkeypatch.setattr(agent_launch, "_open_terminal", lambda t, c: commands.append(c))
    return commands


@pytest.fixture
def client(db: None) -> Iterator[TestClient]:
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture
def manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Cambia el manifiesto real para un test: `manifest(lambda data: …)`."""

    def change(edit: Any) -> None:
        data = yaml.safe_load(agent_registry.MANIFEST.read_text(encoding="utf-8"))
        edit(data["targets"])
        path = tmp_path / "manifest.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
        monkeypatch.setattr(agent_registry, "MANIFEST", path)

    return change


def resolve(
    prefs: Preferences | None = None,
    action: str | None = "assess-fit",
    installed: tuple[str, ...] = tuple(LAUNCHABLE),
    env: str | None = None,
    **kwargs: Any,
) -> agent_prefs.Resolution:
    return agent_prefs.resolve(
        prefs or Preferences(),
        action,
        candidates=LAUNCHABLE,
        installed=lambda name: name in installed,
        env_agent=env,
        **kwargs,
    )


def decoded(terminal: str) -> str:
    """Lo que ejecuta la ventana: el último argumento de `shell_args` es la orden en base64."""
    return base64.b64decode(agent_launch.shell_args(terminal)[-1]).decode("utf-16-le")


# --- Precedencia -------------------------------------------------------------------------------


def test_precedence_button_action_default_env_first_installed() -> None:
    first = resolve(installed=("codex", "qwen"))
    assert (first.agent, first.reason) == ("codex", "first_installed")
    assert resolve(env="qwen").agent == "qwen" and resolve(env="qwen").reason == "env"

    prefs = Preferences(default_agent="opencode")
    assert (resolve(prefs, env="qwen").agent, resolve(prefs).reason) == ("opencode", "default")

    prefs.actions["assess-fit"] = ActionPref(agent="qwen")
    assert (resolve(prefs).agent, resolve(prefs).reason) == ("qwen", "action")
    assert resolve(prefs, action="process-jobs").agent == "opencode"  # otra acción: por defecto

    button = resolve(prefs, agent="codex")
    assert (button.agent, button.reason, button.reason_text) == (
        "codex",
        "explicit",
        "elegido para esta ejecución",
    )
    assert button.display_name == "Codex" and button.usable


def test_model_comes_from_the_level_that_chose_the_agent() -> None:
    prefs = Preferences(
        default_agent="codex",
        agents={"codex": ModelPref(preset="local"), "opencode": ModelPref(model="ollama/qwen3:8b")},
        actions={"generate-cv": ActionPref(agent="codex", model="gpt-5.5")},
    )
    assert (resolve(prefs).preset, resolve(prefs).model) == ("local", None)
    cv = resolve(prefs, action="generate-cv")
    assert (cv.model, cv.preset) == ("gpt-5.5", None)
    # Una acción con agente y sin modelo usa el guardado para ese agente.
    prefs.actions["assess-fit"] = ActionPref(agent="opencode")
    assert resolve(prefs).model == "ollama/qwen3:8b"
    # El botón: su modelo, o el del agente que elige.
    assert resolve(prefs, agent="codex", model="o4").model == "o4"
    assert resolve(prefs, agent="opencode").model == "ollama/qwen3:8b"


def test_preferred_agent_not_installed_is_not_replaced() -> None:
    res = resolve(Preferences(default_agent="codex"), installed=("claude",))
    assert res.agent == "codex" and not res.usable
    assert res.blocked_code == "not_installed" and "no está instalado" in (res.blocked or "")


def test_no_agent_installed_and_unknown_cai_agent() -> None:
    none = resolve(installed=())
    assert none.agent is None and none.blocked_code == "no_agent" and "PATH" in (none.blocked or "")
    unknown = resolve(env="otro")
    assert unknown.agent is None and "CAI_AGENT=otro" in (unknown.blocked or "")


# --- Capacidades y niveles ---------------------------------------------------------------------


def test_capabilities_block_when_false_and_warn_when_unchecked(manifest: Any) -> None:
    # Codex: `browser: null` en el manifiesto real (sin comprobar): se puede, con aviso.
    unchecked = resolve(action="search-jobs", agent="codex")
    assert unchecked.usable and "Sin comprobar si Codex tiene navegador" in (
        unchecked.warning or ""
    )
    assert resolve(action="search-jobs", agent="claude").warning is None

    def no_browser_or_web(targets: dict[str, Any]) -> None:
        targets["codex"]["capabilities"]["browser"] = False
        targets["codex"]["capabilities"]["web"] = False

    manifest(no_browser_or_web)
    for action in ("search-jobs", "research-company", "training-plan", "expand"):
        res = resolve(action=action, agent="codex")
        assert not res.usable and res.blocked_code == "capability", action
    assert resolve(action="assess-fit", agent="codex").usable
    assert agent_prefs.REQUIRES["import-cv-template"] == ("vision",)


def test_level_c_with_untrusted_content_warns_in_terminal_and_never_runs_unattended(
    manifest: Any,
) -> None:
    manifest(lambda targets: targets["qwen"]["capabilities"].update(isolation_level="C"))
    for action in ("process-jobs", "review-replies", "search-jobs", "expand"):
        terminal = resolve(action=action, agent="qwen")
        assert terminal.usable and "sesión dedicada" in (terminal.warning or ""), action
        background = resolve(action=action, agent="qwen", mode="background")
        assert background.blocked_code == "untrusted", action
    assert resolve(action="assess-fit", agent="qwen", mode="background").usable


# --- Modelos -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("agent", "model", "preset", "problem"),
    [
        ("opencode", "ollama/qwen3:8b", None, None),
        ("opencode", "qwen3", None, "formato de OpenCode"),
        ("claude", "sonnet", None, None),
        ("claude", "-rf", None, "no es válido"),
        ("claude", "son net", None, "no es válido"),
        ("claude", "a;b", None, "no es válido"),
        ("claude", None, "local", "no tiene el preset"),
        ("codex", None, "local", None),
        ("codex", "o4", "local", "no los dos"),
    ],
)
def test_model_is_validated_with_the_agent_format(
    agent: str, model: str | None, preset: str | None, problem: str | None
) -> None:
    spec = agent_registry.get(agent)
    assert spec is not None
    found = agent_prefs.model_problem(spec, model, preset)
    assert found is None if problem is None else problem in (found or "")


def test_launch_command_carries_the_model_with_each_agent_flag(db: None, opened: list[str]) -> None:
    cases = {
        ("claude", "sonnet", None): ["claude", "--model", "sonnet", "{prompt}"],
        ("codex", None, "local"): ["codex", "--oss", "-m", "gpt-oss:20b", "{prompt}"],
        ("opencode", "ollama/qwen3:8b", None): [
            "opencode",
            "-m",
            "ollama/qwen3:8b",
            "--prompt",
            "{prompt}",
        ],
        ("qwen", "qwen3-coder", None): ["qwen", "-m", "qwen3-coder", "-i", "{prompt}"],
        ("claude", None, None): ["claude", "{prompt}"],
    }
    with session_scope() as session:
        for (agent, model, preset), command in cases.items():
            launcher, res = agent_launch.choose(
                session, "assess-fit", agent=agent, model=model, preset=preset
            )
            assert launcher is not None, res.blocked
            assert launcher.command == command
    # En segundo plano, el modelo también va detrás del programa.
    with session_scope() as session:
        launcher, _ = agent_launch.choose(
            session, "process-jobs", agent="claude", model="haiku", mode="background"
        )
    assert launcher is not None and launcher.headless is not None
    assert launcher.headless.command[:3] == ["claude", "--model", "haiku"]


# --- Guardar -----------------------------------------------------------------------------------


def test_save_validates_and_round_trips(db: None) -> None:
    prefs = Preferences(
        default_agent="codex",
        agents={"codex": ModelPref(preset="local"), "claude": ModelPref()},
        actions={"generate-cv": ActionPref(agent="claude", model="opus")},
    )
    with session_scope() as session:
        saved = agent_prefs.save_preferences(session, prefs, LAUNCHABLE)
    assert saved.default_agent == "codex"
    assert set(saved.agents) == {"codex"}  # sin modelo ni preset no se guarda
    with session_scope() as session:
        again = agent_prefs.get_preferences(session)
    assert again == saved and again.actions["generate-cv"].model == "opus"

    bad = [
        (Preferences(default_agent="gemini"), "default_agent"),
        (Preferences(default_agent="antigravity"), "default_agent"),  # sin `launch`
        (Preferences(default_agent="nadie"), "default_agent"),
        (Preferences(agents={"opencode": ModelPref(model="qwen3")}), "agents.opencode"),
        (
            Preferences(actions={"assess-fit": ActionPref(agent="cursor")}),
            "actions.assess-fit.agent",
        ),
    ]
    for prefs, field in bad:
        with session_scope() as session, pytest.raises(PreferenceError) as exc:
            agent_prefs.save_preferences(session, prefs, LAUNCHABLE)
        assert exc.value.field == field
    with session_scope() as session:  # lo que falla no pisa lo guardado
        assert agent_prefs.get_preferences(session).default_agent == "codex"


# --- API de extremo a extremo ------------------------------------------------------------------


def _put(client: TestClient, body: dict[str, Any]) -> Any:
    return client.put("/agent/preferences", json=body, headers={"Origin": UI_ORIGIN})


def _effective(client: TestClient, action: str) -> dict[str, Any]:
    actions = {a["id"]: a for a in client.get("/agent").json()["actions"]}
    return actions[action]


def test_default_and_action_preferences_are_used_by_the_next_launch(
    client: TestClient, opened: list[str]
) -> None:
    assert _effective(client, "assess-fit")["agent"]["agent"] == "claude"
    body = {
        "default_agent": "codex",
        "agents": {"codex": {"preset": "local"}},
        "actions": {"review-search": {"agent": "opencode", "model": "ollama/qwen3:8b"}},
    }
    assert _put(client, body).status_code == 200

    effective = _effective(client, "assess-fit")
    assert effective["agent"]["agent"] == "codex" and effective["agent"]["reason"] == "default"
    assert {a["agent"] for a in effective["alternatives"]} == {"claude", "opencode", "qwen"}

    launched = client.post("/agent/launch", json={"action": "assess-fit"}, headers=JSON)
    assert launched.status_code == 202 and launched.json()["model"] == "preset local"
    assert "$env:CAI_CLIENT_NAME = 'codex'" in decoded(opened[-1])
    assert "& 'codex' '--oss' '-m' 'gpt-oss:20b' 'Usa el skill assess-fit" in decoded(opened[-1])

    client.post("/agent/launch", json={"action": "review-search"}, headers=JSON)
    assert "& 'opencode' '-m' 'ollama/qwen3:8b' '--prompt'" in decoded(opened[-1])
    assert "CAI_CLIENT_NAME = 'opencode'" in decoded(opened[-1])

    # Elegido solo para esta ejecución, sin tocar las preferencias.
    once = client.post(
        "/agent/launch", json={"action": "assess-fit", "agent": "qwen"}, headers=JSON
    )
    assert once.json()["agent"] == "qwen" and "& 'qwen' '-i'" in decoded(opened[-1])
    assert _effective(client, "assess-fit")["agent"]["agent"] == "codex"

    overview = client.get("/agent/agents").json()
    assert overview["preferences"]["default_agent"] == "codex"
    by_action = {e["action"]: e for e in overview["effective"]}
    assert by_action["review-search"]["terminal"]["reason_text"] == "elegido para esta acción"
    assert by_action["process-jobs"]["background"]["blocked_code"] == "no_headless"


def test_background_uses_the_preferred_agent_and_model(
    client: TestClient, opened: list[str]
) -> None:
    _put(client, {"default_agent": "claude", "agents": {"claude": {"model": "sonnet"}}})
    started = client.post("/agent/runs", json={"action": "process-jobs"}, headers=JSON)
    assert started.status_code == 202, started.text
    assert started.json()["agent"] == "claude" and started.json()["model"] == "sonnet"
    with session_scope() as session:
        row = session.get(AgentRun, started.json()["id"])
        assert row is not None
        assert row.command[:3] == ["claude", "--model", "sonnet"]
        assert (row.model, row.preset) == ("sonnet", None)

    _put(client, {"default_agent": "codex"})  # Codex no tiene segundo plano
    refused = client.post("/agent/runs", json={"action": "assess-fit"}, headers=JSON)
    assert refused.status_code == 503 and "headless" in refused.json()["error"]["message"]
    assert _effective(client, "assess-fit")["background_agent"]["available"] is False


def test_a_missing_capability_cannot_launch_and_says_why(
    client: TestClient, opened: list[str], manifest: Any
) -> None:
    manifest(lambda targets: targets["codex"]["capabilities"].update(browser=False))
    _put(client, {"actions": {"search-jobs": {"agent": "codex"}}})
    effective = _effective(client, "search-jobs")
    assert effective["agent"]["blocked_code"] == "capability"
    assert "navegador" in effective["agent"]["blocked"]
    response = client.post("/agent/launch", json={"action": "search-jobs"}, headers=JSON)
    assert response.status_code == 422 and "navegador" in response.json()["error"]["message"]
    assert opened == []
    # Con otro agente, solo esta vez, sí.
    ok = client.post(
        "/agent/launch", json={"action": "search-jobs", "agent": "claude"}, headers=JSON
    )
    assert ok.status_code == 202


def test_cai_agent_still_works_without_preferences(
    client: TestClient, opened: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAI_AGENT", "qwen")
    get_settings.cache_clear()
    try:
        effective = _effective(client, "assess-fit")["agent"]
        assert (effective["agent"], effective["reason"]) == ("qwen", "env")
        client.post("/agent/launch", json={"action": "assess-fit"}, headers=JSON)
        assert "& 'qwen'" in decoded(opened[-1])
        _put(client, {"default_agent": "claude"})  # una preferencia gana a CAI_AGENT
        assert _effective(client, "assess-fit")["agent"]["agent"] == "claude"
    finally:
        get_settings.cache_clear()


def test_invalid_preferences_and_choices_are_rejected(
    client: TestClient, opened: list[str]
) -> None:
    response = _put(client, {"agents": {"opencode": {"model": "qwen3"}}})
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "agents.opencode"
    assert _put(client, {"default_agent": "claude", "otra": 1}).status_code == 422
    forbidden = client.put("/agent/preferences", json={}, headers={"Origin": "https://evil.test"})
    assert forbidden.status_code == 403

    bad_model = {"action": "assess-fit", "agent": "claude", "model": "--dangerously"}
    response = client.post("/agent/launch", json=bad_model, headers=JSON)
    assert response.status_code == 422 and opened == []
    unknown = client.post(
        "/agent/launch", json={"action": "assess-fit", "agent": "x"}, headers=JSON
    )
    assert unknown.status_code == 422
    # Los encargos no eligen agente.
    request = {"action": "assess-fit", "agent": "claude"}
    assert client.post("/agent/requests", json=request, headers=JSON).status_code == 422


def test_explicit_choice_errors_from_the_service(db: None, opened: list[str]) -> None:
    with session_scope() as session, pytest.raises(LaunchError) as exc:
        agent_launch.launch(session, "assess-fit", agent="codex", model="o4", preset="local")
    assert exc.value.code == "invalid_request"
    with session_scope() as session, pytest.raises(LaunchError) as exc:
        agent_runs.start(session, "process-jobs", agent="codex")
    assert exc.value.code == "unavailable" and exc.value.prompt
