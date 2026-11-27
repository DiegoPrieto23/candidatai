"""Lectores de la salida de cada agente en segundo plano (fase 19), por el `output` de
`launch.headless` del manifiesto. Es el único código que conoce el formato de un agente concreto
(como los emisores de `scripts/sync_agents.py`): el runner solo usa `StreamState`.

Para dar segundo plano a otro agente, añade aquí un lector de su formato y regístralo en `PARSERS`.

Uso (fase 25.4): todos los lectores rellenan `usage` con las mismas claves
(`agent_usage.USAGE_KEYS`), todas opcionales: cada agente da lo que da y no se estima lo que falta.

Conversación: además del progreso resumido, cada lector deja en `events` lo que pasa en orden
(arranque, herramientas, texto del agente, resultado) para verlo en el portal. De una herramienta,
solo el nombre, un detalle corto (el skill, el subagente, el fichero) y si fue bien: nunca su
entrada ni su salida, que pueden llevar texto de una oferta.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.services.agent_launch import SESSION_ID_RE
from app.services.agent_runs import EventKind, ProgressKind

MCP_SERVER = "candidatai"
TEXT_CHARS = 300  # lo que se guarda de cada mensaje del agente en el progreso
EVENT_TEXT_CHARS = 8_000  # lo que se guarda de cada mensaje del agente en la conversación
DETAIL_CHARS = 120
RESULT_CHARS = 20_000
DENIED = "denied"  # `text` de un `tool_result` que el techo de la acción no permitió
# Estados del servidor MCP en el arranque que no tienen arreglo durante la ejecución.
MCP_BROKEN = frozenset({"failed", "needs-auth", "missing", "disabled"})


def short(text: str, limit: int = TEXT_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def clip(text: str, limit: int = EVENT_TEXT_CHARS) -> str:
    """Como `short`, pero respeta los saltos de línea (el texto del agente se lee en el panel)."""
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


@dataclass(frozen=True)
class RunEvent:
    kind: EventKind
    text: str | None = None
    tool: str | None = None
    ok: bool | None = None
    sub: bool = False  # lo hizo un subagente


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
    events: list[RunEvent] = field(default_factory=list)

    @property
    def mcp_broken(self) -> bool:
        return self.mcp_status in MCP_BROKEN


class StreamParser(Protocol):
    state: StreamState

    def feed(self, line: str) -> None: ...


class _Recorder:
    """Lo común: el progreso resumido y la conversación."""

    state: StreamState

    def _add(self, kind: ProgressKind, text: str) -> None:
        self.state.progress.append((kind, short(text)))

    def _event(
        self,
        kind: EventKind,
        text: str | None = None,
        tool: str | None = None,
        ok: bool | None = None,
        sub: bool = False,
    ) -> None:
        self.state.events.append(RunEvent(kind, text, tool, ok, sub))

    def _said(self, text: str) -> None:
        """Lo que escribe el agente principal."""
        self._add("text", text)
        self._event("text", clip(text))

    def _final(self, ok: bool) -> None:
        """El resultado. Sin repetir el texto si es el último mensaje del agente (Claude Code y
        Codex lo dan dos veces)."""
        result = self.state.result
        said = [e.text for e in self.state.events if e.kind == "text"]
        repeated = result is not None and bool(said) and clip(result) == said[-1]
        self._event("result", None if repeated or not result else clip(result), ok=ok)


def _detail(value: object) -> str | None:
    text = str(value or "").strip()
    return short(text, DETAIL_CHARS) if text else None


class ClaudeStreamParser(_Recorder):
    """`claude -p --output-format stream-json`: un JSON por línea (`system`/`init`, `assistant`,
    `user` con los resultados de herramientas y `result` al final). Lo que no es JSON se ignora."""

    def __init__(self, mcp_prefix: str = f"mcp__{MCP_SERVER}__") -> None:
        self.state = StreamState()
        self.prefix = mcp_prefix
        self._tools: dict[str, tuple[str, bool]] = {}  # id de la llamada → (nombre, subagente)

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
        self._event("system", "started")

    def _assistant(self, event: dict[str, Any]) -> None:
        main = event.get("parent_tool_use_id") is None  # el texto de los subagentes no se guarda
        for block in (event.get("message") or {}).get("content") or []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                name = self._name(block)
                self._tools[str(block.get("id"))] = (name, not main)
                self._add("tool", ("" if main else "↳ ") + self._describe(name, block))
                self._event("tool_start", self._input_detail(name, block), name, sub=not main)
            elif block.get("type") == "text" and main and str(block.get("text") or "").strip():
                self._said(str(block["text"]))

    def _name(self, block: dict[str, Any]) -> str:
        name = str(block.get("name") or "?")
        return name.removeprefix(self.prefix) if name.startswith(self.prefix) else name

    @staticmethod
    def _input_detail(name: str, block: dict[str, Any]) -> str | None:
        """El skill, el subagente o el fichero: lo único de la entrada que se guarda."""
        data = block.get("input") if isinstance(block.get("input"), dict) else {}
        if name in ("Agent", "Task"):
            return _detail(data.get("subagent_type"))
        if name == "Skill":
            return _detail(data.get("skill") or data.get("command"))
        if name == "Read":
            return _detail(data.get("file_path"))
        return None

    def _describe(self, name: str, block: dict[str, Any]) -> str:
        detail = self._input_detail(name, block) or "?"
        if name in ("Agent", "Task"):
            return f"Subagente «{short(detail, 40)}»"
        if name == "Skill":
            return f"Skill «{short(detail, 40)}»"
        if name == "Read":
            return f"Lee {short(detail, 80)}"
        return short(name, 60)

    def _tool_results(self, event: dict[str, Any]) -> None:
        """Si fue bien o no, y en qué herramienta: el detalle de un error puede repetir lo que se
        le pasó (texto de una oferta)."""
        for block in (event.get("message") or {}).get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            name, sub = self._tools.get(str(block.get("tool_use_id")), ("?", False))
            if not block.get("is_error"):
                self._event("tool_result", None, name, ok=True, sub=sub)
                continue
            content = str(block.get("content") or "")
            if "permission" in content.lower() or "denied" in content.lower():
                self._add("error", f"Denegada: {name}")
                self._event("tool_result", DENIED, name, ok=False, sub=sub)
            else:
                self._add("error", f"Error en {name}")
                self._event("tool_result", None, name, ok=False, sub=sub)

    def _result(self, event: dict[str, Any]) -> None:
        state = self.state
        state.finished = True
        state.subtype = str(event.get("subtype") or "")
        state.is_error = bool(event.get("is_error")) or state.subtype != "success"
        result = event.get("result")
        state.result = str(result)[:RESULT_CHARS] if result is not None else None
        for key, source in (
            ("turns", "num_turns"),
            ("duration_ms", "duration_ms"),
            ("cost_usd", "total_cost_usd"),
        ):
            value = event.get(source)
            if isinstance(value, int | float) and not isinstance(value, bool):
                state.usage[key] = value
        # Fase 24.6: los tokens, para la matriz (`cai eval compat`).
        tokens = event.get("usage") if isinstance(event.get("usage"), dict) else {}
        for key, source in (
            ("input_tokens", "input_tokens"),
            ("output_tokens", "output_tokens"),
            ("cached_tokens", "cache_read_input_tokens"),
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
        self._final(not state.is_error)


class OpenCodeJsonParser(_Recorder):
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
            self._event("system", "started")
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
            self._said(str(part["text"]))
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
        detail = (
            _detail(data.get("subagent_type"))
            if name == "task"
            else _detail(data.get("name"))
            if name == "skill"
            else None
        )
        if name == "task":
            label = f"Subagente «{short(detail or '?', 40)}»"
        elif name == "skill":
            label = f"Skill «{short(detail or '?', 40)}»"
        else:
            label = short(name, 60)
        self._add("tool", ("" if main else "↳ ") + label)
        self._event("tool_start", detail, name, sub=not main)
        status = tool_state.get("status")
        if status == "completed":
            self._event("tool_result", None, name, ok=True, sub=not main)
        elif status == "error":
            error = str(tool_state.get("error") or "").lower()
            if "permission" in error or "denied" in error or "rejected" in error:
                self._denied.add(name)
                self.state.usage["denied_tools"] = sorted(self._denied)
                self._add("error", f"Denegada: {name}")
                self._event("tool_result", DENIED, name, ok=False, sub=not main)
            else:
                self._add("error", f"Error en {name}")
                self._event("tool_result", None, name, ok=False, sub=not main)

    def _step_finish(self, part: dict[str, Any], main: bool) -> None:
        usage = self.state.usage
        tokens = part.get("tokens") if isinstance(part.get("tokens"), dict) else {}
        cache = tokens.get("cache") if isinstance(tokens.get("cache"), dict) else {}
        for key, value in (
            ("input_tokens", tokens.get("input")),
            ("output_tokens", (tokens.get("output") or 0) + (tokens.get("reasoning") or 0)),
            ("cached_tokens", cache.get("read")),
            ("cost_usd", part.get("cost")),
        ):
            if isinstance(value, int | float) and not isinstance(value, bool):
                usage[key] = usage.get(key, 0) + value
        if not main:
            return
        self._steps += 1
        usage["turns"] = self._steps
        reason = str(part.get("reason") or "")
        if reason == "tool-calls":
            return
        state = self.state
        state.finished = True
        state.subtype = reason or None
        state.is_error = reason in self.FINAL_ERRORS
        text = "\n\n".join(self._texts).strip()
        state.result = text[:RESULT_CHARS] if text else None
        # Varios textos en el último paso: el resultado los junta y ya están en la conversación.
        if len(self._texts) > 1:
            self._event("result", ok=not state.is_error)
        else:
            self._final(not state.is_error)

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
        self._event("error", state.result)


class CodexJsonParser(_Recorder):
    """`codex exec --json` (fase 46, comprobado con codex-cli 0.163.0): un JSON por línea con `type`
    (`thread.started`, `turn.started`, `item.started`, `item.completed`, `turn.completed`,
    `turn.failed` o `error`). Cada `item` tiene su `type`: `agent_message`, `mcp_tool_call`,
    `collab_tool_call` (un subagente), `command_execution`, `web_search`, `file_change`, `error`…
    La respuesta es el último `agent_message` (los anteriores anuncian lo que va a hacer). Lo que no
    es JSON se ignora."""

    LABELS = {
        "collab_tool_call": "Subagente",
        "command_execution": "Terminal",
        "web_search": "Búsqueda web",
        "file_change": "Edita ficheros",
    }
    DENIED = ("denied", "rejected", "not allowed", "blocked", "not available", "no disponible")

    def __init__(self, mcp_prefix: str = f"mcp__{MCP_SERVER}__") -> None:
        self.state = StreamState()
        self.prefix = mcp_prefix
        self._last: str | None = None  # el último mensaje del agente
        self._turns = 0
        self._denied: set[str] = set()

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
        item = event.get("item") if isinstance(event.get("item"), dict) else {}
        if kind == "thread.started":
            sid = event.get("thread_id")
            if isinstance(sid, str) and SESSION_ID_RE.fullmatch(sid):
                self.state.session_id = sid
            self._add("info", "Agente arrancado.")
            self._event("system", "started")
        elif kind == "item.started":
            self._started(item)
        elif kind == "item.completed":
            self._completed(item)
        elif kind == "turn.completed":
            self._turn_completed(event)
        elif kind == "turn.failed":
            error = event.get("error") if isinstance(event.get("error"), dict) else {}
            self._fail(str(error.get("message") or "sin detalle"))

    def _tool_name(self, item: dict[str, Any]) -> str:
        server = str(item.get("server") or "")
        tool = str(item.get("tool") or "?")
        return tool if server == MCP_SERVER else f"{server}/{tool}" if server else tool

    def _started(self, item: dict[str, Any]) -> None:
        """El nombre de la herramienta; nunca su entrada (puede llevar texto de una oferta)."""
        kind = item.get("type")
        if kind == "mcp_tool_call":
            name = self._tool_name(item)
            self._add("tool", short(name, 60))
            self._event("tool_start", tool=short(name, 80))
        elif kind in self.LABELS:
            self._add("tool", self.LABELS[kind])
            self._event("tool_start", tool=str(kind))

    def _completed(self, item: dict[str, Any]) -> None:
        kind = item.get("type")
        if kind == "agent_message" and str(item.get("text") or "").strip():
            self._last = str(item["text"])
            self._said(self._last)
        elif kind == "mcp_tool_call":
            name = short(self._tool_name(item), 80)
            if not (item.get("error") or item.get("status") == "failed"):
                self._event("tool_result", tool=name, ok=True)
                return
            error = item.get("error") if isinstance(item.get("error"), dict) else {}
            message = str(error.get("message") or "").lower()
            if any(word in message for word in self.DENIED):
                self._denied.add(name)
                self.state.usage["denied_tools"] = sorted(self._denied)
                self._add("error", f"Denegada: {name}")
                self._event("tool_result", DENIED, name, ok=False)
            else:
                self._add("error", f"Error en {name}")
                self._event("tool_result", tool=name, ok=False)
        elif kind in ("command_execution", "file_change"):
            if item.get("status") == "failed":
                self._add("error", f"Denegada: {self.LABELS[str(kind)]}")
                self._event("tool_result", DENIED, str(kind), ok=False)
            else:
                self._event("tool_result", tool=str(kind), ok=True)
        elif kind in self.LABELS:
            self._event("tool_result", tool=str(kind), ok=item.get("status") != "failed")

    def _turn_completed(self, event: dict[str, Any]) -> None:
        state = self.state
        self._turns += 1
        state.usage["turns"] = self._turns
        tokens = event.get("usage") if isinstance(event.get("usage"), dict) else {}
        output = (tokens.get("output_tokens") or 0) + (tokens.get("reasoning_output_tokens") or 0)
        for key, value in (
            ("input_tokens", tokens.get("input_tokens")),
            ("output_tokens", output),
            ("cached_tokens", tokens.get("cached_input_tokens")),
        ):
            if isinstance(value, int) and not isinstance(value, bool):
                state.usage[key] = state.usage.get(key, 0) + value
        state.finished = True
        state.subtype = "success"
        state.is_error = False
        state.result = self._last[:RESULT_CHARS] if self._last else None
        self._final(True)

    def _fail(self, message: str) -> None:
        state = self.state
        state.finished = True
        state.is_error = True
        state.subtype = "error"
        state.result = short(message, 500)
        self._event("error", state.result)


PARSERS: dict[str, Callable[[str], StreamParser]] = {
    "claude-stream-json": ClaudeStreamParser,
    "opencode-json": OpenCodeJsonParser,
    "codex-json": CodexJsonParser,
}
