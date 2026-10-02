"""Worker y alertas por correo: se encolan solo si hay de dónde leer, y caducan los resúmenes."""

import shutil
from pathlib import Path

import pytest
from sqlalchemy import select

from app.core import migrations
from app.core.db import session_scope
from app.models import Job, Task
from app.services import tasks, worker

FIXTURES = Path(__file__).parent / "fixtures" / "email"


@pytest.fixture
def db(isolated_env: Path) -> None:
    migrations.upgrade()


def test_poll_is_not_queued_without_mail(db: None, isolated_env: Path) -> None:
    (isolated_env / "inbox" / "samples").mkdir(parents=True)
    shutil.copy(FIXTURES / "linkedin_alert.eml", isolated_env / "inbox" / "samples" / "a.eml")
    with session_scope() as session:
        assert worker.enqueue_email_poll(session) is False
        assert session.scalars(select(Task)).all() == []


def test_worker_polls_local_inbox_and_logs_it(db: None, isolated_env: Path) -> None:
    (isolated_env / "inbox").mkdir()
    shutil.copy(FIXTURES / "linkedin_alert.eml", isolated_env / "inbox" / "a.eml")
    with session_scope() as session:
        assert worker.enqueue_email_poll(session) is True
    run = worker.run_pending()
    assert run.done == 1
    outcome = run.outcomes[0]
    assert outcome.kind == "poll_email"
    assert worker.describe(outcome) == (
        "Alertas por correo: 1 correo nuevo, 3 ofertas, 3 nuevas (3 como resumen)."
    )
    with session_scope() as session:
        assert len(session.scalars(select(Job)).all()) == 3
        assert worker.enqueue_email_poll(session) is True  # se vuelve a mirar en cada intervalo
    assert worker.run_pending().outcomes[0].result["created"] == 0


def test_expire_task(db: None) -> None:
    with session_scope() as session:
        tasks.enqueue(session, "expire_summaries")
    run = worker.run_pending()
    assert run.done == 1
    assert worker.describe(run.outcomes[0]) == "Ningún resumen caducado."
