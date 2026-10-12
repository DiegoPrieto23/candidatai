"""Vistas de la UI en los servicios (bandeja, ficha, eventos del usuario) y `cai serve`."""

import json
from collections.abc import Callable
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.models import Job, JobExtraction, Match, ProfileVersion
from app.services import events, jobs
from app.services.pipeline import Actor, EventType
from tests.agent_support import runner


def test_search_jobs_validates_paging(session: Session) -> None:
    with pytest.raises(jobs.InvalidQueryError):
        jobs.search_jobs(session, limit=0)
    with pytest.raises(jobs.InvalidQueryError):
        jobs.search_jobs(session, limit=jobs.MAX_LIMIT + 1)
    with pytest.raises(jobs.InvalidQueryError):
        jobs.search_jobs(session, offset=-1)
    with pytest.raises(jobs.InvalidQueryError):
        jobs.search_jobs(session, stage="limbo")


def test_search_jobs_blank_query_matches_all(
    session: Session, make_job: Callable[..., Job]
) -> None:
    make_job()
    make_job("Analista")
    assert jobs.search_jobs(session, q="   ").total == 2
    assert jobs.search_jobs(session, q="acme 2").total == 1  # por empresa


def test_search_jobs_without_events_has_no_stage(
    session: Session, make_job: Callable[..., Job]
) -> None:
    make_job()
    page = jobs.search_jobs(session)
    assert page.items[0].stage is None and page.items[0].remote_mode is None


def _extract(session: Session, job: Job, salary: dict[str, Any] | None) -> None:
    data = {"remote_mode": "hybrid", "salary": salary}
    session.add(JobExtraction(job_id=job.id, schema_version=1, data=data))
    session.flush()


def _score(session: Session, job: Job, score: int) -> None:
    profile = ProfileVersion(data={}, content_hash=f"h{job.id}")
    session.add(profile)
    session.flush()
    session.add(
        Match(
            job_id=job.id, profile_version_id=profile.id, hard_filters={}, score=score, breakdown={}
        )
    )
    session.flush()


def test_search_jobs_sorts_by_score_salary_and_date(
    session: Session, make_job: Callable[..., Job]
) -> None:
    yearly, monthly, hourly, unknown = (make_job(f"Oferta {i}") for i in range(4))
    _extract(session, yearly, {"min": 40000, "max": 50000, "currency": "EUR", "period": "year"})
    _extract(session, monthly, {"min": 4200, "max": None, "currency": "EUR", "period": "month"})
    _extract(session, hourly, {"min": 20, "max": 20, "currency": "EUR", "period": "hour"})
    _extract(session, unknown, {"min": 99999, "max": None, "currency": "EUR", "period": "year"})
    _extract(session, unknown, None)  # la extracción vigente es la última: sin salario
    _score(session, monthly, 80)
    _score(session, yearly, 60)

    def order(**kw: str) -> list[int]:
        return [row.id for row in jobs.search_jobs(session, **kw).items]

    # Anualizado: 4200 × 12 = 50 400; 45 000 (punto medio); 20 × 1760 = 35 200; sin dato, al final.
    assert order(sort="salary") == [monthly.id, yearly.id, hourly.id, unknown.id]
    assert order(sort="salary", direction="asc") == [hourly.id, yearly.id, monthly.id, unknown.id]
    assert order(sort="score") == [monthly.id, yearly.id, unknown.id, hourly.id]
    assert order(sort="score", direction="asc")[:2] == [yearly.id, monthly.id]
    assert order(sort="date", direction="asc") == [yearly.id, monthly.id, hourly.id, unknown.id]
    page = jobs.search_jobs(session, sort="salary")
    assert page.items[2].salary is not None and page.items[2].salary.period == "hour"
    assert page.items[3].salary is None
    with pytest.raises(jobs.InvalidQueryError):
        jobs.search_jobs(session, sort="title")  # type: ignore[arg-type]
    with pytest.raises(jobs.InvalidQueryError):
        jobs.search_jobs(session, direction="up")  # type: ignore[arg-type]


def test_get_job_view_not_found(session: Session) -> None:
    with pytest.raises(events.JobNotFoundError):
        jobs.get_job_view(session, 42)


def test_add_user_event_records_user_actor(session: Session, make_job: Callable[..., Job]) -> None:
    job = make_job()
    events.record(session, job.id, EventType.FOUND, Actor.SYSTEM)
    result = events.add_user_event(session, job.id, "note", note="Llamar el lunes")
    timeline = events.get_timeline(session, job.id)
    assert result.event_id == timeline.events[-1].id
    assert timeline.events[-1].actor == "user"


def test_add_user_event_rejects_reserved(session: Session, make_job: Callable[..., Job]) -> None:
    job = make_job()
    with pytest.raises(events.NotUserEventError):
        events.add_user_event(session, job.id, "extracted")
    with pytest.raises(events.UnknownEventTypeError):
        events.add_user_event(session, job.id, "magic")


def test_serve_runs_uvicorn_on_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    import uvicorn

    from app import cli

    assert runner.invoke(cli.app, ["db", "upgrade"]).exit_code == 0
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(uvicorn, "run", lambda app, **kw: calls.append({"app": app, **kw}))
    result = runner.invoke(cli.app, ["serve", "--port", "8123"])
    assert result.exit_code == 0, result.output
    assert calls == [
        {"app": "app.api.main:app", "host": "127.0.0.1", "port": 8123, "reload": False}
    ]


def test_serve_fails_without_migrations() -> None:
    from app import cli

    result = runner.invoke(cli.app, ["serve"])
    assert result.exit_code != 0


def test_openapi_command() -> None:
    from app import cli

    result = runner.invoke(cli.app, ["openapi"])
    assert result.exit_code == 0
    assert "/jobs/{job_id}/events" in json.loads(result.stdout)["paths"]
