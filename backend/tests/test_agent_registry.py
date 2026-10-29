"""Registro de agentes (fase 24.1): manifiesto validado, detección, `cai agents` y la API."""

import json
import os
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from app import cli
from app.api.main import create_app
from app.core import migrations
from app.core.config import REPO_ROOT, get_settings
from app.services import agent_registry, doctor
from app.services.agent_registry import Detection, ManifestError
from app.services.doctor import CheckStatus

runner = CliRunner()

FAKE_DETECT = """
import os, sys, time
if "--slow" in sys.argv:
    time.sleep(30)
key = "con clave" if os.environ.get("CAI_FAKE_AGENT_KEY") else "sin clave"
print()
print(f"fake-agent 1.2.3 ({key})")
sys.exit(3 if "--fail" in sys.argv else 0)
"""


@pytest.fixture(autouse=True)
def fresh_detection() -> Iterator[None]:
    agent_registry.clear_detection_cache()
    yield
    agent_registry.clear_detection_cache()


@pytest.fixture
def db() -> None:
    migrations.upgrade()


@pytest.fixture
def fake_detect(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Detección sin lanzar procesos: instalados solo `claude` y `copilot`."""
    calls: list[str] = []

    def run(command: list[str], unset_env: list[str], timeout: float) -> Detection:
        calls.append(command[0])
        if command[0] in ("claude", "copilot"):
            return Detection(installed=True, version=f"{command[0]} 9.9")
        return Detection(installed=False)

    monkeypatch.setattr(agent_registry, "_run_detect", run)
    return calls


def _real_manifest() -> dict[str, Any]:
    return yaml.safe_load(agent_registry.MANIFEST.read_text(encoding="utf-8"))


def _write(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


# --- Manifiesto ---------------------------------------------------------------------------------


def test_real_manifest_loads() -> None:
    agents = agent_registry.load()
    assert list(agents) == [
        "claude",
        "codex",
        "antigravity",
        "opencode",
        "qwen",
        "cursor",
        "copilot",
        "pi",
        "gemini",
        "goose",
    ]
    for name in ("claude", "codex", "opencode", "qwen", "antigravity"):
        assert agents[name].enabled and agents[name].config == "generated", name
    assert agents["claude"].capabilities.isolation_level == "A"
    assert agents["codex"].capabilities.isolation_level == "B"
    # Fase 24.3: A solo tras la prueba manual del aislamiento. Antigravity lanza subagentes, pero
    # con las herramientas de la sesión (sin roles generados): sigue en C.
    assert agents["opencode"].capabilities.isolation_level == "B"
    assert agents["qwen"].capabilities.isolation_level == "B"
    assert agents["antigravity"].capabilities.isolation_level == "C"
    assert agents["antigravity"].capabilities.subagents == "inherited"
    assert agents["antigravity"].info.invoke == "/{skill} {args}"
    # Tercera opción de pago: se abre con la orden, como Claude Code y Codex; sin segundo plano.
    assert agents["antigravity"].launchable and agents["antigravity"].headless is None
    for name in ("cursor", "copilot", "pi", "gemini", "goose"):
        spec = agents[name]
        assert not spec.enabled and spec.config == "none", name
        assert spec.capabilities.isolation_level == "C", name
        assert spec.launch is None and not spec.launchable, name


def test_headless_capability_is_derived_from_launch() -> None:
    agents = agent_registry.load()
    assert agents["claude"].capabilities.headless is True
    assert agents["claude"].headless is not None
    assert agents["codex"].capabilities.headless is False


def test_misspelled_key_names_agent_and_key(tmp_path: Path) -> None:
    data = _real_manifest()
    data["targets"]["codex"]["capabilites"] = data["targets"]["codex"].pop("capabilities")
    with pytest.raises(ManifestError) as exc:
        agent_registry.load(_write(tmp_path / "manifest.yaml", data))
    message = str(exc.value)
    assert "«codex»" in message
    assert "clave desconocida «capabilites»" in message
    assert "targets.codex.capabilities: falta la clave" in message


def test_misspelled_nested_key(tmp_path: Path) -> None:
    data = _real_manifest()
    data["targets"]["pi"]["info"]["dispaly_name"] = "Pi"
    with pytest.raises(ManifestError, match=r"targets\.pi\.info\.dispaly_name: clave desconocida"):
        agent_registry.load(_write(tmp_path / "manifest.yaml", data))


def test_invalid_values(tmp_path: Path) -> None:
    data = _real_manifest()
    data["targets"]["goose"]["capabilities"]["isolation_level"] = "D"
    with pytest.raises(ManifestError, match=r"goose\.capabilities\.isolation_level"):
        agent_registry.load(_write(tmp_path / "a.yaml", data))

    data = _real_manifest()
    data["targets"]["claude"]["capabilities"]["headless"] = True
    with pytest.raises(ManifestError, match="se deriva"):
        agent_registry.load(_write(tmp_path / "b.yaml", data))

    data = _real_manifest()
    data["targets"]["cursor"]["enabled"] = True
    with pytest.raises(ManifestError, match="cursor.*config: generated"):
        agent_registry.load(_write(tmp_path / "c.yaml", data))


def test_cache_follows_modification_time(tmp_path: Path) -> None:
    data = _real_manifest()
    path = _write(tmp_path / "manifest.yaml", data)
    first = agent_registry.load(path)
    assert agent_registry.load(path) is first  # sin cambios: la misma lectura

    data["targets"]["pi"]["info"]["display_name"] = "Pi nuevo"
    _write(path, data)
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    assert agent_registry.load(path)["pi"].info.display_name == "Pi nuevo"


def test_incomplete_headless_means_no_background(tmp_path: Path) -> None:
    data = _real_manifest()
    command = data["targets"]["claude"]["launch"]["headless"]["command"]
    command.remove("{denied_tools}")
    spec = agent_registry.load(_write(tmp_path / "manifest.yaml", data))["claude"]
    assert spec.headless is None and spec.capabilities.headless is False


def test_launch_and_runner_do_not_read_the_yaml() -> None:
    for module in ("agent_launch.py", "agent_runner.py"):
        source = (REPO_ROOT / "backend" / "app" / "services" / module).read_text(encoding="utf-8")
        assert "import yaml" not in source, module
        assert "safe_load" not in source, module
        assert "MANIFEST" not in source, module


# --- Detección ----------------------------------------------------------------------------------


def _spec_with_detect(tmp_path: Path, *args: str) -> agent_registry.AgentSpec:
    script = tmp_path / "fake_agent.py"
    script.write_text(FAKE_DETECT, encoding="utf-8")
    data = _real_manifest()
    claude = data["targets"]["claude"]
    claude["info"]["detect"] = [sys.executable, str(script), *args]
    claude["launch"]["unset_env"] = ["cai_fake_agent_key"]  # sin distinguir mayúsculas
    return agent_registry.load(_write(tmp_path / "manifest.yaml", data))["claude"]


def test_detect_reads_version_without_unset_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAI_FAKE_AGENT_KEY", "secreta")
    found = agent_registry.detect(_spec_with_detect(tmp_path))
    assert found == Detection(installed=True, version="fake-agent 1.2.3 (sin clave)")


def test_detect_respects_the_timeout(tmp_path: Path) -> None:
    spec = _spec_with_detect(tmp_path, "--slow")
    started = time.monotonic()
    found = agent_registry.detect(spec, timeout=1.0)
    assert time.monotonic() - started < 10
    assert found.installed and found.version is None
    assert found.error == "no respondió en 1 s"


def test_detect_failure_and_missing_program(tmp_path: Path) -> None:
    found = agent_registry.detect(_spec_with_detect(tmp_path, "--fail"))
    assert found.installed and found.error == "salió con el código 3"

    data = _real_manifest()
    data["targets"]["pi"]["info"]["detect"] = ["cai-no-existe-este-agente", "--version"]
    spec = agent_registry.load(_write(tmp_path / "other.yaml", data))["pi"]
    assert agent_registry.detect(spec) == Detection(installed=False)


def test_detect_is_cached(fake_detect: list[str]) -> None:
    spec = agent_registry.load()["claude"]
    agent_registry.detect(spec)
    agent_registry.detect(spec)
    assert fake_detect == ["claude"]
    agent_registry.detect(spec, refresh=True)
    assert fake_detect == ["claude", "claude"]


def test_list_agents(fake_detect: list[str]) -> None:
    listed = {entry.name: entry for entry in agent_registry.list_agents().agents}
    assert listed["claude"].installed and listed["claude"].version == "claude 9.9"
    assert listed["copilot"].installed and not listed["copilot"].enabled
    assert not listed["codex"].installed
    assert listed["pi"].info.open_source and listed["pi"].info.license == "MIT"


# --- CLI, API y doctor ---------------------------------------------------------------------------


def test_cli_agents_list_json(db: None, fake_detect: list[str]) -> None:
    result = runner.invoke(cli.app, ["agents", "list", "--json"])
    assert result.exit_code == 0, result.output
    agents = {a["name"]: a for a in json.loads(result.output)["agents"]}
    assert set(agents) == {
        "claude",
        "codex",
        "opencode",
        "qwen",
        "antigravity",
        "cursor",
        "copilot",
        "pi",
        "gemini",
        "goose",
    }
    for name in ("opencode", "qwen", "antigravity"):
        assert agents[name]["config"] == "generated" and agents[name]["enabled"] is True, name
    gemini = agents["gemini"]
    assert gemini["enabled"] is False and gemini["config"] == "none"
    assert "clave de pago" in gemini["info"]["note"]
    none = {"example": None, "fast": None, "capable": None}
    assert agents["codex"]["models"] == {"by_name": True, "presets": ["local"], **none}
    assert agents["goose"]["models"] == {"by_name": False, "presets": [], **none}
    assert agents["claude"]["models"]["fast"] == "haiku"  # los roles no heredan el de la sesión
    assert agents["opencode"]["models"]["example"] == "ollama/qwen3:8b"
    assert "preferences" in json.loads(result.output) and "effective" in json.loads(result.output)
    assert agents["claude"]["enabled"] is True and agents["claude"]["installed"] is True
    assert agents["goose"]["config"] == "none" and agents["goose"]["enabled"] is False
    assert agents["claude"]["capabilities"]["headless"] is True
    assert agents["codex"]["info"]["invoke"] == "${skill} {args}"


def test_cli_agents_list_text(fake_detect: list[str]) -> None:
    result = runner.invoke(cli.app, ["agents", "list"])
    assert result.exit_code == 0, result.output
    assert "Claude Code (claude)" in result.output
    assert "solo compatible vía AGENTS.md" in result.output
    assert "Gemini CLI (gemini)\n  deshabilitado" in result.output
    assert "clave de pago de la API de Gemini" in result.output


def test_cli_agents_list_with_invalid_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _real_manifest()
    data["targets"]["codex"]["enabld"] = True
    monkeypatch.setattr(agent_registry, "MANIFEST", _write(tmp_path / "manifest.yaml", data))
    result = runner.invoke(cli.app, ["agents", "list", "--json"])
    assert result.exit_code == 1
    assert "enabld" in json.loads(result.output)["error"]["message"]


def test_cli_agents_doctor(fake_detect: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import agent_launch

    monkeypatch.setattr(agent_launch.shutil, "which", lambda name: f"C:/bin/{name}.exe")
    result = runner.invoke(cli.app, ["agents", "doctor"])
    assert result.exit_code == 0, result.output
    assert "Se usaría: claude (el primero del manifiesto" in result.output
    assert "En segundo plano: claude." in result.output
    assert "falta instalarlo: npm install -g @openai/codex" in result.output
    assert "sin configuración generada" in result.output
    assert "no se recomienda: Desde el 18/06/2026" in result.output
    # Antigravity se abre con la orden (`agy -i`, desde la 1.4.5), pero sin segundo plano.
    antigravity = result.output.split("Antigravity CLI (antigravity)")[1].split("\n\n")[0]
    assert "copian la orden" not in antigravity and "sin «En segundo plano»" in antigravity


def test_overview_follows_cai_agent(
    fake_detect: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import agent_launch

    monkeypatch.setattr(agent_launch.shutil, "which", lambda name: f"C:/bin/{name}.exe")
    monkeypatch.setenv("CAI_AGENT", "codex")
    get_settings.cache_clear()
    try:
        overview = doctor.agents_overview(get_settings())
    finally:
        get_settings.cache_clear()
    assert overview.selected == "codex"
    assert overview.selected_reason == "porque CAI_AGENT=codex"
    assert overview.background is None and "launch.headless" in (overview.background_reason or "")


def test_check_agents(fake_detect: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import agent_launch

    monkeypatch.setattr(agent_launch.shutil, "which", lambda name: f"C:/bin/{name}.exe")
    result = doctor.check_agents(get_settings())
    assert result.status == CheckStatus.OK
    assert "se usa Claude Code claude 9.9" in result.detail
    assert "también instalados: GitHub Copilot CLI" in result.detail

    monkeypatch.setattr(agent_launch.shutil, "which", lambda name: None)
    assert doctor.check_agents(get_settings()).status == CheckStatus.WARN


def test_check_agents_with_invalid_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _real_manifest()
    data["targets"]["claude"]["info"]["licence"] = "x"
    monkeypatch.setattr(agent_registry, "MANIFEST", _write(tmp_path / "manifest.yaml", data))
    result = doctor.check_agents(get_settings())
    assert result.status == CheckStatus.ERROR
    assert "licence" in result.detail


def test_api_lists_agents(db: None, fake_detect: list[str]) -> None:
    with TestClient(create_app()) as client:
        response = client.get("/agent/agents")
    assert response.status_code == 200
    agents = {a["name"]: a for a in response.json()["agents"]}
    assert agents["copilot"]["installed"] is True
    assert agents["copilot"]["info"]["display_name"] == "GitHub Copilot CLI"
    assert agents["cursor"]["capabilities"]["isolation_level"] == "C"


def test_cli_and_api_return_the_same(db: None, fake_detect: list[str]) -> None:
    result = runner.invoke(cli.app, ["agents", "list", "--json"])
    with TestClient(create_app()) as client:
        response = client.get("/agent/agents")
    assert json.loads(result.output) == response.json()


def test_broken_manifest_is_the_reason_in_the_ui(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import agent_launch

    data = _real_manifest()
    data["targets"]["claude"]["lanch"] = data["targets"]["claude"].pop("launch")
    monkeypatch.setattr(agent_registry, "MANIFEST", _write(tmp_path / "manifest.yaml", data))
    monkeypatch.setattr(agent_launch.sys, "platform", "win32")
    info = agent_launch.info()
    assert not info.available
    assert "no es válido" in (info.reason or "") and "lanch" in (info.reason or "")


def test_selection_with_unknown_cai_agent(
    fake_detect: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAI_AGENT", "otro")
    get_settings.cache_clear()
    try:
        overview = doctor.agents_overview(get_settings())
    finally:
        get_settings.cache_clear()
    assert overview.selected is None
    assert "CAI_AGENT=otro" in overview.selected_reason


def test_detection_misses_expire_sooner(
    fake_detect: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    agents = agent_registry.load()
    agent_registry.detect(agents["codex"])  # no instalado
    agent_registry.detect(agents["claude"])  # con versión
    monkeypatch.setattr(agent_registry, "DETECT_TTL_MISS", 0.0)
    agent_registry.detect(agents["codex"])
    agent_registry.detect(agents["claude"])
    assert fake_detect == ["codex", "claude", "codex"]


# --- Modelos (fase 24.3) -------------------------------------------------------------------------


def test_model_args_from_flag_and_presets() -> None:
    agents = agent_registry.load()
    assert agents["claude"].model_args() == []
    assert agents["claude"].model_args(model="opus") == ["--model", "opus"]
    assert agents["codex"].model_args(model="o4-mini") == ["-m", "o4-mini"]
    assert agents["codex"].model_args(preset="local") == ["--oss", "-m", "gpt-oss:20b"]
    assert agents["opencode"].model_args(model="ollama/qwen3") == ["-m", "ollama/qwen3"]
    assert agents["qwen"].model_args(model="qwen3-coder") == ["-m", "qwen3-coder"]
    with pytest.raises(ValueError, match="no tiene el preset «local»"):
        agents["claude"].model_args(preset="local")
    with pytest.raises(ValueError, match="no sabe elegir el modelo"):
        agents["goose"].model_args(model="x")
    with pytest.raises(ValueError, match="no los dos"):
        agents["codex"].model_args(model="x", preset="local")


def test_launch_command_with_a_model() -> None:
    """Lo que la 24.4 lanzará: la orden de `launch` más los argumentos del modelo."""
    codex = agent_registry.load()["codex"]
    assert codex.launch is not None
    command = [*codex.launch.command, *codex.model_args(preset="local")]
    assert command == ["codex", "{prompt}", "--oss", "-m", "gpt-oss:20b"]
    opencode = agent_registry.load()["opencode"]
    assert opencode.launch is not None
    assert [*opencode.launch.command, *opencode.model_args(model="ollama/qwen3")] == [
        "opencode",
        "--prompt",
        "{prompt}",
        "-m",
        "ollama/qwen3",
    ]


def test_invalid_models(tmp_path: Path) -> None:
    data = _real_manifest()
    data["targets"]["codex"]["models"]["flag"] = ["-m"]
    with pytest.raises(ManifestError, match=r"codex\.models.*\{model\}"):
        agent_registry.load(_write(tmp_path / "a.yaml", data))

    data = _real_manifest()
    data["targets"]["codex"]["models"]["presets"]["vacio"] = []
    with pytest.raises(ManifestError, match="preset «vacio» está vacío"):
        agent_registry.load(_write(tmp_path / "b.yaml", data))

    data = _real_manifest()
    data["targets"]["codex"]["models"]["fsat"] = "x"
    with pytest.raises(ManifestError, match="clave desconocida «fsat»"):
        agent_registry.load(_write(tmp_path / "c.yaml", data))
