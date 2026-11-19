"""«Buscar ahora» (fase 45): los portales con tu agente y, a la vez, las empresas con el worker."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.agent_interface.errors import ToolError
from app.api.deps import EmptyBody, SessionDep, require_ui
from app.services import search_runs

router = APIRouter(prefix="/search", tags=["search"])


class StartSearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    portal_ids: list[int] | None = Field(
        default=None,
        max_length=50,
        description="Portales que recorrerá tu agente: `[]`, ninguno; sin valor, los activos.",
    )
    include_companies: bool = Field(
        default=True, description="Revisar también las empresas con portal propio activas."
    )


@router.post("/run", operation_id="start_search", dependencies=[Depends(require_ui)])
def start_search(session: SessionDep, body: StartSearchBody) -> search_runs.StartSearchResult:
    """Abre la búsqueda que sigue el aviso «Buscando…» y encola la revisión de las empresas
    (salvo las revisadas hace menos de `connectors.min_hours_between_runs`). El agente se lanza
    después con `POST /agent/launch` y `search.search_run_id`."""
    return search_runs.start_search(
        session, body.portal_ids, include_companies=body.include_companies
    )


@router.post("/run/{run_id}/stop", operation_id="stop_search", dependencies=[Depends(require_ui)])
def stop_search(
    session: SessionDep, run_id: int, _body: EmptyBody
) -> search_runs.SearchRunResponse:
    """No se pudo abrir tu agente: la búsqueda deja de esperarlo (las empresas siguen)."""
    try:
        search_runs.stop(session, run_id)
    except search_runs.SearchRunNotFoundError as exc:
        raise ToolError("not_found", str(exc)) from exc
    return search_runs.current(session)
