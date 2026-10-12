"""Lectores de la salida de cada agente en segundo plano (fase 19, ADR-032), por el `output` de
`launch.headless` del manifiesto. Es el único código que conoce el formato de un agente concreto
(como los emisores de `scripts/sync_agents.py`): el runner solo usa `StreamState`.

Para dar segundo plano a otro agente, añade aquí un lector de su formato y regístralo en `PARSERS`.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.services.agent_launch import SESSION_ID_RE
from app.services.agent_runs import ProgressKind

MCP_SERVER = "jobhunter"
TEXT_CHARS = 300  # lo que se guarda de cada mensaje del agente en el progreso
RESULT_CHARS = 20_000
# Estados del servidor MCP en el arranque que no tienen arreglo durante la ejecución.
MCP_BROKEN = frozenset({"failed", "needs-auth", "missing", "disabled"})


def short(text: str, limit: int = TEXT_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


@dataclass
class StreamState:
    session_id: str | None = None
    mcp_status: str | None = None  # el del servidor `jobhunter` al arrancar
    result: str | None = None
    is_error: bool = False
    finished: bool = False  # llegó el resultado final
    subtype: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    progress: list[tuple[ProgressKind, str]] = field(default_factory=list)

    @property
    def mcp_broken(self) -> bool:
        return self.mcp_status in MCP_BROKEN


class StreamParser(Protocol):
    state: StreamState

    def feed(self, line: str) -> None: ...


class ClaudeStreamParser:
    """`claude -p --output-format stream-json`: un JSON por línea (`system`/`init`, `assistant`,
    `user` con los resultados de herramientas y `result` al final). Lo que no es JSON se ignora."""

    def __init__(self, mcp_prefix: str = f"mcp__{MCP_SERVER}__") -> None:
        self.state = StreamState()
        self.prefix = mcp_prefix
        self._tools: dict[str, str] = {}  # id de la llamada → nombre (para sus errores)

    def _add(self, kind: ProgressKind, text: str) -> None:
        self.state.progress.append((kind, short(text)))

    def feed(self, line: str) -> None:
        line = line.strip()
        if not line.startswith("{"):
            return
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            return
        if not isinstance(event, dict):
            return
        kind = event.get("type")
        if isinstance(sid := event.get("session_id"), str) and SESSION_ID_RE.fullmatch(sid):
            self.state.session_id = sid
        if kind == "system" and event.get("subtype") == "init":
            self._init(event)
        elif kind == "assistant":
            self._assistant(event)
        elif kind == "user":
            self._tool_results(event)
        elif kind == "result":
            self._result(event)

    def _init(self, event: dict[str, Any]) -> None:
        servers = event.get("mcp_servers") or []
        ours = [s for s in servers if isinstance(s, dict) and s.get("name") == MCP_SERVER]
        self.state.mcp_status = str(ours[0].get("status")) if ours else "missing"
        self._add("info", "Agente arrancado.")

    def _assistant(self, event: dict[str, Any]) -> None:
        main = event.get("parent_tool_use_id") is None  # el texto de los subagentes no se guarda
        for block in (event.get("message") or {}).get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                name = self._name(block)
                self._tools[str(block.get("id"))] = name
                self._add("tool", ("" if main else "↳ ") + self._describe(name, block))
            elif block.get("type") == "text" and main and str(block.get("text") or "").strip():
                self._add("text", str(block["text"]))

    def _name(self, block: dict[str, Any]) -> str:
        name = str(block.get("name") or "?")
        return name.removeprefix(self.prefix) if name.startswith(self.prefix) else name

    def _describe(self, name: str, block: dict[str, Any]) -> str:
        data = block.get("input") if isinstance(block.get("input"), dict) else {}
        if name in ("Agent", "Task"):
            return f"Subagente «{short(str(data.get('subagent_type') or '?'), 40)}»"
        if name == "Skill":
            return f"Skill «{short(str(data.get('skill') or data.get('command') or '?'), 40)}»"
        if name == "Read":
            return f"Lee {short(str(data.get('file_path') or '?'), 80)}"
        return short(name, 60)

    def _tool_results(self, event: dict[str, Any]) -> None:
        """Solo si falló y en qué herramienta: el detalle de un error puede repetir lo que se le
        pasó (texto de una oferta)."""
        for block in (event.get("message") or {}).get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            if block.get("is_error"):
                name = self._tools.get(str(block.get("tool_use_id")), "?")
                content = str(block.get("content") or "")
                if "permission" in content.lower() or "denied" in content.lower():
                    self._add("error", f"Denegada: {name}")
                else:
                    self._add("error", f"Error en {name}")

    def _result(self, event: dict[str, Any]) -> None:
        state = self.state
        state.finished = True
        state.subtype = str(event.get("subtype") or "")
        state.is_error = bool(event.get("is_error")) or state.subtype != "success"
        result = event.get("result")
        state.result = str(result)[:RESULT_CHARS] if result is not None else None
        for key in ("num_turns", "duration_ms", "total_cost_usd"):
            if isinstance(event.get(key), int | float):
                state.usage[key] = event[key]
        denied = sorted(
            {
                self._name({"name": d.get("tool_name")})
                for d in event.get("permission_denials") or []
                if isinstance(d, dict) and d.get("tool_name")
            }
        )
        if denied:
            state.usage["denied_tools"] = denied
            self._add("error", "Herramientas denegadas: " + ", ".join(denied))


PARSERS: dict[str, Callable[[str], StreamParser]] = {"claude-stream-json": ClaudeStreamParser}
