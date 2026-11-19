"""El aviso «Buscando…» de una búsqueda abierta en la terminal del agente.

La app no ve la ventana del agente: sabe que una búsqueda sigue viva y cuándo acaba por lo que el
agente anota. Cada portal termina con `record_source_run` y, al final, `finish_search` cierra la
búsqueda (también cuando no ha podido hacerla). Si el agente no llega a decirlo, pasados 30 minutos
sin ninguna novedad el aviso dice que no hay noticias: nunca se queda en «Buscando…» para siempre.

Desde la fase 45, «Buscar ahora» revisa a la vez las empresas con portal propio (sus ATS, con el
worker y sin agente): `start_search` encola una tarea por empresa activa y la búsqueda no acaba
hasta que el agente termina **y** esas tareas han acabado.
"""

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.models import Job, SearchRun, Source, SourceRun, Task
from app.models.base import utcnow
from app.schemas.sources import ATS_KINDS
from app.services import tasks
from app.services.ingestion.browse import KIND
from app.services.ingestion.service import keys_missing

STALE_AFTER = timedelta(minutes=30)
# Lo que el agente apunta sin que sea un fallo: «leídas 3 de 6 búsquedas».
NOTE_CODE = "other"

SearchOutcome = Literal["done", "no_browser", "stopped"]
SearchRunStatus = Literal["running", "stale", "finished"]


class SearchRunNotFoundError(LookupError):
    """No existe esa búsqueda."""


class SearchRunView(BaseModel):
    """Lo que enseña el aviso. `problems` no cuenta las notas del agente."""

    id: int
    status: SearchRunStatus
    outcome: SearchOutcome | None
    portals_total: int
    portals_done: int
    # Empresas con portal propio revisadas a la vez (fase 45).
    companies_total: int = 0
    companies_done: int = 0
    # Tu agente ya terminó (lo dijo o todos los portales tienen recorrido): solo faltan empresas.
    portals_finished: bool = False
    found: int
    created: int
    reopened: int = 0  # de las nuevas, las que son reaperturas de una vacante anterior
    problems: int
    started_at: datetime
    finished_at: datetime | None


class SearchRunResponse(BaseModel):
    run: SearchRunView | None


class StartSearchResult(BaseModel):
    """Lo que ha empezado «Buscar ahora»: `run_id` es la búsqueda que sigue el aviso."""

    run_id: int | None
    portals: int
    companies: int
    # Empresas que no se revisan ahora: revisadas hace menos de `min_hours_between_runs`.
    companies_skipped: int
    message: str


class FinishSearchResult(BaseModel):
    closed: bool
    message: str


def _portals_to_walk(session: Session, platform_ids: list[int] | None) -> list[int]:
    """Los portales elegidos o, sin elegir (`None` o, por compatibilidad, `[]` del agente), los
    activos que el agente puede recorrer. Un id que no es uno de ellos no entra: si no, la búsqueda
    esperaría un recorrido que nunca llega."""
    rows = session.scalars(select(Source).where(Source.kind == KIND, Source.active)).all()
    usable = {
        row.id
        for row in rows
        if row.config.get("allow_agent_browsing") and row.config.get("access") != "blocked"
    }
    if platform_ids:
        return sorted(usable & set(platform_ids))
    return sorted(usable)


def _companies_due(session: Session) -> tuple[list[Source], int]:
    """Empresas con portal propio activas que toca revisar, y cuántas se saltan por recientes."""
    hours = get_policies().connectors.min_hours_between_runs
    since = utcnow() - timedelta(hours=hours)
    rows = session.scalars(
        select(Source)
        .where(Source.kind.in_(ATS_KINDS), Source.active.is_(True))
        .order_by(Source.id)
    ).all()
    # Con una revisión en cola o en marcha (otro clic, la ingesta diaria): no se repite.
    pending = {
        task.payload.get("source_id")
        for task in session.scalars(
            select(Task).where(Task.kind == "run_source", Task.status.in_(("queued", "running")))
        )
    }
    due = [s for s in rows if not keys_missing(s.kind)]
    skip = [
        s for s in due if (s.last_run_at is not None and s.last_run_at > since) or s.id in pending
    ]
    return [s for s in due if s not in skip], len(skip)


def _open(session: Session, portals: list[int]) -> SearchRun:
    """Una búsqueda nueva; la anterior sin cerrar deja de avisar: ahora se sigue esta."""
    now = utcnow()
    for previous in session.scalars(select(SearchRun).where(SearchRun.dismissed_at.is_(None))):
        previous.dismissed_at = now
    last_walk = session.scalar(select(func.max(SourceRun.id))) or 0
    run = SearchRun(source_ids=portals, after_source_run_id=last_walk, started_at=now)
    session.add(run)
    session.flush()
    return run


def start(session: Session, platform_ids: list[int]) -> SearchRun | None:
    """Empieza a seguir una búsqueda que abre el agente (sin empresas). Una anterior sin cerrar
    deja de avisar: ahora es esta la que se sigue. Sin portales que recorrer no hay nada que
    seguir."""
    portals = _portals_to_walk(session, platform_ids)
    if not portals:
        return None
    return _open(session, portals)


def start_search(
    session: Session, portal_ids: list[int] | None, *, include_companies: bool = True
) -> StartSearchResult:
    """«Buscar ahora»: abre la búsqueda con los portales elegidos (`[]`: ninguno; `None`: los
    activos) y encola la revisión de las empresas activas. El agente se lanza aparte, ligado a
    esta búsqueda (`search_run_id`)."""
    portals = _portals_to_walk(session, portal_ids) if portal_ids != [] else []
    companies, skipped = _companies_due(session) if include_companies else ([], 0)
    if not portals and not companies:
        message = (
            "No hay portales elegidos y las empresas activas ya se revisaron hace poco."
            if skipped
            else "No hay portales elegidos ni empresas activas que revisar."
        )
        return StartSearchResult(
            run_id=None, portals=0, companies=0, companies_skipped=skipped, message=message
        )
    run = _open(session, portals)
    queued = [
        tasks.enqueue(session, "run_source", {"source_id": c.id, "search_run_id": run.id})
        for c in companies
    ]
    run.company_ids = [c.id for c in companies]
    run.task_ids = [t.id for t in queued]
    session.flush()
    return StartSearchResult(
        run_id=run.id,
        portals=len(portals),
        companies=len(companies),
        companies_skipped=skipped,
        message=f"Buscando en {len(portals)} portales y {len(companies)} empresas.",
    )


def attach(session: Session, run_id: int) -> SearchRun:
    """El agente que lanza «Buscar ahora» sigue la búsqueda ya abierta por `start_search`."""
    run = session.get(SearchRun, run_id)
    if run is None or run.dismissed_at is not None or run.outcome is not None:
        raise SearchRunNotFoundError(f"No hay una búsqueda abierta con el id {run_id}.")
    return run


def stop(session: Session, run_id: int) -> None:
    """No se pudo abrir el agente tras «Buscar ahora»: los portales se dan por parados, y el aviso
    sigue solo hasta que acaban las empresas."""
    run = session.get(SearchRun, run_id)
    if run is None:
        raise SearchRunNotFoundError(f"No existe la búsqueda {run_id}.")
    if run.outcome is None:
        run.outcome = "stopped"
        run.finished_at = utcnow()
        session.flush()


def _view(session: Session, run: SearchRun) -> SearchRunView:
    portals = list(run.source_ids or [])
    companies = list(run.company_ids or [])
    # Por id y no por fecha: `started_at` y `finished_at` de un recorrido los puede poner el agente.
    walks = (
        session.scalars(
            select(SourceRun).where(
                SourceRun.id > run.after_source_run_id,
                SourceRun.actor == "agent",
                SourceRun.source_id.in_(portals),
            )
        ).all()
        if portals
        else []
    )
    company_walks = session.scalars(
        select(SourceRun).where(SourceRun.search_run_id == run.id, SourceRun.actor != "agent")
    ).all()
    task_rows = (
        session.scalars(select(Task).where(Task.id.in_(run.task_ids))).all() if run.task_ids else []
    )
    companies_done = sum(1 for task in task_rows if task.status in ("done", "failed"))
    # En cola (también a la espera de un reintento): el worker aún no ha llegado, no es que no haya
    # noticias.
    companies_waiting = any(task.status == "queued" for task in task_rows)
    # Una tarea borrada (limpieza de la cola) cuenta como acabada.
    companies_done += len(run.task_ids or []) - len(task_rows)
    done = {walk.source_id for walk in walks}
    created, reopened, last_job = session.execute(
        select(
            func.count(Job.id),
            func.count(Job.reopening_of),
            func.max(Job.first_seen_at),
        ).where(Job.source_id.in_(portals + companies), Job.first_seen_at >= run.started_at)
    ).one()
    finishes = [w.finished_at for w in [*walks, *company_walks] if w.finished_at is not None]
    activity = max([run.started_at, *finishes, *([last_job] if last_job else [])])

    outcome: SearchOutcome | None = run.outcome  # type: ignore[assignment]
    portals_finished = not portals or outcome is not None or done >= set(portals)
    companies_finished = companies_done >= len(run.task_ids or [])
    status: SearchRunStatus
    if portals_finished and companies_finished:
        status, outcome = "finished", outcome or "done"
    elif utcnow() - activity > STALE_AFTER and not (portals_finished and companies_waiting):
        status = "stale"
    else:
        status = "running"
    return SearchRunView(
        id=run.id,
        status=status,
        outcome=outcome if status == "finished" or run.outcome else None,
        portals_total=len(portals),
        portals_done=len(done),
        companies_total=len(companies),
        companies_done=min(companies_done, len(companies)),
        portals_finished=portals_finished,
        found=sum(walk.found for walk in [*walks, *company_walks]),
        created=created,
        reopened=reopened,
        problems=sum(
            1
            for walk in [*walks, *company_walks]
            for issue in walk.errors
            if issue.get("code") != NOTE_CODE
        ),
        started_at=run.started_at,
        finished_at=(
            max(filter(None, [run.finished_at, activity])) if status == "finished" else None
        ),
    )


def current(session: Session) -> SearchRunResponse:
    """La búsqueda de la que hay que avisar: la última que no has cerrado."""
    run = session.scalar(
        select(SearchRun)
        .where(SearchRun.dismissed_at.is_(None))
        .order_by(SearchRun.id.desc())
        .limit(1)
    )
    return SearchRunResponse(run=_view(session, run) if run else None)


def finish(session: Session, outcome: SearchOutcome) -> FinishSearchResult:
    """El agente ha terminado o no ha podido seguir. Sin búsqueda abierta desde la UI (se la
    pidieron en el chat, p. ej.) no hay aviso que cambiar, y no es un error."""
    run = session.scalar(
        select(SearchRun)
        .where(SearchRun.dismissed_at.is_(None), SearchRun.outcome.is_(None))
        .order_by(SearchRun.id.desc())
        .limit(1)
    )
    if run is None:
        return FinishSearchResult(closed=False, message="No había ninguna búsqueda abierta.")
    run.outcome = outcome
    run.finished_at = utcnow()
    session.flush()
    return FinishSearchResult(closed=True, message="Búsqueda cerrada: la app ya lo avisa.")


def dismiss(session: Session, run_id: int) -> None:
    """El usuario cierra el aviso. También sirve si cerró la ventana del agente a medias."""
    run = session.get(SearchRun, run_id)
    if run is None:
        raise SearchRunNotFoundError(f"No existe la búsqueda {run_id}.")
    run.dismissed_at = run.dismissed_at or utcnow()
    session.flush()
