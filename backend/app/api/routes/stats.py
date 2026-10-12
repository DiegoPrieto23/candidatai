"""Analítica de la búsqueda (fase 10.2) y calibración del score (fase 20)."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import SessionDep
from app.services import analytics

router = APIRouter(tags=["stats"])


@router.get("/stats/funnel", operation_id="get_funnel_stats")
def get_funnel_stats(session: SessionDep, since: date | None = None) -> analytics.FunnelStats:
    """Embudo con su conversión, desglose por fuente, puesto y semana, tiempo hasta la primera
    respuesta y motivos de descarte de las ofertas vistas desde `since`."""
    return analytics.get_funnel_stats(session, since)


@router.get("/stats/calibration", operation_id="get_calibration")
def get_calibration(
    session: SessionDep,
    since: date | None = None,
    min_cases: Annotated[int, Query(ge=1, le=1000)] = analytics.MIN_CASES,
) -> analytics.Calibration:
    """«¿Acierta el score?»: respuesta y entrevista de las candidaturas enviadas desde `since`
    por tramo de score, veredicto, fuente, portal, plantilla, carta, referencia y días hasta el
    envío. Orientativa."""
    return analytics.get_calibration(session, since, min_cases)
