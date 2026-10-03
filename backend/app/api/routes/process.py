"""Seguimiento de los procesos (fase 10): kanban, ficha de proceso, hitos, contactos y calendario.

CORS solo admite GET y POST: editar y borrar van por POST, como en `/sources`.
"""

from typing import Annotated

from fastapi import APIRouter, Query, Response, status
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.services import calendar_ics, process, tracking

router = APIRouter(tags=["process"])

ICS_MEDIA_TYPE = "text/calendar; charset=utf-8"


class OkResult(BaseModel):
    ok: bool = True


@router.get("/board", operation_id="get_board")
def get_board(
    session: SessionDep,
    closed_limit: Annotated[int, Query(ge=0, le=500)] = tracking.CLOSED_LIMIT,
) -> tracking.Board:
    """Kanban: tarjetas de `approved` a `closed` y los movimientos (eventos) posibles."""
    return tracking.get_board(session, closed_limit=closed_limit)


@router.get("/followups", operation_id="list_followups_due")
def list_followups_due(
    session: SessionDep,
    days: Annotated[int | None, Query(ge=1, le=tracking.MAX_DAYS)] = None,
) -> tracking.FollowupList:
    """Candidaturas enviadas sin respuesta desde hace N días (por defecto, los de la política)."""
    return tracking.list_followups_due(session, days)


@router.get("/upcoming", operation_id="list_upcoming")
def list_upcoming(
    session: SessionDep, days: Annotated[int, Query(ge=1, le=tracking.MAX_DAYS)] = 7
) -> tracking.UpcomingList:
    """Entrevistas, pruebas y plazos desde hoy hasta dentro de `days` días."""
    return tracking.list_upcoming(session, days)


@router.get("/jobs/{job_id}/process", operation_id="get_job_process")
def get_job_process(session: SessionDep, job_id: int) -> process.ProcessView:
    """Ficha de proceso: hitos, contactos, notas, documentos usados y seguimiento."""
    return process.get_process(session, job_id)


@router.post(
    "/jobs/{job_id}/milestones",
    operation_id="create_milestone",
    status_code=status.HTTP_201_CREATED,
)
def create_milestone(
    session: SessionDep, job_id: int, body: process.MilestoneCreate
) -> process.MilestoneOut:
    """Crea un hito. Una entrevista registra `interview_scheduled`; una prueba, `test_assigned`."""
    return process.create_milestone(session, job_id, body)


@router.post("/milestones/{milestone_id}", operation_id="update_milestone")
def update_milestone(
    session: SessionDep, milestone_id: int, body: process.MilestoneFields
) -> process.MilestoneOut:
    """Edita un hito programado (reprogramar una entrevista o una prueba deja una nota)."""
    return process.update_milestone(session, milestone_id, body)


@router.post("/milestones/{milestone_id}/status", operation_id="set_milestone_status")
def set_milestone_status(
    session: SessionDep, milestone_id: int, body: process.MilestoneStatusChange
) -> process.MilestoneOut:
    """Marca un hito como hecho (entrevista: `interview_done`) o cancelado."""
    return process.set_milestone_status(session, milestone_id, body)


@router.get(
    "/milestones/{milestone_id}/ics",
    operation_id="get_milestone_ics",
    response_class=Response,
    responses={200: {"content": {"text/calendar": {}}}},
)
def get_milestone_ics(session: SessionDep, milestone_id: int) -> Response:
    """El hito como `.ics`, para descargarlo e importarlo en el calendario."""
    body, filename = calendar_ics.milestone_ics(session, milestone_id)
    return Response(
        content=body.encode("utf-8"),
        media_type=ICS_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/calendar.ics",
    operation_id="get_calendar_feed",
    response_class=Response,
    responses={200: {"content": {"text/calendar": {}}}},
)
def get_calendar_feed(session: SessionDep, download: Annotated[bool, Query()] = False) -> Response:
    """Feed con los hitos futuros y los plazos. Con `download`, como fichero para importar."""
    headers = {"Cache-Control": "no-cache"}
    if download:
        headers["Content-Disposition"] = 'attachment; filename="jobhunter.ics"'
    return Response(
        content=calendar_ics.feed_ics(session).encode("utf-8"),
        media_type=ICS_MEDIA_TYPE,
        headers=headers,
    )


@router.post(
    "/jobs/{job_id}/contacts", operation_id="add_contact", status_code=status.HTTP_201_CREATED
)
def add_contact(
    session: SessionDep, job_id: int, body: process.ContactFields
) -> process.ContactOut:
    """Añade una persona de contacto al proceso."""
    return process.add_contact(session, job_id, body)


@router.post("/contacts/{contact_id}", operation_id="update_contact")
def update_contact(
    session: SessionDep, contact_id: int, body: process.ContactFields
) -> process.ContactOut:
    return process.update_contact(session, contact_id, body)


@router.post("/contacts/{contact_id}/delete", operation_id="delete_contact")
def delete_contact(session: SessionDep, contact_id: int) -> OkResult:
    process.delete_contact(session, contact_id)
    return OkResult()
