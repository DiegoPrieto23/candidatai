from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict

from app.api.deps import SessionDep
from app.schemas.sources import (
    SourceInput,
    SourceList,
    SourceRunResult,
    SourceTestResult,
    SourceView,
)
from app.services.ingestion import service as sources

router = APIRouter(prefix="/sources", tags=["sources"])


class SetActiveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active: bool


@router.get("", operation_id="list_sources")
def list_sources(session: SessionDep, kind: str | None = None) -> SourceList:
    """Fuentes con su configuración (sin secretos) y su última ejecución."""
    return sources.list_sources(session, kind)


@router.post("", operation_id="add_source", status_code=status.HTTP_201_CREATED)
def add_source(session: SessionDep, body: SourceInput) -> SourceView:
    """Añade una empresa objetivo (ATS + slug) o una búsqueda en un portal con API."""
    return sources.add_source(session, body)


@router.post("/test", operation_id="preview_new_source")
def preview_new_source(session: SessionDep, body: SourceInput) -> SourceTestResult:
    """Prueba una fuente sin guardarla: descarga, filtra y no guarda nada."""
    return sources.preview_source(session, body)


@router.post("/{source_id}/test", operation_id="preview_source")
def preview_source(session: SessionDep, source_id: int) -> SourceTestResult:
    """Prueba una fuente guardada sin guardar ofertas."""
    return sources.preview_source(session, source_id)


@router.post("/{source_id}/run", operation_id="run_source")
def run_source(session: SessionDep, source_id: int) -> SourceRunResult:
    """Ejecuta ahora la fuente y guarda las ofertas nuevas en `pending_extraction`."""
    return sources.run_source(session, source_id, actor="user")


@router.post("/{source_id}/active", operation_id="set_source_active")
def set_source_active(session: SessionDep, source_id: int, body: SetActiveBody) -> SourceView:
    """Activa o pausa una fuente en la ingesta diaria."""
    return sources.set_active(session, source_id, body.active)
