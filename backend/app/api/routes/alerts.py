from fastapi import APIRouter

from app.api.deps import SessionDep
from app.services import summaries
from app.services.ingestion.email import service as email_alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", operation_id="list_alerts")
def list_alerts(session: SessionDep) -> summaries.AlertList:
    """Ofertas resumen (`pending_detail`) de las alertas, primero las que pasan el prefiltro."""
    return summaries.list_alerts(session)


@router.post("/poll", operation_id="poll_alerts")
def poll_alerts(session: SessionDep) -> email_alerts.EmailPollResult:
    """Lee ahora las alertas nuevas (IMAP en solo lectura y `data/inbox/`)."""
    return email_alerts.poll_email(session, actor="user")
