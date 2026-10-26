"""La UI compilada servida por la propia API (fase 23.4): `cai start` deja la app entera en
`http://127.0.0.1:8000` sin Node ni un segundo servidor.

Solo si existe la UI construida (`Settings.ui_dir`, por defecto `frontend/dist`). Una navegación del
navegador (`Accept: text/html`) a una ruta de la UI recibe `index.html` y el enrutado lo hace el
cliente. Todo lo demás sigue siendo la API: `/jobs/7` es la ficha si la pide el navegador y el JSON
de la oferta si la pide la UI con `fetch`; y un PDF abierto en una pestaña (`/renders/…/pdf`) no es
una ruta de la UI, así que llega a la API aunque el navegador acepte HTML.
"""

import re
from collections.abc import Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import RequestResponseEndpoint

# Rutas de la UI (`frontend/src/App.tsx`). Un test comprueba que no falta ninguna.
UI_ROUTES = re.compile(
    r"^/(|bandeja|jobs/\d+|nueva|por-revisar|triaje|procesos|calendario|respuestas|embudo|skills|alertas"
    r"|plantillas|perfil|fuentes(/[a-z-]+)?|empresas|plataformas|agente)/?$"
)
# `index.html` no se guarda en caché: tras actualizar, la UI nueva carga a la primera.
_NO_CACHE = {"Cache-Control": "no-cache"}


def is_ui_navigation(request: Request) -> bool:
    return (
        request.method == "GET"
        and "text/html" in request.headers.get("accept", "")
        and UI_ROUTES.match(request.url.path) is not None
    )


def _file_endpoint(path: Path) -> Callable[[], FileResponse]:
    """Una ruta sin parámetros por fichero: la ruta del fichero no puede venir de la petición."""

    def endpoint() -> FileResponse:
        return FileResponse(path)

    return endpoint


def install_ui(app: FastAPI, ui_dir: Path) -> bool:
    """Sirve la UI de `ui_dir` si está construida. Devuelve si la ha montado."""
    index = ui_dir / "index.html"
    if not index.is_file():
        return False
    if (ui_dir / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=ui_dir / "assets"), name="ui-assets")

    # Ficheros sueltos de la raíz (favicon, iconos): solo los que hay, cada uno con su ruta.
    for path in sorted(ui_dir.iterdir()):
        if path.is_file() and path.name != "index.html":
            app.add_api_route(
                f"/{path.name}", _file_endpoint(path), methods=["GET"], include_in_schema=False
            )

    @app.middleware("http")
    async def spa(request: Request, call_next: RequestResponseEndpoint) -> Response:
        if is_ui_navigation(request):
            return FileResponse(index, headers=_NO_CACHE)
        return await call_next(request)

    return True
