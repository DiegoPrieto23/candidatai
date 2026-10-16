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
from app.services import (
    agent_launch,
    agent_prefs,
    agent_registry,
    agent_requests,
    agent_runs,
    local_models,
    spend_tiers,
)
from app.services.agent_launch import ActionId, LaunchError
from app.services.agent_prefs import Preferences, Resolution

router = APIRouter(prefix="/agent", tags=["agent"])

_ERROR_TYPES = {"not_found": "not_found", "invalid_request": "invalid_request"}


class Action(BaseModel):
    id: ActionId
    label: str
    needs_job: bool
    needs_milestone: bool  # acción de un hito de entrevista (`milestone_id`)
    prompt: str | None  # la orden (sin oferta); con oferta, la da `launch` o se compone en la UI
    background: bool  # admite «En segundo plano» (fase 19)
    # Fase 24.4: con qué agente iría y por qué; los demás agentes, para elegir solo esta vez; y en
    # segundo plano, con cuál iría (o por qué no).
    agent: Resolution
    alternatives: list[Resolution]
    background_agent: agent_launch.BackgroundInfo | None


class AgentStatus(agent_launch.AgentInfo):
    actions: list[Action]
    background: agent_launch.BackgroundInfo


class RequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: ActionId
    job_id: int | None = Field(default=None, ge=1)
    milestone_id: int | None = Field(default=None, ge=1)  # acciones de una entrevista (fase 17)


class LaunchBody(RequestBody):
    """Fase 24.4: `agent`, `model` y `preset` eligen agente y modelo solo para esta ejecución."""

    agent: str | None = Field(default=None, max_length=32)
    model: str | None = Field(default=None, max_length=100)
    preset: str | None = Field(default=None, max_length=40)


def _background(res: Resolution, other: Resolution | None) -> agent_launch.BackgroundInfo:
    if res.usable:
        return agent_launch.BackgroundInfo(available=True, agent=res.agent)
    return agent_launch.BackgroundInfo(
        available=False,
        reason=res.blocked,
        suggested=other.agent if other else None,
        suggested_name=other.display_name if other else None,
    )


@router.get("", operation_id="get_agent_launcher")
def get_agent_launcher(session: SessionDep) -> AgentStatus:
    """Qué agente abren los botones (o por qué no se puede) y las órdenes disponibles, con el
    agente de cada una según tus preferencias (fase 24.4)."""
    ctx = agent_launch.Context(session)
    actions = []
    for action_id, spec in agent_launch.ACTIONS.items():
        _, res = agent_launch.choose(session, action_id, ctx=ctx)
        others = [name for name in ctx.by_name if name != res.agent]
        background = None
        if spec.background:
            _, bg = agent_launch.choose(session, action_id, mode="background", ctx=ctx)
            # Fase 24.5: si su agente no puede, se propone uno que sí.
            other = (
                None
                if bg.usable
                else agent_launch.suggest_background(session, action_id, ctx, skip=bg.agent)
            )
            background = _background(bg, other)
        actions.append(
            Action(
                id=action_id,
                label=spec.label,
                needs_job=spec.needs_job,
                needs_milestone=spec.milestone is not None,
                prompt=None if spec.needs_job else agent_launch.prompt_for(action_id),
                background=bool(spec.background),
                agent=res,
                alternatives=[
                    agent_launch.choose(session, action_id, agent=name, ctx=ctx)[1]
                    for name in others
                ],
                background_agent=background,
            )
        )
    return AgentStatus(
        **agent_launch.info(session).model_dump(),
        actions=actions,
        background=agent_launch.background_info(session),
    )


@router.get("/agents", operation_id="list_agents")
def list_agents(session: SessionDep) -> agent_launch.AgentsOverview:
    """Los agentes del manifiesto (fase 24.1): qué son, qué saben hacer y si están instalados, con
    tus preferencias y el agente efectivo de cada acción (fase 24.4). Lo mismo que
    `cai agents list --json`; solo lectura."""
    try:
        return agent_launch.overview(session)
    except agent_registry.ManifestError as exc:
        raise ToolError("internal_error", str(exc)) from exc


@router.get("/local-models", operation_id="get_local_models")
def get_local_models(session: SessionDep) -> local_models.LocalModelsStatus:
    """Si Ollama responde en este equipo, qué modelos tiene y con qué contexto (fase 24.6). Solo
    lee sus metadatos: la app no hace inferencia (ADR-001)."""
    return local_models.diagnose_for(session)


@router.put(
    "/preferences", operation_id="save_agent_preferences", dependencies=[Depends(require_ui)]
)
def save_agent_preferences(session: SessionDep, body: Preferences) -> Preferences:
    """Guarda tus preferencias de agente (fase 24.4): sustituye todas las anteriores."""
    try:
        return agent_launch.save_preferences(session, body)
    except agent_prefs.PreferenceError as exc:
        raise _pref_error(exc) from exc


def _pref_error(exc: agent_prefs.PreferenceError) -> ToolError:
    detail = ErrorDetail(field=exc.field, received=None, reason=str(exc))
    return ToolError("invalid_request", str(exc), [detail])


# --- Niveles de gasto (fase 24.6) -------------------------------------------------------------


@router.get("/tiers", operation_id="get_spend_tiers")
def get_spend_tiers(session: SessionDep) -> spend_tiers.TiersView:
    """«Económico», «Equilibrado» y «Máximo»: el agente y modelo de cada acción en cada nivel (lo
    guardado o la propuesta) y cuál coincide con tus preferencias de ahora."""
    return spend_tiers.tiers(session)


@router.put("/tiers/{tier}", operation_id="save_spend_tier", dependencies=[Depends(require_ui)])
def save_spend_tier(
    session: SessionDep, tier: spend_tiers.Tier, body: spend_tiers.TierActions
) -> spend_tiers.TiersView:
    """Guarda lo que pones en un nivel (sustituye lo que tenía)."""
    try:
        return spend_tiers.save_tier(session, tier, body)
    except agent_prefs.PreferenceError as exc:
        raise _pref_error(exc) from exc


@router.post(
    "/tiers/{tier}/reset", operation_id="reset_spend_tier", dependencies=[Depends(require_ui)]
)
def reset_spend_tier(
    session: SessionDep, tier: spend_tiers.Tier, body: EmptyBody
) -> spend_tiers.TiersView:
    """Vuelve a la propuesta de la app."""
    return spend_tiers.reset_tier(session, tier)


@router.post("/tiers/undo", operation_id="undo_spend_tier", dependencies=[Depends(require_ui)])
def undo_spend_tier(session: SessionDep, body: EmptyBody) -> spend_tiers.TiersView:
    """Devuelve las preferencias por acción de antes de aplicar el último nivel."""
    try:
        return spend_tiers.undo(session)
    except agent_prefs.PreferenceError as exc:
        raise _pref_error(exc) from exc


@router.post(
    "/tiers/{tier}/apply", operation_id="apply_spend_tier", dependencies=[Depends(require_ui)]
)
def apply_spend_tier(
    session: SessionDep, tier: spend_tiers.Tier, body: EmptyBody
) -> spend_tiers.TiersView:
    """Pone en tus preferencias por acción las del nivel. Se puede deshacer."""
    try:
        return spend_tiers.apply(session, tier)
    except agent_prefs.PreferenceError as exc:
        raise _pref_error(exc) from exc


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
        return agent_launch.launch(
            session,
            body.action,
            body.job_id,
            body.milestone_id,
            agent=body.agent,
            model=body.model,
            preset=body.preset,
        )
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
    """Deja en cola una ejecución en segundo plano (la ejecuta `cai worker`, de una en una)."""
    try:
        return agent_runs.start(
            session,
            body.action,
            body.job_id,
            body.milestone_id,
            agent=body.agent,
            model=body.model,
            preset=body.preset,
        )
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
def create_agent_request(session: SessionDep, body: RequestBody) -> agent_requests.AgentRequestView:
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
