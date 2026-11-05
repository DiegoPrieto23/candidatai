"""El aviso de lo que lanzan los botones: la app sabe cómo va por lo que el agente guarda."""

from collections.abc import Iterator
from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import AgentRun, AgentTask, Application, Company, Job, McpCall, Source
from app.models.base import utcnow
from app.services import agent_launch, agent_tasks
from app.services.pipeline import Stage

UI = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


def call(session: Session, tool: str, ok: bool = True, job_id: int | None = None) -> None:
    session.add(McpCall(channel="mcp", tool=tool, ok=ok, job_id=job_id))
    session.flush()


def job(session: Session, stage: Stage = Stage.PENDING_EXTRACTION, title: str = "Analista") -> int:
    source = Source(kind="manual", name=f"src-{title}", active=True, config={})
    company = Company(name="Acme", normalized_name=f"acme-{title}")
    session.add_all([source, company])
    session.flush()
    row = Job(
        source_id=source.id,
        company_id=company.id,
        title=title,
        url=f"https://example.com/{title}",
        raw_text="texto",
        fingerprint=title,
    )
    session.add(row)
    session.flush()
    session.add(Application(job_id=row.id, stage=stage, last_event_at=utcnow()))
    session.flush()
    return row.id


def seen(session: Session) -> agent_tasks.AgentTaskView:
    tasks = agent_tasks.current(session).tasks
    assert len(tasks) == 1
    return tasks[0]


def test_a_single_result_finishes_it(session: Session) -> None:
    job_id = job(session)
    agent_tasks.start(session, "research-company", job_id)
    view = seen(session)
    assert (view.status, view.outcome, view.total) == ("running", None, 0)
    assert view.subject == "Analista · Acme"

    call(session, "get_extraction", job_id=job_id)  # leer no es terminar
    assert seen(session).status == "running"
    call(session, "save_company_research", ok=False, job_id=job_id)  # ni guardar mal
    assert seen(session).status == "running"

    call(session, "save_company_research", job_id=job_id)
    view = seen(session)
    assert (view.status, view.outcome) == ("finished", "done")
    assert view.finished_at is not None


def test_saving_another_job_does_not_finish_it(session: Session) -> None:
    job_id, other = job(session), job(session, title="Otra")
    agent_tasks.start(session, "research-company", job_id)
    call(session, "save_company_research", job_id=other)
    assert seen(session).status == "running"


def test_saving_before_the_button_does_not_count(session: Session) -> None:
    job_id = job(session)
    session.add(
        McpCall(
            channel="mcp",
            tool="save_company_research",
            ok=True,
            job_id=job_id,
            called_at=utcnow() - timedelta(hours=1),
        )
    )
    agent_tasks.start(session, "research-company", job_id)
    assert seen(session).status == "running"


def test_a_batch_counts_against_what_was_pending(session: Session) -> None:
    first, second = job(session, title="Uno"), job(session, title="Dos")
    agent_tasks.start(session, "process-jobs")
    view = seen(session)
    # Una sola tarea para leer y valorar: cada oferta cuenta dos guardados (lectura y valoración).
    assert (view.total, view.done, view.status) == (4, 0, "running")

    call(session, "save_extraction", job_id=first)
    view = seen(session)
    assert (view.done, view.status) == (1, "running")

    call(session, "save_extraction", job_id=second)
    call(session, "save_fit_assessment", job_id=first)
    view = seen(session)
    assert (view.done, view.status) == (3, "running")

    call(session, "save_fit_assessment", job_id=second)
    view = seen(session)
    assert (view.done, view.status, view.outcome) == (4, "finished", "done")


def test_process_jobs_waits_for_one_round_not_for_everything(session: Session) -> None:
    for index in range(agent_tasks.PROCESS_BATCH + 3):
        job(session, title=f"J{index}")
    agent_tasks.start(session, "process-jobs")
    # Lee y valora una tanda: el doble de lo que lee.
    assert seen(session).total == 2 * agent_tasks.PROCESS_BATCH


def test_the_agent_can_close_it_early(session: Session) -> None:
    job(session, Stage.PENDING_TRIAGE)
    agent_tasks.start(session, "assess-fit")
    result = agent_tasks.finish(session, "assess-fit", "done")
    assert result.closed is True
    assert (seen(session).status, seen(session).outcome) == ("finished", "done")


def test_finish_by_skill_reaches_the_single_job_variant(session: Session) -> None:
    agent_tasks.start(session, "assess-fit-job", job(session))
    assert agent_tasks.finish(session, "assess-fit", "stopped").closed is True
    assert seen(session).outcome == "stopped"


def test_finish_without_a_notice_is_not_an_error(session: Session) -> None:
    assert agent_tasks.finish(session, "process-jobs", "done").closed is False


def test_declining_a_correction_closes_it_as_stopped(session: Session) -> None:
    job_id = job(session, Stage.CV_READY)
    agent_tasks.start(session, "correct-cv", job_id)
    call(session, "decline_cv_correction", job_id=job_id)
    assert seen(session).outcome == "stopped"


def test_no_news_for_a_long_time_is_stale(session: Session) -> None:
    agent_tasks.start(session, "research-company", job(session))
    row = session.query(AgentTask).one()
    row.started_at = utcnow() - agent_tasks.STALE_AFTER - timedelta(minutes=1)
    session.flush()
    assert seen(session).status == "stale"


def test_recent_activity_keeps_it_running(session: Session) -> None:
    agent_tasks.start(session, "research-company", job(session))
    row = session.query(AgentTask).one()
    row.started_at = utcnow() - agent_tasks.STALE_AFTER - timedelta(minutes=1)
    session.add(McpCall(channel="mcp", tool="get_extraction", ok=True))
    # La llamada es de ahora: el agente sigue vivo aunque lleve mucho tiempo.
    session.flush()
    assert seen(session).status == "running"


@pytest.mark.parametrize(
    ("status", "outcome"),
    [("done", "done"), ("needs_user", "needs_user"), ("failed", "failed"), ("timeout", "failed")],
)
def test_background_follows_its_run(session: Session, status: str, outcome: str) -> None:
    job_id = job(session)
    run = AgentRun(
        action="generate-cv",
        job_id=job_id,
        agent="claude",
        status="running",
        prompt="x",
        command=[],
        unset_env=[],
        output_format="claude-stream-json",
        progress=[],
        questions=[],
        cancel_requested=False,
    )
    session.add(run)
    session.flush()
    agent_tasks.start(session, "generate-cv", job_id, run_id=run.id)
    view = seen(session)
    assert (view.background, view.status) == (True, "running")

    run.status = status
    session.flush()
    assert (seen(session).status, seen(session).outcome) == ("finished", outcome)


def test_a_queued_background_run_never_goes_stale(session: Session) -> None:
    job_id = job(session)
    run = AgentRun(
        action="generate-cv",
        job_id=job_id,
        agent="claude",
        status="queued",
        prompt="x",
        command=[],
        unset_env=[],
        output_format="claude-stream-json",
        progress=[],
        questions=[],
        cancel_requested=False,
    )
    session.add(run)
    session.flush()
    agent_tasks.start(session, "generate-cv", job_id, run_id=run.id)
    row = session.query(AgentTask).one()
    row.started_at = utcnow() - timedelta(hours=2)
    session.flush()
    assert seen(session).status == "running"


def test_launching_again_replaces_the_previous_notice(session: Session) -> None:
    job_id = job(session)
    agent_tasks.start(session, "research-company", job_id)
    second = agent_tasks.start(session, "research-company", job_id)
    assert second is not None
    assert seen(session).id == second.id


def test_conversations_are_not_followed(session: Session) -> None:
    assert agent_tasks.start(session, "mock-interview", job(session)) is None
    assert agent_tasks.current(session).tasks == []


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


def test_launching_from_a_button_starts_the_notice(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    with session_scope() as session:
        job(session)
    result = agent_launch.LaunchResult(agent="Claude Code", prompt="x", message="ok")
    monkeypatch.setattr(agent_launch, "pick", lambda *a, **k: SimpleNamespace(command=[]))
    monkeypatch.setattr(agent_launch, "_open", lambda *a, **k: result)
    monkeypatch.setattr(agent_launch, "check_target", lambda *a, **k: ("x", None, None))
    response = client.post("/agent/launch", json={"action": "process-jobs"}, headers=UI)
    assert response.status_code == 202, response.text

    tasks = client.get("/agent/tasks").json()["tasks"]
    assert [(t["action"], t["total"], t["status"]) for t in tasks] == [
        ("process-jobs", 2, "running")  # una lectura y una valoración
    ]


def test_closing_the_notice(client: TestClient) -> None:
    with session_scope() as session:
        task = agent_tasks.start(session, "research-company", job(session))
        assert task is not None
        task_id = task.id
    closed = client.post(f"/agent/tasks/{task_id}/dismiss", headers=UI)
    assert closed.status_code == 200, closed.text
    assert closed.json()["tasks"] == []
    assert client.post("/agent/tasks/99/dismiss", headers=UI).status_code == 404
