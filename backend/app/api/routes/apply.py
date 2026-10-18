"""Candidatura asistida (fase 11): preparar, revisar y enviar tras tu confirmación.

Capa fina sobre `services/applier/service.py`. Todo lo que toca el navegador lo hace el worker
(`cai worker`): estas rutas solo encolan y leen el estado. Es la única puerta al envío: no hay
herramienta MCP ni comando `--json` equivalente, a propósito (POLICIES §5).
"""

from collections.abc import Callable
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.agent_interface.errors import ErrorDetail, ToolError
from app.api.deps import SessionDep
from app.services import events
from app.services.applier import service
from app.services.applier.service import ApplierError, AssistedApplication, AttemptView

router = APIRouter(tags=["apply"])

# Código del servicio -> tipo de error de la API (y su estado HTTP en `api/errors.py`).
_ERROR_TYPES = {
    "not_found": "not_found",
    "invalid_url": "invalid_request",
    "company_mismatch": "invalid_request",
}


def _run[T](call: Callable[[], T]) -> T:
    """Traduce `ApplierError` al formato común; el código va en `details` para la UI."""
    try:
        return call()
    except ApplierError as exc:
        detail = ErrorDetail(field="code", received=exc.code, reason=str(exc))
        raise ToolError(
            _ERROR_TYPES.get(exc.code, "invalid_transition"), str(exc), [detail]
        ) from exc


class QueuedResult(BaseModel):
    ok: bool = True
    message: str


class PrepareBody(BaseModel):
    # El formulario de la empresa, si no es la URL de la oferta (p. ej. al que lleva el portal).
    form_url: str | None = Field(default=None, max_length=2000)


class SubmitBody(BaseModel):
    company_confirmation: str = Field(min_length=1, max_length=300)
    # El `updated_at` del intento que revisaste: si cambió después, hay que revisar otra vez.
    reviewed_at: datetime


@router.post(
    "/browser/open",
    operation_id="open_browser",
    status_code=status.HTTP_202_ACCEPTED,
)
def open_browser(session: SessionDep) -> QueuedResult:
    """«Abrir navegador»: el worker abre el navegador de las candidaturas, con una página de inicio
    para que inicies sesión en tus portales (se queda abierto)."""
    _run(lambda: service.open_browser(session))
    return QueuedResult(
        message="El navegador se abrirá en unos segundos si el worker está en marcha."
    )


@router.get("/jobs/{job_id}/apply", operation_id="get_assisted_application")
def get_assisted_application(session: SessionDep, job_id: int) -> AssistedApplication:
    """El último intento de la oferta y lo que haría «Preparar»."""
    return _run(lambda: service.get_state(session, job_id))


@router.post(
    "/jobs/{job_id}/apply/prepare",
    operation_id="prepare_application",
    status_code=status.HTTP_202_ACCEPTED,
)
def prepare_application(
    session: SessionDep, job_id: int, body: PrepareBody | None = None
) -> AttemptView:
    """Encola rellenar el formulario (o, en LinkedIn y en los portales de empleo, solo abrir la
    oferta). Con `form_url`, rellena esa URL (el formulario de la empresa). No envía nada."""
    form_url = body.form_url if body else None
    return _run(lambda: service.prepare(session, job_id, form_url))


@router.post(
    "/apply/{attempt_id}/fill-page",
    operation_id="fill_application_page",
    status_code=status.HTTP_202_ACCEPTED,
)
def fill_application_page(session: SessionDep, attempt_id: int) -> AttemptView:
    """«Rellenar esta página»: rellena la pestaña que tienes delante en el navegador de Job
    Hunter (el formulario de la empresa al que llegaste desde el portal). No envía nada."""
    return _run(lambda: service.fill_page(session, attempt_id))


@router.post(
    "/apply/{attempt_id}/rescan",
    operation_id="rescan_application",
    status_code=status.HTTP_202_ACCEPTED,
)
def rescan_application(session: SessionDep, attempt_id: int) -> AttemptView:
    """Vuelve a leer los campos y a capturar, tras completar algo tú en el navegador."""
    return _run(lambda: service.rescan(session, attempt_id))


@router.post(
    "/apply/{attempt_id}/submit",
    operation_id="submit_application",
    status_code=status.HTTP_202_ACCEPTED,
)
def submit_application(session: SessionDep, attempt_id: int, body: SubmitBody) -> AttemptView:
    """Tu confirmación de envío: con el nombre de la empresa escrito por ti, emite la confirmación
    de un solo uso y encola el envío."""
    return _run(
        lambda: service.confirm_submission(
            session, attempt_id, body.company_confirmation, body.reviewed_at
        )
    )


@router.post(
    "/apply/{attempt_id}/focus",
    operation_id="focus_application",
    status_code=status.HTTP_202_ACCEPTED,
)
def focus_application(session: SessionDep, attempt_id: int) -> AttemptView:
    """«Lo termino yo»: trae la pestaña al frente y deja que envíes tú."""
    return _run(lambda: service.focus(session, attempt_id))


@router.post("/jobs/{job_id}/apply/manual-done", operation_id="mark_application_sent")
def mark_application_sent(session: SessionDep, job_id: int) -> events.AddEventResult:
    """«Marcar como enviada» tras terminar tú: registra `applied_manually`."""
    return _run(lambda: service.mark_manual_done(session, job_id))


@router.get(
    "/apply/{attempt_id}/screenshot/{kind}",
    operation_id="get_application_screenshot",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}}},
)
def get_application_screenshot(
    session: SessionDep, attempt_id: int, kind: Literal["review", "confirmation"]
) -> FileResponse:
    """La captura de revisión o la de después de enviar."""
    path = _run(lambda: service.screenshot_file(session, attempt_id, kind))
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-store"})
