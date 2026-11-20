from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import SessionDep, require_ui
from app.services import erase, status

router = APIRouter(tags=["status"])


@router.get("/status", operation_id="get_status")
def get_status(session: SessionDep) -> status.StatusReport:
    """Recuento de ofertas por etapa y tareas pendientes del worker."""
    return status.get_status(session)


class EraseAllBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: str = Field(description="«BORRAR», escrito por el usuario.")


@router.post("/data/erase", operation_id="erase_all_jobs", dependencies=[Depends(require_ui)])
def erase_all_jobs(session: SessionDep, body: EraseAllBody) -> erase.EraseResult:
    """Borra todas las ofertas y candidaturas, tras copiar la base de datos. Solo desde la UI."""
    return erase.erase_all(session, body.confirm)
