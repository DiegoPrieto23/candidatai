"""Botones «en tu agente» (ADR-024): qué agente abrirían y abrirlo con la orden de un skill, y
desde la fase 19 (ADR-032) lanzarlo en segundo plano y seguir sus ejecuciones.

Capa fina sobre `services/agent_launch.py`. Solo para la UI: no hay herramienta MCP ni comando
`--json` equivalente, a propósito (un agente no se lanza a sí mismo).

Lanzar un programa desde una API local sin autenticación es delicado: cualquier web abierta en el
navegador puede enviar un POST a 127.0.0.1. Por eso `POST /agent/launch` exige que la petición
venga de la UI: `Origin` de la UI (si lo trae) y cuerpo JSON, que desde otra web obliga a una
comprobación previa CORS que esta API no concede.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field

from app.agent_interface.errors import ErrorDetail, ToolError
from app.api.deps import EmptyBody, SessionDep, require_ui
from app.services import agent_launch, agent_requests, agent_runs
from app.services.agent_launch import ActionId, LaunchError

router = APIRouter(prefix="/agent", tags=["agent"])

_ERROR_TYPES = {"not_found": "not_found", "invalid_request": "invalid_request"}


class Action(BaseModel):
    id: ActionId
    label: str
    needs_job: bool
    needs_milestone: bool  # acción de un hito de entrevista (`milestone_id`)
    prompt: str | None  # la orden (sin oferta); con oferta, la da `launch` o se compone en la UI
    background: bool  # admite «En segundo plano» (fase 19)


class AgentStatus(agent_launch.AgentInfo):
    actions: list[Action]
    background: agent_launch.BackgroundInfo


class LaunchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ActionId
    job_id: int | None = Field(default=None, ge=1)
    milestone_id: int | None = Field(default=None, ge=1)  # acciones de una entrevista (fase 17)


@router.get("", operation_id="get_agent_launcher")
def get_agent_launcher() -> AgentStatus:
    """Qué agente abren los botones (o por qué no se puede) y las órdenes disponibles."""
    actions = [
        Action(
            id=action_id,
            label=spec.label,
            needs_job=spec.needs_job,
            needs_milestone=spec.milestone is not None,
            prompt=None if spec.needs_job else agent_launch.prompt_for(action_id),
            background=bool(spec.background),
        )
        for action_id, spec in agent_launch.ACTIONS.items()
    ]
    return AgentStatus(
        **agent_launch.info().model_dump(),
        actions=actions,
        background=agent_launch.background_info(),
    )


def _raise(exc: LaunchError) -> None:
    if exc.code == "unavailable":
        # La UI copia la orden: va en `details` para que no tenga que componerla.
        detail = ErrorDetail(field="prompt", received=exc.prompt, reason=str(exc))
        raise ToolError("agent_unavailable", str(exc), [detail]) from exc
    raise ToolError(_ERROR_TYPES[exc.code], str(exc)) from exc


@router.post(
    "/launch",
    operation_id="launch_agent",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_ui)],
)
def launch_agent(session: SessionDep, body: LaunchBody) -> agent_launch.LaunchResult:
    """Abre tu agente en una terminal con la orden ya escrita. Tú ves y apruebas lo que haga."""
    try:
        return agent_launch.launch(session, body.action, body.job_id, body.milestone_id)
    except LaunchError as exc:
        _raise(exc)
        raise


# --- En segundo plano (fase 19) ----------------------------------------------------------------


def _not_found(exc: agent_runs.RunNotFoundError) -> ToolError:
    return ToolError("not_found", str(exc))


@router.post(
    "/runs",
    operation_id="start_agent_run",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_ui)],
)
def start_agent_run(session: SessionDep, body: LaunchBody) -> agent_runs.AgentRunView:
    """Deja en cola una ejecución en segundo plano (la ejecuta `jh worker`, de una en una)."""
    try:
        return agent_runs.start(session, body.action, body.job_id, body.milestone_id)
    except LaunchError as exc:
        _raise(exc)
        raise


@router.get("/runs", operation_id="list_agent_runs")
def list_agent_runs(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    job_id: Annotated[int | None, Query(ge=1)] = None,
) -> agent_runs.AgentRunList:
    """Las últimas ejecuciones en segundo plano (las más recientes primero)."""
    return agent_runs.list_runs(session, limit, job_id)


@router.get("/runs/{run_id}", operation_id="get_agent_run")
def get_agent_run(session: SessionDep, run_id: int) -> agent_runs.AgentRunView:
    try:
        return agent_runs.get_run(session, run_id)
    except agent_runs.RunNotFoundError as exc:
        raise _not_found(exc) from exc


@router.post(
    "/runs/{run_id}/cancel", operation_id="cancel_agent_run", dependencies=[Depends(require_ui)]
)
def cancel_agent_run(session: SessionDep, run_id: int, body: EmptyBody) -> agent_runs.AgentRunView:
    """En cola: se cancela ya. En curso: el worker para el agente en unos segundos."""
    try:
        return agent_runs.cancel(session, run_id)
    except agent_runs.RunNotFoundError as exc:
        raise _not_found(exc) from exc
    except LaunchError as exc:
        _raise(exc)
        raise


@router.post(
    "/runs/{run_id}/open",
    operation_id="open_agent_run",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_ui)],
)
def open_agent_run(session: SessionDep, run_id: int, body: EmptyBody) -> agent_launch.LaunchResult:
    """«Abrir en terminal»: sigue la sesión de una ejecución terminada (p. ej. para contestar)."""
    try:
        return agent_runs.open_in_terminal(session, run_id)
    except agent_runs.RunNotFoundError as exc:
        raise _not_found(exc) from exc
    except LaunchError as exc:
        _raise(exc)
        raise


# --- Cola de encargos (fase 19) ----------------------------------------------------------------


@router.get("/requests", operation_id="list_agent_requests")
def list_agent_requests(
    session: SessionDep,
    state: Annotated[agent_requests.RequestStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> agent_requests.AgentRequestList:
    """Los encargos para tu próxima sesión del agente (sin `status`, todos)."""
    return agent_requests.list_requests(session, state, limit)


@router.post(
    "/requests",
    operation_id="create_agent_request",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_ui)],
)
def create_agent_request(session: SessionDep, body: LaunchBody) -> agent_requests.AgentRequestView:
    """«Dejar para mi próxima sesión»: el agente lo verá con `list_agent_requests`."""
    try:
        return agent_requests.create(session, body.action, body.job_id, body.milestone_id)
    except LaunchError as exc:
        _raise(exc)
        raise


@router.post(
    "/requests/{request_id}/cancel",
    operation_id="cancel_agent_request",
    dependencies=[Depends(require_ui)],
)
def cancel_agent_request(
    session: SessionDep, request_id: int, body: EmptyBody
) -> agent_requests.AgentRequestView:
    try:
        return agent_requests.cancel(session, request_id)
    except agent_requests.RequestNotFoundError as exc:
        raise ToolError("not_found", str(exc)) from exc
    except agent_requests.RequestClosedError as exc:
        raise ToolError("invalid_request", str(exc)) from exc
