"""Configuración propia de cada ejecución en segundo plano (fase 24.5): el techo de
herramientas de los agentes que lo ponen por configuración (`ceiling: config` en
`launch.headless`), no por argumentos como Claude Code.

- La configuración se escribe en `data/tmp/agent-runs/<id>/` justo antes de lanzar y se borra al
  terminar, también si la ejecución se cancela, falla o se para el worker (`agent_runner`).
- Define un agente propio de la ejecución con **todo denegado** salvo las herramientas MCP de la
  acción, su skill y los roles en que delega. Sin terminal, edición ni web. Va la última en las
  reglas del agente y la última regla que coincide es la que manda, así que la configuración del
  proyecto (`opencode.json`) no la amplía.
- Un rol solo se puede lanzar si sus herramientas caben en las de la acción: un subagente no puede
  tener más que la ejecución. Si no caben, esa acción no tiene segundo plano con ese agente.
- Codex (fase 46) solo lee configuración de su carpeta (`CODEX_HOME`, o `~/.codex`): la de la
  ejecución es un perfil `cai-run-<id>.config.toml` que la orden carga con `-p`. Se escribe ahí y se
  borra igual que lo demás; su ruta se apunta en la carpeta de la ejecución (`external.txt`) para
  borrarlo aunque se pare el worker. No puede ignorar la configuración del usuario (con
  `--ignore-user-config` no carga el perfil), así que apaga los demás servidores MCP que tenga.
- Como `agent_output.py`, es el único código que conoce el formato de un agente concreto: para dar
  segundo plano con configuración a otro, añade aquí quien la escribe y regístralo en `WRITERS`.
"""

import contextlib
import json
import os
import re
import shutil
import tomllib
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from app.core.config import REPO_ROOT, get_settings
from app.services.agent_actions import ACTIONS, ActionId
from app.services.agent_registry import MANIFEST, RunConfigSpec

ROLES_DIR = REPO_ROOT / ".agents" / "roles"
CONFIG_FILE = "config.json"
EXTERNAL_FILE = "external.txt"  # ficheros de la ejecución fuera de su carpeta (el perfil de Codex)
MCP_SERVER = "candidatai"


class RunConfigError(Exception):
    pass


def runs_dir() -> Path:
    return get_settings().tmp_dir / "agent-runs"


def run_dir(run_id: int) -> Path:
    return runs_dir() / str(run_id)


@cache
def role_tools(role: str) -> frozenset[str]:
    """Las herramientas lógicas del rol (`tools` del frontmatter de `.agents/roles/<rol>.md`)."""
    path = ROLES_DIR / f"{role}.md"
    try:
        text = path.read_text(encoding="utf-8")
        _, front, _ = text.split("---", 2)
        tools = yaml.safe_load(front).get("tools") or []
    except (OSError, ValueError, AttributeError, yaml.YAMLError) as exc:
        raise RunConfigError(f"No se puede leer el rol «{role}» ({path.name}).") from exc
    return frozenset(str(tool) for tool in tools)


def ceiling_problem(action: ActionId) -> str | None:
    """Por qué `action` no se puede limitar con una configuración propia, o `None` si se puede:
    algún rol en que delega necesita más herramientas que la acción (p. ej. leer ficheros)."""
    spec = ACTIONS[action]
    allowed = {f"mcp:{tool}" for tool in spec.background}
    for role in spec.roles:
        try:
            extra = sorted(role_tools(role) - allowed)
        except RunConfigError as exc:
            return str(exc)
        if extra:
            return (
                f"El rol «{role}» de «{spec.label}» necesita {', '.join(extra)}, que no está "
                "entre las herramientas de la acción, y este agente no puede acotarlo a lo que "
                "tiene la ejecución: hace falta otro agente o «En terminal»."
            )
    return None


def opencode_config(action: ActionId, agent: str, mcp_prefix: str) -> dict[str, Any]:
    """OpenCode: un agente primario con `"*": "deny"` y, detrás (la última regla que coincide
    manda), las herramientas MCP de la acción, su skill y sus roles. Sin compartir la sesión ni
    actualizarse durante la ejecución."""
    spec = ACTIONS[action]
    permission: dict[str, Any] = {"*": "deny"}
    permission.update({mcp_prefix + tool: "allow" for tool in spec.background})
    permission["skill"] = {"*": "deny", spec.skill or action: "allow"}
    permission["task"] = {"*": "deny", **{role: "allow" for role in spec.roles}}
    return {
        "$schema": "https://opencode.ai/config.json",
        "share": "disabled",
        "autoupdate": False,
        "agent": {
            agent: {
                "mode": "primary",
                "description": f"CandidatAI en segundo plano: {spec.label}",
                "permission": permission,
            }
        },
    }


# Codex (fase 46, comprobado con codex-cli 0.163.0): sin terminal, ficheros, web, subagentes,
# navegador, imágenes ni plugins, y en solo lectura sin aprobaciones (lo que pediría permiso se
# rechaza). Las MCP de la acción, aprobadas y a la vista: con `deferred` el modelo a veces no las
# encontraba, y con `code_mode` las buscaba como funciones de un script.
CODEX_FEATURES_OFF = (
    "shell_tool",
    "multi_agent",
    "view_image",
    "apps",
    "plugins",
    "browser_use",
    "browser_use_external",
    "computer_use",
    "in_app_browser",
    "image_generation",
    "goals",
    "code_mode_host",
)


@cache
def _mcp_server() -> dict[str, Any]:
    """`mcp_server` del manifiesto: cómo se arranca el servidor MCP de la app."""
    try:
        data = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise RunConfigError(f"No se puede leer {MANIFEST.name}.") from exc
    server = data.get("mcp_server") if isinstance(data, dict) else None
    if not isinstance(server, dict) or not server.get("command"):
        raise RunConfigError(f"{MANIFEST.name} no dice cómo arrancar el servidor MCP.")
    return server


def codex_config(action: ActionId, _agent: str, _mcp_prefix: str) -> dict[str, Any]:
    """Codex: el perfil de la ejecución. Define el servidor de la app entero (aunque el proyecto no
    sea de confianza y no se cargue `.codex/config.toml`) con solo las herramientas de la acción."""
    spec = ACTIONS[action]
    server = _mcp_server()
    ours: dict[str, Any] = {
        "command": server["command"],
        "args": list(server.get("args") or []),
        "enabled_tools": list(spec.background),
        "default_tools_approval_mode": "approve",
        "omit_tools_from": ["deferred", "code_mode"],
        "required": True,
        "startup_timeout_sec": 60,
    }
    if server.get("pass_env"):
        ours["env_vars"] = list(server["pass_env"])
    if server.get("env"):
        ours["env"] = dict(server["env"])
    return {
        "approval_policy": "never",
        "sandbox_mode": "read-only",
        "web_search": "disabled",
        "features": {
            **dict.fromkeys(CODEX_FEATURES_OFF, False),
            "code_mode": {"enabled": False},
        },
        "mcp_servers": {MCP_SERVER: ours},
    }


WRITERS: dict[str, Callable[[ActionId, str, str], dict[str, Any]]] = {
    "opencode": opencode_config,
    "codex": codex_config,
}

_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")


def _toml_key(key: str) -> str:
    return key if _BARE_KEY.fullmatch(key) else json.dumps(key, ensure_ascii=False)


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)  # una cadena JSON es una cadena TOML válida
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise RunConfigError(f"No se sabe escribir en TOML un {type(value).__name__}.")


def to_toml(data: dict[str, Any], path: tuple[str, ...] = ()) -> str:
    """Lo justo de TOML para la configuración de una ejecución: escalares, listas y tablas."""
    lines = [
        f"{_toml_key(k)} = {_toml_value(v)}" for k, v in data.items() if not isinstance(v, dict)
    ]
    for key, value in data.items():
        if isinstance(value, dict):
            inner = (*path, key)
            lines += ["", "[" + ".".join(_toml_key(part) for part in inner) + "]"]
            lines.append(to_toml(value, inner))
    text = "\n".join(lines).strip("\n")
    return text + "\n" if not path else text


def agent_home(spec: RunConfigSpec) -> Path:
    """La carpeta de configuración del agente (`profile`): la de la variable `env`, o `home`."""
    return Path(os.environ.get(spec.env) or spec.home or "").expanduser()


def _servers_in(path: Path) -> set[str]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return set()
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RunConfigError(f"No se puede leer {path}.") from exc
    servers = data.get("mcp_servers")
    return set(servers) if isinstance(servers, dict) else set()


def _other_servers(home: Path) -> list[str]:
    """Los demás servidores MCP de tu configuración y de la del proyecto: el perfil los apaga,
    porque Codex las carga siempre."""
    found = _servers_in(home / "config.toml") | _servers_in(REPO_ROOT / ".codex" / "config.toml")
    return sorted(found - {MCP_SERVER})


def build(action: ActionId, spec: RunConfigSpec, mcp_prefix: str) -> dict[str, Any]:
    if (problem := ceiling_problem(action)) is not None:
        raise RunConfigError(problem)
    writer = WRITERS.get(spec.format)
    if writer is None:
        raise RunConfigError(f"No se sabe escribir la configuración «{spec.format}».")
    return writer(action, spec.agent, mcp_prefix)


def write(run_id: int, action: ActionId, spec: RunConfigSpec, mcp_prefix: str) -> dict[str, str]:
    """Escribe la configuración de la ejecución y devuelve las variables de entorno que se la
    pasan al agente (`RunConfigError` si no se puede limitar)."""
    config = build(action, spec, mcp_prefix)
    if spec.value == "profile":
        _write_profile(run_id, spec, config)
        return {}
    folder = run_dir(run_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / CONFIG_FILE
    text = json.dumps(config, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")
    return {spec.env: text if spec.value == "content" else str(path)}


def _write_profile(run_id: int, spec: RunConfigSpec, config: dict[str, Any]) -> None:
    """Codex: el perfil va en su carpeta, con los demás servidores MCP del usuario apagados."""
    home = agent_home(spec)
    if not home.is_dir():
        raise RunConfigError(f"No existe la carpeta de configuración del agente ({home}).")
    servers = config.setdefault("mcp_servers", {})
    for name in _other_servers(home):
        servers.setdefault(name, {"enabled": False})
    path = home / f"{spec.name_for(run_id)}.config.toml"
    folder = run_dir(run_id)
    folder.mkdir(parents=True, exist_ok=True)
    # Primero se apunta, para borrarlo aunque el worker se pare justo después de escribirlo.
    (folder / EXTERNAL_FILE).write_text(str(path), encoding="utf-8")
    path.write_text(to_toml(config), encoding="utf-8")


def remove(run_id: int) -> None:
    """Borra la configuración de la ejecución, también la que está fuera de su carpeta (el perfil
    de Codex). No hace nada si no hay."""
    folder = run_dir(run_id)
    try:
        listed = (folder / EXTERNAL_FILE).read_text(encoding="utf-8").splitlines()
    except OSError:
        listed = []
    for line in listed:
        path = Path(line.strip())
        # Solo el perfil de esta ejecución (`cai-run-<id>.config.toml`), nunca otro fichero.
        if path.name.endswith(f"-{run_id}.config.toml") and path.name != "config.toml":
            with contextlib.suppress(OSError):
                path.unlink(missing_ok=True)
    shutil.rmtree(folder, ignore_errors=True)
