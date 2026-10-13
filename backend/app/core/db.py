"""Conexión a la base de datos: engine SQLite (WAL + claves foráneas) y sesión por contexto."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.policies import get_policies


def iso_week(value: str | None) -> str | None:
    """Semana ISO (`2026-W39`) de una fecha UTC guardada por `UTCDateTime`, en la zona de la UI.

    SQLite no sabe de zonas horarias con cambio de hora: la analítica (fase 10.2) agrupa por
    semana en la BD con esta función, registrada como `cai_iso_week` en cada conexión.
    """
    if value is None:
        return None
    moment = datetime.fromisoformat(value).replace(tzinfo=UTC)
    # `ZoneInfo` guarda en caché cada zona: no se vuelve a leer en cada fila.
    year, week, _ = moment.astimezone(ZoneInfo(get_policies().calendar.timezone)).isocalendar()
    return f"{year}-W{week:02d}"


def _set_sqlite_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
    dbapi_connection.create_function("cai_iso_week", 1, iso_week, deterministic=True)


def make_engine(url: str) -> Engine:
    """Crea un engine; en SQLite activa WAL y `foreign_keys` en cada conexión."""
    engine = create_engine(url)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _set_sqlite_pragmas)
    return engine


@lru_cache
def get_engine() -> Engine:
    url = get_settings().db_url
    assert url is not None  # Settings siempre la rellena
    return make_engine(url)


def get_sessionmaker(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=engine or get_engine(), expire_on_commit=False)


@contextmanager
def session_scope(engine: Engine | None = None) -> Iterator[Session]:
    """Sesión que hace commit al salir sin errores y rollback si hay una excepción."""
    session = get_sessionmaker(engine)()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
