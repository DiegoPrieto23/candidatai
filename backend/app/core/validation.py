"""Traducción de los errores de validación de Pydantic a mensajes en español.

La usan la interfaz para agentes (`app/agent_interface/errors.py`) y el perfil
(`app/services/profile.py`), para que el mismo error se explique igual en todas partes.
"""

import json
from typing import Any

from pydantic_core import ErrorDetails

MAX_RECEIVED_CHARS = 80


def _received(value: Any) -> str:
    """Valor recibido como texto y recortado: basta para que el agente reconozca su error."""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return text if len(text) <= MAX_RECEIVED_CHARS else text[: MAX_RECEIVED_CHARS - 1] + "…"


def _expected(ctx: dict[str, Any]) -> str:
    # Pydantic da los valores esperados como "'a', 'b' or 'c'"; se dejan como "a, b, c".
    expected = str(ctx.get("expected", ""))
    return expected.replace("'", "").replace(" or ", ", ")


def _reason(error: ErrorDetails) -> str:
    kind = error["type"]
    ctx: dict[str, Any] = dict(error.get("ctx") or {})
    match kind:
        case "missing":
            return "Campo obligatorio."
        case "extra_forbidden":
            return "Campo no permitido: no existe en el esquema."
        case "literal_error" | "enum":
            return f"Debe ser uno de: {_expected(ctx)}."
        case "int_type" | "int_parsing" | "int_from_float":
            return "Debe ser un número entero."
        case "string_type":
            return "Debe ser texto."
        case "bool_type" | "bool_parsing":
            return "Debe ser true o false."
        case "list_type":
            return "Debe ser una lista."
        case "dict_type" | "model_type" | "model_attributes_type":
            return "Debe ser un objeto."
        case "string_too_short":
            return "No puede estar vacío."
        case "string_too_long":
            return f"Demasiado largo: máximo {ctx.get('max_length')} caracteres."
        case "too_long":
            return f"Demasiados elementos: máximo {ctx.get('max_length')}."
        case "greater_than_equal":
            return f"Debe ser mayor o igual que {ctx.get('ge')}."
        case "less_than_equal":
            return f"Debe ser menor o igual que {ctx.get('le')}."
        case "date_type" | "date_parsing" | "date_from_datetime_parsing":
            return "Debe ser una fecha con formato AAAA-MM-DD."
        case "datetime_type" | "datetime_parsing" | "datetime_from_date_parsing":
            return "Debe ser una fecha y hora ISO 8601 con zona (p. ej. 2026-09-24T10:00:00+02:00)."
        case "timezone_aware":
            return "La fecha y hora debe llevar zona horaria (p. ej. +02:00 o Z)."
        case "value_error" | "assertion_error":
            return str(ctx.get("error", error["msg"]))
        case _:
            return error["msg"]


def describe_error(error: ErrorDetails) -> tuple[str | None, str]:
    """(valor recibido como texto, o None si falta; motivo en español)."""
    received = None if error["type"] == "missing" else _received(error["input"])
    return received, _reason(error)
