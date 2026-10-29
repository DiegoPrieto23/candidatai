from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.agent_interface.errors import ToolError
from app.api.deps import EmptyBody, SessionDep, require_ui, require_ui_read
from app.core.config import get_settings
from app.services import capture as capture_service

router = APIRouter(prefix="/capture", tags=["capture"])


def require_capture_auth(
    authorization: Annotated[str | None, Header()] = None,
    origin: Annotated[str | None, Header()] = None,
) -> None:
    """Origen de la extensión y su token. Es una dependencia para que FastAPI la resuelva antes
    de validar el cuerpo: una petición sin autorizar recibe 401/403, nunca un 422.

    La defensa real es el token: la clave pública de la extensión está en el repositorio, así que
    cualquiera podría montar otra con el mismo id. El origen evita que una web cualquiera lo
    intente desde el navegador."""
    settings = get_settings()
    if origin != settings.capture_origin:
        raise ToolError(
            "forbidden",
            "Solo se acepta la extensión «Enviar a CandidatAI» configurada "
            "(`CAI_CAPTURE_EXTENSION_ID`).",
        )
    scheme, _, token = (authorization or "").partition(" ")
    try:
        valid = scheme.lower() == "bearer" and capture_service.check_token(settings, token.strip())
    except capture_service.CaptureNotConfiguredError as exc:
        raise ToolError("capture_not_configured", str(exc)) from None
    if not valid:
        raise ToolError(
            "unauthorized",
            "Token no válido: en CandidatAI, «Dónde buscar → Extensión», pulsa «Conectar».",
        )


@router.post("", operation_id="capture_job", dependencies=[Depends(require_capture_auth)])
def capture_job(
    session: SessionDep, body: capture_service.CaptureInput
) -> capture_service.CaptureResult:
    """Botón «Enviar a CandidatAI»: completa un resumen, reconoce una oferta ya guardada o da de
    alta una nueva. Solo desde la extensión configurada y con su token."""
    return capture_service.capture(session, body)


@router.get(
    "/extension", operation_id="get_extension_status", dependencies=[Depends(require_ui_read)]
)
def extension_status() -> capture_service.ExtensionStatus:
    """Para la guía de la UI: si hay token, el id de la extensión, su versión y su carpeta."""
    return capture_service.extension_status(get_settings())


@router.post("/pair", operation_id="pair_extension", dependencies=[Depends(require_ui)])
def pair_extension(_: EmptyBody) -> capture_service.Pairing:
    """«Conectar»: un token nuevo que la UI pasa a la extensión. Solo desde la UI."""
    return capture_service.pair(get_settings())
