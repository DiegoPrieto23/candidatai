"""Ninguna web abierta en el navegador puede cambiar nada en la API (CSRF).

Un formulario de otra web puede enviar un POST «simple» (`application/x-www-form-urlencoded`,
`multipart/form-data` o `text/plain`) a `http://127.0.0.1:8000` sin comprobación previa CORS: el
navegador no deja leer la respuesta, pero la acción se hace. `require_ui` lo impedía solo en las
rutas que lo declaran; las que no reciben cuerpo (borrar un hito, marcar una candidatura como
enviada, subir un CV…) quedaban abiertas. Este middleware lo cierra para todas a la vez.

Una petición que cambia algo (POST, PUT, PATCH, DELETE) solo pasa si:
- trae `Origin` y es la UI (`is_ui_origin`), o la extensión de captura en `POST /capture` (que,
  además, exige su token); o
- no trae `Origin` (la CLI, los tests, un script local: no es un navegador) y el navegador tampoco
  la marca como de otro sitio (`Sec-Fetch-Site`).

Los navegadores mandan siempre `Origin` en un POST de otro origen, también `null` desde un iframe
aislado o un fichero local, y eso no es la UI.
"""

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.agent_interface.errors import ToolError
from app.api.deps import is_ui_origin
from app.core.config import get_settings

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
CAPTURE_PATH = "/capture"
_OTHER_SITE = frozenset({"cross-site", "same-site"})


def is_allowed(request: Request) -> bool:
    """Si una petición que cambia algo puede llegar a la ruta."""
    origin = request.headers.get("origin")
    if origin is None:
        return request.headers.get("sec-fetch-site") not in _OTHER_SITE
    if is_ui_origin(request, origin):
        return True
    return request.url.path == CAPTURE_PATH and origin == get_settings().capture_origin


class CrossSiteGuard:
    """ASGI puro: solo mira la cabecera de la petición, no toca el cuerpo ni la respuesta."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] == "http"
            and scope["method"] in UNSAFE_METHODS
            and not is_allowed(Request(scope))
        ):
            error = ToolError("forbidden", "Solo la UI de CandidatAI puede cambiar datos.")
            await JSONResponse(status_code=403, content=error.payload())(scope, receive, send)
            return
        await self.app(scope, receive, send)
