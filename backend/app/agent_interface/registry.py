"""Definición única de cada herramienta de la interfaz para agentes.

De cada `ToolSpec` se derivan la herramienta MCP (`app/mcp/server.py`) y el comando CLI
(`app/agent_interface/cli.py`). Ambos canales validan con el mismo `input_model`, ejecutan el
mismo `handler` a través de `runner.call_tool` y devuelven el mismo JSON: paridad por construcción.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.services.audit import Channel


@dataclass(frozen=True)
class CallContext:
    channel: Channel
    client_name: str | None = None  # el cliente MCP (`claude-code`, `codex`…) o `JH_CLIENT_NAME`
    audit: bool = True


@dataclass(frozen=True)
class CliSpec:
    """Forma del comando `jh` equivalente. Todos los valores llegan como texto y los valida el
    `input_model`, igual que por MCP, para que los errores coincidan."""

    path: tuple[str, ...]  # p. ej. ("jobs", "add-url")
    arguments: tuple[str, ...] = ()  # campos posicionales, en orden
    option_names: Mapping[str, str] = field(default_factory=dict)  # campo -> "--opcion"
    file_field: str | None = None  # campo que se lee de `--file` (solo rutas en data/tmp/)
    file_format: Literal["text", "json"] = "text"


Handler = Callable[[Session, Any, CallContext], BaseModel]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Handler
    cli: CliSpec
    # Campos de texto que pueden ir tal cual a `mcp_calls` (nunca texto de ofertas ni del perfil).
    audit_fields: tuple[str, ...] = ()

    def job_id_of(self, args: BaseModel, result: BaseModel | None) -> int | None:
        for source in (args, result):
            value = getattr(source, "job_id", None)
            if isinstance(value, int):
                return value
        return None
