from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.api.deps import EmptyBody, SessionDep, require_ui, require_ui_read
from app.services import (
    agent_costs,
    duplicates,
    erase,
    events,
    ingest,
    jobs,
    liveness,
    reopenings,
)
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


class EraseJobBody(_Body):
    confirm: str = Field(description="El nombre de la empresa, escrito por el usuario.")


class EraseDuplicatesBody(_Body):
    job_ids: list[int] = Field(
        min_length=1, max_length=100_000, description="Las duplicadas de la vista previa."
    )


class CheckOpenBody(_Body):
    force: bool = Field(default=False, description="Repetir aunque haya una comprobación reciente.")


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
    remove_event_ids: list[int] | None = Field(
        default=None,
        max_length=50,
        description="Solo la UI: eventos posteriores anotados por error que se quitan para "
        "poder anotar este con fecha pasada (los de `POST /jobs/{id}/events/check`).",
    )


class CheckUserEventBody(_Body):
    type: EventType
    occurred_at: AwareDatetime


@router.get("", operation_id="list_jobs")
def list_jobs(
    session: SessionDep,
    stage: Stage | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=jobs.MAX_LIMIT)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    sort: jobs.JobSort = "date",
    dir: jobs.SortDirection = "desc",
    source_kind: Annotated[str | None, Query(max_length=32)] = None,
    remote_mode: Annotated[
        jobs.RemoteMode | None, Query(description="Modalidad de la extracción vigente.")
    ] = None,
    has_salary: Annotated[
        bool | None, Query(description="`true`: indica salario; `false`: no lo indica.")
    ] = None,
    has_score: Annotated[
        bool | None, Query(description="`true`: con encaje (score); `false`: sin encaje.")
    ] = None,
    min_score: Annotated[
        int | None, Query(ge=0, le=100, description="Encaje (score) mínimo.")
    ] = None,
    stages: Annotated[
        list[Stage] | None,
        Query(description="Varias etapas a la vez (`?stages=cv_ready&stages=closed`)."),
    ] = None,
    close_reason: Annotated[
        jobs.CloseReason | None, Query(description="Solo las cerradas con este motivo.")
    ] = None,
) -> jobs.JobPage:
    """Bandeja: filtrada por etapa (una o varias), texto (título o empresa), modalidad, salario,
    encaje y motivo de cierre, ordenada por fecha de alta, score o salario anualizado (por
    defecto, las más recientes primero; sin el dato, al final)."""
    return jobs.search_jobs(
        session,
        stage=stage.value if stage else None,
        q=q,
        limit=limit,
        offset=offset,
        sort=sort,
        direction=dir,
        source_kind=source_kind,
        remote_mode=remote_mode,
        has_salary=has_salary,
        has_score=has_score,
        min_score=min_score,
        stages=[value.value for value in stages] if stages is not None else None,
        reason=close_reason,
    )


@router.get(
    "/republished",
    operation_id="list_republished_jobs",
    dependencies=[Depends(require_ui_read)],
)
def list_republished_jobs(session: SessionDep) -> reopenings.RepublishedList:
    """Ofertas que cerraste tú y han vuelto a publicarse (fase 45): el aviso de la Bandeja."""
    return reopenings.list_republished(session)


@router.get("/duplicates", operation_id="list_duplicates")
def list_duplicates(session: SessionDep) -> duplicates.DuplicateList:
    """Ofertas guardadas como duplicadas de otra, con su original y si se pueden borrar."""
    return duplicates.list_duplicates(session)


@router.post(
    "/duplicates/erase",
    operation_id="erase_duplicates",
    dependencies=[Depends(require_ui)],
)
def erase_duplicates(session: SessionDep, body: EraseDuplicatesBody) -> duplicates.DuplicatesErased:
    """Borra las duplicadas de la vista previa que no tienen nada propio, tras copiar la base de
    datos. Solo desde la UI."""
    return duplicates.erase_duplicates(session, body.job_ids)


@router.post(
    "/{job_id}/republished/dismiss",
    operation_id="dismiss_republished_job",
    dependencies=[Depends(require_ui)],
)
def dismiss_republished_job(
    session: SessionDep, job_id: int, body: EmptyBody
) -> reopenings.RepublishedList:
    """«Ignorar» el aviso «Ha vuelto a publicarse». Para reabrirla, el evento `reopened`."""
    return reopenings.dismiss(session, job_id)


@router.get("/{job_id}", operation_id="get_job")
def get_job(session: SessionDep, job_id: int) -> jobs.JobView:
    """Ficha: metadatos, texto original, extracción vigente, eventos y aviso de inyección."""
    return jobs.get_job_view(session, job_id)


@router.get("/{job_id}/costs", operation_id="get_job_costs")
def get_job_costs(session: SessionDep, job_id: int) -> agent_costs.JobCost:
    """Lo que se ha gastado en esta oferta en segundo plano (fase 25.4): sus ejecuciones y su
    parte de las de lote. Lo de una terminal no cuenta: el agente no lo devuelve."""
    return agent_costs.job_cost(session, job_id)


@router.get("/{job_id}/match", operation_id="get_job_match")
def get_job_match(session: SessionDep, job_id: int) -> matching.MatchView:
    """Filtros duros, score y desglose vigentes (se recalculan si estaban desfasados)."""
    return matching.get_match(session, job_id)


@router.get(
    "/{job_id}/salary-gap",
    operation_id="get_job_salary_gap",
    dependencies=[Depends(require_ui_read)],
)
def get_job_salary_gap(session: SessionDep, job_id: int) -> matching.SalaryGapView:
    """Cuánto queda el sueldo publicado por debajo de tu mínimo. Solo la UI."""
    return matching.salary_gap(session, job_id)


@router.post("/{job_id}/erase", operation_id="erase_job", dependencies=[Depends(require_ui)])
def erase_job(session: SessionDep, job_id: int, body: EraseJobBody) -> erase.EraseResult:
    """Borra la oferta con todo lo suyo, tras copiar la base de datos. Solo desde la UI."""
    return erase.erase_job(session, job_id, body.confirm)


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
    session: SessionDep, request: Request, job_id: int, body: AddUserEventBody
) -> events.AddEventResult:
    """Registra un evento del usuario (nota, aprobar, descartar con motivo, reabrir…)."""
    if body.remove_event_ids:
        require_ui(request)  # quitar eventos, solo con el usuario delante
    return events.add_user_event(
        session,
        job_id,
        body.type,
        note=body.note,
        occurred_at=body.occurred_at,
        reason=body.reason,
        channel=body.channel,
        remove_event_ids=body.remove_event_ids,
    )


@router.post(
    "/{job_id}/events/check",
    operation_id="check_job_event",
    dependencies=[Depends(require_ui)],
)
def check_job_event(
    session: SessionDep, job_id: int, body: CheckUserEventBody
) -> events.EventConflicts:
    """Qué anotado después impide anotar un evento con fecha pasada y cómo arreglarlo. No escribe
    nada."""
    return events.check_user_event(session, job_id, body.type, body.occurred_at)


@router.post(
    "/{job_id}/check-open", operation_id="check_job_open", dependencies=[Depends(require_ui)]
)
def check_job_open(session: SessionDep, job_id: int, body: CheckOpenBody) -> liveness.LivenessView:
    """¿Sigue abierta? (fase 16). Solo avisa: nunca cierra la oferta."""
    return liveness.check_job(session, job_id, force=body.force)


@router.post(
    "/{job_id}/still-open", operation_id="confirm_job_open", dependencies=[Depends(require_ui)]
)
def confirm_job_open(session: SessionDep, job_id: int, body: EmptyBody) -> liveness.LivenessView:
    """«Sigue abierta»: quita el aviso de posible cierre; ese motivo ya no vuelve a avisar."""
    return liveness.confirm_open(session, job_id)
