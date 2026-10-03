"""Carta de presentación de una oferta (fase 08c.3). Capa fina sobre `cover_letter.py`.

Renderizar o retocar desde aquí no usa IA. Los PDF y DOCX se sirven por `/renders/{id}/…` (solo
desde `data/cvs/`) y la selección, por `/renders/{id}/select`, como en el CV. Nada se envía.
"""

from fastapi import APIRouter, Response, status

from app.api.deps import SessionDep
from app.schemas.cover_letter import (
    CoverLetterBriefInput,
    CoverLetterContent,
    CoverLetterRenderOptions,
)
from app.services.documents import cover_letter

router = APIRouter(tags=["cover_letter"])


@router.get("/jobs/{job_id}/cover-letter", operation_id="get_job_cover_letter")
def get_job_cover_letter(session: SessionDep, job_id: int) -> cover_letter.JobCoverLetter:
    """Indicaciones, carta vigente (con su texto plano) y plantillas con diseño de carta."""
    return cover_letter.get_job_cover_letter(session, job_id)


@router.post("/jobs/{job_id}/cover-letter/brief", operation_id="save_cover_letter_brief")
def save_cover_letter_brief(
    session: SessionDep, job_id: int, body: CoverLetterBriefInput
) -> cover_letter.SaveBriefResult:
    """Indicaciones de la carta de esta oferta; sustituyen a las anteriores (vacías: borrar)."""
    return cover_letter.save_brief(session, job_id, body)


@router.post(
    "/jobs/{job_id}/cover-letter",
    operation_id="save_user_cover_letter",
    status_code=status.HTTP_201_CREATED,
)
def save_user_cover_letter(
    session: SessionDep, job_id: int, body: CoverLetterContent
) -> cover_letter.SaveLetterResult:
    """Edición a mano: documento nuevo «Editada por ti», sin verificación, y su render."""
    return cover_letter.save_user_letter(session, job_id, body)


@router.post(
    "/cover-letters/{document_id}/renders",
    operation_id="render_cover_letter",
    status_code=status.HTTP_201_CREATED,
)
def render_cover_letter(
    session: SessionDep, document_id: int, body: CoverLetterRenderOptions
) -> cover_letter.LetterRenderResult:
    """Renderiza la carta con otro diseño, foto o color, sin agente."""
    return cover_letter.render_cover_letter(session, document_id, body)


@router.get(
    "/cover-letters/{document_id}/text",
    operation_id="get_cover_letter_text",
    response_class=Response,
    responses={200: {"content": {"text/plain": {}}}},
)
def get_cover_letter_text(session: SessionDep, document_id: int) -> Response:
    """La carta en TXT (UTF-8, saltos de Windows) para descargarla."""
    text = cover_letter.plain_text(session, document_id)
    name = cover_letter.text_file_name(session, document_id)
    return Response(
        content=text.encode("utf-8"),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
