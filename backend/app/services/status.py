"""Resumen del estado de la búsqueda (`jh status`)."""

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Application
from app.services.pipeline import Stage


class StatusReport(BaseModel):
    total: int
    by_stage: dict[Stage, int]


def get_status(session: Session) -> StatusReport:
    """Recuento de ofertas por etapa, con todas las etapas presentes (también las vacías)."""
    rows = session.execute(
        select(Application.stage, func.count()).group_by(Application.stage)
    ).all()
    counts = {stage: 0 for stage in Stage}
    for stage, count in rows:
        counts[Stage(stage)] = count
    return StatusReport(total=sum(counts.values()), by_stage=counts)
