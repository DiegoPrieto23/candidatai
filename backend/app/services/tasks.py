"""Cola de trabajo del worker en la tabla `tasks` (sin Redis). Solo encolar y cambiar estado.

Los manejadores de cada tipo de tarea viven en `services/worker.py`, para que encolar no arrastre
sus dependencias (y no haya importaciones circulares con quien encola).
"""

from datetime import datetime, timedelta
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Task
from app.models.base import utcnow

TaskKind = Literal[
    "score_job",
    "rescore_all",
    "run_source",
    "poll_email",
    "expire_summaries",
    "browser_open",
    "apply_open",
    "apply_fill",
    "apply_rescan",
    "apply_submit",
    "apply_focus",
    "archive_application",
]
# Candidatura asistida (fase 11): sin reintentos (POLICIES §5.4). Si fallan o el worker se cierra
# a medias, quedan `failed` y decides tú; un envío nunca se repite solo.
NO_RETRY_KINDS = frozenset(
    {
        "browser_open",
        "apply_open",
        "apply_fill",
        "apply_fill_page",
        "apply_rescan",
        "apply_submit",
        "apply_focus",
    }  # fmt: skip
)
TaskStatus = Literal["queued", "running", "done", "failed"]
MAX_ATTEMPTS = 3
RETRY_DELAY = timedelta(minutes=1)  # se multiplica por el número de intentos


def enqueue(session: Session, kind: TaskKind, payload: dict[str, Any] | None = None) -> Task:
    """Encola una tarea. Si ya hay una igual en cola, devuelve esa en vez de duplicarla."""
    payload = payload or {}
    for task in session.scalars(select(Task).where(Task.kind == kind, Task.status == "queued")):
        if task.payload == payload:
            return task
    task = Task(kind=kind, payload=payload, status="queued", attempts=0, run_after=utcnow())
    session.add(task)
    session.flush()
    return task


def claim_next(session: Session, now: datetime | None = None) -> Task | None:
    """Marca como `running` la tarea en cola más antigua que ya toca ejecutar."""
    now = now or utcnow()
    task = session.scalars(
        select(Task)
        .where(Task.status == "queued", Task.run_after <= now)
        .order_by(Task.run_after, Task.id)
        .limit(1)
    ).first()
    if task is None:
        return None
    task.status = "running"
    task.attempts += 1
    session.flush()
    return task


def mark_done(session: Session, task_id: int) -> None:
    task = session.get(Task, task_id)
    if task is not None:
        task.status = "done"
        task.last_error = None


def mark_failed(session: Session, task_id: int, error: str, now: datetime | None = None) -> None:
    """Vuelve a la cola con espera creciente, o queda `failed` tras `MAX_ATTEMPTS` intentos."""
    task = session.get(Task, task_id)
    if task is None:
        return
    task.last_error = error[:2000]
    if task.attempts < MAX_ATTEMPTS and task.kind not in NO_RETRY_KINDS:
        task.status = "queued"
        task.run_after = (now or utcnow()) + RETRY_DELAY * task.attempts
    else:
        task.status = "failed"


def fail_interrupted(session: Session) -> list[Task]:
    """Las tareas sin reintentos que quedaron `running` (el worker se cerró a medias) quedan
    `failed`: nunca vuelven a la cola. Devuelve esas tareas."""
    stuck = list(
        session.scalars(select(Task).where(Task.status == "running", Task.kind.in_(NO_RETRY_KINDS)))
    )
    for task in stuck:
        task.status = "failed"
        task.last_error = "El worker se cerró mientras se ejecutaba. No se repite."
    session.flush()
    return stuck


def requeue_running(session: Session) -> int:
    """Devuelve a la cola las tareas que quedaron `running` (el worker se cerró a medias). Solo
    hay un worker, así que al arrancar ninguna puede estar ejecutándose de verdad. Las que no se
    reintentan las cierra antes `fail_interrupted`."""
    stuck = list(
        session.scalars(
            select(Task).where(Task.status == "running", Task.kind.not_in(NO_RETRY_KINDS))
        )
    )
    for task in stuck:
        task.status = "queued"
        task.run_after = utcnow()
    session.flush()
    return len(stuck)
