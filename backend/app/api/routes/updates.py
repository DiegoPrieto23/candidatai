"""Versiones nuevas de la app: el aviso de Inicio y «Actualizar ahora». Solo la UI."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import SessionDep, require_ui, require_ui_read
from app.services import ui_language, updates

router = APIRouter(prefix="/updates", tags=["updates"])


class ApplyUpdateBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str = Field(description="La versión que se ha confirmado en el aviso.")


@router.get("", operation_id="get_update_status", dependencies=[Depends(require_ui_read)])
def get_update_status() -> updates.UpdateStatus:
    """La versión en uso, la última publicada y cómo se actualiza esta instalación."""
    return updates.status()


@router.post("/apply", operation_id="apply_update", dependencies=[Depends(require_ui)])
def apply_update(session: SessionDep, body: ApplyUpdateBody) -> updates.UpdateStarted:
    """Cierra la app y la actualiza en una ventana aparte (instalación de Windows)."""
    return updates.apply(ui_language.current(session), body.version)
