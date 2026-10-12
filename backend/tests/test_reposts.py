"""Republicadas (`services/reposts.py`): publicaciones vistas, canales, días y conectores."""

from datetime import timedelta

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, JobSighting
from app.schemas.sources import SourceInput
from app.services import ingest, reposts
from app.services.ingestion import service as sources
from app.services.jobs import list_jobs
from app.services.signals import read
from tests.sources_support import GREENHOUSE_URL

TEXT = "Buscamos Data Engineer con Python y SQL para el equipo de datos. " * 10


def _infojobs(n: int) -> str:
    return f"https://www.infojobs.net/vigo/data-engineer/of-i{n:030x}"


def _add(session: Session, url: str, title: str = "Data Engineer", location: str = "Vigo") -> int:
    return ingest.add_from_text(
        session, title, "Acme Datos", TEXT, url=url, location=location
    ).job_id


def _age(session: Session, days: int) -> None:
    """Retrasa `days` días todo lo visto hasta ahora (como si hubiera pasado ese tiempo)."""
    for sighting in session.scalars(select(JobSighting)):
        sighting.seen_at -= timedelta(days=days)
    session.flush()


def _reposted(session: Session, job_id: int) -> tuple[int, str] | None:
    job = session.get(Job, job_id)
    assert job is not None
    signal = read(job).reposted
    return (signal.count, signal.channel) if signal else None


@pytest.mark.parametrize(
    ("url", "platform", "external_id", "channel", "ref"),
    [
        (_infojobs(1), None, None, "infojobs", f"{1:030x}"),
        (
            "https://es.indeed.com/viewjob?jk=0123456789abcdef&from=x",
            None,
            None,
            "indeed",
            "0123456789abcdef",
        ),
        (
            "https://www.Acme.com/jobs/9/?utm_source=x#top",
            None,
            None,
            "acme.com",
            "acme.com/jobs/9",
        ),
        ("", "infojobs", "abc", "infojobs", "abc"),
        ("", None, None, None, None),
        (
            "https://boards.greenhouse.io/acme/jobs/1",
            None,
            "1",
            "boards.greenhouse.io",
            "1",
        ),
    ],
)
def test_channel_and_ref(
    url: str, platform: str | None, external_id: str | None, channel: str | None, ref: str | None
) -> None:
    assert reposts.channel_of(url, platform) == channel
    assert reposts.ref_of(url, platform, external_id) == ref


def test_title_key_uses_title_aliases() -> None:
    assert reposts.title_key("Ingeniero de Datos (m/f)") == reposts.title_key("Data Engineer")
    assert reposts.title_key("Senior Data Engineer") != reposts.title_key("Data Engineer")


def test_same_offer_with_new_id_on_another_day_is_reposted(session: Session) -> None:
    first = _add(session, _infojobs(1))
    _age(session, 20)
    again = _add(session, _infojobs(2))  # misma huella: devuelve la existente
    assert again == first
    assert _reposted(session, first) == (2, "infojobs")
    job = session.get(Job, first)
    assert job is not None
    dates = read(job).reposted.dates  # type: ignore[union-attr]
    assert len(dates) == 2 and dates[0] < dates[1]

    _age(session, 5)
    _add(session, _infojobs(3))
    assert _reposted(session, first) == (3, "infojobs")


def test_same_id_seen_again_is_not_a_repost(session: Session) -> None:
    first = _add(session, _infojobs(1))
    _age(session, 20)
    _add(session, _infojobs(1))
    assert _reposted(session, first) is None
    assert session.scalars(select(JobSighting)).all().__len__() == 1


def test_same_day_new_ids_are_not_reposts(session: Session) -> None:
    first = _add(session, _infojobs(1))
    _add(session, _infojobs(2))  # misma huella, otro id, el mismo día
    assert _reposted(session, first) is None


def test_other_portal_is_cross_posting_not_repost(session: Session) -> None:
    first = _add(session, _infojobs(1))
    _age(session, 10)
    _add(session, "https://es.indeed.com/viewjob?jk=0123456789abcdef")
    assert _reposted(session, first) is None


def test_fuzzy_duplicate_and_translated_title_count(session: Session) -> None:
    first = _add(session, _infojobs(1))
    _age(session, 15)
    second = _add(session, _infojobs(2), title="Ingeniero de datos")
    assert second != first
    assert _reposted(session, first) == (2, "infojobs")
    assert _reposted(session, second) == (2, "infojobs")  # todas las del grupo


def test_same_title_in_another_city_is_not_a_repost(session: Session) -> None:
    first = _add(session, _infojobs(1))
    _age(session, 10)
    _add(session, _infojobs(2), location="Madrid")
    assert _reposted(session, first) is None


def test_ids_in_the_query_are_kept() -> None:
    a = reposts.ref_of("https://acme.com/careers?gh_jid=77&utm_source=x", None, None)
    b = reposts.ref_of("https://acme.com/careers?utm_source=y&gh_jid=78", None, None)
    assert (a, b) == ("acme.com/careers?gh_jid=77", "acme.com/careers?gh_jid=78")
    assert reposts.ref_of("https://acme.com/careers?gh_jid=77", None, "77") == "77"


def test_old_sightings_fall_out_of_the_window(session: Session) -> None:
    first = _add(session, _infojobs(1))
    _age(session, 200)
    _add(session, _infojobs(2))
    assert _reposted(session, first) is None


def test_other_company_does_not_count(session: Session) -> None:
    first = _add(session, _infojobs(1))
    _age(session, 10)
    ingest.add_from_text(
        session, "Data Engineer", "Otra Empresa", TEXT, url=_infojobs(2), location="Vigo"
    )
    assert _reposted(session, first) is None


def test_reposted_shows_in_job_list(session: Session) -> None:
    first = _add(session, _infojobs(1))
    _age(session, 20)
    _add(session, _infojobs(2))
    [summary] = list_jobs(session)
    assert summary.id == first
    assert summary.signals.reposted is not None and summary.signals.reposted.count == 2


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
def test_connector_repost_with_new_id_is_noted(session: Session) -> None:
    source = sources.add_source(
        session, SourceInput(kind="greenhouse", name="Acme Datos", slug="acmedatos")
    )
    route = respx.get(GREENHOUSE_URL)
    route.mock(return_value=httpx.Response(200, json=_greenhouse(100)))
    first = sources.run_source(session, source.id)
    assert first.created == 1
    _age(session, 30)

    route.mock(return_value=httpx.Response(200, json=_greenhouse(200)))
    second = sources.run_source(session, source.id)
    assert (second.created, second.existing) == (0, 1)  # misma huella: ya estaba
    assert _reposted(session, first.job_ids[0]) == (2, "boards.greenhouse.io")

    # La misma publicación al día siguiente no suma.
    sources.run_source(session, source.id)
    assert _reposted(session, first.job_ids[0]) == (2, "boards.greenhouse.io")
