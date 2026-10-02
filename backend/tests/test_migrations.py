"""La migración crea exactamente el esquema de los modelos y se deshace limpia."""

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError

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


def test_0005_moves_document_files_to_a_render_and_back(db_url: str) -> None:
    migrations.upgrade(db_url, "0004")
    engine = create_engine(db_url)
    now = "2026-09-01 09:00:00"
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO sources (id, kind, name, config, active) "
                "VALUES (1, 'manual_text', 'x', '{}', 1)"
            )
            conn.exec_driver_sql(
                "INSERT INTO companies (id, name, normalized_name, watchlist) "
                "VALUES (1, 'Acme', 'acme', 0)"
            )
            conn.exec_driver_sql(
                "INSERT INTO jobs (id, source_id, company_id, url, title, raw_text, risk_flags, "
                f"fingerprint, first_seen_at) VALUES (1, 1, 1, '', 'T', 'x', '[]', 'f', '{now}')"
            )
            conn.exec_driver_sql(
                "INSERT INTO profile_versions (id, data, content_hash, created_at) "
                f"VALUES (1, '{{}}', 'h', '{now}')"
            )
            conn.exec_driver_sql(
                "INSERT INTO documents (id, job_id, profile_version_id, kind, language, content, "
                "docx_path, pdf_path, pages, created_at) VALUES "
                f"(1, 1, 1, 'cv', 'es', '{{}}', 'cvs/1.docx', 'cvs/1.pdf', 1, '{now}'), "
                f"(2, 1, 1, 'cv', 'es', '{{}}', NULL, NULL, NULL, '{now}')"
            )
            conn.exec_driver_sql(
                "INSERT INTO applications (job_id, stage, document_id, last_event_at) "
                f"VALUES (1, 'applied', 1, '{now}')"
            )
        engine.dispose()

        migrations.upgrade(db_url, "0005")
        with engine.connect() as conn:
            renders = conn.exec_driver_sql(
                "SELECT id, document_id, template_id, docx_path, pdf_path, pages, selected "
                "FROM document_renders"
            ).all()
            assert [tuple(r) for r in renders] == [
                (1, 1, "legacy", "cvs/1.docx", "cvs/1.pdf", 1, 1)
            ]
            assert conn.exec_driver_sql("SELECT render_id FROM applications").scalar() == 1
        engine.dispose()

        migrations.downgrade(db_url, "0004")
        with engine.connect() as conn:
            docs = conn.exec_driver_sql(
                "SELECT id, docx_path, pdf_path, pages FROM documents ORDER BY id"
            ).all()
            assert [tuple(d) for d in docs] == [
                (1, "cvs/1.docx", "cvs/1.pdf", 1),
                (2, None, None, None),
            ]
            assert conn.exec_driver_sql("SELECT document_id FROM applications").scalar() == 1
    finally:
        engine.dispose()


def test_0007_keeps_jobs_full_and_platform_id_is_unique(db_url: str) -> None:
    migrations.upgrade(db_url, "0006")
    engine = create_engine(db_url)
    now = "2026-09-01 09:00:00"
    insert = (
        "INSERT INTO jobs (id, source_id, company_id, external_id, url, title, raw_text, "
        "risk_flags, fingerprint, first_seen_at) VALUES ({id}, 1, 1, '42', '', 'T', 'x', '[]', "
        "'f{id}', '{now}')"
    )
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO sources (id, kind, name, config, active) "
                "VALUES (1, 'greenhouse', 'x', '{}', 1)"
            )
            conn.exec_driver_sql(
                "INSERT INTO companies (id, name, normalized_name, watchlist) "
                "VALUES (1, 'Acme', 'acme', 0)"
            )
            conn.exec_driver_sql(insert.format(id=1, now=now))
        engine.dispose()

        migrations.upgrade(db_url, "0007")
        with engine.begin() as conn:
            row = conn.exec_driver_sql("SELECT platform, detail_level FROM jobs").one()
            assert tuple(row) == (None, "full")
            # Sin plataforma, el mismo id externo puede repetirse (fuentes distintas).
            conn.exec_driver_sql(insert.format(id=2, now=now))
            conn.exec_driver_sql("UPDATE jobs SET platform = 'linkedin' WHERE id = 1")
        with pytest.raises(IntegrityError), engine.begin() as conn:
            conn.exec_driver_sql("UPDATE jobs SET platform = 'linkedin' WHERE id = 2")
    finally:
        engine.dispose()
