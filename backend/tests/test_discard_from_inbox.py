"""Fase 27.6: descartar desde la Bandeja (`not_interested`) y la fecha de cierre (`closed_at`)."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from app import cli
from app.core.db import session_scope
from app.models import Job
from app.models import JobExtraction as JobExtractionRow
from app.services import analytics, events, jobs
from app.services.pipeline import Actor, EventType
from tests.agent_support import POSTING_TEXT, extraction, mcp_call

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def _found(session: Session, job: Job, summary: bool = False) -> None:
    payload = {"detail_level": "summary"} if summary else None
    events.record(session, job.id, EventType.FOUND, Actor.SYSTEM, payload=payload, occurred_at=T0)


@pytest.mark.parametrize("summary", [True, False], ids=["pending_detail", "pending_extraction"])
def test_not_interested_discards_before_extraction(
    session: Session, make_job: Callable[..., Job], summary: bool
) -> None:
    job = make_job()
    _found(session, job, summary)
    result = events.add_user_event(session, job.id, "discarded", reason="not_interested")
    assert result.stage == "closed"
    assert events.job_events(session, job.id)[-1].payload == {"reason": "not_interested"}


def test_search_jobs_sorts_by_closed_at_with_open_jobs_last(
    session: Session, make_job: Callable[..., Job]
) -> None:
    early, late, still_open = (make_job(f"Oferta {i}") for i in range(3))
    for job in (early, late, still_open):
        _found(session, job)
    at = T0 + timedelta(days=1)
    events.add_user_event(session, early.id, "discarded", reason="skills", occurred_at=at)
    events.add_user_event(
        session, late.id, "discarded", reason="not_interested", occurred_at=at + timedelta(days=1)
    )
    # Una nota posterior mueve `last_event_at`, no la fecha de cierre.
    events.add_user_event(
        session, early.id, "note", note="Ya no", occurred_at=at + timedelta(days=5)
    )

    def order(**kw: str) -> list[int]:
        return [row.id for row in jobs.search_jobs(session, sort="closed", **kw).items]

    assert order(stage="closed") == [late.id, early.id]
    assert order(stage="closed", direction="asc") == [early.id, late.id]
    assert order() == [late.id, early.id, still_open.id]  # sin fecha, al final
    assert order(direction="asc")[-1] == still_open.id
    rows = {r.id: r for r in jobs.search_jobs(session).items}
    assert (rows[early.id].closed_at, rows[early.id].closed_by) == (at, "discarded")
    assert (rows[still_open.id].closed_at, rows[still_open.id].closed_by) == (None, None)


def test_not_interested_counts_in_funnel_but_not_in_calibration(
    session: Session, make_job: Callable[..., Job]
) -> None:
    job = make_job()
    _found(session, job, summary=True)
    events.add_user_event(session, job.id, "discarded", reason="not_interested")
    funnel = analytics.get_funnel_stats(session)
    assert [(r.reason, r.count) for r in funnel.discard_reasons] == [("not_interested", 1)]
    assert analytics.get_calibration(session).total.applied == 0


def test_batch_skips_a_job_discarded_while_extracting() -> None:
    """Un lote de `process-jobs` guarda cada oferta por separado: la que se descartó desde la
    Bandeja mientras tanto falla sola, con una pista para saltarla, sin dejar extracción a medias;
    las demás se guardan."""
    runner = CliRunner()
    assert runner.invoke(cli.app, ["db", "upgrade"]).exit_code == 0
    ids = []
    for title in ("Data Engineer", "Analytics Engineer"):
        _, added = mcp_call(
            "add_job_from_text", {"title": title, "company": "Acme", "text": POSTING_TEXT}
        )
        ids.append(added["job_id"])
    discarded, kept = ids
    with session_scope() as session:
        events.add_user_event(session, discarded, "discarded", reason="not_interested")

    results = [
        mcp_call("save_extraction", {"job_id": job_id, "extraction": extraction()})
        for job_id in ids
    ]
    (failed, error), (ok, saved) = results
    assert failed and error["error"]["type"] == "invalid_transition"
    assert "sáltala" in error["error"]["message"]
    assert not ok and saved["stage"] == "pending_triage"
    with session_scope() as session:
        count = select(func.count()).where(JobExtractionRow.job_id == discarded)
        assert session.scalar(count) == 0
        assert events.current_stage(session, discarded) == "closed"
        assert saved["job_id"] == kept
