"""Errores de la API con el mismo formato que la interfaz para agentes.

`{"ok": false, "error": {"type", "message", "details": [{field, received, reason}]}}`
"""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.agent_interface.errors import ErrorDetail, ErrorInfo, ToolError
from app.agent_interface.runner import to_tool_error
from app.core.migrations import DatabaseNotReadyError
from app.core.validation import describe_error

STATUS_BY_TYPE = {
    "unauthorized": 401,
    "forbidden": 403,
    "not_allowed": 403,
    "capture_not_configured": 503,
    "not_found": 404,
    "validation_error": 422,
    "invalid_request": 422,
    "invalid_transition": 409,
    "exists": 409,
    "invalid_file": 422,
    "too_large": 413,
    "pdf_unavailable": 503,
    "pdf_failed": 500,
    "database_not_ready": 503,
    "internal_error": 500,
}


class ErrorResponse(BaseModel):
    ok: bool = False
    error: ErrorInfo


def _respond(error: ToolError) -> JSONResponse:
    status = STATUS_BY_TYPE.get(error.info.type, 500)
    return JSONResponse(status_code=status, content=error.payload())


def _from_request_validation(exc: RequestValidationError) -> ToolError:
    details: list[ErrorDetail] = []
    for error in exc.errors():
        received, reason = describe_error(error)
        # Se quita el prefijo de FastAPI (`body`, `query`, `path`): basta con el campo.
        loc = [str(part) for part in error["loc"][1:]] or [str(error["loc"][0])]
        details.append(ErrorDetail(field=".".join(loc), received=received, reason=reason))
    count = len(details)
    noun = "error" if count == 1 else "errores"
    fields = ", ".join(d.field for d in details)
    return ToolError("validation_error", f"Entrada no válida ({count} {noun}): {fields}.", details)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return _respond(_from_request_validation(exc))

    async def _expected(_request: Request, exc: Exception) -> JSONResponse:
        return _respond(to_tool_error(exc))

    # Errores esperables de los servicios. El resto lo recoge el manejador de `Exception`: responde
    # 500 `internal_error` con el mismo formato y `to_tool_error` registra la traza.
    # `OSError` está por `FileNotFoundError` (un fichero que no existe: 404); cualquier otro
    # `OSError` acaba en `internal_error` 500, con la traza en el log y sin la ruta en la respuesta.
    for exc_type in (ToolError, ValueError, LookupError, OSError, DatabaseNotReadyError):
        app.add_exception_handler(exc_type, _expected)

    @app.exception_handler(Exception)
    async def _unexpected(_request: Request, exc: Exception) -> JSONResponse:
        return _respond(to_tool_error(exc))


ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    status: {"model": ErrorResponse} for status in sorted(set(STATUS_BY_TYPE.values()))
}
