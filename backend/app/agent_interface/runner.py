"""Punto único de ejecución de las herramientas: validar, ejecutar, auditar y traducir errores."""

import logging
from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ValidationError

from app.agent_interface.errors import ErrorDetail, ToolError, from_validation_error
from app.agent_interface.registry import CallContext, ToolSpec
from app.core import migrations
from app.core.db import session_scope
from app.services.audit import record_call, summarize_args
from app.services.documents.checks import CvContentError
from app.services.documents.importer import TemplateImportError
from app.services.documents.importer.build import TemplateExistsError
from app.services.documents.importer.paths import OutsideDataError
from app.services.documents.pdf import PdfConversionError, PdfConverterUnavailableError
from app.services.documents.service import (
    DocumentNotFoundError,
    FileNotAvailableError,
    RenderNotFoundError,
)
from app.services.documents.templates import TemplateNotFoundError
from app.services.documents.uploads import InvalidUploadError, UploadTooLargeError
from app.services.events import JobNotFoundError
from app.services.extractions import ExtractionNotFoundError
from app.services.ingestion.browse import BrowsingNotAllowedError
from app.services.ingestion.service import SourceExistsError, SourceNotFoundError
from app.services.pipeline import InvalidTransitionError
from app.services.process import ContactNotFoundError, MilestoneNotFoundError
from app.services.profile import ProfileNotFoundError

logger = logging.getLogger(__name__)

_ERROR_TYPES: tuple[tuple[type[Exception], str], ...] = (
    (JobNotFoundError, "not_found"),
    (ExtractionNotFoundError, "not_found"),
    (ProfileNotFoundError, "not_found"),
    (SourceNotFoundError, "not_found"),
    (SourceExistsError, "exists"),
    (BrowsingNotAllowedError, "not_allowed"),
    (MilestoneNotFoundError, "not_found"),
    (ContactNotFoundError, "not_found"),
    (DocumentNotFoundError, "not_found"),
    (RenderNotFoundError, "not_found"),
    (FileNotAvailableError, "not_found"),
    (TemplateNotFoundError, "not_found"),
    (FileNotFoundError, "not_found"),
    (OutsideDataError, "invalid_file"),
    (TemplateExistsError, "exists"),
    (UploadTooLargeError, "too_large"),
    (InvalidUploadError, "invalid_file"),
    (PdfConverterUnavailableError, "pdf_unavailable"),
    (PdfConversionError, "pdf_failed"),
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
    if isinstance(exc, CvContentError | TemplateImportError):
        details = [ErrorDetail(**issue.model_dump()) for issue in exc.issues]
        return ToolError("validation_error", str(exc), details)
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
