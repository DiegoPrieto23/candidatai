"""Salida JSON común de los dos canales (MCP y CLI).

Módulo aparte para que el servidor MCP no importe la CLI (Typer y Rich) solo por esta función.
"""

import json
from typing import Any

from pydantic import BaseModel


def dump_json(payload: BaseModel | dict[str, Any]) -> str:
    """JSON compacto, igual en los dos canales."""
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
