"""La migración crea exactamente el esquema de los modelos y se deshace limpia."""

import json
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
    assert (isolated_env / "candidatai.db").exists()
    migrations.ensure_current()


def test_ensure_current_on_missing_db_creates_nothing(db_url: str, isolated_env: Path) -> None:
    with pytest.raises(migrations.DatabaseNotReadyError, match="cai db upgrade"):
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


def test_0015_backfills_one_sighting_per_job_with_identity(db_url: str) -> None:
    migrations.upgrade(db_url, "0014")
    engine = create_engine(db_url)
    insert = (
        "INSERT INTO jobs (id, source_id, company_id, external_id, platform, url, title, "
        "raw_text, risk_flags, fingerprint, first_seen_at) VALUES ({id}, 1, 1, {ext}, {plat}, "
        "'{url}', 'T', 'x', '[]', 'f{id}', '2026-09-01 09:00:00')"
    )
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
            url = "https://www.infojobs.net/madrid/data/of-i0123456789abcdef0123456789abcd"
            conn.exec_driver_sql(
                insert.format(
                    id=1, ext="'0123456789abcdef0123456789abcd'", plat="'infojobs'", url=url
                )
            )
            conn.exec_driver_sql(
                insert.format(id=2, ext="NULL", plat="NULL", url="https://acme.com/jobs/9?utm=x")
            )
            conn.exec_driver_sql(insert.format(id=3, ext="NULL", plat="NULL", url=""))
        engine.dispose()

        migrations.upgrade(db_url, "0015")
        with engine.begin() as conn:
            rows = conn.exec_driver_sql(
                "SELECT job_id, channel, ref, seen_at FROM job_sightings ORDER BY job_id"
            ).all()
            assert [tuple(r[:3]) for r in rows] == [
                (1, "infojobs", "0123456789abcdef0123456789abcd"),
                (2, "acme.com", "acme.com/jobs/9"),
            ]
            assert str(rows[0][3]).startswith("2026-09-01 09:00:00")
            assert conn.exec_driver_sql("SELECT signals FROM jobs WHERE id = 3").scalar() == "{}"
        migrations.downgrade(db_url, "0014")
    finally:
        engine.dispose()


def test_0021_translates_skill_names_in_queued_work_and_back(db_url: str) -> None:
    """Fase 23.2: un encargo o una ejecución guardados con los nombres en español siguen
    funcionando con los skills renombrados; el `downgrade` los devuelve."""
    migrations.upgrade(db_url, "0020")
    engine = create_engine(db_url)
    now = "2026-10-12 09:00:00"
    prompt = (
        "Usa el skill procesar-ofertas y delega en el rol `redactor`; no toques data-revisor "
        "ni data/documentos/plan-formacion.md."
    )
    command = '["claude", "-p", "x", "--allowedTools", "Skill(generar-cv),Agent(verificador)"]'
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(
                "INSERT INTO agent_requests (id, action, prompt, status, created_at) "
                f"VALUES (1, 'procesar-ofertas', '{prompt}', 'pending', '{now}'), "
                f"(2, 'dudas-oferta', 'x', 'pending', '{now}')"
            )
            conn.exec_driver_sql(
                "INSERT INTO agent_runs (id, action, agent, status, prompt, command, unset_env, "
                "output_format, progress, questions, cancel_requested, created_at) VALUES "
                f"(1, 'generar-cv', 'claude-code', 'queued', '{prompt}', '{command}', '[]', "
                f"'stream-json', '[]', '[]', 0, '{now}')"
            )
        engine.dispose()

        migrations.upgrade(db_url, "0021")
        with engine.begin() as conn:
            req, other = conn.exec_driver_sql(
                "SELECT action, prompt FROM agent_requests ORDER BY id"
            ).all()
            run = conn.exec_driver_sql("SELECT action, prompt, command FROM agent_runs").one()
        assert req[0] == "process-jobs" and run[0] == "generate-cv"
        assert other[0] == "offer-questions"
        assert req[1] == (
            "Usa el skill process-jobs y delega en el rol `writer`; no toques data-revisor "
            "ni data/documentos/plan-formacion.md."
        )
        assert "Skill(generate-cv)" in run[2] and "Agent(verifier)" in run[2]
        engine.dispose()

        migrations.downgrade(db_url, "0020")
        with engine.begin() as conn:
            req, other = conn.exec_driver_sql(
                "SELECT action, prompt FROM agent_requests ORDER BY id"
            ).all()
            run = conn.exec_driver_sql("SELECT command FROM agent_runs").one()
        assert tuple(req) == ("procesar-ofertas", prompt) and other[0] == "dudas-oferta"
        assert "Skill(generar-cv)" in run[0] and "Agent(verificador)" in run[0]
    finally:
        engine.dispose()


def test_0026_numbers_platform_priorities_without_ties(db_url: str) -> None:
    """Fase 27.3: las plataformas con prioridades repetidas (todas entraban con 5) quedan
    numeradas 1…N por `(prioridad, nombre)`; otras fuentes no se tocan y repetir no cambia nada."""
    migrations.upgrade(db_url, "0025")
    engine = create_engine(db_url)
    rows = [
        (1, "agent_browse", "Tecnoempleo", '{"priority": 5, "platform": "tecnoempleo"}'),
        (2, "agent_browse", "indeed", '{"priority": 5, "platform": "indeed"}'),
        (3, "agent_browse", "LinkedIn", '{"priority": 2, "platform": "linkedin"}'),
        (4, "agent_browse", "Sin prioridad", '{"platform": "otra"}'),
        (5, "greenhouse", "Acme", '{"slug": "acme"}'),
    ] + [
        (10 + i, "agent_browse", f"Portal {i:02d}", '{"priority": 9, "platform": "p"}')
        for i in range(9)
    ]
    try:
        with engine.begin() as conn:
            for row in rows:
                conn.exec_driver_sql(
                    "INSERT INTO sources (id, kind, name, config, active) VALUES (?, ?, ?, ?, 1)",
                    row,
                )
        engine.dispose()

        def priorities() -> dict[str, object]:
            with engine.begin() as conn:
                found = conn.exec_driver_sql("SELECT name, config FROM sources").all()
            return {name: json.loads(config).get("priority") for name, config in found}

        migrations.upgrade(db_url, "0026")
        after = priorities()
        expected = ["LinkedIn", "indeed", "Tecnoempleo"] + [f"Portal {i:02d}" for i in range(9)]
        assert [after[name] for name in [*expected, "Sin prioridad"]] == list(range(1, 14))
        assert after["Acme"] is None

        migrations.downgrade(db_url, "0025")
        migrations.upgrade(db_url, "0026")
        assert priorities() == after  # idempotente
        migrations.downgrade(db_url, "0025")
        assert max(p for p in priorities().values() if isinstance(p, int)) == 10
    finally:
        engine.dispose()
