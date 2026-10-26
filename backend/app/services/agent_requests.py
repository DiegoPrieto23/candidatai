"""Cola de encargos (fase 19): lo que la UI deja para la próxima sesión interactiva del
agente («Dejar para mi próxima sesión»). Inspirada en `agent-inbox` de career-ops.

- La orden la compone la app con la lista cerrada de `agent_launch.ACTIONS`, como los botones:
  ningún texto de una oferta. Crear y cancelar solo desde la UI.
- El agente los lee con `list_agent_requests` (también los cuenta `get_status`) y, al terminar
  cada uno, lo cierra con `complete_agent_request` y un resumen corto.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AgentRequest
from app.models.base import utcnow
from app.services import agent_launch
from app.services.agent_launch import ACTIONS, ActionId, LaunchError

RequestStatus = Literal["pending", "done", "cancelled"]
SUMMARY_CHARS = 2000


class AgentRequestView(BaseModel):
    id: int
    action: ActionId
    label: str
    job_id: int | None
    milestone_id: int | None
    prompt: str  # la orden que hay que seguir, como si la escribiera el usuario
    status: RequestStatus
    summary: str | None
    agent_name: str | None
    created_at: datetime
    completed_at: datetime | None


class AgentRequestList(BaseModel):
    requests: list[AgentRequestView]
    pending: int


class CompleteRequestResult(BaseModel):
    ok: bool = True
    request_id: int
    message: str


class RequestNotFoundError(LookupError):
    pass


class RequestClosedError(ValueError):
    pass


class CompleteRequestInput(BaseModel):
    summary: str = Field(
        min_length=1,
        max_length=SUMMARY_CHARS,
        description="Qué has hecho, en 1-3 frases (p. ej. «CV de la oferta 42 generado y "
        "verificado»). Lo ve el usuario en la UI.",
    )


def view(row: AgentRequest) -> AgentRequestView:
    return AgentRequestView(
        id=row.id,
        action=row.action,
        label=ACTIONS[row.action].label,
        job_id=row.job_id,
        milestone_id=row.milestone_id,
        prompt=row.prompt,
        status=row.status,
        summary=row.summary,
        agent_name=row.agent_name,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


def create(
    session: Session,
    action: ActionId,
    job_id: int | None = None,
    milestone_id: int | None = None,
) -> AgentRequestView:
    """Deja un encargo. Si ya hay uno pendiente igual, devuelve ese."""
    if action == "handle-requests":
        raise LaunchError("invalid_request", "Atender los encargos no puede ser un encargo.")
    prompt, job_id, milestone_id = agent_launch.check_target(session, action, job_id, milestone_id)
    existing = session.scalars(
        select(AgentRequest).where(
            AgentRequest.status == "pending",
            AgentRequest.action == action,
            AgentRequest.job_id == job_id,
            AgentRequest.milestone_id == milestone_id,
        )
    ).first()
    if existing is not None:
        return view(existing)
    row = AgentRequest(
        action=action, job_id=job_id, milestone_id=milestone_id, prompt=prompt, status="pending"
    )
    session.add(row)
    session.flush()
    return view(row)


def pending_count(session: Session) -> int:
    query = select(func.count()).select_from(AgentRequest).where(AgentRequest.status == "pending")
    return session.scalar(query) or 0


def list_requests(
    session: Session, status: RequestStatus | None = "pending", limit: int = 50
) -> AgentRequestList:
    """Los encargos, el más antiguo primero (pendientes) o el más reciente primero (el resto)."""
    query = select(AgentRequest).limit(limit)
    if status is not None:
        query = query.where(AgentRequest.status == status)
    order = AgentRequest.id if status == "pending" else AgentRequest.id.desc()
    rows = session.scalars(query.order_by(order)).all()
    return AgentRequestList(requests=[view(r) for r in rows], pending=pending_count(session))


def _pending(session: Session, request_id: int) -> AgentRequest:
    row = session.get(AgentRequest, request_id)
    if row is None:
        raise RequestNotFoundError(f"No existe el encargo {request_id}.")
    if row.status != "pending":
        raise RequestClosedError(f"El encargo {request_id} ya está cerrado ({row.status}).")
    return row


def complete(
    session: Session, request_id: int, summary: str, agent_name: str | None = None
) -> CompleteRequestResult:
    row = _pending(session, request_id)
    row.status = "done"
    row.summary = summary.strip()[:SUMMARY_CHARS]
    row.agent_name = agent_name
    row.completed_at = utcnow()
    session.flush()
    return CompleteRequestResult(
        request_id=row.id, message=f"Encargo {row.id} («{ACTIONS[row.action].label}») cerrado."
    )


def cancel(session: Session, request_id: int) -> AgentRequestView:
    """Desde la UI: el usuario ya no lo quiere."""
    row = _pending(session, request_id)
    row.status = "cancelled"
    row.completed_at = utcnow()
    session.flush()
    return view(row)
