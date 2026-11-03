"""Resumen del estado de la búsqueda (`get_status` / `cai status`)."""

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Application, Task
from app.services import agent_requests
from app.services.pipeline import Stage


class StatusReport(BaseModel):
    total: int
    by_stage: dict[Stage, int]
    pending_tasks: int  # tareas del worker en cola
    agent_requests: int  # encargos que el usuario te dejó en la UI (fase 19): `list_agent_requests`
    demo_mode: bool  # datos ficticios de `cai demo seed` (fase 12.1)


def get_status(session: Session) -> StatusReport:
    """Recuento de ofertas por etapa, con todas las etapas presentes (también las vacías)."""
    rows = session.execute(
        select(Application.stage, func.count()).group_by(Application.stage)
    ).all()
    counts = {stage: 0 for stage in Stage}
    for stage, count in rows:
        counts[Stage(stage)] = count
    pending_tasks = session.scalar(
        select(func.count()).select_from(Task).where(Task.status == "queued")
    )
    return StatusReport(
        total=sum(counts.values()),
        by_stage=counts,
        pending_tasks=pending_tasks or 0,
        agent_requests=agent_requests.pending_count(session),
        demo_mode=get_settings().demo_mode,
    )
