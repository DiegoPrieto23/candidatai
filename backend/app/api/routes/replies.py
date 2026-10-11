"""«Respuestas» (fase 15): correos de las empresas y sus propuestas.

Aceptar o ignorar solo lo puede pedir la UI (`require_ui`): una propuesta la guarda un agente a
partir de un correo no confiable, y solo el usuario, en la UI, la convierte en un evento.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import EmptyBody, SessionDep, require_ui
from app.services import replies

router = APIRouter(prefix="/replies", tags=["replies"])


@router.get("", operation_id="get_reply_inbox")
def get_reply_inbox(
    session: SessionDep,
    status: replies.ReplyStatus | None = None,
    job_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> replies.ReplyInbox:
    """Respuestas guardadas, la más reciente primero, con sus ofertas y la propuesta."""
    return replies.inbox(session, status=status, job_id=job_id, limit=limit)


@router.post("/poll", operation_id="poll_replies", dependencies=[Depends(require_ui)])
def poll_replies(session: SessionDep, body: EmptyBody) -> replies.RepliesPollResult:
    """Lee ahora el correo (IMAP en solo lectura y `data/inbox/respuestas/`)."""
    return replies.poll_replies(session)


@router.get("/{reply_id}", operation_id="get_reply_view")
def get_reply_view(session: SessionDep, reply_id: int) -> replies.ReplyView:
    """Una respuesta con el texto visible del correo (para mostrarlo como texto)."""
    return replies.reply_view(session, reply_id)


@router.post("/{reply_id}/accept", operation_id="accept_reply", dependencies=[Depends(require_ui)])
def accept_reply(
    session: SessionDep, reply_id: int, body: replies.ReplyDecision
) -> replies.ReplyDecisionResult:
    """Registra el evento (y el hito) de la propuesta, tal cual o cambiada por el usuario."""
    return replies.accept_reply(session, reply_id, body)


@router.post("/{reply_id}/ignore", operation_id="ignore_reply", dependencies=[Depends(require_ui)])
def ignore_reply(
    session: SessionDep, reply_id: int, body: EmptyBody
) -> replies.ReplyDecisionResult:
    """Deja la respuesta sin registrar nada. Cuerpo `{}` (JSON: solo puede pedirlo la UI)."""
    return replies.ignore_reply(session, reply_id)
