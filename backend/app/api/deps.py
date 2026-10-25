"""Dependencias comunes de las rutas."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.agent_interface.errors import ToolError
from app.core import migrations
from app.core.db import session_scope

# Origen de la UI en desarrollo (`pnpm dev`): el único que admite CORS. Desde la fase 23.4
# la API sirve también la UI compilada en su propio origen (`cai start`): ver `is_ui_origin`.
UI_ORIGIN = "http://127.0.0.1:5173"
_LOCAL_HOSTS = ("127.0.0.1", "localhost")


def is_ui_origin(request: Request, origin: str) -> bool:
    """La UI de desarrollo, o la UI compilada servida por esta misma API. El mismo origen solo vale
    con `127.0.0.1` o `localhost`: comparar con la cabecera `Host` sin más dejaría pasar a una web
    que apunte su dominio a 127.0.0.1 (DNS rebinding)."""
    if origin == UI_ORIGIN:
        return True
    port = request.url.port
    return any(origin == f"http://{host}:{port}" for host in _LOCAL_HOSTS) and (
        request.url.hostname in _LOCAL_HOSTS
    )


def get_session() -> Iterator[Session]:
    """Sesión por petición: commit si la ruta termina bien, rollback si lanza."""
    migrations.ensure_current()
    with session_scope() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def require_ui(request: Request) -> None:
    """Solo la UI: mismo origen que permite CORS y cuerpo JSON.

    Para las acciones que no puede pedir otra web abierta en el navegador (lanzar el agente, abrir
    carpetas, aceptar respuestas…): desde otro origen, un cuerpo JSON obliga a una comprobación
    previa CORS que esta API no concede.
    """
    origin = request.headers.get("origin")
    if origin is not None and not is_ui_origin(request, origin):
        raise ToolError("forbidden", "Solo la UI de CandidatAI puede hacer esto.")
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("application/json"):
        raise ToolError("forbidden", "La petición tiene que ser JSON y venir de la UI.")


def require_ui_read(request: Request) -> None:
    """Lecturas solo para la UI (fase 25.7: el perfil con tu email y teléfono).

    Un GET no lleva cuerpo, así que no vale `require_ui`. Basta con que no venga de otra web: el
    navegador manda `Origin` o `Sec-Fetch-Site: cross-site` en una petición de otro origen, y una
    web que apunte su dominio a 127.0.0.1 (DNS rebinding) llega con otro `Host`.
    """
    if request.url.hostname not in _LOCAL_HOSTS:
        raise ToolError("forbidden", "Solo la UI de CandidatAI puede leer esto.")
    origin = request.headers.get("origin")
    if origin is not None and not is_ui_origin(request, origin):
        raise ToolError("forbidden", "Solo la UI de CandidatAI puede leer esto.")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise ToolError("forbidden", "Solo la UI de CandidatAI puede leer esto.")


class EmptyBody(BaseModel):
    """Cuerpo `{}` de las acciones de la UI sin datos: JSON, para que `require_ui` lo compruebe."""

    model_config = ConfigDict(extra="forbid")
