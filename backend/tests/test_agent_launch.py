"""Botones «en tu agente» (ADR-024): órdenes cerradas, comando desde el manifiesto, y la API solo
desde la UI. Ningún test abre una terminal de verdad: `_open_terminal` se sustituye."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.services import agent_launch
from app.services.agent_launch import LaunchError
from tests.test_api_triage import add_extracted, import_profile

JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Windows con `claude` instalado; registra las terminales que se abrirían."""
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(agent_launch.sys, "platform", "win32")
    monkeypatch.setattr(agent_launch.shutil, "which", lambda name: f"C:/bin/{name}.exe")
    monkeypatch.setattr(agent_launch, "_open_terminal", lambda t, c: calls.append((t, c)))
    return calls


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


# --- Servicio ----------------------------------------------------------------------------------


def test_prompts_are_fixed_and_only_take_a_job_id() -> None:
    assert agent_launch.prompt_for("buscar-ofertas").startswith("Usa el skill buscar-ofertas")
    assert agent_launch.prompt_for("generar-cv", 42) == (
        "Usa el skill generar-cv de Job Hunter para la oferta 42."
    )
    with pytest.raises(LaunchError, match="necesita una oferta"):
        agent_launch.prompt_for("generar-cv")


def test_skills_page_prompts_carry_no_skill_names() -> None:
    """Fase 14: los nombres de las skills vienen de las ofertas; el agente los lee de las marcas."""
    assert agent_launch.prompt_for("anadir-skills").startswith("Usa el skill actualizar-perfil")
    assert "get_skill_gaps" in agent_launch.prompt_for("anadir-skills")
    assert agent_launch.prompt_for("plan-formacion").startswith("Usa el skill plan-formacion")
    for action in ("anadir-skills", "plan-formacion"):
        assert agent_launch.ACTIONS[action].needs_job is False


def test_launchers_come_from_the_manifest() -> None:
    launchers = {launcher.agent: launcher for launcher in agent_launch._launchers()}
    assert launchers["claude"].command == ["claude", "{prompt}"]
    assert launchers["claude"].unset_env == ["ANTHROPIC_API_KEY"]
    assert "codex" in launchers


def test_powershell_command_unsets_api_keys_and_quotes_the_prompt() -> None:
    launcher = agent_launch._Launcher("claude", ["claude", "{prompt}"], ["ANTHROPIC_API_KEY"])
    command = agent_launch.powershell_command(launcher, "Usa 'esto'; y aquello")
    assert command == (
        "Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue; "
        "& 'claude' 'Usa ''esto''; y aquello'"
    )


def test_info_without_windows_or_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_launch.sys, "platform", "linux")
    assert agent_launch.info().available is False
    monkeypatch.setattr(agent_launch.sys, "platform", "win32")
    monkeypatch.setattr(agent_launch.shutil, "which", lambda name: None)
    info = agent_launch.info()
    assert info.available is False and "PATH" in (info.reason or "")


def test_jh_agent_picks_the_agent(
    opened: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("JH_AGENT", "codex")
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert agent_launch.info().agent == "codex"
    monkeypatch.setenv("JH_AGENT", "otro")
    get_settings.cache_clear()
    assert "JH_AGENT=otro" in (agent_launch.info().reason or "")


# --- API ---------------------------------------------------------------------------------------


def test_get_lists_agent_and_actions(client: TestClient, opened: list[tuple[str, str]]) -> None:
    body = client.get("/agent").json()
    assert body["available"] is True and body["agent"] == "claude"
    actions = {a["id"]: a for a in body["actions"]}
    assert set(actions) == {
        "buscar-ofertas",
        "procesar-ofertas",
        "evaluar-encaje",
        "generar-cv",
        "anadir-skills",
        "plan-formacion",
    }
    assert actions["generar-cv"]["needs_job"] is True and actions["generar-cv"]["prompt"] is None
    assert "buscar-ofertas" in actions["buscar-ofertas"]["prompt"]


def test_launch_opens_a_terminal(client: TestClient, opened: list[tuple[str, str]]) -> None:
    response = client.post("/agent/launch", json={"action": "buscar-ofertas"}, headers=JSON)
    assert response.status_code == 202
    assert response.json()["agent"] == "claude"
    [(title, command)] = opened
    assert title == "Job Hunter · Buscar ofertas"
    assert "& 'claude' 'Usa el skill buscar-ofertas" in command


def test_generate_cv_needs_an_approved_job(
    client: TestClient, opened: list[tuple[str, str]]
) -> None:
    import_profile()
    job_id = add_extracted("Data Engineer", "Acme")
    body = {"action": "generar-cv", "job_id": job_id}
    response = client.post("/agent/launch", json=body, headers=JSON)
    assert response.status_code == 422
    assert "aprobada" in response.json()["error"]["message"]

    client.post(f"/jobs/{job_id}/events", json={"type": "approved"})
    response = client.post("/agent/launch", json=body, headers=JSON)
    assert response.status_code == 202
    assert opened[-1][1].endswith(f"para la oferta {job_id}.'")

    missing = client.post("/agent/launch", json={**body, "job_id": 999}, headers=JSON)
    assert missing.status_code == 404


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://example.com", "Content-Type": "application/json"},
        {"Origin": UI_ORIGIN, "Content-Type": "text/plain"},
    ],
)
def test_only_the_ui_can_launch(
    client: TestClient, opened: list[tuple[str, str]], headers: dict[str, str]
) -> None:
    response = client.post("/agent/launch", content='{"action": "buscar-ofertas"}', headers=headers)
    assert response.status_code == 403
    assert opened == []


def test_unavailable_returns_the_prompt_to_copy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(agent_launch.sys, "platform", "linux")
    response = client.post("/agent/launch", json={"action": "procesar-ofertas"}, headers=JSON)
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["type"] == "agent_unavailable"
    assert error["details"][0]["field"] == "prompt"
    assert error["details"][0]["received"].startswith("Usa el skill procesar-ofertas")


def test_shell_args_carry_no_characters_wt_would_split() -> None:
    import base64

    launcher = agent_launch._Launcher("claude", ["claude", "{prompt}"], ["ANTHROPIC_API_KEY"])
    command = agent_launch.powershell_command(launcher, agent_launch.prompt_for("generar-cv", 7))
    args = agent_launch.shell_args(command)
    # `wt` parte su línea de comandos por cada `;`: ninguno puede llegarle.
    assert not any(";" in arg for arg in args)
    assert args[:4] == ["powershell", "-NoLogo", "-NoExit", "-EncodedCommand"]
    assert base64.b64decode(args[4]).decode("utf-16-le") == command
