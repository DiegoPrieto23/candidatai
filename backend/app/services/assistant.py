"""«Asistente»: la caja de texto de la ayuda del portal.

La app no llama a ningún modelo: lo que escribes se lo pasa a tu agente, como los demás botones.

- El texto se guarda en `assistant_requests` y **no va en la orden**: la orden es fija y solo
  lleva el id de la petición. El skill `assistant` lo lee con `get_assistant_request`.
- Dos formas de enviarlo: ahora, en segundo plano (`agent_runs`, con las herramientas de la acción
  `assistant` y ninguna más), o como encargo para tu próxima sesión (`agent_requests`).
- El agente contesta con `save_assistant_answer`: un texto y enlaces a una oferta o a una pantalla
  de la app, nunca una dirección libre.
- Lo que la app protege (enviar una candidatura, borrar, aceptar una respuesta) no tiene
  herramienta: se confirma en la UI, lo pida quien lo pida.
"""

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AgentRequest, AgentRun, AssistantRequest, Company, Job
from app.models.base import utcnow
from app.services import agent_requests, agent_runs
from app.services.agent_launch import LaunchError

MAX_TEXT = 2000  # como la corrección de un CV
MAX_ANSWER = 4000
MAX_LINKS = 8
HISTORY = 20
MAX_ACTIVE = 3  # en cola o en curso a la vez: cada una es una ejecución de tu agente
PROGRESS_LINES = 8

Mode = Literal["background", "session"]
AssistantStatus = Literal["queued", "running", "waiting", "done", "failed", "cancelled"]
# Las pantallas a las que puede enlazar una respuesta: las mismas claves que usa la ayuda del
# portal (`frontend/src/lib/helpTopics.json`), que es quien sabe su ruta.
Screen = Literal[
    "home",
    "howItWorks",
    "profile",
    "skills",
    "templates",
    "search",
    "searchSettings",
    "sources",
    "companies",
    "email",
    "extension",
    "newJob",
    "inbox",
    "review",
    "complete",
    "board",
    "calendar",
    "replies",
    "funnel",
    "agent",
]
RequestText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT)
]

_RUN_STATUS: dict[str, AssistantStatus] = {
    "queued": "queued",
    "running": "running",
    "done": "done",
    "needs_user": "done",
    "failed": "failed",
    "timeout": "failed",
    "cancelled": "cancelled",
}
_REQUEST_STATUS: dict[str, AssistantStatus] = {
    "pending": "waiting",
    "done": "done",
    "cancelled": "cancelled",
}


class AssistantNotFoundError(LookupError):
    pass


class AssistantClosedError(ValueError):
    pass


class AssistantLink(BaseModel):
    """Un enlace de la respuesta: a la ficha de una oferta o a una pantalla de la app."""

    model_config = ConfigDict(extra="forbid")

    job_id: int | None = Field(default=None, ge=1, description="La ficha de esta oferta.")
    screen: Screen | None = Field(default=None, description="Una pantalla de la app.")

    @model_validator(mode="after")
    def _one_target(self) -> Self:
        if (self.job_id is None) == (self.screen is None):
            raise ValueError("Cada enlace lleva `job_id` o `screen`, uno de los dos.")
        return self


class LinkView(BaseModel):
    job_id: int | None
    screen: Screen | None
    label: str | None  # «Puesto · Empresa» de la oferta; las pantallas las nombra la UI


class ProgressView(BaseModel):
    at: datetime
    kind: agent_runs.ProgressKind
    text: str


class AssistantView(BaseModel):
    """Una petición, como la enseña el panel."""

    id: int
    text: str
    mode: Mode
    status: AssistantStatus
    answer: str | None
    links: list[LinkView]
    questions: list[str]  # lo que el agente dejó preguntado al terminar
    error: str | None
    progress: list[ProgressView]  # las últimas líneas, mientras trabaja
    agent: str | None
    run_id: int | None
    created_at: datetime
    finished_at: datetime | None


class AssistantList(BaseModel):
    requests: list[AssistantView]


class PendingAssistantRequest(BaseModel):
    """Lo que lee el skill `assistant`."""

    request_id: int
    text: str
    mode: Mode
    open: bool  # `false`: cancelada o ya contestada; no hay nada que hacer
    created_at: datetime


class SaveAnswerInput(BaseModel):
    answer: str = Field(
        min_length=1,
        max_length=MAX_ANSWER,
        description="La respuesta que verá el usuario en el panel, en su idioma y en texto "
        "llano: qué has hecho o qué has encontrado, y qué le toca a él.",
    )
    links: list[AssistantLink] = Field(
        default_factory=list,
        max_length=MAX_LINKS,
        description="Enlaces a lo que has cambiado o a donde se hace lo que pide: `job_id` (la "
        "ficha de una oferta) o `screen` (una pantalla).",
    )


class SaveAnswerResult(BaseModel):
    ok: bool = True
    request_id: int
    message: str


def _row(session: Session, request_id: int) -> AssistantRequest:
    row = session.get(AssistantRequest, request_id)
    if row is None:
        raise AssistantNotFoundError(f"No existe la petición {request_id}.")
    return row


def _status(row: AssistantRequest, run: AgentRun | None, request: AgentRequest | None) -> str:
    if run is not None:
        return _RUN_STATUS.get(run.status, "failed")
    if request is not None:
        return _REQUEST_STATUS.get(request.status, "waiting")
    return "failed"  # sin ejecución ni encargo: `create` no deja filas así


def _links(session: Session, rows: list[AssistantRequest]) -> dict[int, str]:
    job_ids = {link["job_id"] for row in rows for link in row.links or [] if link.get("job_id")}
    if not job_ids:
        return {}
    named = session.execute(
        select(Job.id, Job.title, Company.name)
        .join(Company, Company.id == Job.company_id)
        .where(Job.id.in_(job_ids))
    )
    return {job_id: f"{title} · {company}" for job_id, title, company in named}


def _view(session: Session, row: AssistantRequest, labels: dict[int, str]) -> AssistantView:
    run = session.get(AgentRun, row.run_id) if row.run_id else None
    request = session.get(AgentRequest, row.request_id) if row.request_id else None
    status = _status(row, run, request)
    answer = row.answer
    if answer is None and status == "done":
        # Terminó sin guardar la respuesta: vale lo último que dijo, o el resumen del encargo.
        answer = (run.result if run is not None else None) or (
            request.summary if request is not None else None
        )
    finished = row.answered_at
    if run is not None and run.finished_at is not None:
        finished = run.finished_at
    elif request is not None and request.completed_at is not None:
        finished = request.completed_at
    active = status in ("queued", "running")
    progress = (run.progress or [])[-PROGRESS_LINES:] if run is not None and active else []
    return AssistantView(
        id=row.id,
        text=row.text,
        mode=row.mode,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        answer=answer,
        links=[
            LinkView(
                job_id=link.get("job_id"),
                screen=link.get("screen"),
                label=labels.get(link.get("job_id") or 0),
            )
            for link in row.links or []
        ],
        questions=list(run.questions or []) if run is not None else [],
        error=run.error if run is not None and status == "failed" else None,
        progress=[ProgressView.model_validate(line) for line in progress],
        agent=(run.agent if run is not None else None) or row.agent_name,
        run_id=row.run_id,
        created_at=row.created_at,
        finished_at=finished if not active and status != "waiting" else None,
    )


def create(
    session: Session,
    text: str,
    mode: Mode,
    *,
    agent: str | None = None,
    model: str | None = None,
    preset: str | None = None,
) -> AssistantView:
    """Guarda lo que pide el usuario y lo envía: a una ejecución en segundo plano o a la cola de
    encargos. Si no se puede lanzar (`LaunchError`), no queda nada guardado."""
    if mode == "background":
        active = session.scalar(
            select(func.count())
            .select_from(AssistantRequest)
            .join(AgentRun, AgentRun.id == AssistantRequest.run_id)
            .where(AgentRun.status.in_(agent_runs.ACTIVE))
        )
        if (active or 0) >= MAX_ACTIVE:
            raise LaunchError(
                "invalid_request",
                f"Tu agente ya tiene {MAX_ACTIVE} peticiones en marcha: espera a que termine "
                "alguna o cancélala.",
            )
    row = AssistantRequest(text=text.strip()[:MAX_TEXT], mode=mode, links=[])
    session.add(row)
    session.flush()
    try:
        if mode == "background":
            run = agent_runs.start(
                session, "assistant", agent=agent, model=model, preset=preset, assistant_id=row.id
            )
            row.run_id = run.id
        else:
            request = agent_requests.create(session, "assistant", assistant_id=row.id)
            row.request_id = request.id
    except LaunchError:
        session.delete(row)
        session.flush()
        raise
    session.flush()
    return _view(session, row, {})


def get(session: Session, request_id: int) -> AssistantView:
    row = _row(session, request_id)
    return _view(session, row, _links(session, [row]))


def list_recent(session: Session, limit: int = HISTORY) -> AssistantList:
    """Las últimas peticiones, la más reciente primero: el historial del panel."""
    rows = list(
        session.scalars(select(AssistantRequest).order_by(AssistantRequest.id.desc()).limit(limit))
    )
    labels = _links(session, rows)
    return AssistantList(requests=[_view(session, row, labels) for row in rows])


def cancel(session: Session, request_id: int) -> AssistantView:
    """Desde la UI: para la ejecución o retira el encargo."""
    row = _row(session, request_id)
    try:
        if row.run_id is not None:
            agent_runs.cancel(session, row.run_id)
        elif row.request_id is not None:
            agent_requests.cancel(session, row.request_id)
    except agent_requests.RequestClosedError as exc:
        raise LaunchError("invalid_request", "Esa petición ya ha terminado.") from exc
    return get(session, request_id)


# --- Lo que usa el agente ----------------------------------------------------------------------


def _open(session: Session, row: AssistantRequest) -> bool:
    run = session.get(AgentRun, row.run_id) if row.run_id else None
    request = session.get(AgentRequest, row.request_id) if row.request_id else None
    return row.answer is None and _status(row, run, request) in ("queued", "running", "waiting")


def pending(session: Session, request_id: int) -> PendingAssistantRequest:
    row = _row(session, request_id)
    return PendingAssistantRequest(
        request_id=row.id,
        text=row.text,
        mode=row.mode,  # type: ignore[arg-type]
        open=_open(session, row),
        created_at=row.created_at,
    )


def save_answer(
    session: Session,
    request_id: int,
    answer: str,
    links: list[AssistantLink] | None = None,
    agent_name: str | None = None,
) -> SaveAnswerResult:
    """Guarda la respuesta del agente. Una sola por petición, y solo mientras sigue abierta."""
    row = _row(session, request_id)
    if not _open(session, row):
        raise AssistantClosedError(f"La petición {request_id} ya está cerrada.")
    links = links or []
    wanted = {link.job_id for link in links if link.job_id is not None}
    known = set(session.scalars(select(Job.id).where(Job.id.in_(wanted)))) if wanted else set()
    if missing := sorted(wanted - known):
        raise AssistantNotFoundError(
            f"No existe la oferta {missing[0]}: enlaza solo ofertas que hayas visto en la app."
        )
    row.answer = answer.strip()[:MAX_ANSWER]
    row.links = [link.model_dump(exclude_none=True) for link in links]
    row.agent_name = agent_name
    row.answered_at = utcnow()
    session.flush()
    return SaveAnswerResult(
        request_id=row.id, message=f"Respuesta de la petición {row.id} guardada."
    )
