"""Analítica de la búsqueda (fase 10.2)."""

from datetime import date

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.services import analytics

router = APIRouter(tags=["stats"])


@router.get("/stats/funnel", operation_id="get_funnel_stats")
def get_funnel_stats(session: SessionDep, since: date | None = None) -> analytics.FunnelStats:
    """Embudo con su conversión, desglose por fuente, puesto y semana, tiempo hasta la primera
    respuesta y motivos de descarte de las ofertas vistas desde `since`."""
    return analytics.get_funnel_stats(session, since)
