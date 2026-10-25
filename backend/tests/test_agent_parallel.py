"""Lote en paralelo (fase 25.4): hasta N ejecuciones a la vez, nunca dos de la misma oferta
ni dos lotes de la misma acción, con tope por agente y reintentos si SQLite está bloqueado."""

import threading
import time

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.core.db import session_scope
from app.models import AgentRun
from app.services import agent_runner, agent_runs, ingest
from tests.test_agent_runs import db, fake, run_row, start  # noqa: F401 - fixtures

TEXT = "Buscamos Data Engineer con Python y SQL para el equipo de datos. " * 10


def _job(n: int) -> int:
    with session_scope() as session:
        return ingest.add_from_text(
            session, f"Data Engineer {n}", f"Empresa {n}", TEXT, url=f"https://acme{n}.example/j"
        ).job_id


def _clone(template: int, action: str, job_id: int | None, agent: str | None = None) -> int:
    """Otra ejecución en cola con el mismo comando (el del agente falso)."""
    with session_scope() as session:
        base = session.get(AgentRun, template)
        assert base is not None
        row = AgentRun(
            action=action,
            job_id=job_id,
            agent=agent or base.agent,
            status="queued",
            prompt=base.prompt,
            command=list(base.command),
            unset_env=list(base.unset_env),
            output_format=base.output_format,
            progress=[],
            questions=[],
            cancel_requested=False,
        )
        session.add(row)
        session.flush()
        return row.id


def _set(run_id: int, status: str) -> None:
    with session_scope() as session:
        row = session.get(AgentRun, run_id)
        assert row is not None
        row.status = status


def _cancel_queued() -> None:
    with session_scope() as session:
        for row in session.scalars(select(AgentRun).where(AgentRun.status == "queued")):
            row.status = "cancelled"


@pytest.mark.usefixtures("db", "fake")
def test_claim_rules() -> None:
    template = start("process-jobs")
    _set(template, "running")  # un lote de «Procesar ofertas» en curso
    one, two = _job(1), _job(2)
    batch = _clone(template, "process-jobs", None)
    cv_one = _clone(template, "generate-cv", one)
    cv_one_again = _clone(template, "generate-cv", one)
    cv_two = _clone(template, "generate-cv", two)

    # Con 1, nada más: hay una en curso.
    assert agent_runner.claim_next(1, {}) is None
    # Con 3: el segundo lote de la misma acción no; la oferta 1 sí, pero solo una vez.
    first = agent_runner.claim_next(3, {})
    assert first is not None and first.id == cv_one
    second = agent_runner.claim_next(3, {})
    assert second is not None and second.id == cv_two
    assert agent_runner.claim_next(4, {}) is None  # la otra de la oferta 1 y el lote, esperan
    assert run_row(batch).status == run_row(cv_one_again).status == "queued"

    _set(cv_one, "done")
    third = agent_runner.claim_next(4, {})
    assert third is not None and third.id == cv_one_again  # ya no choca


@pytest.mark.usefixtures("db", "fake")
def test_per_agent_cap() -> None:
    template = start("process-jobs")
    _set(template, "running")  # del agente «claude»
    other = _clone(template, "generate-cv", _job(1))
    assert agent_runner.claim_next(4, {"claude": 1}) is None  # su tope: 1
    assert agent_runner.claim_next(4, {"claude": 2}) is not None
    assert run_row(other).status == "running"


@pytest.mark.usefixtures("db", "fake")
def test_two_jobs_at_once_and_the_same_job_never_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "slow")
    monkeypatch.setenv("FAKE_AGENT_SLEEP", "3")  # holgado: dos procesos reales
    template = start("process-jobs")
    _cancel_queued()  # solo las de abajo
    one, two = _job(1), _job(2)
    a = _clone(template, "generate-cv", one)
    b = _clone(template, "generate-cv", two)
    c = _clone(template, "generate-cv", one)

    outcomes = agent_runner.run_pending(poll=0.05, max_parallel=2)
    assert sorted(o.run_id for o in outcomes) == [a, b, c]
    assert all(o.status == "done" for o in outcomes), outcomes
    ra, rb, rc = run_row(a), run_row(b), run_row(c)
    assert ra.started_at and ra.finished_at and rb.started_at and rb.finished_at and rc.started_at
    assert rb.started_at < ra.finished_at and ra.started_at < rb.finished_at  # a la vez
    assert rc.started_at >= ra.finished_at  # la misma oferta, después


def _running(*run_ids: int) -> None:
    """Espera a que todas tengan proceso (como mucho 10 s)."""
    for _ in range(200):
        if all(run_row(r).pid for r in run_ids):
            return
        time.sleep(0.05)
    raise AssertionError("no arrancaron")


@pytest.mark.usefixtures("db", "fake")
def test_stopping_the_worker_stops_all_running(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "hang")
    template = start("process-jobs")
    _cancel_queued()
    a = _clone(template, "generate-cv", _job(1))
    b = _clone(template, "generate-cv", _job(2))
    c = _clone(template, "generate-cv", _job(3))  # en cola: no debe empezar tras parar
    outcomes: list[agent_runner.AgentRunOutcome] = []
    worker = threading.Thread(
        target=lambda: outcomes.extend(
            agent_runner.run_pending(timeout=30, poll=0.05, max_parallel=2)
        )
    )
    worker.start()
    try:
        _running(a, b)
        assert agent_runner.stop_active() == 2
        worker.join(timeout=30)
        assert sorted(o.run_id for o in outcomes) == [a, b]
        assert all(
            o.status == "failed" and "Se paró el worker" in (o.error or "") for o in outcomes
        )
        assert run_row(c).status == "queued"
    finally:
        agent_runner._shutdown.clear()


@pytest.mark.usefixtures("db", "fake")
def test_cancelling_one_of_two_leaves_the_other_running(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "slow")
    monkeypatch.setenv("FAKE_AGENT_SLEEP", "4")
    template = start("process-jobs")
    _cancel_queued()
    a = _clone(template, "generate-cv", _job(1))
    b = _clone(template, "generate-cv", _job(2))
    outcomes: list[agent_runner.AgentRunOutcome] = []
    worker = threading.Thread(
        target=lambda: outcomes.extend(
            agent_runner.run_pending(timeout=30, poll=0.05, max_parallel=2)
        )
    )
    worker.start()
    _running(a, b)
    with session_scope() as session:
        agent_runs.cancel(session, a)
    worker.join(timeout=30)
    status = {o.run_id: o.status for o in outcomes}
    assert status == {a: "cancelled", b: "done"}


@pytest.mark.usefixtures("db", "fake")
def test_stop_and_recovery_with_several_running(monkeypatch: pytest.MonkeyPatch) -> None:
    template = start("process-jobs")
    _set(template, "running")
    other = _clone(template, "generate-cv", _job(1))
    _set(other, "running")
    assert agent_runner.recover_interrupted() == 2
    assert run_row(template).status == run_row(other).status == "failed"


def test_retry_when_the_database_is_locked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_runner, "LOCK_PAUSE", 0.001)
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise OperationalError("UPDATE", {}, Exception("database is locked"))
        return "ok"

    assert agent_runner._retry_locked(flaky) == "ok" and calls["n"] == 3

    def broken() -> str:
        raise OperationalError("UPDATE", {}, Exception("no such table"))

    with pytest.raises(OperationalError):
        agent_runner._retry_locked(broken)  # otro error: no se reintenta
