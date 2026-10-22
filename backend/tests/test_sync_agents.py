"""Emisores de `scripts/sync_agents.py` (fase 24.3): cada rol con solo sus herramientas nativas en
cada agente, salida determinista y errores claros."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from app.core.config import REPO_ROOT


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "sync_agents", REPO_ROOT / "scripts" / "sync_agents.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["sync_agents"] = module
    spec.loader.exec_module(module)
    return module


sync = _load_script()
MANIFEST: dict[str, Any] = yaml.safe_load(
    (REPO_ROOT / ".agents" / "manifest.yaml").read_text(encoding="utf-8")
)
ROLES = [
    sync.read_doc(p)
    for p in sorted((REPO_ROOT / ".agents" / "roles").glob("*.md"))
    if p.name != "README.md"
]
TERMINAL_ROLES = {r.meta["name"] for r in ROLES if "git_read" in r.meta.get("tools", [])}


def _emit(agent: str, roles: list[Any] | None = None) -> dict[Path, str]:
    cfg = MANIFEST["targets"][agent]
    return sync.EMITTERS[agent](
        cfg, [], ROLES if roles is None else roles, MANIFEST["mcp_server"], MANIFEST["policy"]
    )


def _frontmatter(text: str) -> dict[str, Any]:
    return yaml.safe_load(text.split("---\n", 2)[1])


def _role_file(agent: str, role: str) -> dict[str, Any]:
    cfg = MANIFEST["targets"][agent]
    return _frontmatter(_emit(agent)[REPO_ROOT / cfg["agents_dir"] / f"{role}.md"])


def test_output_is_deterministic() -> None:
    first, _ = sync.build()
    second, _ = sync.build()
    assert first == second
    for name in ("opencode.json", ".qwen/settings.json", ".agents/mcp_config.json"):
        assert REPO_ROOT / name in first, name
    assert REPO_ROOT / ".opencode/agents/extractor.md" in first
    assert REPO_ROOT / ".qwen/agents/extractor.md" in first
    assert REPO_ROOT / ".qwen/skills/process-jobs/SKILL.md" in first


def test_extractor_only_has_its_two_tools() -> None:
    claude = _role_file("claude", "extractor")
    assert claude["tools"] == "mcp__candidatai__get_job, mcp__candidatai__save_extraction"
    opencode = _role_file("opencode", "extractor")
    assert opencode["mode"] == "subagent"
    assert opencode["permission"] == {
        "*": "deny",
        "candidatai_get_job": "allow",
        "candidatai_save_extraction": "allow",
    }
    qwen = _role_file("qwen", "extractor")
    assert qwen["tools"] == ["mcp__candidatai__get_job", "mcp__candidatai__save_extraction"]


@pytest.mark.parametrize("role", [r.meta["name"] for r in ROLES])
def test_no_role_gets_a_terminal_it_does_not_declare(role: str) -> None:
    opencode = _role_file("opencode", role)["permission"]
    assert next(iter(opencode.items())) == ("*", "deny")  # lo primero: todo denegado
    qwen = _role_file("qwen", role)["tools"]
    claude = _role_file("claude", role)["tools"]
    assert "run_shell_command" not in qwen  # nunca la terminal entera
    for forbidden in ("edit", "write", "webfetch", "websearch", "task", "skill"):
        assert forbidden not in opencode, (role, forbidden)
    if role in TERMINAL_ROLES:
        assert opencode["bash"] == {
            "*": "deny",
            "git diff *": "allow",
            "git status *": "allow",
            "git log *": "allow",
        }
    else:
        assert "bash" not in opencode
        assert "Bash" not in claude
    # Qwen: sin terminal en ningún rol (no está comprobado que su sintaxis acotada acote).
    assert not any("shell" in t for t in qwen)


def test_opencode_main_session_asks_before_writing() -> None:
    config = json.loads(_emit("opencode")[REPO_ROOT / "opencode.json"])
    assert config["$schema"] == "https://opencode.ai/config.json"
    server = config["mcp"]["candidatai"]
    assert server["type"] == "local"
    assert server["command"] == ["uv", "run", "--directory", "backend", "cai-mcp"]
    rules = list(config["permission"].items())
    assert rules[0] == ("candidatai_*", "ask")  # la primera: gana la última que encaja
    allowed = {k for k, v in rules if v == "allow"}
    assert {"candidatai_get_status", "candidatai_get_job", "candidatai_save_extraction"} <= allowed
    for writes in ("candidatai_add_event", "candidatai_add_job_from_url", "candidatai_render_cv"):
        assert writes not in config["permission"]
    assert config["permission"]["read"][".env"] == "deny"


def test_qwen_settings() -> None:
    settings = json.loads(_emit("qwen")[REPO_ROOT / ".qwen/settings.json"])
    assert settings["context"] == {"fileName": "AGENTS.md"}
    assert settings["mcpServers"]["candidatai"]["command"] == "uv"
    assert "mcp__candidatai__get_status" in settings["permissions"]["allow"]
    assert "mcp__candidatai__add_event" not in settings["permissions"]["allow"]
    assert "Read(./.env)" in settings["permissions"]["deny"]


def test_codex_mcp_receives_the_data_dir() -> None:
    """Codex solo pasa al servidor MCP una lista blanca del entorno: sin `env_vars`, una demo
    (`CAI_DATA_DIR`) abriría `data/`."""
    config = _emit("codex")[REPO_ROOT / ".codex" / "config.toml"]
    assert 'env_vars = ["CAI_DATA_DIR"]' in config
    # `policy.auto_allow` sin preguntar; las que no están, con la aprobación de Codex.
    assert '[mcp_servers.candidatai.tools.get_status]\napproval_mode = "approve"' in config
    assert "tools.add_event]" not in config


def test_antigravity_only_gets_the_workspace_mcp() -> None:
    out = _emit("antigravity")
    assert list(out) == [REPO_ROOT / ".agents" / "mcp_config.json"]
    assert json.loads(out[REPO_ROOT / ".agents" / "mcp_config.json"]) == {
        "mcpServers": {
            "candidatai": {"command": "uv", "args": ["run", "--directory", "backend", "cai-mcp"]}
        }
    }


def test_gemini_md_does_not_import_agents_md() -> None:
    assert "@AGENTS.md" not in (REPO_ROOT / "GEMINI.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("agent", ["claude", "opencode", "qwen"])
def test_unknown_logical_tool_fails_clearly(agent: str) -> None:
    role = sync.Doc(
        meta={"name": "spy", "description": "x", "tools": ["mcp:get_job", "teleport"]},
        body="cuerpo",
        source=REPO_ROOT / ".agents" / "roles" / "spy.md",
    )
    with pytest.raises(SystemExit) as exc:
        _emit(agent, [role])
    message = str(exc.value)
    assert f"{agent}, rol spy" in message
    assert "'teleport'" in message and ".agents/manifest.yaml" in message


def test_claude_settings_must_match_policy(tmp_path: Path) -> None:
    cfg = MANIFEST["targets"]["claude"]
    real = json.loads((REPO_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    sync.check_claude_settings(cfg, MANIFEST["policy"])  # el real cuadra

    real["permissions"]["allow"].remove("mcp__candidatai__get_status")
    real["permissions"]["allow"].append("mcp__candidatai__add_event")
    real["permissions"]["deny"].remove("Read(./.env)")
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(real), encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        sync.check_claude_settings(cfg, MANIFEST["policy"], path)
    message = str(exc.value)
    assert "falta en allow: mcp__candidatai__get_status" in message
    assert "sobra en allow (no está en policy.auto_allow): mcp__candidatai__add_event" in message
    assert "falta en deny: Read(./.env)" in message
