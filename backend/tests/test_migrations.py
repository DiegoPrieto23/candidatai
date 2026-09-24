"""La migración crea exactamente el esquema de los modelos y se deshace limpia."""

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.core import migrations
from app.models import Base


@pytest.fixture
def db_url(isolated_env: Path) -> str:
    isolated_env.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(isolated_env / 'migrated.db').as_posix()}"


def _tables(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_creates_all_tables_and_downgrade_empties(db_url: str) -> None:
    migrations.upgrade(db_url)
    assert _tables(db_url) == set(Base.metadata.tables) | {"alembic_version"}
    assert migrations.current_revision(db_url) == migrations.head_revision()

    migrations.downgrade(db_url)
    assert _tables(db_url) == {"alembic_version"}
    assert migrations.current_revision(db_url) is None


def test_migrations_match_models(db_url: str) -> None:
    migrations.upgrade(db_url)
    engine = create_engine(db_url)
    try:
        with engine.connect() as conn:
            context = MigrationContext.configure(conn, opts={"compare_type": True})
            assert compare_metadata(context, Base.metadata) == []
    finally:
        engine.dispose()


def test_default_url_comes_from_settings(isolated_env: Path) -> None:
    migrations.upgrade()
    assert (isolated_env / "jobhunter.db").exists()
    migrations.ensure_current()


def test_ensure_current_on_missing_db_creates_nothing(db_url: str, isolated_env: Path) -> None:
    with pytest.raises(migrations.DatabaseNotReadyError, match="jh db upgrade"):
        migrations.ensure_current(db_url)
    assert not (isolated_env / "migrated.db").exists()


def test_url_with_percent_is_escaped(isolated_env: Path) -> None:
    folder = isolated_env / "con%20espacio"
    folder.mkdir(parents=True)
    url = f"sqlite:///{(folder / 'x.db').as_posix()}"
    assert migrations.alembic_config(url).get_main_option("sqlalchemy.url") == url
