"""Entorno de Alembic. La URL sale de `Settings` salvo que se pase otra explícitamente."""

from logging.config import fileConfig
from typing import Any, Literal

from alembic import context
from sqlalchemy import Connection

from app.core.config import get_settings
from app.core.db import make_engine
from app.models import Base
from app.models.base import UTCDateTime

config = context.config

# Solo configuramos logging al usarlo desde la línea de comandos; desde `cai db upgrade` o los
# tests no queremos pisar la configuración de logging de la app.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _url() -> str:
    url = config.get_main_option("sqlalchemy.url") or get_settings().db_url
    assert url is not None
    return url


def _render_item(type_: str, obj: Any, autogen_context: Any) -> str | Literal[False]:
    # Las migraciones no dependen del código de la app: `UTCDateTime` es un DATETIME en la BD.
    if type_ == "type" and isinstance(obj, UTCDateTime):
        return "sa.DateTime()"
    return False


def _configure(connection: Connection) -> None:
    # `render_as_batch`: SQLite no admite ALTER TABLE completo; Alembic recrea la tabla.
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        compare_type=True,
        render_item=_render_item,
    )


def run_migrations_offline() -> None:
    context.configure(
        url=_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        _configure(connection)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = make_engine(_url())
    with engine.connect() as conn:
        sqlite = conn.dialect.name == "sqlite"
        if sqlite:
            # Recrear una tabla en modo batch (DROP + RENAME) falla si otra la referencia con las
            # claves foráneas activas. Se desactivan durante la migración (fuera de transacción,
            # como exige SQLite) y al final se comprueba que no ha quedado ninguna rota.
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            conn.commit()
        _configure(conn)
        with context.begin_transaction():
            context.run_migrations()
            if sqlite:
                broken = conn.exec_driver_sql("PRAGMA foreign_key_check").all()
                if broken:
                    raise RuntimeError(f"La migración deja claves foráneas rotas: {broken[:5]}")
        if sqlite:
            conn.commit()
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
