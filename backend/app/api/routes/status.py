from fastapi import APIRouter

from app.api.deps import SessionDep
from app.services import status

router = APIRouter(tags=["status"])


@router.get("/status", operation_id="get_status")
def get_status(session: SessionDep) -> status.StatusReport:
    """Recuento de ofertas por etapa y tareas pendientes del worker."""
    return status.get_status(session)
