"""Auditoría de la interfaz para agentes (`mcp_calls`). Nunca guarda texto crudo ni del perfil."""

import json
from collections.abc import Iterable, Mapping
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models import McpCall

Channel = Literal["mcp", "cli"]

MAX_VALUE_CHARS = 200
MAX_SUMMARY_CHARS = 1000
MAX_ERROR_CHARS = 500


def _shape(value: Any) -> Any:
    """Describe un valor sin revelar su contenido."""
    if isinstance(value, str):
        return f"<texto: {len(value)} caracteres>"
    if isinstance(value, Mapping):
        return f"<objeto: {len(value)} campos>"
    if isinstance(value, list | tuple):
        return f"<lista: {len(value)} elementos>"
    return f"<{type(value).__name__}>"


def summarize_args(args: Mapping[str, Any], safe_fields: Iterable[str]) -> str:
    """Resumen de los argumentos: los campos seguros tal cual (recortados); el resto, su forma.

    Números, booleanos y nulos son siempre seguros. Un campo es «seguro» si no puede contener texto
    de la oferta ni del perfil (ids, URLs, etapas, tipos de evento…); lo decide cada herramienta.
    """
    safe = set(safe_fields)
    summary: dict[str, Any] = {}
    for key, value in args.items():
        if value is None or isinstance(value, bool | int | float):
            summary[key] = value
        elif key in safe and isinstance(value, str):
            summary[key] = value[:MAX_VALUE_CHARS]
        elif key in safe and isinstance(value, list) and all(isinstance(v, str) for v in value):
            summary[key] = [v[:MAX_VALUE_CHARS] for v in value]  # p. ej. `sections`
        else:
            summary[key] = _shape(value)
    return json.dumps(summary, ensure_ascii=False)[:MAX_SUMMARY_CHARS]


def record_call(
    session: Session,
    *,
    channel: Channel,
    tool: str,
    args_summary: str,
    ok: bool,
    client_name: str | None = None,
    job_id: int | None = None,
    error: str | None = None,
) -> McpCall:
    call = McpCall(
        channel=channel,
        client_name=client_name[:64] if client_name else None,
        tool=tool,
        args_summary=args_summary,
        job_id=job_id,
        ok=ok,
        error=error[:MAX_ERROR_CHARS] if error else None,
    )
    session.add(call)
    session.flush()
    return call
