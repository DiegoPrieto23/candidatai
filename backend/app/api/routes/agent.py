"""Botones «en tu agente» (ADR-024): qué agente abrirían y abrirlo con la orden de un skill.

Capa fina sobre `services/agent_launch.py`. Solo para la UI: no hay herramienta MCP ni comando
`--json` equivalente, a propósito (un agente no se lanza a sí mismo).

Lanzar un programa desde una API local sin autenticación es delicado: cualquier web abierta en el
navegador puede enviar un POST a 127.0.0.1. Por eso `POST /agent/launch` exige que la petición
venga de la UI: `Origin` de la UI (si lo trae) y cuerpo JSON, que desde otra web obliga a una
comprobación previa CORS que esta API no concede.
"""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from app.agent_interface.errors import ErrorDetail, ToolError
from app.api.deps import SessionDep, require_ui
from app.services import agent_launch
from app.services.agent_launch import ActionId, LaunchError

router = APIRouter(prefix="/agent", tags=["agent"])

_ERROR_TYPES = {"not_found": "not_found", "invalid_request": "invalid_request"}


class Action(BaseModel):
    id: ActionId
    label: str
    needs_job: bool
    prompt: str | None  # la orden (sin oferta); con oferta, la da `launch` o se compone en la UI


class AgentStatus(agent_launch.AgentInfo):
    actions: list[Action]


class LaunchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ActionId
    job_id: int | None = Field(default=None, ge=1)


@router.get("", operation_id="get_agent_launcher")
def get_agent_launcher() -> AgentStatus:
    """Qué agente abren los botones (o por qué no se puede) y las órdenes disponibles."""
    actions = [
        Action(
            id=action_id,
            label=spec.label,
            needs_job=spec.needs_job,
            prompt=None if spec.needs_job else agent_launch.prompt_for(action_id),
        )
        for action_id, spec in agent_launch.ACTIONS.items()
    ]
    return AgentStatus(**agent_launch.info().model_dump(), actions=actions)


@router.post(
    "/launch",
    operation_id="launch_agent",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_ui)],
)
def launch_agent(session: SessionDep, body: LaunchBody) -> agent_launch.LaunchResult:
    """Abre tu agente en una terminal con la orden ya escrita. Tú ves y apruebas lo que haga."""
    try:
        return agent_launch.launch(session, body.action, body.job_id)
    except LaunchError as exc:
        if exc.code == "unavailable":
            # La UI copia la orden: va en `details` para que no tenga que componerla.
            prompt = agent_launch.prompt_for(body.action, body.job_id)
            detail = ErrorDetail(field="prompt", received=prompt, reason=str(exc))
            raise ToolError("agent_unavailable", str(exc), [detail]) from exc
        raise ToolError(_ERROR_TYPES[exc.code], str(exc)) from exc
