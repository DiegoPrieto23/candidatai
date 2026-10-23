"""Plataformas para la búsqueda con el navegador del agente (`ingestion/browse.py`, fase 09b)."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, Job, Source, SourceRun
from app.schemas.sources import AgentBrowseSource, SourceRunSummary
from app.services import ingest
from app.services.events import current_stage
from app.services.ingestion import browse, service
from app.services.pipeline import Stage
from tests.agent_support import POSTING_TEXT

TECNO: dict[str, Any] = {
    "name": "Tecnoempleo",
    "platform": "tecnoempleo",
    "search_urls": ["https://www.tecnoempleo.com/ofertas-trabajo/?te=data+engineer"],
}
LINKEDIN: dict[str, Any] = {
    "name": "LinkedIn",
    "platform": "linkedin",
    "search_urls": ["https://www.linkedin.com/jobs/search/?keywords=data"],
    "allow_agent_browsing": False,
}
TECNO_JOB = "https://www.tecnoempleo.com/data-engineer/python/rf-0a1b2c3d4e5f60718293"


def _save(session: Session, **data: Any) -> browse.SaveSourceResult:
    return browse.save_source(session, AgentBrowseSource.model_validate(data))


def _config(session: Session, source_id: int) -> dict[str, Any]:
    source = session.get(Source, source_id)
    assert source is not None
    return dict(source.config)


# --- save_source ------------------------------------------------------------------------------


def test_save_creates_with_defaults(session: Session) -> None:
    result = _save(session, **TECNO)

    assert (result.created, result.allow_agent_browsing) == (True, True)
    assert _config(session, result.source_id) == {
        "platform": "tecnoempleo",
        "search_urls": TECNO["search_urls"],
        "priority": 5,
        "access": "free",
        "allow_agent_browsing": True,
        "max_offers": 15,  # agent_browse.default_max_offers
        "notes": None,
    }
    view = service.get_source(session, result.source_id)
    assert view.kind == "agent_browse" and view.kind_label == "Búsqueda con navegador"
    assert view.browse is not None and view.browse.name == "Tecnoempleo"


def test_save_updates_by_normalized_name(session: Session) -> None:
    first = _save(session, **TECNO)
    second = _save(session, **{**TECNO, "name": "  tecnoempleo ", "priority": 1})

    assert second.source_id == first.source_id and second.created is False
    assert _config(session, first.source_id)["priority"] == 1
    assert session.get(Source, first.source_id).name == "tecnoempleo"  # type: ignore[union-attr]


@pytest.mark.parametrize(
    "data",
    [
        {**LINKEDIN, "allow_agent_browsing": True},
        {**LINKEDIN, "name": "Otra", "platform": "otra", "allow_agent_browsing": True},
        {
            **TECNO,
            "allow_agent_browsing": True,
            "search_urls": [*TECNO["search_urls"], "https://es.linkedin.com/jobs/search/?k=x"],
        },
        {**TECNO, "allow_agent_browsing": True, "search_urls": ["https://lnkd.in/abc"]},
    ],
    ids=["explicit", "disguised", "one-url", "short-link"],
)
def test_agent_cannot_enable_linkedin(session: Session, data: dict[str, Any]) -> None:
    with pytest.raises(browse.BrowsingNotAllowedError, match="LinkedIn"):
        _save(session, **data)
    assert session.scalars(select(Source)).first() is None


def test_linkedin_defaults_to_disabled(session: Session) -> None:
    data = {k: v for k, v in LINKEDIN.items() if k != "allow_agent_browsing"}
    result = _save(session, **data)
    assert result.allow_agent_browsing is False


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"search_urls": ["https://evil.example.com/empleos"]}, "no es de Tecnoempleo"),
        (
            {"platform": "welcome", "search_urls": ["https://www.infojobs.net/ofertas?q=x"]},
            "usa `platform: infojobs`",
        ),
        (
            {
                "platform": "welcome",
                "search_urls": ["https://welcome.example/a", "https://other.example/b"],
            },
            "mismo sitio",
        ),
        (
            {
                "search_urls": [*TECNO["search_urls"], "https://es.linkedin.com/jobs/search/"],
            },
            "no es de LinkedIn",  # sin `true` se trata como LinkedIn, y la otra URL sobra
        ),
    ],
    ids=["known", "other-known", "unknown-mixed", "mixed-linkedin"],
)
def test_search_urls_must_belong_to_the_platform(
    session: Session, changes: dict[str, Any], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _save(session, **{**TECNO, **changes})


def test_unknown_platform_same_site_is_fine(session: Session) -> None:
    result = _save(
        session,
        name="Welcome",
        platform="welcome",
        search_urls=["https://www.welcome.example/a", "https://welcome.example/b"],
    )
    assert result.created


def test_linkedin_platform_cannot_become_another(session: Session) -> None:
    _save(session, **LINKEDIN)
    with pytest.raises(ValueError, match="no puede pasar a ser otra"):
        _save(session, **{**TECNO, "name": "LinkedIn"})


def test_linkedin_saved_disabled_and_platform_fixed(session: Session) -> None:
    result = _save(session, **{**LINKEDIN, "platform": "otra"})

    assert result.allow_agent_browsing is False
    assert "solo el usuario" in result.message
    assert _config(session, result.source_id)["platform"] == "linkedin"


def test_agent_keeps_linkedin_enabled_by_user(session: Session) -> None:
    source_id = _save(session, **LINKEDIN).source_id
    browse.update_settings(session, source_id, allow_agent_browsing=True, confirm_risk=True)

    result = _save(session, **{**LINKEDIN, "priority": 3})

    assert result.allow_agent_browsing is True and "la activó el usuario" in result.message
    assert _config(session, source_id)["allow_agent_browsing"] is True
    assert _config(session, source_id)["priority"] == 3


@pytest.mark.parametrize(
    "changes",
    [
        {"search_urls": []},
        {"search_urls": ["javascript:alert(1)"]},
        {"platform": "Tecno Empleo"},
        {"priority": 0},
        {"access": "maybe"},
        {"max_offers": 0},
        {"extra": True},
    ],
)
def test_invalid_platform_config(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        AgentBrowseSource.model_validate({**TECNO, **changes})


# --- update_settings (UI) ---------------------------------------------------------------------


def test_user_enabling_linkedin_requires_confirmation(session: Session) -> None:
    source_id = _save(session, **LINKEDIN).source_id

    with pytest.raises(browse.BrowsingNotAllowedError, match="confirm_risk"):
        browse.update_settings(session, source_id, allow_agent_browsing=True)
    view = browse.update_settings(session, source_id, allow_agent_browsing=True, confirm_risk=True)
    assert view.browse is not None and view.browse.allow_agent_browsing is True

    # Desactivar o cambiar otra cosa no pide confirmación.
    view = browse.update_settings(session, source_id, priority=2, access="login")
    assert view.browse is not None and (view.browse.priority, view.browse.access) == (2, "login")
    view = browse.update_settings(session, source_id, allow_agent_browsing=False)
    assert view.browse is not None and view.browse.allow_agent_browsing is False


def test_user_sets_offers_per_run_and_the_agent_keeps_it(session: Session) -> None:
    source_id = _save(session, **TECNO).source_id

    view = browse.update_settings(session, source_id, max_offers=40)
    assert view.browse is not None and view.browse.max_offers == 40
    with pytest.raises(ValidationError):
        browse.update_settings(session, source_id, max_offers=101)

    # El agente vuelve a guardarla sin `max_offers`: no vuelve al valor por defecto.
    _save(session, **{**TECNO, "priority": 2})
    assert _config(session, source_id)["max_offers"] == 40
    _save(session, **{**TECNO, "max_offers": 20})
    assert _config(session, source_id)["max_offers"] == 20


def test_update_settings_only_on_platforms(session: Session) -> None:
    ingest.add_from_text(session, "Data Engineer", "Acme", POSTING_TEXT)
    manual = session.scalars(select(Source)).one()
    with pytest.raises(ValueError, match="no es una plataforma"):
        browse.update_settings(session, manual.id, priority=1)
    with pytest.raises(service.SourceNotFoundError):
        browse.update_settings(session, 99, priority=1)


# --- record_run -------------------------------------------------------------------------------


def test_record_run_stores_and_advances_last_run(session: Session) -> None:
    source_id = _save(session, **TECNO).source_id
    started = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
    finished = started + timedelta(minutes=4)
    summary = SourceRunSummary.model_validate(
        {
            "found": 12,
            "created": 3,
            "existing": 2,
            "incidents": [{"code": "captcha", "message": "Captcha en la página 2."}],
            "started_at": started,
            "finished_at": finished,
        }
    )

    result = browse.record_run(session, source_id, summary)

    run = session.get(SourceRun, result.run_id)
    assert run is not None
    assert (run.actor, run.found, run.after_filters, run.created) == ("agent", 12, 5, 3)
    assert run.errors == [{"code": "captcha", "message": "Captcha en la página 2."}]
    assert (run.started_at, run.finished_at) == (started, finished)
    assert session.get(Source, source_id).last_run_at == finished  # type: ignore[union-attr]

    view = service.get_source(session, source_id)
    assert view.last_run is not None and view.last_run.created == 3

    # Un recorrido anterior no hace retroceder `last_run_at`.
    older = SourceRunSummary(found=1, created=0, finished_at=started - timedelta(days=1))
    browse.record_run(session, source_id, older)
    assert session.get(Source, source_id).last_run_at == finished  # type: ignore[union-attr]


def test_record_run_defaults_to_now(session: Session) -> None:
    source_id = _save(session, **TECNO).source_id
    before = datetime.now(UTC)
    result = browse.record_run(session, source_id, SourceRunSummary(found=0, created=0))
    run = session.get(SourceRun, result.run_id)
    assert run is not None and run.finished_at is not None and run.finished_at >= before
    assert run.started_at == run.finished_at


def test_record_run_rejects_future_and_disabled(session: Session) -> None:
    tecno = _save(session, **TECNO).source_id
    future = datetime.now(UTC) + timedelta(days=1)
    with pytest.raises(ValueError, match="futuro"):
        browse.record_run(session, tecno, SourceRunSummary(found=0, created=0, finished_at=future))

    linkedin = _save(session, **LINKEDIN).source_id
    with pytest.raises(browse.BrowsingNotAllowedError):
        browse.record_run(session, linkedin, SourceRunSummary(found=0, created=0))


def test_run_summary_validation() -> None:
    with pytest.raises(ValidationError, match="no puede superar"):
        SourceRunSummary(found=2, created=2, existing=1)
    start = datetime(2026, 10, 1, tzinfo=UTC)
    with pytest.raises(ValidationError, match="anterior"):
        SourceRunSummary(
            found=0, created=0, started_at=start, finished_at=start - timedelta(seconds=1)
        )
    with pytest.raises(ValidationError):
        SourceRunSummary.model_validate(
            {"found": 1, "created": 0, "incidents": [{"code": "solved", "message": "x"}]}
        )


# --- add_from_text con plataforma -----------------------------------------------------------


def test_job_found_browsing_is_linked_to_the_platform(session: Session) -> None:
    source_id = _save(session, **TECNO).source_id
    source = browse.source_for_job(session, source_id, TECNO_JOB)

    result = ingest.add_from_text(
        session, "Data Engineer", "Gamma", POSTING_TEXT, url=TECNO_JOB, source=source
    )

    job = session.get(Job, result.job_id)
    assert job is not None
    assert (job.source_id, job.platform, job.external_id) == (
        source_id,
        "tecnoempleo",
        "0a1b2c3d4e5f60718293",
    )
    found = session.scalars(select(Event).where(Event.job_id == job.id)).first()
    assert found is not None and found.payload == {"source": "agent_browse", "source_id": source_id}
    assert current_stage(session, job.id) == Stage.PENDING_EXTRACTION

    # La misma oferta, encontrada otra vez (otra URL con el mismo id), no se duplica.
    again = ingest.add_from_text(
        session,
        "Data Engineer (remoto)",
        "Gamma SL",
        POSTING_TEXT,
        url=TECNO_JOB + "?utm_source=x",
        source=source,
    )
    assert (again.created, again.job_id) == (False, job.id)


def test_explicit_external_id_and_platform_from_source(session: Session) -> None:
    source_id = _save(session, **TECNO).source_id
    source = browse.source_for_job(session, source_id, None)

    result = ingest.add_from_text(
        session,
        "Data Engineer",
        "Gamma",
        POSTING_TEXT,
        url="https://empleo.example.com/o?id=7",
        source=source,
        external_id="7",
    )

    job = session.get(Job, result.job_id)
    assert job is not None and (job.platform, job.external_id) == ("tecnoempleo", "7")


def test_platform_without_matching_url_keeps_no_id(session: Session) -> None:
    result = ingest.add_from_text(
        session, "Data Engineer", "Gamma", POSTING_TEXT, url=TECNO_JOB, platform="infojobs"
    )
    job = session.get(Job, result.job_id)
    assert job is not None and (job.platform, job.external_id) == (None, None)


def test_source_for_job_guards(session: Session) -> None:
    tecno = _save(session, **TECNO).source_id
    linkedin = _save(session, **LINKEDIN).source_id
    linkedin_job = "https://www.linkedin.com/jobs/view/123456789/"

    with pytest.raises(browse.BrowsingNotAllowedError, match="solo entran"):
        browse.source_for_job(session, tecno, linkedin_job)
    with pytest.raises(browse.BrowsingNotAllowedError, match="solo entran"):
        browse.source_for_job(session, tecno, None, "linkedin")
    with pytest.raises(browse.BrowsingNotAllowedError, match="solo entran"):
        browse.source_for_job(session, tecno, "https://lnkd.in/abc")
    with pytest.raises(browse.BrowsingNotAllowedError, match="no está activada"):
        browse.source_for_job(session, linkedin, linkedin_job)

    browse.update_settings(session, linkedin, allow_agent_browsing=True, confirm_risk=True)
    assert browse.source_for_job(session, linkedin, linkedin_job).id == linkedin
