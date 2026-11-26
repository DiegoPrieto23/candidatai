"""Ofertas caducadas: segundo intento con el navegador, caducidad por antigüedad, lo que guarda el
agente y el aviso de la Bandeja. Sin red ni navegador: respx y `fetch_rendered` simulado."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import migrations
from app.core.db import session_scope
from app.core.policies import get_policies
from app.models import Event, Job, Task
from app.services import events, ingest, liveness, liveness_browser
from app.services.signals import read

NOW = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=1)
TEXT = "Buscamos Data Engineer con Python y SQL para el equipo de datos. " * 10
INDEED = "https://es.indeed.com/viewjob?jk=0402f8bb5567dba7"
GLASSDOOR = "https://www.glassdoor.es/job-listing/data-engineer-acme-JV_KO0,13.htm?jl=1010307973574"
GENERIC = "https://careers.example.com/jobs/data-engineer-42"

INDEED_CLOSED = (
    "<html><body><h1>Data Engineer</h1><p>Este empleo ha caducado en Indeed</p>"
    "<p>Entre otros motivos, esto podría deberse a que la empresa ya no acepta más solicitudes."
    "</p></body></html>"
)
INDEED_OPEN = "<html><body><h1>Data Engineer</h1><p>Requisitos: Python y SQL.</p></body></html>"


def _job(session: Session, url: str, title: str = "Data Engineer") -> Job:
    result = ingest.add_from_text(session, title, "Acme Datos", TEXT, url=url, location="Vigo")
    job = session.get(Job, result.job_id)
    assert job is not None
    return job


def _approve(session: Session, job_id: int) -> None:
    events.record(session, job_id, "extracted", "agent")
    events.record(session, job_id, "approved", "user")


def _age(session: Session, job: Job, days: int) -> None:
    job.first_seen_at = NOW - timedelta(days=days)
    session.flush()


def _browser(
    monkeypatch: pytest.MonkeyPatch, html: str, status: int = 200, final_url: str | None = None
) -> list[str]:
    """Simula el navegador fuera de la pantalla; devuelve las URLs que abre."""
    opened: list[str] = []

    def fake(url: str, _timeout: float, _wait: float, allow: Callable[[str], bool]) -> object:
        assert allow(url)
        opened.append(url)
        return liveness_browser.RenderedPage(
            status=status, final_url=final_url or url, html=html, redirected=False
        )

    monkeypatch.setattr(liveness_browser, "fetch_rendered", fake)
    return opened


# --- La frase de Indeed ------------------------------------------------------------------------


def test_indeed_expired_phrase_is_closed() -> None:
    result = liveness.analyze_page(INDEED, 200, INDEED, False, INDEED_CLOSED, NOW, "Data Engineer")
    assert result.status == "possibly_closed"
    assert result.reason == "closed_text"
    assert "este empleo ha caducado en indeed" in result.detail


# --- Segundo intento con el navegador ----------------------------------------------------------


@respx.mock
def test_blocked_request_is_retried_in_the_browser(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    respx.get(INDEED).mock(return_value=httpx.Response(401))
    opened = _browser(monkeypatch, INDEED_CLOSED)
    job = _job(session, INDEED)
    _approve(session, job.id)

    view = liveness.check_job(session, job.id, now=NOW)

    assert opened == [INDEED]
    assert view.status == "possibly_closed"
    assert view.reason == "closed_text"
    assert "comprobado en el navegador" in view.detail
    assert read(job).possibly_closed is not None


@respx.mock
def test_browser_open_page_is_open(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    respx.get(INDEED).mock(return_value=httpx.Response(403))
    _browser(monkeypatch, INDEED_OPEN)
    job = _job(session, INDEED)
    _approve(session, job.id)
    view = liveness.check_job(session, job.id, now=NOW)
    assert view.status == "open"


@respx.mock
def test_anti_bot_in_the_browser_stays_unknown(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    respx.get(INDEED).mock(return_value=httpx.Response(403))
    _browser(monkeypatch, "<html><body>Verify you are human</body></html>", status=403)
    job = _job(session, INDEED)
    _approve(session, job.id)
    view = liveness.check_job(session, job.id, now=NOW)
    assert view.status == "unknown"
    assert view.detail.startswith("tampoco en el navegador")
    assert read(job).possibly_closed is None


@respx.mock
def test_without_browser_keeps_the_blocked_result(session: Session) -> None:
    respx.get(INDEED).mock(return_value=httpx.Response(401))  # `conftest`: sin navegador
    job = _job(session, INDEED)
    _approve(session, job.id)
    view = liveness.check_job(session, job.id, now=NOW)
    assert view.status == "unknown"
    assert view.detail == "la página bloquea el acceso (HTTP 401)"


@respx.mock
def test_skipped_platform_and_disabled_fallback_do_not_open_the_browser(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    respx.get(GLASSDOOR).mock(return_value=httpx.Response(403))
    respx.get(INDEED).mock(return_value=httpx.Response(403))
    opened = _browser(monkeypatch, INDEED_CLOSED)
    glassdoor = _job(session, GLASSDOOR)
    assert liveness.check_job(session, glassdoor.id, now=NOW).status == "unknown"
    assert opened == []  # Glassdoor bloquea también al navegador: ni se intenta

    monkeypatch.setattr(get_policies().liveness, "browser_fallback", False)
    indeed = _job(session, INDEED, title="BI Engineer")
    assert liveness.check_job(session, indeed.id, now=NOW).status == "unknown"
    assert opened == []


@respx.mock
def test_not_found_is_not_retried_in_the_browser(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    respx.get(GENERIC).mock(return_value=httpx.Response(404))
    opened = _browser(monkeypatch, INDEED_OPEN)
    job = _job(session, GENERIC)
    assert liveness.check_job(session, job.id, now=NOW).status == "possibly_closed"
    assert opened == []


def test_browser_never_navigates_to_local_or_linkedin_addresses() -> None:
    assert liveness._allowed_in_browser(GENERIC)
    assert not liveness._allowed_in_browser("http://127.0.0.1:8000/jobs")
    assert not liveness._allowed_in_browser("https://www.linkedin.com/jobs/view/123/")


# --- Caducidad por antigüedad ------------------------------------------------------------------


def _closure_events(session: Session, job_id: int) -> list[Event]:
    return list(
        session.scalars(
            select(Event).where(Event.job_id == job_id, Event.type == "closure_suspected")
        )
    )


def test_old_jobs_are_flagged_once_and_never_closed(session: Session) -> None:
    old = _job(session, GENERIC)
    _age(session, old, 45)
    recent = _job(session, "https://careers.example.com/jobs/reciente", title="BI Engineer")
    _age(session, recent, 5)

    assert liveness.flag_stale(session, NOW) == [old.id]
    closed = read(old).possibly_closed
    assert closed is not None and closed.reason == "stale"
    assert closed.detail == "vista hace 45 días (más de 30)"
    assert len(_closure_events(session, old.id)) == 1
    assert liveness.flag_stale(session, NOW) == []  # ya tiene aviso: no se repite
    assert len(_closure_events(session, old.id)) == 1
    assert events.current_stage(session, old.id) == "pending_extraction"


def test_posted_date_counts_when_known(session: Session) -> None:
    job = _job(session, GENERIC)
    _age(session, job, 2)
    job.posted_at = NOW - timedelta(days=40)
    session.flush()
    assert liveness.flag_stale(session, NOW) == [job.id]
    closed = read(job).possibly_closed
    assert closed is not None and closed.detail.startswith("publicada hace 40 días")


def test_recent_open_check_and_still_open_prevent_the_flag(session: Session) -> None:
    checked = _job(session, GENERIC)
    _age(session, checked, 45)
    liveness.apply_result(
        session, checked, liveness.LivenessResult(status="open", detail="ok"), now=NOW
    )
    confirmed = _job(session, "https://careers.example.com/jobs/otra", title="BI Engineer")
    _age(session, confirmed, 45)
    assert liveness.flag_stale(session, NOW) == [confirmed.id]
    liveness.confirm_open(session, confirmed.id, now=NOW)
    assert read(confirmed).possibly_closed is None
    assert liveness.flag_stale(session, NOW + timedelta(days=1)) == []


def test_sent_and_closed_jobs_are_not_flagged(session: Session) -> None:
    applied = _job(session, GENERIC)
    _approve(session, applied.id)
    events.record(session, applied.id, "applied_manually", "user", {"channel": "portal"})
    discarded = _job(session, "https://careers.example.com/jobs/otra", title="BI Engineer")
    events.record(session, discarded.id, "discarded", "user", {"reason": "skills"})
    for job in (applied, discarded):
        _age(session, job, 90)
    assert liveness.flag_stale(session, NOW) == []


def test_zero_days_disables_the_age_rule(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    job = _job(session, GENERIC)
    _age(session, job, 400)
    monkeypatch.setattr(get_policies().liveness, "stale_after_days", 0)
    assert liveness.flag_stale(session, NOW) == []


@respx.mock
def test_open_check_clears_the_age_flag(session: Session) -> None:
    job = _job(session, GENERIC)
    _age(session, job, 45)
    liveness.flag_stale(session, NOW)
    respx.get(GENERIC).mock(
        return_value=httpx.Response(200, text=f"<html><body><h1>{job.title}</h1></body></html>")
    )
    view = liveness.check_job(session, job.id, now=NOW)
    assert view.status == "open"
    assert read(job).possibly_closed is None


# --- Lo que guarda el agente -------------------------------------------------------------------


def test_agent_check_flags_and_clears(session: Session) -> None:
    job = _job(session, GLASSDOOR)
    _approve(session, job.id)

    view = liveness.save_agent_check(
        session, job.id, "possibly_closed", "  La página dice\n«ya no acepta solicitudes» ", NOW
    )
    assert view.status == "possibly_closed"
    closed = read(job).possibly_closed
    assert closed is not None and closed.reason == "agent_browser"
    assert (
        closed.detail
        == "La página dice «ya no acepta solicitudes» (lo vio el agente en el navegador)"
    )
    assert len(_closure_events(session, job.id)) == 1

    unknown = liveness.save_agent_check(session, job.id, "unknown", "captcha", NOW)
    assert unknown.status == "unknown" and read(job).possibly_closed is not None

    opened = liveness.save_agent_check(session, job.id, "open", "", NOW)
    assert opened.status == "open" and read(job).possibly_closed is None
    assert opened.detail == "comprobada en el navegador (lo vio el agente en el navegador)"


def test_agent_check_needs_an_open_job_before_sending(session: Session) -> None:
    job = _job(session, GENERIC)
    events.record(session, job.id, "discarded", "user", {"reason": "skills"})
    with pytest.raises(liveness.StageNotAllowedError):
        liveness.save_agent_check(session, job.id, "open", "ok", NOW)
    with pytest.raises(events.JobNotFoundError):
        liveness.save_agent_check(session, 999, "open", "ok", NOW)


# --- Aviso de la Bandeja -----------------------------------------------------------------------


def test_closure_suspects_and_unverified_important(session: Session) -> None:
    old = _job(session, GENERIC)
    _age(session, old, 45)
    blocked = _job(session, INDEED, title="BI Engineer")
    _approve(session, blocked.id)
    liveness.apply_result(
        session, blocked, liveness.LivenessResult(status="unknown", detail="HTTP 403"), now=NOW
    )
    checked = _job(session, "https://careers.example.com/jobs/abierta", title="Data Analyst")
    _approve(session, checked.id)
    liveness.apply_result(
        session, checked, liveness.LivenessResult(status="open", detail="ok"), now=NOW
    )
    liveness.flag_stale(session, NOW)

    suspects = liveness.closure_suspects(session)
    assert [item.job_id for item in suspects.items] == [old.id]
    assert suspects.items[0].company == "Acme Datos"
    assert suspects.items[0].reason == "stale"
    assert suspects.unverified_important == 1  # la de Indeed; la abierta ya está comprobada


# --- Worker y API ------------------------------------------------------------------------------


@pytest.fixture
def db(isolated_env: Path) -> None:
    migrations.upgrade()


def test_refresh_flags_and_queues(db: None) -> None:
    with session_scope() as session:
        old = _job(session, GENERIC)
        _age(session, old, 45)
        pending = _job(session, "https://careers.example.com/jobs/otra", title="BI Engineer")
        ids = {old.id, pending.id}
    with session_scope() as session:
        result = liveness.refresh(session, NOW)
    assert (result.stale, result.queued) == (1, 2)
    assert result.message == "1 marcadas por antigüedad; 2 comprobaciones en cola."
    with session_scope() as session:
        queued = session.scalars(select(Task).where(Task.kind == "check_open"))
        assert {t.payload["job_id"] for t in queued} == ids


def test_api_closure_suspects_and_check_now(db: None) -> None:
    from fastapi.testclient import TestClient

    from app.api.deps import UI_ORIGIN
    from app.api.main import create_app

    with session_scope() as session:
        job = _job(session, GENERIC)
        job.first_seen_at = datetime.now(UTC) - timedelta(days=45)
        job_id = job.id
    ui = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}
    with TestClient(create_app(), base_url="http://127.0.0.1:8000") as client:
        assert client.get("/jobs/closure-suspects").json()["items"] == []
        forbidden = client.post("/jobs/check-open", json={}, headers={"Origin": "https://x.ex"})
        assert forbidden.status_code == 403
        done = client.post("/jobs/check-open", content="{}", headers=ui)
        assert done.status_code == 200
        assert done.json()["stale"] == 1 and done.json()["queued"] == 1
        suspects = client.get("/jobs/closure-suspects").json()
        assert [item["job_id"] for item in suspects["items"]] == [job_id]
        assert suspects["items"][0]["reason"] == "stale"
