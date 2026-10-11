"""Dependencias comunes de las rutas."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.agent_interface.errors import ToolError
from app.core import migrations
from app.core.db import session_scope

# Origen de la UI local: el único que admite CORS y el único que puede abrir tu agente (ADR-024).
UI_ORIGIN = "http://127.0.0.1:5173"


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
    if origin is not None and origin != UI_ORIGIN:
        raise ToolError("forbidden", "Solo la UI de Job Hunter puede hacer esto.")
    content_type = request.headers.get("content-type", "")
    if not content_type.startswith("application/json"):
        raise ToolError("forbidden", "La petición tiene que ser JSON y venir de la UI.")
