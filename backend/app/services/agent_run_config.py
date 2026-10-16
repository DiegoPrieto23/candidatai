"""Configuración propia de cada ejecución en segundo plano (fase 24.5, ADR-032): el techo de
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
- Como `agent_output.py`, es el único código que conoce el formato de un agente concreto: para dar
  segundo plano con configuración a otro, añade aquí quien la escribe y regístralo en `WRITERS`.
"""

import json
import shutil
from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from app.core.config import REPO_ROOT, get_settings
from app.services.agent_actions import ACTIONS, ActionId
from app.services.agent_registry import RunConfigSpec

ROLES_DIR = REPO_ROOT / ".agents" / "roles"
CONFIG_FILE = "config.json"


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
                "tiene la ejecución: usa otro agente o «En terminal»."
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


WRITERS: dict[str, Callable[[ActionId, str, str], dict[str, Any]]] = {"opencode": opencode_config}


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
    folder = run_dir(run_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / CONFIG_FILE
    text = json.dumps(config, ensure_ascii=False, indent=2)
    path.write_text(text, encoding="utf-8")
    return {spec.env: text if spec.value == "content" else str(path)}


def remove(run_id: int) -> None:
    """Borra la configuración de la ejecución (no hace nada si no hay)."""
    shutil.rmtree(run_dir(run_id), ignore_errors=True)
