"""El aviso «Leyendo ofertas…», «Generando el CV…» de lo que lanzas con un botón de la app.

La app no ve la ventana del agente. Sabe cómo va por lo que el agente guarda: cada herramienta de la
interfaz queda anotada en `mcp_calls` (por MCP y por `cai … --json`), así que un guardado correcto
posterior al botón dice que ha avanzado o que ha terminado. Las acciones por lotes cuentan guardados
frente a lo que había pendiente al pulsar. Si termina antes (ofertas por debajo del umbral, una que
no se puede leer), el agente lo dice con `finish_task`. Sin ninguna novedad en 30 minutos, el aviso
dice que no hay noticias: nunca se queda en «Trabajando…» para siempre.

Con una ejecución en segundo plano manda además cómo acaba esa ejecución (`agent_runs`).

Solo se siguen las acciones que dejan un resultado. Las conversaciones (un simulacro, ampliar el
perfil…) ocurren a la vista, en su ventana, y no tienen un final que avisar.

Fase 48.1d: la ventana deja su PID al abrirse (`console_window`). Si ese proceso termina sin que
el agente haya acabado, el aviso pasa a `closed` («La ventana se cerró»). Si en `SILENT_AFTER` el
agente no ha llamado a ninguna herramienta de la app (o, sin ventana, el proceso no ha dado ninguna
salida), pasa a `silent` («El agente no ha empezado»): puede estar esperando una respuesta.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AgentRun,
    AgentRunEvent,
    AgentTask,
    Application,
    Company,
    Job,
    McpCall,
    Reply,
)
from app.models.base import utcnow
from app.services import agent_registry, console_window
from app.services.agent_actions import ACTIONS, ActionId
from app.services.launch_window import OpenedStyle
from app.services.pipeline import Stage

STALE_AFTER = timedelta(minutes=30)
SILENT_AFTER = timedelta(minutes=3)
PROCESS_BATCH = 20
TaskOutcome = Literal["done", "stopped", "failed", "needs_user"]
TaskStatus = Literal["running", "silent", "stale", "closed", "finished"]

_RUN_OUTCOMES: dict[str, TaskOutcome] = {
    "done": "done",
    "needs_user": "needs_user",
    "failed": "failed",
    "timeout": "failed",
    "cancelled": "stopped",
}


@dataclass(frozen=True)
class _Track:
    done_tools: tuple[str, ...]  # un guardado correcto: uno más hecho, o terminado si no es lote
    stop_tools: tuple[str, ...] = ()  # lo cierra sin resultado (p. ej. rechazar una corrección)
    batch: bool = False  # cuenta frente a lo pendiente al empezar (`_pending`)


TRACKED: dict[ActionId, _Track] = {
    # Un solo aviso para leer y valorar: cuenta lecturas y valoraciones guardadas.
    "process-jobs": _Track(("save_extraction", "save_fit_assessment"), batch=True),
    "assess-fit": _Track(("save_fit_assessment",), batch=True),
    "assess-fit-job": _Track(("save_fit_assessment",)),
    "review-replies": _Track(("save_reply_proposal",), batch=True),
    "generate-cv": _Track(("save_cv_verification",)),
    "correct-cv": _Track(("save_cv_verification",), stop_tools=("decline_cv_correction",)),
    "verify-cv": _Track(("save_cv_verification",)),
    "generate-cover-letter": _Track(("save_cover_letter_verification",)),
    "research-company": _Track(("save_company_research",)),
    "prepare-interview": _Track(("save_interview_guide",)),
    "correct-interview-guide": _Track(("save_interview_guide",)),
    "draft-follow-up": _Track(("save_message_draft",)),
    "draft-message": _Track(("save_message_draft",)),
}


class AgentTaskNotFoundError(LookupError):
    """No existe ese aviso."""


@dataclass(frozen=True)
class Window:
    """La ventana que se acaba de abrir: el fichero de su PID, cómo se abrió y su título."""

    token: str
    style: OpenedStyle
    title: str


class WindowView(BaseModel):
    style: OpenedStyle
    title: str
    # Hay un PID vivo y la app sabe traer esa ventana delante (Windows, consola: no una pestaña de
    # Windows Terminal).
    can_show: bool


class ShowWindowResult(BaseModel):
    shown: bool  # se encontró y se restauró
    foreground: bool  # además, se puso delante (si no, parpadea en la barra de tareas)


StepState = Literal["done", "current", "pending"]


class TaskStep(BaseModel):
    id: str  # el nombre sale de los textos de la UI
    state: StepState


class AgentTaskView(BaseModel):
    id: int
    action: ActionId
    job_id: int | None
    milestone_id: int | None
    subject: str | None  # «Puesto · Empresa» si es de una oferta
    background: bool
    # Fase 47.4: la ejecución en segundo plano (para «Detener»); `None` si se abrió en una terminal.
    run_id: int | None = None
    stopping: bool = False  # se pidió detenerla y el worker aún no ha parado el proceso
    stopped_by_user: bool = False  # la detuvo el usuario (`outcome` = `stopped`)
    status: TaskStatus
    outcome: TaskOutcome | None
    done: int
    total: int  # 0: no es por lotes
    # Los pasos de la acción (`agent_actions.Step`), si los tiene, y la última herramienta de la
    # app que ha llamado el agente (la actividad, para las que no tienen pasos).
    steps: list[TaskStep] = []
    last_tool: str | None = None
    agent: str | None = None  # el de la ejecución en segundo plano
    # Fase 48.1b: su agente pide los permisos a la app (si no, lo no permitido se deniega solo).
    asks_permissions: bool = False
    window: WindowView | None = None  # fase 48.1d: la ventana en la que se abrió
    started_at: datetime
    finished_at: datetime | None


class AgentTaskList(BaseModel):
    tasks: list[AgentTaskView]


class FinishTaskResult(BaseModel):
    closed: bool
    message: str


def _pending(session: Session, action: str) -> int:
    if action == "review-replies":
        count = session.scalar(select(func.count()).select_from(Reply).where(Reply.status == "new"))
        return count or 0

    def waiting(stage: Stage) -> int:
        count = session.scalar(
            select(func.count()).select_from(Application).where(Application.stage == stage)
        )
        return count or 0

    if action == "process-jobs":
        # Lee 20 de cada vez y valora esas más las que ya esperaban en «Por revisar»: lo que
        # espera esta tanda, no todo lo pendiente. Es un máximo: lo que queda por debajo del
        # umbral no se valora y el agente cierra el aviso con `finish_task`.
        read = min(waiting(Stage.PENDING_EXTRACTION), PROCESS_BATCH)
        return read + read + waiting(Stage.PENDING_TRIAGE)
    return waiting(Stage.PENDING_TRIAGE)


def start(
    session: Session,
    action: ActionId,
    job_id: int | None = None,
    milestone_id: int | None = None,
    run_id: int | None = None,
    window: Window | None = None,
) -> AgentTask | None:
    """Empieza a seguir lo que acaba de lanzar un botón. Si ya se seguía lo mismo, deja de avisar de
    lo anterior. Lo que no deja un resultado que detectar no se sigue."""
    track = TRACKED.get(action)
    if track is None:
        return None
    now = utcnow()
    earlier = select(AgentTask).where(
        AgentTask.action == action,
        AgentTask.job_id.is_(None) if job_id is None else AgentTask.job_id == job_id,
        AgentTask.dismissed_at.is_(None),
    )
    for row in session.scalars(earlier):
        row.dismissed_at = now
    task = AgentTask(
        action=action,
        job_id=job_id,
        milestone_id=milestone_id,
        run_id=run_id,
        total=_pending(session, action) if track.batch else 0,
        started_at=now,
        window_token=window.token if window else None,
        window_style=window.style if window else None,
        window_title=window.title if window else None,
    )
    session.add(task)
    session.flush()
    return task


def _calls_since(session: Session, row: AgentTask) -> list[McpCall]:
    stmt = select(McpCall).where(McpCall.called_at >= row.started_at).order_by(McpCall.id)
    return list(session.scalars(stmt))


def _for_this_job(row: AgentTask, call: McpCall) -> bool:
    return row.job_id is None or call.job_id is None or call.job_id == row.job_id


def _steps(action: str, called: set[str], finished_ok: bool) -> list[TaskStep]:
    """Hecho: se llamó bien a una de sus herramientas o a la de un paso posterior. El primero sin
    hacer es el actual. Los pasos sin herramientas («Listo») solo al terminar bien."""
    spec = ACTIONS.get(action)  # type: ignore[call-overload]
    if spec is None or not spec.steps:
        return []
    reached = -1
    for index, step in enumerate(spec.steps):
        if step.tools and called.intersection(step.tools):
            reached = index
    if finished_ok:
        reached = len(spec.steps) - 1
    steps: list[TaskStep] = []
    for index, step in enumerate(spec.steps):
        state: StepState = (
            "done" if index <= reached else "current" if index == reached + 1 else "pending"
        )
        steps.append(TaskStep(id=step.id, state=state))
    return steps


def asks_permissions(agent: str) -> bool:
    try:
        spec = agent_registry.get(agent)
    except agent_registry.ManifestError:
        return False
    return spec is not None and spec.headless is not None and spec.headless.asks_permissions


def _window_alive(row: AgentTask) -> bool | None:
    """Si su ventana sigue abierta (`None`: no se sabe). La primera vez que se ve cerrada se anota,
    para no depender de un PID que el sistema puede volver a usar."""
    if row.window_token is None:
        return None
    if row.window_closed_at is not None:
        return False
    if row.window_pid is None:
        row.window_pid = console_window.read_pid(row.window_token)
    if row.window_pid is None:
        return None
    if console_window.alive(row.window_pid):
        return True
    row.window_closed_at = utcnow()
    return False


def _run_silent(session: Session, run: AgentRun | None) -> bool:
    """Sin ventana: el proceso lleva `SILENT_AFTER` en marcha sin dar ninguna salida."""
    if run is None or run.status != "running" or run.started_at is None:
        return False
    if utcnow() - run.started_at <= SILENT_AFTER:
        return False
    first = session.scalar(select(AgentRunEvent.id).where(AgentRunEvent.run_id == run.id).limit(1))
    return first is None


def _view(session: Session, row: AgentTask, subject: str | None) -> AgentTaskView:
    track = TRACKED[row.action]  # type: ignore[index]
    calls = _calls_since(session, row)
    saved = [
        call
        for call in calls
        if call.ok and call.tool in track.done_tools and _for_this_job(row, call)
    ]
    stopped = any(
        call.ok and call.tool in track.stop_tools and _for_this_job(row, call) for call in calls
    )
    done = len(saved)

    outcome: TaskOutcome | None = row.outcome  # type: ignore[assignment]
    finished_at = row.finished_at
    run = session.get(AgentRun, row.run_id) if row.run_id else None
    if outcome is None and run is not None and run.status in _RUN_OUTCOMES:
        outcome = _RUN_OUTCOMES[run.status]
        finished_at = run.finished_at
    if outcome is None and stopped:
        outcome = "stopped"
    if outcome is None and saved and (not track.batch or 0 < row.total <= done):
        outcome = "done"
        finished_at = saved[-1].called_at

    status: TaskStatus
    activity = max([row.started_at, *(call.called_at for call in calls)])
    alive = _window_alive(row) if run is None and outcome is None else None
    if outcome is not None:
        status = "finished"
        finished_at = finished_at or activity
    elif alive is False:
        status = "closed"
    elif (run is None or run.status not in ("queued", "running")) and (
        utcnow() - activity > STALE_AFTER
    ):
        status = "stale"
    elif (run is None and not calls and utcnow() - row.started_at > SILENT_AFTER) or _run_silent(
        session, run
    ):
        status = "silent"
    else:
        status = "running"
    mine = [call for call in calls if _for_this_job(row, call)]
    called = {call.tool for call in mine if call.ok}
    return AgentTaskView(
        id=row.id,
        action=row.action,  # type: ignore[arg-type]
        job_id=row.job_id,
        milestone_id=row.milestone_id,
        subject=subject,
        background=row.run_id is not None,
        run_id=row.run_id,
        stopping=run is not None and run.status == "running" and run.cancel_requested,
        # Solo si la cerró la cancelación: si el agente ya había dicho que paraba, fue él.
        stopped_by_user=run is not None and run.status == "cancelled" and row.outcome is None,
        status=status,
        outcome=outcome,
        done=min(done, row.total) if row.total else done,
        total=row.total,
        steps=_steps(row.action, called, outcome == "done"),
        last_tool=mine[-1].tool if mine else None,
        agent=run.agent if run is not None else None,
        asks_permissions=run is not None and asks_permissions(run.agent),
        window=_window_view(row, alive) if run is None and outcome is None else None,
        started_at=row.started_at,
        finished_at=finished_at if status == "finished" else None,
    )


def _window_view(row: AgentTask, alive: bool | None) -> WindowView | None:
    if row.window_style is None or row.window_title is None:
        return None
    return WindowView(
        style=row.window_style,  # type: ignore[arg-type]
        title=row.window_title,
        can_show=bool(alive) and row.window_style != "wt" and console_window.can_show(),
    )


def show_window(session: Session, task_id: int) -> ShowWindowResult:
    """«Mostrar la ventana»: restaura la consola del aviso y, si Windows deja, la pone delante."""
    row = session.get(AgentTask, task_id)
    if row is None:
        raise AgentTaskNotFoundError(f"No existe el aviso {task_id}.")
    if row.run_id is not None or row.window_style == "wt" or not _window_alive(row):
        session.flush()
        return ShowWindowResult(shown=False, foreground=False)
    assert row.window_pid is not None  # `_window_alive` lo ha leído y está vivo
    shown = console_window.show(row.window_pid)
    return ShowWindowResult(shown=shown.found, foreground=shown.foreground)


def current(session: Session) -> AgentTaskList:
    """Los avisos que siguen abiertos, del más antiguo al más nuevo."""
    rows = session.scalars(
        select(AgentTask).where(AgentTask.dismissed_at.is_(None)).order_by(AgentTask.id)
    ).all()
    job_ids = {row.job_id for row in rows if row.job_id is not None}
    named = session.execute(
        select(Job.id, Job.title, Company.name)
        .join(Company, Company.id == Job.company_id)
        .where(Job.id.in_(job_ids))
    )
    subjects = {job_id: f"{title} · {company}" for job_id, title, company in named}
    return AgentTaskList(tasks=[_view(session, r, subjects.get(r.job_id or 0)) for r in rows])


def finish(session: Session, action: str, outcome: Literal["done", "stopped"]) -> FinishTaskResult:
    """El agente dice que ha terminado o que ha parado. `action` es la acción o el skill. Sin aviso
    abierto (se lo pidieron en el chat, p. ej.) no hay nada que cambiar, y no es un error."""
    names = {action} | {name for name, spec in ACTIONS.items() if spec.skill == action}
    if action == "assess-fit":
        names.add("assess-fit-job")
    row = session.scalar(
        select(AgentTask)
        .where(
            AgentTask.action.in_(names),
            AgentTask.dismissed_at.is_(None),
            AgentTask.outcome.is_(None),
        )
        .order_by(AgentTask.id.desc())
        .limit(1)
    )
    if row is None:
        return FinishTaskResult(closed=False, message="No había ningún aviso abierto de esto.")
    row.outcome = outcome
    row.finished_at = utcnow()
    session.flush()
    return FinishTaskResult(closed=True, message="Hecho: la app ya lo avisa.")


def reopen(session: Session, run_id: int) -> None:
    """Fase 48.1c: al retomar una ejecución, su aviso vuelve a estar en curso (aunque se hubiera
    cerrado). Los pasos se cuentan desde ahora."""
    row = session.scalars(
        select(AgentTask).where(AgentTask.run_id == run_id).order_by(AgentTask.id.desc()).limit(1)
    ).first()
    if row is None:
        return
    row.outcome = None
    row.finished_at = None
    row.dismissed_at = None
    row.started_at = utcnow()
    session.flush()


def dismiss(session: Session, task_id: int) -> None:
    """El usuario cierra el aviso. También sirve si cerró la ventana del agente a medias."""
    row = session.get(AgentTask, task_id)
    if row is None:
        raise AgentTaskNotFoundError(f"No existe el aviso {task_id}.")
    row.dismissed_at = row.dismissed_at or utcnow()
    session.flush()
