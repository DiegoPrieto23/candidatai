"""Comandos `jh db upgrade`, `jh status` y `jh events list`."""

import json
from datetime import UTC, datetime

from typer.testing import CliRunner

from app import cli
from app.core.db import session_scope
from app.models import Company, Job, Source
from app.services.events import record

runner = CliRunner()


def _seed_job() -> int:
    with session_scope() as session:
        source = Source(kind="manual_text", name="Manual")
        company = Company(name="Acme", normalized_name="acme")
        session.add_all([source, company])
        session.flush()
        job = Job(
            source_id=source.id,
            company_id=company.id,
            url="https://example.com/1",
            title="Data Engineer",
            raw_text="Texto que nunca debe salir en la cronología.",
            fingerprint="fp-1",
        )
        session.add(job)
        session.flush()
        record(session, job.id, "found", "system", occurred_at=datetime(2026, 9, 1, tzinfo=UTC))
        record(session, job.id, "extracted", "agent", {"schema_version": 1}, agent_name="codex")
        return job.id


def test_commands_require_migrated_db() -> None:
    result = runner.invoke(cli.app, ["status", "--json"])
    assert result.exit_code == 1
    error = json.loads(result.stdout)["error"]
    assert error["type"] == "database_not_ready"
    assert "jh db upgrade" in error["message"]

    result = runner.invoke(cli.app, ["status"])
    assert result.exit_code == 1
    assert "jh db upgrade" in result.stderr


def test_db_upgrade() -> None:
    result = runner.invoke(cli.app, ["db", "upgrade", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"ok": True, "from": None, "to": "0017"}

    result = runner.invoke(cli.app, ["db", "upgrade"])
    assert result.exit_code == 0
    assert "ya estaba al día" in result.stdout


def test_db_upgrade_text() -> None:
    result = runner.invoke(cli.app, ["db", "upgrade"])
    assert result.exit_code == 0
    assert "vacía -> 0017" in result.stdout


def test_status() -> None:
    runner.invoke(cli.app, ["db", "upgrade"])
    _seed_job()

    result = runner.invoke(cli.app, ["status", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["total"] == 1
    assert data["by_stage"]["pending_triage"] == 1
    assert data["by_stage"]["closed"] == 0

    result = runner.invoke(cli.app, ["status"])
    assert result.exit_code == 0
    assert "pending_triage" in result.stdout
    assert "total" in result.stdout


def test_events_list() -> None:
    runner.invoke(cli.app, ["db", "upgrade"])
    job_id = _seed_job()

    result = runner.invoke(cli.app, ["events", "list", str(job_id), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["job_id"] == job_id
    assert data["stage"] == "pending_triage"
    assert [e["type"] for e in data["events"]] == ["found", "extracted"]
    assert data["events"][0]["occurred_at"] == "2026-09-01T00:00:00Z"
    assert "nunca debe salir" not in result.stdout

    result = runner.invoke(cli.app, ["events", "list", str(job_id)])
    assert result.exit_code == 0
    assert "etapa: pending_triage" in result.stdout
    assert "agent/codex" in result.stdout


def test_events_list_unknown_job() -> None:
    runner.invoke(cli.app, ["db", "upgrade"])
    result = runner.invoke(cli.app, ["events", "list", "999", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout) == {
        "ok": False,
        "error": {"type": "not_found", "message": "No existe la oferta 999.", "details": []},
    }
