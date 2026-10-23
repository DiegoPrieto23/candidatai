"""Buzones de las alertas (fase 27.4, ADR-045). Solo la UI: la contraseña entra por aquí y no
vuelve nunca. El agente solo los ve (`list_mail_sources`)."""

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.api.deps import EmptyBody, SessionDep, require_ui, require_ui_read
from app.schemas.mail_sources import (
    MailSaveResult,
    MailSourceInput,
    MailSourceList,
    MailSourcePatch,
    MailTestResult,
)
from app.services import mail_sources

router = APIRouter(prefix="/mail-sources", tags=["mail-sources"])


class MailDeleteResult(BaseModel):
    message: str


@router.get("", operation_id="list_mail_sources", dependencies=[Depends(require_ui_read)])
def list_mail_sources(session: SessionDep) -> MailSourceList:
    """Los buzones, su estado y si tienen contraseña (nunca cuál)."""
    return mail_sources.list_mail_sources(session)


@router.post(
    "",
    operation_id="create_mail_source",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_ui)],
)
def create_mail_source(session: SessionDep, body: MailSourceInput) -> MailSaveResult:
    """Añade un buzón. La contraseña se guarda en `.env` (en Docker, dice qué línea añadir)."""
    return mail_sources.create_mail_source(session, body)


@router.post("/test", operation_id="test_new_mail_source", dependencies=[Depends(require_ui)])
def test_new_mail_source(body: MailSourceInput) -> MailTestResult:
    """Prueba un buzón antes de guardarlo: login y `EXAMINE`, sin leer correos."""
    return mail_sources.probe_new_mail_source(body)


@router.patch("/{source_id}", operation_id="update_mail_source", dependencies=[Depends(require_ui)])
def update_mail_source(
    session: SessionDep, source_id: int, body: MailSourcePatch
) -> MailSaveResult:
    """Cambia un buzón (también activarlo o desactivarlo). La contraseña, solo si se escribe."""
    return mail_sources.update_mail_source(session, source_id, body)


@router.post(
    "/{source_id}/test", operation_id="test_mail_source", dependencies=[Depends(require_ui)]
)
def test_mail_source(session: SessionDep, source_id: int, _body: EmptyBody) -> MailTestResult:
    """Prueba un buzón guardado: login y `EXAMINE` de su carpeta, sin leer correos."""
    return mail_sources.probe_mail_source(session, source_id)


@router.delete(
    "/{source_id}", operation_id="delete_mail_source", dependencies=[Depends(require_ui)]
)
def delete_mail_source(session: SessionDep, source_id: int, _body: EmptyBody) -> MailDeleteResult:
    """Quita un buzón y su línea de `.env`. Lo ya leído se queda."""
    return MailDeleteResult(message=mail_sources.delete_mail_source(session, source_id))
