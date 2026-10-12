"""Migraciones de Alembic invocables desde código (`cai db upgrade`, tests).

Alembic se importa dentro de cada función: cargarlo cuesta ~0,3 s y este módulo lo importan el
servidor MCP y la CLI al arrancar, aunque la comprobación solo se hace al llamar a una herramienta.
"""

from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import create_engine, make_url

from app.core.config import get_settings

if TYPE_CHECKING:
    from alembic.config import Config

# backend/app/core/migrations.py -> parents[2] es backend/
ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def alembic_config(url: str | None = None) -> "Config":
    from alembic.config import Config

    config = Config(ALEMBIC_INI)
    # `configparser` interpreta `%`: hay que escaparlo (p. ej. rutas con `%20`).
    db_url = url or get_settings().db_url or ""
    config.set_main_option("sqlalchemy.url", db_url.replace("%", "%%"))
    # Desde la app no queremos que Alembic reconfigure el logging global.
    config.attributes["configure_logger"] = False
    return config


def upgrade(url: str | None = None, revision: str = "head") -> None:
    from alembic import command

    command.upgrade(alembic_config(url), revision)


def downgrade(url: str | None = None, revision: str = "base") -> None:
    from alembic import command

    command.downgrade(alembic_config(url), revision)


def current_revision(url: str | None = None) -> str | None:
    from alembic.runtime.migration import MigrationContext

    db_url = make_url(url or get_settings().db_url or "")
    # Conectar a un SQLite inexistente crearía un fichero vacío solo por comprobar la versión.
    database = db_url.database
    is_sqlite_file = db_url.get_backend_name() == "sqlite" and database not in ("", ":memory:")
    if is_sqlite_file and database and not Path(database).exists():
        return None
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            return MigrationContext.configure(conn).get_current_revision()
    finally:
        engine.dispose()


@cache  # las migraciones no cambian con el proceso en marcha; leerlas cuesta en cada llamada
def head_revision() -> str | None:
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(alembic_config()).get_current_head()


class DatabaseNotReadyError(RuntimeError):
    pass


def ensure_current(url: str | None = None) -> None:
    """Falla con un mensaje claro si la BD no existe o le faltan migraciones."""
    current, head = current_revision(url), head_revision()
    if current != head:
        raise DatabaseNotReadyError(
            f"La base de datos no está al día (versión {current or 'vacía'}, última {head}). "
            "Ejecuta `cai db upgrade`."
        )
