"""Dependencias comunes de las rutas."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core import migrations
from app.core.db import session_scope


def get_session() -> Iterator[Session]:
    """Sesión por petición: commit si la ruta termina bien, rollback si lanza."""
    migrations.ensure_current()
    with session_scope() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
