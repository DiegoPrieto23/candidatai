"""La app ya no lee ni enseña los correos de las empresas, pero lo que una versión anterior dejó en
la base (filas, encargos, ejecuciones, tareas en cola) se conserva y no rompe nada."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect, select

from app.agent_interface.tools import TOOLS
from app.core import migrations
from app.core.config import REPO_ROOT
from app.core.db import get_engine, session_scope
from app.models import AgentPreference, AgentRequest, AgentRun, Reply
from app.models.base import utcnow
from app.services import agent_prefs, agent_requests, agent_runs, status, tracking, worker
from app.services.agent_actions import ACTIONS
from tests.applied_support import APPLIED, add_applied_job

RETIRED = "review-replies"


@pytest.fixture(autouse=True)
def _migrated() -> None:
    migrations.upgrade()


def _old_reply(job_id: int) -> Reply:
    return Reply(
        message_id="<r1@acme.example>",
        origin="local",
        sender="rrhh@acme.example",
        sender_name="Acme",
        subject="Entrevista",
        received_at=datetime(2026, 10, 5, 8, 0, tzinfo=UTC),
        body_text="¿Te va bien el jueves?",
        risk_flags=[],
        candidates=[{"job_id": job_id, "reason": "domain"}],
        status="new",
        created_at=utcnow(),
    )


def test_the_action_tools_and_skill_are_gone() -> None:
    assert RETIRED not in ACTIONS
    assert not {"list_replies", "get_reply", "save_reply_proposal"} & {t.name for t in TOOLS}
    assert not (REPO_ROOT / ".agents" / "skills" / RETIRED).exists()
    assert not (REPO_ROOT / ".agents" / "roles" / "classifier.md").exists()


def test_old_replies_stay_stored_and_no_longer_hold_back_a_followup() -> None:
    """Sin nadie que los clasifique, un correo «nuevo» taparía el recordatorio para siempre."""
    now = datetime(2026, 11, 1, 9, 0, tzinfo=UTC)
    assert now > APPLIED
    with session_scope() as session:
        job = add_applied_job(session, "Acme")
        session.add(_old_reply(job.id))
        session.flush()
        due = tracking.list_followups_due(session, days_without_reply=3, now=now)
        assert [item.job_id for item in due.followups] == [job.id]
    assert "replies" in inspect(get_engine()).get_table_names()
    with session_scope() as session:
        assert len(session.scalars(select(Reply)).all()) == 1


def test_a_request_of_the_retired_action_is_kept_but_not_listed_nor_counted() -> None:
    with session_scope() as session:
        old = AgentRequest(action=RETIRED, prompt="Usa el skill", status="pending")
        session.add(old)
        session.flush()
        old_id = old.id
        agent_requests.create(session, "search-jobs")
        listed = agent_requests.list_requests(session)
        assert [r.action for r in listed.requests] == ["search-jobs"]
        assert listed.pending == 1
        assert status.get_status(session).agent_requests == 1
        with pytest.raises(agent_requests.RequestNotFoundError):
            agent_requests.complete(session, old_id, "hecho")
        assert session.get(AgentRequest, old_id) is not None


def test_a_run_of_the_retired_action_is_kept_but_not_listed_nor_started() -> None:
    with session_scope() as session:
        old = AgentRun(
            action=RETIRED,
            agent="claude",
            status="queued",
            prompt="Usa el skill",
            command=[],
            output_format="text",
        )
        session.add(old)
        session.flush()
        old_id = old.id
        runs = agent_runs.list_runs(session)
        assert runs.runs == []
        assert runs.active == 0
        with pytest.raises(agent_runs.RunNotFoundError):
            agent_runs.get_run(session, old_id)
    from app.services import agent_runner

    assert agent_runner.claim_next() is None


def test_a_saved_preference_of_the_retired_action_is_ignored() -> None:
    with session_scope() as session:
        session.add(AgentPreference(scope="action", key=RETIRED, agent="claude"))
        session.flush()
        assert RETIRED not in agent_prefs.get_preferences(session).actions


def test_a_task_left_in_the_queue_ends_without_doing_anything() -> None:
    with session_scope() as session:
        assert worker.HANDLERS["poll_replies"](session, {}) == {}
