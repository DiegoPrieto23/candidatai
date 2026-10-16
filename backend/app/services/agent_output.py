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

MCP_SERVER = "candidatai"
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
    mcp_status: str | None = None  # el del servidor `candidatai` al arrancar
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
        # Fase 24.6: los tokens, para la matriz (`cai eval compat`).
        tokens = event.get("usage") if isinstance(event.get("usage"), dict) else {}
        for key, source in (
            ("input_tokens", "input_tokens"),
            ("output_tokens", "output_tokens"),
            ("cache_read_tokens", "cache_read_input_tokens"),
        ):
            value = tokens.get(source)
            if isinstance(value, int) and not isinstance(value, bool):
                state.usage[key] = value
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


class OpenCodeJsonParser:
    """`opencode run --format json` (fase 24.5, comprobado con OpenCode 1.19.3): un JSON por línea
    con `type` (`step_start`, `text`, `tool_use`, `step_finish` o `error`), `sessionID` y `part`.
    No hay evento de resultado: el final es un `step_finish` de la sesión principal con un `reason`
    distinto de `tool-calls`, y la respuesta, el texto de ese último paso. El uso (tokens y coste)
    se suma de cada `step_finish`. Lo que no es JSON se ignora."""

    FINAL_ERRORS = frozenset({"length", "error", "content-filter"})

    def __init__(self, mcp_prefix: str = f"{MCP_SERVER}_") -> None:
        self.state = StreamState()
        self.prefix = mcp_prefix
        self._main: str | None = None  # la sesión principal (la del primer evento)
        self._texts: list[str] = []  # el texto del paso en curso de la sesión principal
        self._started: int | None = None
        self._steps = 0
        self._denied: set[str] = set()

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
        sid = event.get("sessionID")
        if self._main is None and isinstance(sid, str) and SESSION_ID_RE.fullmatch(sid):
            self._main = self.state.session_id = sid
            self._add("info", "Agente arrancado.")
        main = sid == self._main
        if isinstance(ts := event.get("timestamp"), int):
            self._started = self._started if self._started is not None else ts
            self.state.usage["duration_ms"] = ts - self._started
        part = event.get("part") if isinstance(event.get("part"), dict) else {}
        kind = event.get("type")
        if kind == "step_start" and main:
            self._texts = []
        elif kind == "text" and main and str(part.get("text") or "").strip():
            self._texts.append(str(part["text"]))
            self._add("text", str(part["text"]))
        elif kind == "tool_use":
            self._tool(part, main)
        elif kind == "step_finish":
            self._step_finish(part, main)
        elif kind == "error":
            self._error(event)

    def _name(self, part: dict[str, Any]) -> str:
        name = str(part.get("tool") or "?")
        return name.removeprefix(self.prefix) if name.startswith(self.prefix) else name

    def _tool(self, part: dict[str, Any], main: bool) -> None:
        """El nombre y si falló; nunca su entrada ni su salida (pueden llevar texto de una
        oferta)."""
        name = self._name(part)
        tool_state = part.get("state") if isinstance(part.get("state"), dict) else {}
        data = tool_state.get("input") if isinstance(tool_state.get("input"), dict) else {}
        if name == "task":
            label = f"Subagente «{short(str(data.get('subagent_type') or '?'), 40)}»"
        elif name == "skill":
            label = f"Skill «{short(str(data.get('name') or '?'), 40)}»"
        else:
            label = short(name, 60)
        self._add("tool", ("" if main else "↳ ") + label)
        if tool_state.get("status") == "error":
            error = str(tool_state.get("error") or "").lower()
            if "permission" in error or "denied" in error or "rejected" in error:
                self._denied.add(name)
                self.state.usage["denied_tools"] = sorted(self._denied)
                self._add("error", f"Denegada: {name}")
            else:
                self._add("error", f"Error en {name}")

    def _step_finish(self, part: dict[str, Any], main: bool) -> None:
        usage = self.state.usage
        tokens = part.get("tokens") if isinstance(part.get("tokens"), dict) else {}
        cache = tokens.get("cache") if isinstance(tokens.get("cache"), dict) else {}
        for key, value in (
            ("input_tokens", tokens.get("input")),
            ("output_tokens", (tokens.get("output") or 0) + (tokens.get("reasoning") or 0)),
            ("cache_read_tokens", cache.get("read")),
            ("total_cost_usd", part.get("cost")),
        ):
            if isinstance(value, int | float) and not isinstance(value, bool):
                usage[key] = usage.get(key, 0) + value
        if not main:
            return
        self._steps += 1
        usage["num_turns"] = self._steps
        reason = str(part.get("reason") or "")
        if reason == "tool-calls":
            return
        state = self.state
        state.finished = True
        state.subtype = reason or None
        state.is_error = reason in self.FINAL_ERRORS
        text = "\n\n".join(self._texts).strip()
        state.result = text[:RESULT_CHARS] if text else None

    def _error(self, event: dict[str, Any]) -> None:
        """Un error que para la ejecución (p. ej. el proveedor rechaza el modelo). Del detalle,
        solo el mensaje."""
        error = event.get("error") if isinstance(event.get("error"), dict) else {}
        data = error.get("data") if isinstance(error.get("data"), dict) else {}
        state = self.state
        state.finished = True
        state.is_error = True
        state.subtype = str(error.get("name") or "error")
        state.result = short(str(data.get("message") or error.get("name") or "sin detalle"), 500)


PARSERS: dict[str, Callable[[str], StreamParser]] = {
    "claude-stream-json": ClaudeStreamParser,
    "opencode-json": OpenCodeJsonParser,
}
