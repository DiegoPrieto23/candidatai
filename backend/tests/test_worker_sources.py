"""Worker y fuentes: ingesta diaria, recuperación al arrancar, reintentos y log legible."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import select
from typer.testing import CliRunner

from app import cli
from app.core import migrations
from app.core.db import session_scope
from app.core.policies import ConnectorsPolicy, get_policies
from app.models import Source, SourceRun, Task
from app.schemas.sources import SourceInput
from app.services import profile, tasks, worker
from app.services.ingestion import service as sources
from tests.sources_support import GREENHOUSE_URL, mock_greenhouse

POLICY = ConnectorsPolicy(
    daily_at="07:30", timezone="Europe/Madrid", timeout_seconds=5, max_jobs_per_source=100
)


@pytest.fixture
def db(isolated_env: Path) -> None:
    migrations.upgrade()


def _add(name: str = "Acme Datos", slug: str = "acmedatos", kind: str = "greenhouse") -> int:
    with session_scope() as session:
        return sources.add_source(session, SourceInput(kind=kind, name=name, slug=slug)).id  # type: ignore[arg-type]


def _queued() -> list[tuple[str, dict[str, Any]]]:
    with session_scope() as session:
        rows = session.scalars(select(Task).where(Task.status == "queued").order_by(Task.id))
        return [(t.kind, dict(t.payload)) for t in rows]


# --- Hora programada -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        # Verano (UTC+2): 07:30 en Madrid son las 05:30 UTC.
        (datetime(2026, 7, 10, 6, 0, tzinfo=UTC), datetime(2026, 7, 10, 5, 30, tzinfo=UTC)),
        (datetime(2026, 7, 10, 5, 0, tzinfo=UTC), datetime(2026, 7, 9, 5, 30, tzinfo=UTC)),
        (datetime(2026, 7, 10, 5, 30, tzinfo=UTC), datetime(2026, 7, 10, 5, 30, tzinfo=UTC)),
        # Invierno (UTC+1).
        (datetime(2026, 12, 1, 12, 0, tzinfo=UTC), datetime(2026, 12, 1, 6, 30, tzinfo=UTC)),
        # El día del cambio de hora (25-10-2026), el día anterior era verano.
        (datetime(2026, 10, 25, 5, 0, tzinfo=UTC), datetime(2026, 10, 24, 5, 30, tzinfo=UTC)),
    ],
)
def test_last_scheduled(now: datetime, expected: datetime) -> None:
    assert worker.last_scheduled(now, POLICY) == expected


def test_policy_rejects_bad_time_and_zone() -> None:
    with pytest.raises(ValueError):
        ConnectorsPolicy(
            daily_at="7:30", timezone="Europe/Madrid", timeout_seconds=1, max_jobs_per_source=1
        )
    with pytest.raises(ValueError, match="Zona horaria"):
        ConnectorsPolicy(
            daily_at="07:30", timezone="Marte/Olympus", timeout_seconds=1, max_jobs_per_source=1
        )
    assert get_policies().connectors.daily_at == "07:30"


# --- Encolar las fuentes que tocan -----------------------------------------------------------


def test_enqueue_due_sources(db: None) -> None:
    never_run = _add()
    recent = _add("Beta", "beta")
    paused = _add("Gamma", "gamma")
    old = _add("Delta", "delta")
    now = datetime.now(UTC)
    due = worker.last_scheduled(now, get_policies().connectors)
    with session_scope() as session:
        session.get(Source, recent).last_run_at = due + timedelta(minutes=1)  # type: ignore[union-attr]
        session.get(Source, old).last_run_at = due - timedelta(minutes=1)  # type: ignore[union-attr]
        sources.set_active(session, paused, False)
        queued = worker.enqueue_due_sources(session, now)

    assert queued == [never_run, old]
    assert _queued() == [
        ("run_source", {"source_id": never_run}),
        ("run_source", {"source_id": old}),
    ]
    # Volver a encolar no duplica las que siguen en cola.
    with session_scope() as session:
        worker.enqueue_due_sources(session, now)
    assert len(_queued()) == 2


# --- Ejecución por la cola -------------------------------------------------------------------


@respx.mock
def test_run_source_task_logs_a_readable_line(db: None) -> None:
    with session_scope() as session:
        profile.import_profile(session, profile.EXAMPLE_PATH)
    source_id = _add()
    mock_greenhouse()
    with session_scope() as session:
        tasks.enqueue(session, "run_source", {"source_id": source_id})

    run = worker.run_pending()

    outcome = next(o for o in run.outcomes if o.kind == "run_source")
    assert outcome.ok
    assert worker.describe(outcome) == (
        "Greenhouse · Acme Datos: 5 ofertas encontradas, 3 tras filtros, 3 nuevas; 1 avisos"
    )
    assert _queued() == []


@respx.mock
def test_failing_source_is_recorded_and_retried(db: None) -> None:
    source_id = _add()
    respx.get(GREENHOUSE_URL).mock(return_value=httpx.Response(500))
    with session_scope() as session:
        task_id = tasks.enqueue(session, "run_source", {"source_id": source_id}).id

    run = worker.run_pending()

    outcome = run.outcomes[0]
    assert not outcome.ok and run.failed == 1
    assert "error HTTP 500" in (outcome.error or "")
    assert worker.describe(outcome).endswith("Se reintentará más tarde.")
    with session_scope() as session:
        task = session.get(Task, task_id)
        assert task is not None
        assert (task.status, task.attempts) == ("queued", 1)
        assert task.run_after > datetime.now(UTC)
        assert "HTTP 500" in (task.last_error or "")
        # La ejecución fallida queda registrada aunque la tarea se reintente.
        run_row = session.scalars(select(SourceRun)).one()
        assert run_row.errors[0]["code"] == "http_error"


@respx.mock
def test_one_failing_source_does_not_stop_the_rest(db: None) -> None:
    with session_scope() as session:
        profile.import_profile(session, profile.EXAMPLE_PATH)
    broken = _add("Rota", "rota")
    ok = _add()
    respx.get("https://boards-api.greenhouse.io/v1/boards/rota/jobs").mock(
        return_value=httpx.Response(404)
    )
    mock_greenhouse()
    with session_scope() as session:
        worker.enqueue_due_sources(session)
    run = worker.run_pending()
    by_source = {o.result["source_id"]: o for o in run.outcomes if o.kind == "run_source"}  # type: ignore[index]
    assert by_source[broken].ok  # 404 no se reintenta: queda en `errors` de la ejecución
    assert "Revisa el slug" in worker.describe(by_source[broken])
    assert by_source[ok].result["created"] == 3  # type: ignore[index]


# --- Scheduler -------------------------------------------------------------------------------


@respx.mock
def test_run_scheduler_catches_up_and_schedules_daily(
    db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    source_id = _add()
    mock_greenhouse()
    captured: dict[str, Any] = {}

    def fake_start(self: BlockingScheduler, *args: object, **kwargs: object) -> None:
        captured["jobs"] = {job.id: job.trigger for job in self.get_jobs()}
        raise KeyboardInterrupt

    monkeypatch.setattr(BlockingScheduler, "start", fake_start)
    messages: list[str] = []
    runs: list[Any] = []
    with pytest.raises(KeyboardInterrupt):
        worker.run_scheduler(30, runs.append, messages.append)

    assert "hour='7'" in str(captured["jobs"]["daily_sources"])
    assert "minute='30'" in str(captured["jobs"]["daily_sources"])
    assert "0:00:30" in str(captured["jobs"]["tasks"])
    assert "0:00:30" in str(captured["jobs"]["agent_runs"])  # fase 19, en su propio hilo
    assert messages[0] == "Fuentes pendientes desde la última ingesta: 1 en cola."
    assert messages[-1] == "Próxima ingesta diaria: 07:30 (Europe/Madrid)."
    assert runs[0].outcomes[0].result["source_id"] == source_id


def test_cli_worker_logs_and_stops(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_scheduler(interval: float, on_run: Any, on_message: Any) -> None:
        on_message("Próxima ingesta diaria: 07:30 (Europe/Madrid).")
        raise KeyboardInterrupt

    monkeypatch.setattr(worker, "run_scheduler", fake_scheduler)
    result = CliRunner().invoke(cli.app, ["worker", "--interval", "2"])
    assert result.exit_code == 0, result.output
    log = (get_settings_logs() / "worker.log").read_text(encoding="utf-8")
    assert "Worker en marcha (cola cada 2 s)" in log
    assert "Próxima ingesta diaria" in log
    assert "Worker parado." in log


def get_settings_logs() -> Path:
    from app.core.config import get_settings

    return get_settings().logs_dir


def test_portals_without_keys_are_not_enqueued(db: None) -> None:
    with session_scope() as session:
        sources.add_source(session, SourceInput(kind="adzuna", name="Adzuna", query="data"))
        assert worker.enqueue_due_sources(session) == []


def test_orphan_running_tasks_go_back_to_the_queue(db: None) -> None:
    with session_scope() as session:
        task = tasks.enqueue(session, "rescore_all")
        task.status = "running"
    with session_scope() as session:
        assert tasks.requeue_running(session) == 1
    assert _queued() == [("rescore_all", {})]
