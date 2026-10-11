"""Borradores de seguimiento y agradecimiento (fase 15).

Los redacta el agente (`save_message_draft`). La app no envía nada: el usuario copia el texto y,
cuando lo ha mandado desde su correo, lo marca aquí. Marcar y descartar, solo desde la UI.
"""

from fastapi import APIRouter, Depends

from app.api.deps import EmptyBody, SessionDep, require_ui
from app.services import drafts

router = APIRouter(tags=["drafts"])


@router.get("/jobs/{job_id}/drafts", operation_id="list_job_drafts")
def list_job_drafts(session: SessionDep, job_id: int) -> drafts.DraftList:
    """Borradores vigentes de la oferta y cuántos seguimientos llevas enviados."""
    return drafts.list_drafts(session, job_id)


@router.post(
    "/drafts/{draft_id}/sent", operation_id="mark_draft_sent", dependencies=[Depends(require_ui)]
)
def mark_draft_sent(
    session: SessionDep, draft_id: int, body: drafts.DraftSentBody
) -> drafts.DraftActionResult:
    """«Ya lo he enviado»: un seguimiento registra `followup_sent`."""
    return drafts.mark_draft_sent(session, draft_id, body.occurred_at)


@router.post(
    "/drafts/{draft_id}/discard",
    operation_id="discard_draft",
    dependencies=[Depends(require_ui)],
)
def discard_draft(session: SessionDep, draft_id: int, body: EmptyBody) -> drafts.DraftActionResult:
    """Descarta el borrador sin registrar nada."""
    return drafts.discard_draft(session, draft_id)
