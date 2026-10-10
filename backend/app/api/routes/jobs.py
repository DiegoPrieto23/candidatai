from typing import Annotated

from fastapi import APIRouter, Query, status
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.api.deps import SessionDep
from app.services import events, ingest, jobs
from app.services.matching import service as matching
from app.services.pipeline import EventType, Stage

router = APIRouter(prefix="/jobs", tags=["jobs"])


class _Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AddFromUrlBody(_Body):
    url: str = Field(min_length=1, description="URL pública de la oferta (no LinkedIn).")


class AddFromTextBody(_Body):
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    text: str = Field(min_length=1)
    url: str | None = None
    location: str | None = None


class AddUserEventBody(_Body):
    type: EventType = Field(description="Solo eventos de actor `user` (ver DATA_MODEL.md).")
    note: str | None = Field(default=None, max_length=2000)
    occurred_at: AwareDatetime | None = None
    reason: events.DiscardReason | None = Field(
        default=None, description="Motivo al descartar (obligatorio en `discarded`)."
    )
    channel: events.ApplicationChannel | None = Field(
        default=None, description="Canal del envío (solo en `applied` y `applied_manually`)."
    )


@router.get("", operation_id="list_jobs")
def list_jobs(
    session: SessionDep,
    stage: Stage | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=jobs.MAX_LIMIT)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort: jobs.JobSort = "date",
    dir: jobs.SortDirection = "desc",
) -> jobs.JobPage:
    """Bandeja: filtrada por etapa y texto (título o empresa), ordenada por fecha de alta, score
    o salario anualizado (por defecto, las más recientes primero; sin el dato, al final)."""
    return jobs.search_jobs(
        session,
        stage=stage.value if stage else None,
        q=q,
        limit=limit,
        offset=offset,
        sort=sort,
        direction=dir,
    )


@router.get("/{job_id}", operation_id="get_job")
def get_job(session: SessionDep, job_id: int) -> jobs.JobView:
    """Ficha: metadatos, texto original, extracción vigente, eventos y aviso de inyección."""
    return jobs.get_job_view(session, job_id)


@router.get("/{job_id}/match", operation_id="get_job_match")
def get_job_match(session: SessionDep, job_id: int) -> matching.MatchView:
    """Filtros duros, score y desglose vigentes (se recalculan si estaban desfasados)."""
    return matching.get_match(session, job_id)


@router.post("/url", operation_id="add_job_from_url", status_code=status.HTTP_201_CREATED)
def add_job_from_url(session: SessionDep, body: AddFromUrlBody) -> ingest.AddJobResult:
    """Descarga la oferta y la da de alta (deduplicada, con `risk_flags`)."""
    return ingest.add_from_url(session, body.url)


@router.post("/text", operation_id="add_job_from_text", status_code=status.HTTP_201_CREATED)
def add_job_from_text(session: SessionDep, body: AddFromTextBody) -> ingest.AddJobResult:
    """Da de alta una oferta a partir de su texto pegado."""
    return ingest.add_from_text(
        session, body.title, body.company, body.text, url=body.url, location=body.location
    )


@router.post("/{job_id}/events", operation_id="add_job_event", status_code=status.HTTP_201_CREATED)
def add_job_event(
    session: SessionDep, job_id: int, body: AddUserEventBody
) -> events.AddEventResult:
    """Registra un evento del usuario (nota, aprobar, descartar con motivo, reabrir…)."""
    return events.add_user_event(
        session,
        job_id,
        body.type,
        note=body.note,
        occurred_at=body.occurred_at,
        reason=body.reason,
        channel=body.channel,
    )
