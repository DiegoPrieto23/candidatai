from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import EmptyBody, SessionDep, require_ui
from app.schemas.sources import (
    AgentBrowseSource,
    BrowseAccess,
    LinkedInPublicRunResult,
    LinkedInPublicView,
    SourceInput,
    SourceList,
    SourceRunResult,
    SourceTestResult,
    SourceView,
    Website,
)
from app.services.ingestion import browse, linkedin_public
from app.services.ingestion import service as sources

router = APIRouter(prefix="/sources", tags=["sources"])


class SetActiveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active: bool


class SetWebsiteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    website: Website | None  # `null` la quita


@router.get("", operation_id="list_sources")
def list_sources(session: SessionDep, kind: str | None = None) -> SourceList:
    """Fuentes con su configuración (sin secretos) y su última ejecución."""
    return sources.list_sources(session, kind)


@router.post("", operation_id="add_source", status_code=status.HTTP_201_CREATED)
def add_source(session: SessionDep, body: SourceInput) -> SourceView:
    """Añade una empresa objetivo (ATS + slug) o una búsqueda en un portal con API."""
    return sources.add_source(session, body)


@router.post("/platforms", operation_id="add_platform", status_code=status.HTTP_201_CREATED)
def add_platform(session: SessionDep, body: AgentBrowseSource) -> browse.SaveSourceResult:
    """«Añadir plataforma»: una web donde el agente busca ofertas con tu navegador. LinkedIn se
    crea siempre con la búsqueda desactivada (se activa después, aceptando el riesgo)."""
    return browse.add_platform(session, body)


# --- Búsqueda pública de LinkedIn (fase 22). Antes de las rutas `/{source_id}`. ---------


class LinkedInPublicSettingsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool | None = None
    fetch_detail: bool | None = None
    confirm_risk: bool = False  # obligatorio para encender cualquiera de los dos


@router.get("/linkedin-public", operation_id="get_linkedin_public")
def get_linkedin_public(session: SessionDep) -> LinkedInPublicView:
    """Estado de la búsqueda pública de LinkedIn sin sesión: interruptores, búsquedas que lanzará,
    límites, última ejecución y desde cuándo puede volver a ejecutarse."""
    return linkedin_public.get_view(session)


@router.post(
    "/linkedin-public/settings",
    operation_id="update_linkedin_public",
    dependencies=[Depends(require_ui)],
)
def update_linkedin_public(
    session: SessionDep, body: LinkedInPublicSettingsBody
) -> LinkedInPublicView:
    """Enciende o apaga la búsqueda pública (y la descarga de la descripción). Encender exige
    `confirm_risk: true`. Solo desde la UI."""
    return linkedin_public.update_settings(
        session,
        enabled=body.enabled,
        fetch_detail=body.fetch_detail,
        confirm_risk=body.confirm_risk,
    )


@router.post(
    "/linkedin-public/run",
    operation_id="run_linkedin_public",
    dependencies=[Depends(require_ui)],
)
def run_linkedin_public(session: SessionDep, _body: EmptyBody) -> LinkedInPublicRunResult:
    """«Buscar ahora»: respeta los mismos límites (una vez al día, días sin buscar tras un
    bloqueo). Tarda: hay una pausa de al menos 10 s entre peticiones."""
    return linkedin_public.run(session, actor="user")


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


@router.post("/{source_id}/website", operation_id="set_source_website")
def set_source_website(session: SessionDep, source_id: int, body: SetWebsiteBody) -> SourceView:
    """Pone o quita la web de una empresa objetivo, que la UI usa para su logo."""
    return sources.set_website(session, source_id, body.website)


class BrowseSettingsBody(BaseModel):
    """Cambios del usuario en una plataforma de búsqueda con navegador."""

    model_config = ConfigDict(extra="forbid")

    allow_agent_browsing: bool | None = None
    # Puesto en el orden (1…N); uno ocupado se intercambia. `expected_priority`, el que la UI
    # ve: si otra pestaña lo cambió, 409 y la UI recarga.
    priority: int | None = Field(default=None, ge=1)
    expected_priority: int | None = Field(default=None, ge=1)
    access: BrowseAccess | None = None
    max_offers: int | None = Field(default=None, ge=1, le=100)
    confirm_risk: bool = False  # obligatorio para activar LinkedIn


@router.post("/{source_id}/browse", operation_id="update_browse_settings")
def update_browse_settings(
    session: SessionDep, source_id: int, body: BrowseSettingsBody
) -> SourceView:
    """Activa o desactiva la búsqueda con navegador de una plataforma, o cambia su prioridad (un
    puesto ocupado se intercambia), su acceso o cuántas ofertas abre en cada recorrido. Activar
    LinkedIn exige `confirm_risk: true`."""
    return browse.update_settings(
        session,
        source_id,
        allow_agent_browsing=body.allow_agent_browsing,
        priority=body.priority,
        access=body.access,
        max_offers=body.max_offers,
        confirm_risk=body.confirm_risk,
        expected_priority=body.expected_priority,
    )
