"""El aviso «Buscando…» de una búsqueda abierta en la terminal del agente.

La app no ve la ventana del agente: sabe que una búsqueda sigue viva y cuándo acaba por lo que el
agente anota. Cada portal termina con `record_source_run` y, al final, `finish_search` cierra la
búsqueda (también cuando no ha podido hacerla). Si el agente no llega a decirlo, pasados 30 minutos
sin ninguna novedad el aviso dice que no hay noticias: nunca se queda en «Buscando…» para siempre.
"""

from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Job, SearchRun, Source, SourceRun
from app.models.base import utcnow
from app.services.ingestion.browse import KIND

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
    found: int
    created: int
    problems: int
    started_at: datetime
    finished_at: datetime | None


class SearchRunResponse(BaseModel):
    run: SearchRunView | None


class FinishSearchResult(BaseModel):
    closed: bool
    message: str


def _portals_to_walk(session: Session, platform_ids: list[int]) -> list[int]:
    if platform_ids:
        return sorted(set(platform_ids))
    rows = session.scalars(select(Source).where(Source.kind == KIND, Source.active)).all()
    return sorted(
        row.id
        for row in rows
        if row.config.get("allow_agent_browsing") and row.config.get("access") != "blocked"
    )


def start(session: Session, platform_ids: list[int]) -> SearchRun | None:
    """Empieza a seguir una búsqueda recién abierta. Una anterior sin cerrar deja de avisar: ahora
    es esta la que se sigue. Sin portales que recorrer no hay nada que seguir."""
    portals = _portals_to_walk(session, platform_ids)
    if not portals:
        return None
    now = utcnow()
    for previous in session.scalars(select(SearchRun).where(SearchRun.dismissed_at.is_(None))):
        previous.dismissed_at = now
    last_walk = session.scalar(select(func.max(SourceRun.id))) or 0
    run = SearchRun(source_ids=portals, after_source_run_id=last_walk, started_at=now)
    session.add(run)
    session.flush()
    return run


def _view(session: Session, run: SearchRun) -> SearchRunView:
    # Por id y no por fecha: `started_at` y `finished_at` de un recorrido los puede poner el agente.
    walks = session.scalars(
        select(SourceRun).where(
            SourceRun.id > run.after_source_run_id,
            SourceRun.actor == "agent",
            SourceRun.source_id.in_(run.source_ids),
        )
    ).all()
    done = {walk.source_id for walk in walks}
    created, last_job = session.execute(
        select(func.count(Job.id), func.max(Job.first_seen_at)).where(
            Job.source_id.in_(run.source_ids), Job.first_seen_at >= run.started_at
        )
    ).one()
    finishes = [walk.finished_at for walk in walks if walk.finished_at is not None]
    activity = max([run.started_at, *finishes, *([last_job] if last_job else [])])

    outcome: SearchOutcome | None = run.outcome  # type: ignore[assignment]
    status: SearchRunStatus
    if outcome is not None:
        status = "finished"
    elif done >= set(run.source_ids):
        status, outcome = "finished", "done"
    elif utcnow() - activity > STALE_AFTER:
        status = "stale"
    else:
        status = "running"
    return SearchRunView(
        id=run.id,
        status=status,
        outcome=outcome,
        portals_total=len(run.source_ids),
        portals_done=len(done),
        found=sum(walk.found for walk in walks),
        created=created,
        problems=sum(
            1 for walk in walks for issue in walk.errors if issue.get("code") != NOTE_CODE
        ),
        started_at=run.started_at,
        finished_at=(run.finished_at or activity) if status == "finished" else None,
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
