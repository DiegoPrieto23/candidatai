"""Worker: ejecuta las tareas de la cola (`services/tasks.py`) y programa la ingesta diaria. Lo
lanza `jh worker`.

Cada tarea corre en su propia transacción: si falla, no deja nada a medias y vuelve a la cola con
espera creciente hasta `tasks.MAX_ATTEMPTS` intentos.

La ingesta diaria (fase 09) encola una tarea `run_source` por fuente activa a la hora de
`connectors.daily_at`. Al arrancar se encolan también las que no han corrido desde la última hora
programada (el portátil estaba apagado): así no se pierde ningún día.
"""

import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.core.policies import ConnectorsPolicy, get_policies
from app.models.base import utcnow
from app.services import tasks
from app.services.ingestion import service as sources
from app.services.matching import service as matching

logger = logging.getLogger(__name__)

Handler = Callable[[Session, dict[str, Any]], dict[str, Any]]
# Clave del resultado de una tarea que, aunque haya guardado lo que pudo, debe reintentarse.
RETRY_KEY = "retry_error"


def _score_job(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    match = matching.current_match(session, int(payload["job_id"]))
    return {"job_id": match.job_id, "match_id": match.id, "score": match.score}


def _rescore_all(session: Session, _payload: dict[str, Any]) -> dict[str, Any]:
    return matching.rescore_open_jobs(session).model_dump()


def _run_source(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    result = sources.run_source(session, int(payload["source_id"]), actor="system")
    data = result.model_dump(mode="json")
    # La ejecución fallida queda en `source_runs` (se confirma) y la tarea se reintenta.
    if (error := sources.retryable_error(result)) is not None:
        data[RETRY_KEY] = error
    return data


HANDLERS: dict[str, Handler] = {
    "score_job": _score_job,
    "rescore_all": _rescore_all,
    "run_source": _run_source,
}


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
    retry = result.get(RETRY_KEY)
    with session_scope() as session:
        if retry:
            tasks.mark_failed(session, task_id, str(retry))
        else:
            tasks.mark_done(session, task_id)
    return TaskOutcome(task_id=task_id, kind=kind, ok=not retry, result=result, error=retry)


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


# --- Ingesta diaria --------------------------------------------------------------------------


def last_scheduled(now: datetime, policy: ConnectorsPolicy) -> datetime:
    """La última vez (en UTC) que tocaba la ingesta diaria, en o antes de `now`."""
    zone = ZoneInfo(policy.timezone)
    hour, minute = (int(part) for part in policy.daily_at.split(":"))
    local = now.astimezone(zone)
    scheduled = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if scheduled > local:
        scheduled = (scheduled - timedelta(days=1)).replace(hour=hour, minute=minute)
    return scheduled.astimezone(now.tzinfo)


def enqueue_due_sources(session: Session, now: datetime | None = None) -> list[int]:
    """Encola `run_source` para cada fuente activa que no ha corrido desde la última hora
    programada (o nunca). Devuelve los ids de las fuentes encoladas."""
    now = now or utcnow()
    due = last_scheduled(now, get_policies().connectors)
    queued = []
    for source in sources.connector_sources(session):
        if sources.keys_missing(source.kind):
            continue  # portal sin claves: se avisa en la UI, no se encola cada día
        if source.last_run_at is None or source.last_run_at < due:
            tasks.enqueue(session, "run_source", {"source_id": source.id})
            queued.append(source.id)
    return queued


def describe(outcome: TaskOutcome) -> str:
    """Una línea legible para el log del worker."""
    result = outcome.result or {}
    if outcome.kind == "run_source" and result.get("message"):
        line = str(result["message"])
        if outcome.error:
            line += " Se reintentará más tarde."
        return line
    if not outcome.ok:
        return f"Tarea {outcome.task_id} ({outcome.kind}) fallida: {outcome.error}"
    if outcome.kind == "score_job":
        return f"Oferta {result.get('job_id')}: score {result.get('score')}"
    if outcome.kind == "rescore_all":
        scored, closed = result.get("scored", 0), len(result.get("closed") or [])
        return f"Recálculo de matches: {scored} ofertas, {closed} cerradas por filtros"
    return f"Tarea {outcome.task_id} ({outcome.kind}) hecha"


def run_scheduler(
    interval: float,
    on_run: Callable[[WorkerRun], None],
    on_message: Callable[[str], None],
) -> None:
    """Bloquea: procesa la cola cada `interval` segundos y la ingesta a `connectors.daily_at`."""
    from apscheduler.executors.pool import ThreadPoolExecutor
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    policy = get_policies().connectors
    hour, minute = (int(part) for part in policy.daily_at.split(":"))

    def process() -> None:
        try:
            run = run_pending()
        except Exception as exc:  # APScheduler lo tragaría sin que se viera en el log
            logger.exception("Fallo del worker al procesar la cola")
            on_message(f"Error al procesar la cola: {type(exc).__name__}: {exc}")
            return
        if run.outcomes:
            on_run(run)

    def daily() -> None:
        try:
            with session_scope() as session:
                queued = enqueue_due_sources(session)
        except Exception as exc:
            logger.exception("Fallo al encolar la ingesta diaria")
            on_message(f"Error al encolar la ingesta diaria: {type(exc).__name__}: {exc}")
            return
        on_message(f"Ingesta diaria: {len(queued)} fuentes en cola.")
        process()

    # Un solo hilo: la cola y la ingesta nunca escriben a la vez en SQLite.
    scheduler = BlockingScheduler(
        executors={"default": ThreadPoolExecutor(1)},
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600},
        timezone=ZoneInfo(policy.timezone),
    )
    scheduler.add_job(daily, CronTrigger(hour=hour, minute=minute), id="daily_sources")
    scheduler.add_job(process, "interval", seconds=interval, id="tasks")

    with session_scope() as session:
        if stuck := tasks.requeue_running(session):
            on_message(f"Tareas que quedaron a medias, de vuelta a la cola: {stuck}.")
        queued = enqueue_due_sources(session)
    if queued:
        on_message(f"Fuentes pendientes desde la última ingesta: {len(queued)} en cola.")
    process()
    on_message(f"Próxima ingesta diaria: {policy.daily_at} ({policy.timezone}).")
    scheduler.start()


def run_forever(
    interval: float,
    on_run: Callable[[WorkerRun], None],
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Solo la cola, sin ingesta programada (para pruebas)."""
    while True:
        run = run_pending()
        if run.outcomes:
            on_run(run)
        sleep(interval)
