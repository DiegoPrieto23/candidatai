"""Punto único de ejecución de las herramientas: validar, ejecutar, auditar y traducir errores."""

import logging
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agent_interface.errors import ToolError, from_validation_error
from app.agent_interface.registry import CallContext, ToolSpec
from app.core import migrations
from app.core.db import session_scope
from app.services.audit import record_call, summarize_args
from app.services.events import JobNotFoundError
from app.services.extractions import ExtractionNotFoundError
from app.services.pipeline import InvalidTransitionError

logger = logging.getLogger(__name__)

_ERROR_TYPES: tuple[tuple[type[Exception], str], ...] = (
    (JobNotFoundError, "not_found"),
    (ExtractionNotFoundError, "not_found"),
    (migrations.DatabaseNotReadyError, "database_not_ready"),
    (InvalidTransitionError, "invalid_transition"),
    # IngestError, InvalidQueryError, UnknownEventTypeError, ReservedEventError…
    (ValueError, "invalid_request"),
)


def to_tool_error(exc: Exception) -> ToolError:
    if isinstance(exc, ToolError):
        return exc
    if isinstance(exc, ValidationError):
        return from_validation_error(exc)
    for exc_type, error_type in _ERROR_TYPES:
        if isinstance(exc, exc_type):
            return ToolError(error_type, str(exc))
    logger.exception("Error inesperado en la interfaz para agentes")
    return ToolError(
        "internal_error",
        f"Error interno ({type(exc).__name__}). Los detalles están en data/logs/.",
    )


def _audit(
    spec: ToolSpec,
    raw_args: Mapping[str, Any],
    ctx: CallContext,
    job_id: int | None,
    error: ToolError | None,
) -> None:
    if not ctx.audit or (error is not None and error.info.type == "database_not_ready"):
        return  # sin tablas no hay dónde auditar
    try:
        with session_scope() as session:
            record_call(
                session,
                channel=ctx.channel,
                client_name=ctx.client_name,
                tool=spec.name,
                args_summary=summarize_args(raw_args, spec.audit_fields),
                job_id=job_id,
                ok=error is None,
                error=f"{error.info.type}: {error.info.message}" if error else None,
            )
    except Exception:  # la auditoría nunca debe tumbar la llamada (p. ej. BD sin migrar)
        logger.warning("No se pudo auditar la llamada a %s", spec.name, exc_info=True)


def call_tool(spec: ToolSpec, raw_args: Mapping[str, Any] | None, ctx: CallContext) -> BaseModel:
    """Ejecuta una herramienta. Devuelve su salida o lanza `ToolError` (ya auditado)."""
    raw_args = dict(raw_args or {})
    args: BaseModel | None = None
    result: BaseModel | None = None
    try:
        args = spec.input_model.model_validate(raw_args)
        migrations.ensure_current()
        with session_scope() as session:
            result = spec.handler(session, args, ctx)
    except Exception as exc:
        error = to_tool_error(exc)
        job_id = spec.job_id_of(args, None) if args is not None else None
        _audit(spec, raw_args, ctx, job_id, error)
        raise error from exc
    _audit(spec, raw_args, ctx, spec.job_id_of(args, result), None)
    return result
