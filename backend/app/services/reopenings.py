"""Ofertas que vuelven a publicarse (fase 45), vistas desde la UI.

La decisión al dar de alta está en `ingest.republication`. Aquí, lo que enseña la UI:
- en la ficha de una reapertura, de qué oferta viene y cómo acabó;
- en la Bandeja, las ofertas que cerraste tú y han vuelto a publicarse (señal
  `republished_after_close`), para reabrirlas o ignorar el aviso.
"""

from datetime import datetime

from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Application, Company, Job
from app.models.base import utcnow
from app.services import ingest
from app.services.events import JobNotFoundError
from app.services.pipeline import Stage, job_events, project
from app.services.signals import JobSignals, read, set_signal

MAX_NOTICES = 50


class ReopeningOf(BaseModel):
    """La oferta cerrada de la que viene una reapertura."""

    job_id: int
    first_seen_at: datetime
    closed_at: datetime | None
    closed_by: str | None
    # Hasta dónde llegaste antes del cierre (`interview`, `applied`…), si se sabe.
    stage_before_close: Stage | None
    discard_reason: str | None


class RepublishedNotice(BaseModel):
    job_id: int
    title: str
    company: str
    closed_at: datetime | None
    closed_by: str | None
    seen_at: datetime
    url: str | None


class RepublishedList(BaseModel):
    items: list[RepublishedNotice]


def reopening_of(session: Session, job: Job) -> ReopeningOf | None:
    if job.reopening_of is None:
        return None
    previous = session.get(Job, job.reopening_of)
    if previous is None:
        return None
    app = session.get(Application, previous.id)
    events = job_events(session, previous.id)
    state = project(events) if events else None
    closed = app is not None and app.stage == Stage.CLOSED
    return ReopeningOf(
        job_id=previous.id,
        first_seen_at=previous.first_seen_at,
        closed_at=app.closed_at if closed and app else None,
        closed_by=app.closed_by if closed and app else None,
        stage_before_close=state.stage_before_close if closed and state else None,
        discard_reason=(
            ingest.discard_reason(session, previous.id)
            if closed and app and app.closed_by == "discarded"
            else None
        ),
    )


def list_republished(session: Session) -> RepublishedList:
    """Ofertas cerradas por ti que han vuelto a publicarse, la más reciente primero."""
    rows = session.execute(
        select(Job.id, Job.title, Job.signals, Company.name, Application.closed_at)
        .join(Company, Company.id == Job.company_id)
        .join(Application, Application.job_id == Job.id)
        .where(
            Application.stage == Stage.CLOSED,
            func.json_extract(Job.signals, "$.republished_after_close").is_not(None),
        )
        .add_columns(Application.closed_by)
    ).all()
    items: list[RepublishedNotice] = []
    for job_id, title, signals, company, closed_at, closed_by in rows:
        try:
            signal = JobSignals.model_validate(
                {"republished_after_close": (signals or {}).get("republished_after_close")}
            ).republished_after_close
        except ValidationError:  # editada a mano: se ignora, como en `signals.read`
            continue
        if signal is None or signal.dismissed_at is not None:
            continue
        items.append(
            RepublishedNotice(
                job_id=job_id,
                title=title,
                company=company,
                closed_at=closed_at,
                closed_by=closed_by,
                seen_at=signal.seen_at,
                url=signal.url,
            )
        )
    items.sort(key=lambda item: item.seen_at, reverse=True)
    return RepublishedList(items=items[:MAX_NOTICES])


def dismiss(session: Session, job_id: int) -> RepublishedList:
    """«Ignorar»: oculta el aviso. Si sigue publicándose pasados `dedup.reopen_after_days`,
    vuelve a avisar."""
    job = session.get(Job, job_id)
    if job is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    signal = read(job).republished_after_close
    if signal is not None and signal.dismissed_at is None:
        set_signal(
            job, "republished_after_close", signal.model_copy(update={"dismissed_at": utcnow()})
        )
        session.flush()
    return list_republished(session)
