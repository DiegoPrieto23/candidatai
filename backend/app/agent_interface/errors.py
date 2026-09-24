"""Formato de error común de la interfaz para agentes, idéntico por MCP y por CLI.

```json
{"ok": false, "error": {"type": "validation_error", "message": "…",
                        "details": [{"field": "extraction.seniority", "received": "sr",
                                     "reason": "Debe ser uno de: intern, junior, …"}]}}
```
"""

from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.validation import describe_error


class ErrorDetail(BaseModel):
    field: str
    received: str | None  # siempre como texto: por CLI todo llega como texto (paridad)
    reason: str


class ErrorInfo(BaseModel):
    type: str
    message: str
    details: list[ErrorDetail] = []


class ToolError(Exception):
    """Error esperable de una herramienta: se devuelve al agente para que corrija y reintente."""

    def __init__(self, type: str, message: str, details: list[ErrorDetail] | None = None) -> None:
        super().__init__(message)
        self.info = ErrorInfo(type=type, message=message, details=details or [])

    def payload(self) -> dict[str, Any]:
        return {"ok": False, "error": self.info.model_dump(mode="json")}


def from_validation_error(exc: ValidationError) -> ToolError:
    details: list[ErrorDetail] = []
    for error in exc.errors(include_url=False):
        received, reason = describe_error(error)
        field = ".".join(str(part) for part in error["loc"]) or "(entrada)"
        details.append(ErrorDetail(field=field, received=received, reason=reason))
    count = len(details)
    noun = "error" if count == 1 else "errores"
    fields = ", ".join(d.field for d in details)
    return ToolError("validation_error", f"Entrada no válida ({count} {noun}): {fields}.", details)
