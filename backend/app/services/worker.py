"""Worker: ejecuta las tareas de la cola (`services/tasks.py`) y programa la ingesta diaria. Lo
lanza `cai worker`.

Cada tarea corre en su propia transacción: si falla, no deja nada a medias y vuelve a la cola con
espera creciente hasta `tasks.MAX_ATTEMPTS` intentos.

La ingesta diaria (fase 09) encola una tarea `run_source` por fuente activa a la hora de
`connectors.daily_at`. Al arrancar se encolan también las que no han corrido desde la última hora
programada (el portátil estaba apagado): así no se pierde ningún día.

Alertas por correo (fase 09b): cada `email_alerts.poll_minutes` se encola `poll_email` si hay IMAP
configurado o correos en `data/inbox/`, y cada día, con la ingesta, `expire_summaries`.

Respuestas de las empresas (fase 15): con la misma frecuencia se encola `poll_replies` si hay de
dónde leer y alguna candidatura enviada abierta.

¿Sigue abierta? (fase 16): cada día, con la ingesta, y al arrancar se encola `check_open` para
cada oferta aprobada o con CV listo sin comprobación reciente. Una tarea por oferta: cada una en su
transacción, sin bloquear SQLite mientras espera a la red.

Candidatura asistida (fase 11): el worker es el único dueño del navegador persistente
(`services/applier/browser.py`). Sus tareas no se reintentan y, si el worker se cierra a medias,
quedan `failed` al arrancar, nunca vuelven a la cola.

Búsqueda pública de LinkedIn (fase 22, ADR-033): solo si el usuario la activó en la UI, con la
ingesta diaria y al arrancar se encola `run_linkedin_public` si le toca (una vez al día y, tras un
bloqueo, unos días después). Nunca se reintenta.

En segundo plano (fase 19): las `agent_runs` que deja la UI se ejecutan en un hilo propio, de una
en una, para que un agente de varios minutos no pare la cola. Tampoco se repiten si el worker se
cierra a medias.
"""

import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import session_scope
from app.core.policies import ConnectorsPolicy, get_policies
from app.models.base import utcnow
from app.services import (
    agent_runner,
    application_archive,
    container,
    liveness,
    replies,
    summaries,
    tasks,
)
from app.services.ingestion import linkedin_public
from app.services.ingestion import service as sources
from app.services.ingestion.email import service as email_alerts
from app.services.ingestion.email.mailboxes import has_local_mail
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


def _poll_email(session: Session, _payload: dict[str, Any]) -> dict[str, Any]:
    result = email_alerts.poll_email(session, actor="system")
    data = result.model_dump(mode="json")
    # El buzón entero falló por la red: queda en `source_runs` y se reintenta.
    if any(e.code == "network" and e.item is None for e in result.errors):
        data[RETRY_KEY] = next(e.message for e in result.errors if e.code == "network")
    return data


def _poll_replies(session: Session, _payload: dict[str, Any]) -> dict[str, Any]:
    result = replies.poll_replies(session)
    data = result.model_dump(mode="json")
    if any(e.code == "network" for e in result.errors):
        data[RETRY_KEY] = next(e.message for e in result.errors if e.code == "network")
    return data


def _expire_summaries(session: Session, _payload: dict[str, Any]) -> dict[str, Any]:
    return summaries.expire_summaries(session).model_dump(mode="json")


def _run_linkedin_public(session: Session, _payload: dict[str, Any]) -> dict[str, Any]:
    # Sin `RETRY_KEY`: un fallo o un bloqueo de LinkedIn no se reintenta.
    if not linkedin_public.due(session):
        return {"message": f"{linkedin_public.NAME}: no toca ahora o está desactivada."}
    return linkedin_public.run(session, actor="system").model_dump(mode="json")


def _check_open(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    return liveness.check_job(session, int(payload["job_id"])).model_dump(mode="json")


# Candidatura asistida (fase 11). Abren sus propias sesiones cortas: el navegador puede tardar.
def _browser_open(_session: Session, _payload: dict[str, Any]) -> dict[str, Any]:
    from app.services.applier import service as applier

    return applier.run_browser_open()


def _apply_open(_session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    from app.services.applier import service as applier

    return applier.run_open(int(payload["attempt_id"]))


def _apply_fill(_session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    from app.services.applier import service as applier

    return applier.run_fill(int(payload["attempt_id"]))


def _apply_fill_page(_session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    from app.services.applier import service as applier

    return applier.run_fill_page(
        int(payload["attempt_id"]), str(payload.get("previous") or "manual")
    )


def _apply_rescan(_session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    from app.services.applier import service as applier

    return applier.run_rescan(int(payload["attempt_id"]))


def _apply_submit(_session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    from app.services.applier import service as applier

    return applier.run_submit(
        int(payload["attempt_id"]), str(payload["token"]), list(payload.get("consents") or [])
    )


def _apply_focus(_session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    from app.services.applier import service as applier

    return applier.run_focus(int(payload["attempt_id"]))


def _archive_application(session: Session, payload: dict[str, Any]) -> dict[str, Any]:
    return application_archive.archive(session, payload).model_dump()


HANDLERS: dict[str, Handler] = {
    "score_job": _score_job,
    "rescore_all": _rescore_all,
    "run_source": _run_source,
    "poll_email": _poll_email,
    "run_linkedin_public": _run_linkedin_public,
    "poll_replies": _poll_replies,
    "expire_summaries": _expire_summaries,
    "browser_open": _browser_open,
    "apply_open": _apply_open,
    "apply_fill": _apply_fill,
    "apply_fill_page": _apply_fill_page,
    "apply_rescan": _apply_rescan,
    "apply_submit": _apply_submit,
    "apply_focus": _apply_focus,
    "archive_application": _archive_application,
    "check_open": _check_open,
}


# Las que usan el navegador visible de la candidatura asistida: en Docker no hay (fase 26.3).
BROWSER_KINDS = frozenset(
    {
        "browser_open",
        "apply_open",
        "apply_fill",
        "apply_fill_page",
        "apply_rescan",
        "apply_submit",
        "apply_focus",
    }
)


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
    agent_runs: list[agent_runner.AgentRunOutcome] = []  # `cai worker --once` (fase 19)


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
        if kind in BROWSER_KINDS and container.in_docker():
            from app.services.applier import service as applier

            attempt_id = payload.get("attempt_id")
            applier.refuse_in_docker(int(attempt_id) if attempt_id is not None else None)
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


def email_alerts_enabled() -> bool:
    """Si hay de dónde leer alertas: IMAP configurado o correos en `data/inbox/`."""
    settings = get_settings()
    return settings.imap_configured or has_local_mail(settings.inbox_dir)


def enqueue_email_poll(session: Session) -> bool:
    if not email_alerts_enabled():
        return False
    tasks.enqueue(session, "poll_email")
    return True


def enqueue_linkedin_public(session: Session) -> bool:
    """Encola la búsqueda pública de LinkedIn solo si está activada y le toca: apagada, nada."""
    if not linkedin_public.due(session):
        return False
    tasks.enqueue(session, "run_linkedin_public")
    return True


def enqueue_replies_poll(session: Session) -> bool:
    if not replies.replies_enabled() or not replies.has_open_processes(session):
        return False
    tasks.enqueue(session, "poll_replies")
    return True


def enqueue_liveness_checks(session: Session) -> int:
    """Encola `check_open` para las aprobadas y con CV listo sin comprobación reciente."""
    due = liveness.due_for_check(session)
    for job_id in due:
        tasks.enqueue(session, "check_open", {"job_id": job_id})
    return len(due)


def describe(outcome: TaskOutcome) -> str:
    """Una línea legible para el log del worker."""
    result = outcome.result or {}
    kinds = ("run_source", "poll_email", "poll_replies", "expire_summaries", "run_linkedin_public")
    if outcome.kind in kinds and result.get("message"):
        line = str(result["message"])
        if outcome.error:
            line += " Se reintentará más tarde."
        return line
    if not outcome.ok:
        return f"Tarea {outcome.task_id} ({outcome.kind}) fallida: {outcome.error}"
    if outcome.kind == "score_job":
        return f"Oferta {result.get('job_id')}: score {result.get('score')}"
    if outcome.kind.startswith("apply_") and result.get("attempt_id") is not None:
        state = result.get("status") or result.get("result") or result.get("skipped") or "hecho"
        return f"Candidatura asistida, intento {result['attempt_id']}: {state}"
    if outcome.kind == "archive_application" and result.get("folder"):
        verb = "archivada en" if result.get("created") else "ya estaba archivada en"
        return f"Candidatura de la oferta {result.get('job_id')} {verb} data/{result['folder']}"
    if outcome.kind == "check_open" and result.get("message"):
        return f"Oferta {result.get('job_id')}: {result['message']}"
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
                linkedin = enqueue_linkedin_public(session)
                tasks.enqueue(session, "expire_summaries")
                checks = enqueue_liveness_checks(session)
        except Exception as exc:
            logger.exception("Fallo al encolar la ingesta diaria")
            on_message(f"Error al encolar la ingesta diaria: {type(exc).__name__}: {exc}")
            return
        on_message(f"Ingesta diaria: {len(queued)} fuentes en cola.")
        if linkedin:
            on_message("Búsqueda pública de LinkedIn en cola (la activaste en Plataformas).")
        if checks:
            on_message(f"¿Siguen abiertas?: {checks} ofertas aprobadas o con CV en cola.")
        process()

    # Un solo hilo: la cola y la ingesta nunca escriben a la vez en SQLite. Las ejecuciones del
    # agente (fase 19) van en otro: duran minutos y solo escriben su propia fila de vez en cuando.
    scheduler = BlockingScheduler(
        executors={"default": ThreadPoolExecutor(1), "agents": ThreadPoolExecutor(1)},
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600},
        timezone=ZoneInfo(policy.timezone),
    )
    scheduler.add_job(daily, CronTrigger(hour=hour, minute=minute), id="daily_sources")
    scheduler.add_job(process, "interval", seconds=interval, id="tasks")

    def poll_email() -> None:
        try:
            with session_scope() as session:
                queued = enqueue_email_poll(session)
                queued = enqueue_replies_poll(session) or queued
        except Exception as exc:
            logger.exception("Fallo al encolar la lectura de alertas")
            on_message(f"Error al encolar la lectura de alertas: {type(exc).__name__}: {exc}")
            return
        if queued:
            process()

    poll_minutes = get_policies().email_alerts.poll_minutes
    scheduler.add_job(poll_email, "interval", minutes=poll_minutes, id="email_alerts")

    def background() -> None:
        try:
            for outcome in agent_runner.run_pending():
                on_message(agent_runner.describe(outcome))
        except Exception as exc:
            logger.exception("Fallo al ejecutar las ejecuciones en segundo plano")
            on_message(f"Error en segundo plano: {type(exc).__name__}: {exc}")

    scheduler.add_job(background, "interval", seconds=interval, id="agent_runs", executor="agents")

    if broken := agent_runner.recover_interrupted():
        on_message(f"En segundo plano, quedaron a medias (no se repiten): {broken}.")
    with session_scope() as session:
        if interrupted := tasks.fail_interrupted(session):
            from app.services.applier import service as applier

            ids = [int(t.payload["attempt_id"]) for t in interrupted if "attempt_id" in t.payload]
            applier.recover_interrupted(session, ids)
            on_message(
                f"Tareas del navegador que quedaron a medias (no se repiten): {len(interrupted)}."
            )
        if stuck := tasks.requeue_running(session):
            on_message(f"Tareas que quedaron a medias, de vuelta a la cola: {stuck}.")
        queued = enqueue_due_sources(session)
        linkedin = enqueue_linkedin_public(session)
        email = enqueue_email_poll(session)
        email = enqueue_replies_poll(session) or email
        tasks.enqueue(session, "expire_summaries")
        checks = enqueue_liveness_checks(session)
    if queued:
        on_message(f"Fuentes pendientes desde la última ingesta: {len(queued)} en cola.")
    if checks:
        on_message(f"¿Siguen abiertas?: {checks} ofertas aprobadas o con CV en cola.")
    if linkedin:
        on_message("Búsqueda pública de LinkedIn en cola (la activaste en Plataformas).")
    if email:
        on_message(f"Correo (alertas y respuestas): se lee al arrancar y cada {poll_minutes} min.")
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
