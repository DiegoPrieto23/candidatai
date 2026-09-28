from fastapi import APIRouter

from app.api.deps import SessionDep
from app.services import triage

router = APIRouter(prefix="/triage", tags=["triage"])


@router.get("", operation_id="get_triage")
def get_triage(session: SessionDep) -> triage.TriageQueue:
    """Ofertas por revisar con su match (filtros, score y desglose), mayor score primero."""
    return triage.triage_queue(session)
