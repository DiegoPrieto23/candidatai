"""Worker: ejecuta las tareas de la cola (`services/tasks.py`). Lo lanza `jh worker`.

Cada tarea corre en su propia transacción: si falla, no deja nada a medias y vuelve a la cola con
espera creciente hasta `tasks.MAX_ATTEMPTS` intentos.
"""

import logging
import time
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.services import tasks
from app.services.matching import service as matching

logger = logging.getLogger(__name__)

Handler = Callable[[Session, dict[str, Any]], dict[str, Any]]


def _score_job(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    match = matching.current_match(session, int(payload["job_id"]))
    return {"job_id": match.job_id, "match_id": match.id, "score": match.score}


def _rescore_all(session: Session, _payload: dict[str, Any]) -> dict[str, Any]:
    return matching.rescore_open_jobs(session).model_dump()


HANDLERS: dict[str, Handler] = {"score_job": _score_job, "rescore_all": _rescore_all}


class TaskOutcome(BaseModel):
    task_id: int
    kind: str
    ok: bool
    result: dict[str, Any] | None = None
    error: str | None = None


class WorkerRun(BaseModel):
    done: int
    failed: int
    outcomes: list[TaskOutcome]


def run_one() -> TaskOutcome | None:
    """Reclama y ejecuta la siguiente tarea. `None` si no hay ninguna pendiente."""
    with session_scope() as session:
        task = tasks.claim_next(session)
        if task is None:
            return None
        task_id, kind, payload = task.id, task.kind, dict(task.payload)
    try:
        handler = HANDLERS.get(kind)
        if handler is None:
            raise ValueError(f"Tipo de tarea desconocido: «{kind}».")
        with session_scope() as session:
            result = handler(session, payload)
    except Exception as exc:
        logger.warning("La tarea %s (%s) ha fallado", task_id, kind, exc_info=True)
        error = f"{type(exc).__name__}: {exc}"
        with session_scope() as session:
            tasks.mark_failed(session, task_id, error)
        return TaskOutcome(task_id=task_id, kind=kind, ok=False, error=error)
    with session_scope() as session:
        tasks.mark_done(session, task_id)
    return TaskOutcome(task_id=task_id, kind=kind, ok=True, result=result)


def run_pending(limit: int | None = None) -> WorkerRun:
    """Ejecuta las tareas que ya tocan, hasta vaciar la cola o llegar a `limit`."""
    outcomes: list[TaskOutcome] = []
    while limit is None or len(outcomes) < limit:
        outcome = run_one()
        if outcome is None:
            break
        outcomes.append(outcome)
    done = sum(o.ok for o in outcomes)
    return WorkerRun(done=done, failed=len(outcomes) - done, outcomes=outcomes)


def run_forever(
    interval: float,
    on_run: Callable[[WorkerRun], None],
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    while True:
        run = run_pending()
        if run.outcomes:
            on_run(run)
        sleep(interval)
