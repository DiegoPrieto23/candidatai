"""¿Ya tengo estas ofertas? (`services/known.py`, herramienta `check_known`)."""

from datetime import timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent_interface.tools import CheckKnownInput
from app.core.policies import AgentBrowsePolicy, get_policies
from app.models import Event, Job, JobSighting
from app.services import events, ingest
from app.services.known import MAX_ITEMS, KnownItem, check_known
from app.services.pipeline import Actor, EventType, rebuild_projection

TEXT = "Buscamos Data Engineer con Python y SQL para el equipo de datos. " * 10


def _infojobs(n: int) -> str:
    return f"https://www.infojobs.net/vigo/data-engineer/of-i{n:030x}"


def _add(
    session: Session,
    url: str,
    title: str = "Data Engineer",
    company: str = "Acme Datos",
    location: str | None = "Vigo",
) -> int:
    return ingest.add_from_text(session, title, company, TEXT, url=url, location=location).job_id


def _close(session: Session, job_id: int, days_ago: int, how: EventType) -> None:
    """Cierra la oferta y retrasa `days_ago` días todos sus eventos (como si hubiera pasado)."""
    events.record(
        session,
        job_id,
        how,
        Actor.SYSTEM if how == EventType.EXPIRED else Actor.USER,
        {"reason": "closed"} if how == EventType.DISCARDED else {},
    )
    for event in session.scalars(select(Event).where(Event.job_id == job_id)):
        event.occurred_at -= timedelta(days=days_ago)
    session.flush()
    rebuild_projection(session, job_id)


def _counts(session: Session) -> tuple[int, int, int]:
    return (
        session.scalar(select(func.count(Job.id))) or 0,
        session.scalar(select(func.count(Event.id))) or 0,
        session.scalar(select(func.count(JobSighting.id))) or 0,
    )


def test_mixed_batch_gets_the_right_status_for_each(session: Session) -> None:
    by_id = _add(session, _infojobs(1))
    by_url = _add(session, "https://careers.acme.com/jobs/42?ref=home", title="BI Analyst")
    alive = _add(session, "https://careers.acme.com/jobs/50", title="Analytics Engineer")
    recent = _add(session, "https://careers.acme.com/jobs/60", title="Data Architect")
    old = _add(session, "https://careers.acme.com/jobs/70", title="ML Engineer")
    _close(session, recent, 10, EventType.EXPIRED)
    _close(session, old, 40, EventType.DISCARDED)
    before = _counts(session)

    result = check_known(
        session,
        [
            KnownItem(url="https://jobs.example.com/nueva/1", title="Chef", company="Otra"),
            # Mismo id de InfoJobs, con otra ruta y parámetros.
            KnownItem(url=_infojobs(1).replace("/vigo/", "/madrid/") + "?utm_source=alerta"),
            # Misma URL con parámetros de seguimiento, sin www y sin barra final distinta.
            KnownItem(url="https://careers.acme.com/jobs/42/?utm_campaign=x&gclid=1#apply"),
            # La misma oferta con otro id de plataforma.
            KnownItem(
                url=_infojobs(9), title="Analytics Engineer", company="ACME Datos", location="Vigo"
            ),
            KnownItem(
                url=_infojobs(10), title="Data Architect", company="Acme Datos", location="Vigo"
            ),  # fmt: skip
            KnownItem(
                url=_infojobs(11), title="ML Engineer", company="Acme Datos", location="Vigo"
            ),  # fmt: skip
            # Sin título ni empresa y sin coincidencia de id ni URL.
            KnownItem(url="https://jobs.example.com/otra/2"),
        ],
    )

    statuses = [(item.status, item.matched_by, item.job_id) for item in result.items]
    assert statuses == [
        ("new", None, None),
        ("known", "platform_id", by_id),
        ("known", "url", by_url),
        ("same_offer", "fingerprint", alive),
        ("same_offer", "fingerprint", recent),
        ("reopen_candidate", "fingerprint", old),
        ("new", None, None),
    ]
    assert [item.url for item in result.items][0] == "https://jobs.example.com/nueva/1"
    assert result.counts.model_dump() == {
        "new": 2,
        "known": 2,
        "same_offer": 2,
        "reopen_candidate": 1,
    }
    reopen = result.items[5]
    assert reopen.stage == "closed"
    assert reopen.closed_by == "discarded"
    assert reopen.closed_at is not None
    assert result.items[3].stage == "pending_extraction"
    assert result.items[3].closed_by is None
    assert result.items[4].closed_by == "expired"
    # Solo lee: ni ofertas, ni eventos, ni publicaciones nuevas.
    assert _counts(session) == before


def test_given_platform_id_wins_over_the_url(session: Session) -> None:
    job_id = ingest.add_from_text(
        session, "Data Engineer", "Acme Datos", TEXT, platform="tecnoempleo", external_id="abc123"
    ).job_id
    [item] = check_known(
        session,
        [KnownItem(url="https://otra.example.com/x", platform="tecnoempleo", external_id="abc123")],
    ).items
    assert (item.status, item.matched_by, item.job_id) == ("known", "platform_id", job_id)


def test_url_without_sighting_matches_exactly(session: Session) -> None:
    job_id = _add(session, "https://careers.acme.com/jobs/5")
    session.query(JobSighting).delete()
    [item] = check_known(session, [KnownItem(url="https://careers.acme.com/jobs/5")]).items
    assert (item.status, item.matched_by, item.job_id) == ("known", "url", job_id)


def test_threshold_follows_the_policy(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    job_id = _add(session, "https://careers.acme.com/jobs/8")
    _close(session, job_id, 10, EventType.EXPIRED)
    item = KnownItem(url=_infojobs(3), title="Data Engineer", company="Acme Datos", location="Vigo")
    assert check_known(session, [item]).items[0].status == "same_offer"

    monkeypatch.setattr(get_policies().dedup, "reopen_after_days", 7)
    assert check_known(session, [item]).items[0].status == "reopen_candidate"


def test_fingerprint_needs_title_and_company(session: Session) -> None:
    _add(session, "https://careers.acme.com/jobs/8")
    [no_company, bad_company] = check_known(
        session,
        [
            KnownItem(url=_infojobs(4), title="Data Engineer", location="Vigo"),
            KnownItem(url=_infojobs(5), title="Data Engineer", company="  ", location="Vigo"),
        ],
    ).items
    assert no_company.status == bad_company.status == "new"


def test_reopened_offer_is_same_offer(session: Session) -> None:
    job_id = _add(session, "https://careers.acme.com/jobs/8")
    _close(session, job_id, 40, EventType.EXPIRED)
    events.record(session, job_id, EventType.REOPENED, Actor.USER)
    item = KnownItem(url=_infojobs(3), title="Data Engineer", company="Acme Datos", location="Vigo")
    [result] = check_known(session, [item]).items
    assert (result.status, result.closed_by, result.closed_at) == ("same_offer", None, None)
    assert result.stage != "closed"


def test_known_closed_offer_reports_how_it_was_closed(session: Session) -> None:
    job_id = _add(session, "https://boards.greenhouse.io/acme/jobs/77?gh_jid=77")
    _close(session, job_id, 5, EventType.DISCARDED)
    [result] = check_known(
        session, [KnownItem(url="https://boards.greenhouse.io/acme/jobs/77?gh_src=x&gh_jid=77")]
    ).items
    assert (result.status, result.matched_by, result.job_id) == ("known", "url", job_id)
    assert (result.stage, result.closed_by) == ("closed", "discarded")
    assert result.closed_at is not None


def test_external_id_without_platform_uses_the_host(session: Session) -> None:
    job_id = ingest.add_from_text(
        session,
        "Data Engineer",
        "Acme Datos",
        TEXT,
        url="https://www.infojobs.net/oferta-sin-id",
        external_id="abc123",
    ).job_id
    [result] = check_known(
        session, [KnownItem(url="https://www.infojobs.net/otra-ruta", external_id="abc123")]
    ).items
    assert (result.status, result.matched_by, result.job_id) == ("known", "platform_id", job_id)


def test_repeated_items_keep_order_and_count_each(session: Session) -> None:
    job_id = _add(session, _infojobs(1))
    result = check_known(session, [KnownItem(url=_infojobs(n)) for n in (1, 2, 1)])
    assert [r.job_id for r in result.items] == [job_id, None, job_id]
    assert (result.counts.known, result.counts.new) == (2, 1)


def test_input_limits() -> None:
    url = "https://jobs.example.com/1"
    CheckKnownInput(items=[{"url": url}] * MAX_ITEMS)
    with pytest.raises(ValidationError):
        CheckKnownInput(items=[{"url": url}] * (MAX_ITEMS + 1))
    with pytest.raises(ValidationError):
        CheckKnownInput(items=[])
    with pytest.raises(ValidationError):
        CheckKnownInput(items=[{"url": ""}])


def test_search_policies_come_from_the_yaml() -> None:
    policies = get_policies()
    assert policies.dedup.reopen_after_days == 30
    browse = policies.agent_browse
    assert (browse.max_result_pages, browse.stop_after_known) == (5, 5)
    with pytest.raises(ValidationError):
        AgentBrowsePolicy(
            max_result_pages=5, delay_seconds=5, default_max_offers=15, stop_after_known=0
        )


def test_closed_by_you_is_same_offer_not_reopen(session: Session) -> None:
    """Como `store_job`: solo es reapertura lo que cerró la empresa o caducó."""
    job_id = _add(session, "https://careers.acme.com/jobs/8")
    events.record(session, job_id, EventType.DISCARDED, Actor.USER, {"reason": "salary"})
    for event in session.scalars(select(Event).where(Event.job_id == job_id)):
        event.occurred_at -= timedelta(days=40)
    session.flush()
    rebuild_projection(session, job_id)
    item = KnownItem(url=_infojobs(3), title="Data Engineer", company="Acme Datos", location="Vigo")
    [result] = check_known(session, [item]).items
    assert (result.status, result.closed_by) == ("same_offer", "discarded")


def test_almost_same_title_is_same_offer_and_writes_nothing(session: Session) -> None:
    """Lo que `store_job` no daría de alta (la misma vacante con un título casi igual) tampoco se
    abre."""
    job_id = _add(session, "https://careers.acme.com/jobs/1", title="Data Engineer Python")
    before = _counts(session)
    item = KnownItem(
        url="https://careers.acme.com/jobs/2",
        title="Data Engineer - Python / SQL",
        company="ACME DATOS",
        location="Remoto",
    )
    [result] = check_known(session, [item]).items
    assert (result.status, result.matched_by, result.job_id) == (
        "same_offer",
        "fuzzy_title",
        job_id,
    )
    assert _counts(session) == before
    stored = ingest.add_from_text(
        session, item.title or "", item.company or "", TEXT, url=item.url, location=item.location
    )
    assert (stored.created, stored.job_id) == (False, job_id)


def test_almost_same_title_closed_by_the_company_is_a_reopen_candidate(session: Session) -> None:
    job_id = _add(session, "https://careers.acme.com/jobs/1", title="Data Engineer Python")
    _close(session, job_id, 40, EventType.EXPIRED)
    item = KnownItem(
        url="https://careers.acme.com/jobs/2", title="Data Engineer - Python", company="Acme Datos"
    )
    [result] = check_known(session, [item]).items
    assert (result.status, result.matched_by) == ("reopen_candidate", "fuzzy_title")


def test_same_platform_ids_are_not_almost_the_same_offer(session: Session) -> None:
    """Dos ids distintos de la misma plataforma son publicaciones distintas, como al dar de alta."""
    _add(session, _infojobs(1), title="Data Engineer")
    item = KnownItem(url=_infojobs(2), title="Senior Data Engineer", company="Acme Datos")
    [result] = check_known(session, [item]).items
    assert result.status == "new"
    other = KnownItem(
        url="https://careers.acme.com/jobs/9", title="Senior Data Engineer", company="Acme Datos"
    )
    assert check_known(session, [other]).items[0].status == "same_offer"


def test_almost_same_title_of_another_company_is_new(session: Session) -> None:
    _add(session, "https://careers.acme.com/jobs/1", title="Data Engineer Python")
    item = KnownItem(
        url="https://globex.example/jobs/1", title="Data Engineer - Python", company="Globex"
    )
    assert check_known(session, [item]).items[0].status == "new"
