"""Ofertas que vuelven a publicarse (fase 45): `ingest.republication`, `store_job`, conectores,
alertas por correo, señales y la UI (`services/reopenings.py`)."""

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.api.main import UI_ORIGIN, create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import EmailMessage, Event, Job, JobSighting
from app.schemas.sources import SourceInput
from app.services import events, ingest, reopenings, reposts
from app.services.ingestion import service as sources
from app.services.ingestion.email.service import poll_email
from app.services.jobs import get_job_view, list_jobs
from app.services.pipeline import Actor, EventType, Stage, job_events, rebuild_projection
from app.services.signals import read
from tests.sources_support import GREENHOUSE_URL
from tests.test_email_alerts import LINKEDIN, _inbox, _no_fetch

TEXT = "Buscamos Data Engineer con Python y SQL para el equipo de datos. " * 10


def _infojobs(n: int) -> str:
    return f"https://www.infojobs.net/vigo/data-engineer/of-i{n:030x}"


def _add(session: Session, url: str, title: str = "Data Engineer") -> ingest.AddJobResult:
    return ingest.add_from_text(session, title, "Acme Datos", TEXT, url=url, location="Vigo")


def _stage(session: Session, job_id: int) -> Stage:
    return events.current_stage(session, job_id)


def _close(session: Session, job_id: int, how: str, days_ago: int, **payload: Any) -> None:
    """Cierra la oferta como lo haría quien corresponda y lo retrasa `days_ago` días."""
    if how in ("rejected", "withdrawn"):
        events.record(session, job_id, EventType.APPLIED_MANUALLY, Actor.USER)
    if how == "accepted":
        events.record(session, job_id, EventType.APPLIED_MANUALLY, Actor.USER)
        events.record(session, job_id, EventType.INTERVIEW_SCHEDULED, Actor.USER)
    actor = Actor.SYSTEM if how == "hard_filter_failed" else Actor.USER
    if how == "hard_filter_failed":
        events.record(session, job_id, EventType.EXTRACTED, Actor.AGENT)
    events.record(session, job_id, how, actor, payload or None)
    for event in session.scalars(select(Event).where(Event.job_id == job_id)):
        event.occurred_at -= timedelta(days=days_ago)
    for sighting in session.scalars(select(JobSighting).where(JobSighting.job_id == job_id)):
        sighting.seen_at -= timedelta(days=days_ago)
    job = session.get(Job, job_id)
    assert job is not None
    job.first_seen_at -= timedelta(days=days_ago)
    session.flush()
    rebuild_projection(session, job_id)


def _jobs(session: Session) -> int:
    return session.scalar(select(func.count(Job.id))) or 0


# --- Otra publicación (misma huella) ---------------------------------------------------------


@pytest.mark.parametrize(
    ("how", "payload"),
    [
        ("rejected", {}),
        ("expired", {}),
        ("discarded", {"reason": "closed"}),
    ],
)
def test_closed_by_the_company_comes_back_as_a_linked_new_offer(
    session: Session, how: str, payload: dict[str, Any]
) -> None:
    old = _add(session, _infojobs(1)).job_id
    _close(session, old, how, 40, **payload)

    result = _add(session, _infojobs(2))

    assert result.created and result.reopening_of == old
    assert result.duplicate_of is None
    job = session.get(Job, result.job_id)
    assert job is not None and job.reopening_of == old
    assert job.fingerprint == session.get(Job, old).fingerprint  # type: ignore[union-attr]
    found = job_events(session, job.id)[0]
    assert found.type == EventType.FOUND and found.payload["reopening_of"] == old
    assert _stage(session, job.id) == Stage.PENDING_EXTRACTION
    assert _stage(session, old) == Stage.CLOSED
    assert not session.scalars(
        select(Event).where(Event.job_id == job.id, Event.type == EventType.DUPLICATE_DETECTED)
    ).first()

    # Una tercera publicación de la reapertura viva es la misma oferta: no crea otra.
    again = _add(session, _infojobs(3))
    assert (again.created, again.job_id) == (False, job.id)


@pytest.mark.parametrize(
    ("how", "payload"),
    [
        ("withdrawn", {}),
        ("accepted", {}),
        ("discarded", {"reason": "salary"}),
    ],
)
def test_closed_by_you_only_warns(session: Session, how: str, payload: dict[str, Any]) -> None:
    old = _add(session, _infojobs(1)).job_id
    _close(session, old, how, 40, **payload)
    before = _jobs(session)

    result = _add(session, _infojobs(2))

    assert (result.created, result.job_id, result.republished_after_close) == (False, old, True)
    assert _jobs(session) == before
    assert _stage(session, old) == Stage.CLOSED
    job = session.get(Job, old)
    assert job is not None
    signal = read(job).republished_after_close
    assert signal is not None and signal.url == _infojobs(2)


def test_closed_less_than_30_days_ago_changes_nothing(session: Session) -> None:
    old = _add(session, _infojobs(1)).job_id
    _close(session, old, "rejected", 20)

    result = _add(session, _infojobs(2))

    assert (result.created, result.job_id, result.reopening_of) == (False, old, None)
    assert not result.republished_after_close and not result.reopened
    assert _stage(session, old) == Stage.CLOSED
    job = session.get(Job, old)
    assert job is not None and read(job).republished_after_close is None
    # La publicación sí se anota, como siempre.
    assert session.scalar(select(func.count(JobSighting.id)).where(JobSighting.job_id == old)) == 2


def test_the_threshold_is_the_policy(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.policies import get_policies

    old = _add(session, _infojobs(1)).job_id
    _close(session, old, "rejected", 20)
    monkeypatch.setattr(get_policies().dedup, "reopen_after_days", 10)
    assert _add(session, _infojobs(2)).reopening_of == old


def test_closed_by_the_hard_filter_is_not_reconsidered(session: Session) -> None:
    old = _add(session, _infojobs(1)).job_id
    _close(session, old, "hard_filter_failed", 40)
    result = _add(session, _infojobs(2))
    assert (result.created, result.job_id) == (False, old)
    assert not result.republished_after_close


# --- La misma publicación --------------------------------------------------------------------


def test_same_id_that_expired_reopens_the_same_offer(session: Session) -> None:
    old = _add(session, _infojobs(1)).job_id
    _close(session, old, "expired", 40)
    before = _jobs(session)

    result = _add(session, _infojobs(1) + "?utm_source=alerta")

    assert (result.created, result.job_id, result.reopened) == (False, old, True)
    assert _jobs(session) == before
    assert _stage(session, old) == Stage.PENDING_EXTRACTION
    last = job_events(session, old)[-1]
    assert (last.type, last.actor, last.payload) == (
        EventType.REOPENED,
        Actor.SYSTEM,
        {"reason": "republished"},
    )


def test_same_id_closed_otherwise_stays_closed(session: Session) -> None:
    old = _add(session, _infojobs(1)).job_id
    _close(session, old, "rejected", 40)
    result = _add(session, _infojobs(1))
    assert (result.created, result.reopened, result.reopening_of) == (False, False, None)
    assert _stage(session, old) == Stage.CLOSED


# --- Otras vías ------------------------------------------------------------------------------


def _greenhouse(job_id: int) -> dict[str, object]:
    return {
        "jobs": [
            {
                "id": job_id,
                "title": "Data Engineer",
                "location": {"name": "Vigo"},
                "absolute_url": f"https://boards.greenhouse.io/acmedatos/jobs/{job_id}",
                "content": "&lt;p&gt;" + TEXT + "&lt;/p&gt;",
            }
        ]
    }


@respx.mock
def test_connector_reopening_and_reactivation(session: Session) -> None:
    source = sources.add_source(
        session, SourceInput(kind="greenhouse", name="Acme Datos", slug="acmedatos")
    )
    route = respx.get(GREENHOUSE_URL)
    route.mock(return_value=httpx.Response(200, json=_greenhouse(100)))
    [old] = sources.run_source(session, source.id).job_ids
    _close(session, old, "rejected", 40)

    # Otra publicación (otro id) de una que cerró la empresa: oferta nueva enlazada.
    route.mock(return_value=httpx.Response(200, json=_greenhouse(200)))
    second = sources.run_source(session, source.id)
    assert second.created == 1
    reopening = session.get(Job, second.job_ids[0])
    assert reopening is not None and reopening.reopening_of == old

    # La misma publicación, caducada hace más de 30 días, que el ATS vuelve a listar: se reabre.
    _close(session, reopening.id, "expired", 40)
    third = sources.run_source(session, source.id)
    assert (third.created, third.existing) == (0, 1)
    assert _stage(session, reopening.id) == Stage.PENDING_EXTRACTION


def test_email_alert_with_a_reopening(session: Session, isolated_env: Path) -> None:
    inbox = _inbox(isolated_env, LINKEDIN)
    poll_email(session, fetch=_no_fetch)
    first = session.scalars(select(Job).order_by(Job.id)).first()
    assert first is not None
    _close(session, first.id, "expired", 40)
    # El mismo correo, otra vez, con otro id para esa oferta: es otra publicación.
    first.external_id = "3999999999"
    session.execute(delete(EmailMessage))
    session.flush()
    _inbox(isolated_env, LINKEDIN)
    assert inbox.exists()

    result = poll_email(session, fetch=_no_fetch)

    assert result.created == 1
    reopening = session.scalars(select(Job).where(Job.reopening_of == first.id)).one()
    assert (reopening.platform, reopening.external_id) == ("linkedin", "4000000001")
    assert _stage(session, reopening.id) == Stage.PENDING_DETAIL


def test_email_alert_reactivates_the_same_expired_id(session: Session, isolated_env: Path) -> None:
    _inbox(isolated_env, LINKEDIN)
    poll_email(session, fetch=_no_fetch)
    first = session.scalars(select(Job).order_by(Job.id)).first()
    assert first is not None
    _close(session, first.id, "expired", 40)
    session.execute(delete(EmailMessage))
    session.flush()
    _inbox(isolated_env, LINKEDIN)

    poll_email(session, fetch=_no_fetch)

    assert _stage(session, first.id) == Stage.PENDING_DETAIL
    assert session.scalar(select(func.count(Job.id))) == 3


# --- Republicadas y ofertas dudosas ----------------------------------------------------------


def test_reposts_only_count_after_the_last_reopening(session: Session) -> None:
    old = _add(session, _infojobs(1)).job_id
    # Muchas publicaciones viejas: la antigua parece «publicada hace meses».
    for n in range(2, 6):
        job = session.get(Job, old)
        assert job is not None
        reposts.note_sighting(
            session,
            job,
            url=_infojobs(n),
            platform=None,
            external_id=None,
            seen_at=job.first_seen_at + timedelta(days=n * 3),
        )
    _close(session, old, "rejected", 200)
    job = session.get(Job, old)
    assert job is not None and read(job).stale_repost is not None

    reopening = _add(session, _infojobs(9)).job_id

    new = session.get(Job, reopening)
    assert new is not None
    signals = read(new)
    assert signals.stale_repost is None and signals.reposted is None


# --- Vista y UI ------------------------------------------------------------------------------


def test_job_view_and_list_say_where_it_comes_from(session: Session) -> None:
    old = _add(session, _infojobs(1)).job_id
    _close(session, old, "rejected", 40)
    reopening = _add(session, _infojobs(2)).job_id

    view = get_job_view(session, reopening)
    assert view.reopening_of == old
    assert view.reopening is not None
    assert (view.reopening.job_id, view.reopening.closed_by) == (old, "rejected")
    assert view.reopening.stage_before_close == Stage.APPLIED
    assert get_job_view(session, old).reopening is None
    listed = {j.id: j.reopening_of for j in list_jobs(session)}
    assert listed[reopening] == old


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app(), base_url="http://127.0.0.1:8000") as client:
        yield client


JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


def test_notice_list_reopen_and_dismiss(client: TestClient) -> None:
    with session_scope() as session:
        first = _add(session, _infojobs(1)).job_id
        second = _add(session, _infojobs(5), title="BI Analyst").job_id
        _close(session, first, "discarded", 40, reason="salary")
        _close(session, second, "withdrawn", 40)
        _add(session, _infojobs(2))
        _add(session, _infojobs(6), title="BI Analyst")

    response = client.get("/jobs/republished")
    assert response.status_code == 200, response.text
    body = response.json()
    assert {item["job_id"] for item in body["items"]} == {first, second}

    # «Reabrir»: el evento `reopened` de siempre quita el aviso.
    response = client.post(f"/jobs/{first}/events", json={"type": "reopened"}, headers=JSON)
    assert response.status_code == 201, response.text
    assert [i["job_id"] for i in client.get("/jobs/republished").json()["items"]] == [second]

    # «Ignorar».
    response = client.post(f"/jobs/{second}/republished/dismiss", json={}, headers=JSON)
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []
    missing = client.post("/jobs/999/republished/dismiss", json={}, headers=JSON)
    assert missing.status_code == 404


def test_notice_is_listed_with_reopenings_list(session: Session) -> None:
    old = _add(session, _infojobs(1)).job_id
    _close(session, old, "withdrawn", 40)
    _add(session, _infojobs(2))
    [item] = reopenings.list_republished(session).items
    assert (item.job_id, item.closed_by, item.url) == (old, "withdrawn", _infojobs(2))


def test_dismissed_notice_stays_quiet_for_a_while(session: Session) -> None:
    old = _add(session, _infojobs(1)).job_id
    _close(session, old, "withdrawn", 40)
    _add(session, _infojobs(2))
    reopenings.dismiss(session, old)
    assert reopenings.list_republished(session).items == []

    # Un conector que la ve al día siguiente no vuelve a avisar…
    _add(session, _infojobs(3))
    assert reopenings.list_republished(session).items == []

    # …hasta pasados `reopen_after_days` desde «Ignorar».
    job = session.get(Job, old)
    assert job is not None
    signal = read(job).republished_after_close
    assert signal is not None and signal.dismissed_at is not None
    from app.services.signals import set_signal

    set_signal(
        job,
        "republished_after_close",
        signal.model_copy(update={"dismissed_at": signal.dismissed_at - timedelta(days=31)}),
    )
    session.flush()
    _add(session, _infojobs(4))
    assert [i.job_id for i in reopenings.list_republished(session).items] == [old]


def test_a_broken_notice_is_skipped(session: Session) -> None:
    old = _add(session, _infojobs(1)).job_id
    _close(session, old, "withdrawn", 40)
    job = session.get(Job, old)
    assert job is not None
    job.signals = {**(job.signals or {}), "republished_after_close": {"seen_at": "ayer"}}
    session.flush()
    assert reopenings.list_republished(session).items == []
