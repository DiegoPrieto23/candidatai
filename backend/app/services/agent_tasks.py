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
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AgentRun, AgentTask, Application, Company, Job, McpCall, Reply
from app.models.base import utcnow
from app.services.agent_actions import ACTIONS, ActionId
from app.services.pipeline import Stage

STALE_AFTER = timedelta(minutes=30)
PROCESS_BATCH = 20
TaskOutcome = Literal["done", "stopped", "failed", "needs_user"]
TaskStatus = Literal["running", "stale", "finished"]

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


class AgentTaskView(BaseModel):
    id: int
    action: ActionId
    job_id: int | None
    milestone_id: int | None
    subject: str | None  # «Puesto · Empresa» si es de una oferta
    background: bool
    status: TaskStatus
    outcome: TaskOutcome | None
    done: int
    total: int  # 0: no es por lotes
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
    )
    session.add(task)
    session.flush()
    return task


def _calls_since(session: Session, row: AgentTask) -> list[McpCall]:
    stmt = select(McpCall).where(McpCall.called_at >= row.started_at).order_by(McpCall.id)
    return list(session.scalars(stmt))


def _for_this_job(row: AgentTask, call: McpCall) -> bool:
    return row.job_id is None or call.job_id is None or call.job_id == row.job_id


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
    if outcome is not None:
        status = "finished"
        finished_at = finished_at or activity
    elif (run is None or run.status not in ("queued", "running")) and (
        utcnow() - activity > STALE_AFTER
    ):
        status = "stale"
    else:
        status = "running"
    return AgentTaskView(
        id=row.id,
        action=row.action,  # type: ignore[arg-type]
        job_id=row.job_id,
        milestone_id=row.milestone_id,
        subject=subject,
        background=row.run_id is not None,
        status=status,
        outcome=outcome,
        done=min(done, row.total) if row.total else done,
        total=row.total,
        started_at=row.started_at,
        finished_at=finished_at if status == "finished" else None,
    )


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


def dismiss(session: Session, task_id: int) -> None:
    """El usuario cierra el aviso. También sirve si cerró la ventana del agente a medias."""
    row = session.get(AgentTask, task_id)
    if row is None:
        raise AgentTaskNotFoundError(f"No existe el aviso {task_id}.")
    row.dismissed_at = row.dismissed_at or utcnow()
    session.flush()
