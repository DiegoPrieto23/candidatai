"""Búsqueda pública de LinkedIn sin sesión (fase 22, ADR-033): apagada por defecto, límites y
corte ante bloqueo. HTML inventado en `fixtures/linkedin_public/`; sin red."""

from collections.abc import Callable, Iterator
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent_interface.tools import TOOLS_BY_NAME as TOOLS
from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import Job, Source, SourceRun, Task
from app.models.base import utcnow
from app.schemas.sources import AgentBrowseSource
from app.services import profile, tasks, worker
from app.services.events import current_stage
from app.services.ingestion import browse
from app.services.ingestion import linkedin_public as lp
from app.services.pipeline import Stage

FIXTURES = Path(__file__).parent / "fixtures" / "linkedin_public"
SEARCH = "https://es.linkedin.com/jobs/search/?keywords=Data%20Engineer&location=Galicia&f_WT=2%2C3"
SEARCH_2 = "https://www.linkedin.com/jobs/search?keywords=Analytics%20Engineer&geoId=100994331"
UI = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


def _html(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _platform(session: Session, urls: list[str] | None = None) -> int:
    result = browse.add_platform(
        session,
        AgentBrowseSource(name="LinkedIn", platform="linkedin", search_urls=urls or [SEARCH]),
    )
    return result.source_id


def _enable(session: Session, *, fetch_detail: bool = False) -> None:
    lp.update_settings(session, enabled=True, fetch_detail=fetch_detail, confirm_risk=True)


def _pages(request: httpx.Request) -> httpx.Response:
    start = request.url.params.get("start")
    body = {"0": "search_page1.html", "4": "search_page2.html"}.get(start or "")
    return httpx.Response(200, text=_html(body) if body else "")


class Sleeps(list[float]):
    def __call__(self, seconds: float) -> None:
        self.append(seconds)


@pytest.fixture
def with_profile(session: Session) -> None:
    profile.import_profile(session, profile.EXAMPLE_PATH)
    session.flush()


@pytest.fixture
def sleeps() -> Sleeps:
    return Sleeps()


@pytest.fixture
def run(session: Session, sleeps: Sleeps) -> Callable[..., lp.LinkedInPublicRunResult]:
    def _run(**kwargs: object) -> lp.LinkedInPublicRunResult:
        with lp.make_client(5) as client:
            return lp.run(session, client=client, sleep=sleeps, **kwargs)  # type: ignore[arg-type]

    return _run


@pytest.fixture
def no_network() -> Iterator[respx.Route]:
    """Cualquier petición, a donde sea, hace fallar el test."""
    with respx.mock(assert_all_called=False) as mock:
        route = mock.route().mock(side_effect=AssertionError("petición inesperada"))
        yield route


# --- Apagada por defecto -----------------------------------------------------------------------


def test_off_by_default_and_no_request_while_off(
    session: Session, no_network: respx.Route, with_profile: None
) -> None:
    _platform(session)
    view = lp.get_view(session)
    assert (view.enabled, view.fetch_detail, view.source_id) == (False, False, None)
    assert [s.keywords for s in view.searches] == ["Data Engineer"]

    with pytest.raises(browse.BrowsingNotAllowedError, match="desactivada"):
        lp.run(session)
    assert lp.due(session) is False
    assert worker.enqueue_linkedin_public(session) is False

    # Encendida y apagada de nuevo: tampoco.
    _enable(session)
    lp.update_settings(session, enabled=False)
    with pytest.raises(browse.BrowsingNotAllowedError):
        lp.run(session)
    assert worker.enqueue_linkedin_public(session) is False
    assert no_network.call_count == 0
    assert session.scalars(select(Task).where(Task.kind == "run_linkedin_public")).all() == []


def test_turning_on_requires_confirming_the_risk(session: Session) -> None:
    _platform(session)
    with pytest.raises(browse.BrowsingNotAllowedError, match="confirm_risk"):
        lp.update_settings(session, enabled=True)
    with pytest.raises(browse.BrowsingNotAllowedError, match="confirm_risk"):
        lp.update_settings(session, fetch_detail=True)
    # La descripción va con la búsqueda: no se enciende sola.
    with pytest.raises(ValueError, match="Activa antes"):
        lp.update_settings(session, fetch_detail=True, confirm_risk=True)
    # Apagar lo que nunca se encendió no crea la fuente.
    assert lp.update_settings(session, enabled=False).source_id is None

    view = lp.update_settings(session, enabled=True, confirm_risk=True)
    assert view.enabled and not view.fetch_detail and view.enabled_at is not None
    # Apagar no pide confirmación.
    assert lp.update_settings(session, enabled=False).enabled is False


def test_turning_on_needs_a_usable_search(session: Session) -> None:
    with pytest.raises(ValueError, match="ninguna búsqueda"):
        _enable(session)
    _platform(session, ["https://www.linkedin.com/jobs/collections/recommended/"])
    with pytest.raises(ValueError, match="ninguna búsqueda"):
        _enable(session)


def test_the_agent_cannot_turn_it_on(session: Session) -> None:
    # Ninguna herramienta para agentes toca esta fuente.
    assert not [name for name in TOOLS if "linkedin" in name]
    _platform(session)
    _enable(session)
    lp.update_settings(session, enabled=False)
    # Guardar la plataforma desde el agente no cambia la búsqueda pública.
    browse.save_source(
        session, AgentBrowseSource(name="LinkedIn", platform="linkedin", search_urls=[SEARCH_2])
    )
    assert lp.get_view(session).enabled is False


# --- Búsquedas ---------------------------------------------------------------------------------


def test_searches_from_the_linkedin_platform(session: Session) -> None:
    _platform(
        session,
        [
            SEARCH,
            SEARCH,  # repetida: una sola
            SEARCH_2 + "&f_TPR=r604800&trk=public_jobs&currentJobId=123",
            "https://www.linkedin.com/jobs/view/3901234567/",
            "https://www.linkedin.com/jobs/search/?f_WT=2",
        ],
    )
    view = lp.get_view(session)
    assert [s.params for s in view.searches] == [
        {"keywords": "Data Engineer", "location": "Galicia", "f_WT": "2,3", "f_TPR": "r86400"},
        {"keywords": "Analytics Engineer", "geoId": "100994331", "f_TPR": "r604800"},
    ]
    assert [i.code for i in view.ignored] == ["unusable_search", "unusable_search"]
    assert "no es una búsqueda" in view.ignored[0].message
    assert "ni palabras clave ni ubicación" in view.ignored[1].message


def test_searches_over_the_limit_are_ignored(session: Session) -> None:
    urls = [f"https://www.linkedin.com/jobs/search/?keywords=Data%20{n}" for n in range(7)]
    _platform(session, urls)
    view = lp.get_view(session)
    assert len(view.searches) == 5
    assert [i.code for i in view.ignored] == ["over_limit", "over_limit"]


# --- Ejecución ---------------------------------------------------------------------------------


@respx.mock
def test_run_stores_summaries_with_the_prefilter_and_limits(
    session: Session,
    with_profile: None,
    run: Callable[..., lp.LinkedInPublicRunResult],
    sleeps: Sleeps,
) -> None:
    _platform(session)
    _enable(session)
    route = respx.get(lp.SEARCH_URL).mock(side_effect=_pages)

    result = run()

    # Dos páginas por búsqueda como mucho, sin cookies y con el user-agent honesto.
    assert route.call_count == 2
    first = route.calls[0].request
    assert first.headers["User-Agent"] == lp.USER_AGENT and "cookie" not in first.headers
    assert dict(first.url.params) == {
        "keywords": "Data Engineer",
        "location": "Galicia",
        "f_WT": "2,3",
        "f_TPR": "r86400",
        "start": "0",
    }
    assert route.calls[1].request.url.params["start"] == "4"
    assert sleeps == [10]  # pausa entre peticiones
    assert (result.requests, result.found, result.after_filters) == (2, 5, 3)
    assert (result.created, result.summaries, result.existing, result.blocked) == (3, 3, 0, False)
    assert [e.code for e in result.errors] == ["invalid_item"]

    jobs = session.scalars(select(Job).order_by(Job.id)).all()
    assert [j.external_id for j in jobs] == ["3901234567", "3901234570", "3901234571"]
    assert all(j.platform == "linkedin" and j.detail_level == "summary" for j in jobs)
    assert jobs[0].url == "https://www.linkedin.com/jobs/view/3901234567/"
    assert all(current_stage(session, j.id) == Stage.PENDING_DETAIL for j in jobs)
    source = session.get(Source, result.source_id)
    assert source is not None and jobs[0].source_id == source.id
    run_row = session.get(SourceRun, result.run_id)
    assert run_row is not None and (run_row.found, run_row.created) == (5, 3)


@respx.mock
def test_once_a_day(
    session: Session, with_profile: None, run: Callable[..., lp.LinkedInPublicRunResult]
) -> None:
    _platform(session)
    _enable(session)
    route = respx.get(lp.SEARCH_URL).mock(side_effect=_pages)
    run()
    calls = route.call_count

    again = run()
    assert again.skipped is not None and "menos de un día" in again.skipped
    assert again.run_id is None and route.call_count == calls
    assert lp.due(session) is False
    assert lp.due(session, now=utcnow() + timedelta(hours=21)) is True

    # Pasado el día, lo ya guardado no se duplica.
    later = run(now=utcnow() + timedelta(hours=21))
    assert (later.created, later.existing) == (0, 3)


@respx.mock
def test_a_run_at_the_same_time_is_refused(
    session: Session, with_profile: None, run: Callable[..., lp.LinkedInPublicRunResult]
) -> None:
    """La reserva se hace con un commit antes de salir a la red: otra sesión que leyó el estado
    antes (el worker y «Buscar ahora» a la vez) no lanza una segunda ráfaga."""
    _platform(session)
    _enable(session)
    session.commit()
    bind = session.get_bind()
    with Session(bind) as other:
        stale = other.scalars(select(Source).where(Source.kind == lp.KIND)).one()
        assert stale.last_run_at is None
        respx.get(lp.SEARCH_URL).mock(side_effect=_pages)
        run()
        assert lp._claim(other, stale, utcnow()) is False


@respx.mock
def test_detail_only_when_enabled_and_within_its_limit(
    session: Session,
    with_profile: None,
    run: Callable[..., lp.LinkedInPublicRunResult],
    monkeypatch: pytest.MonkeyPatch,
    sleeps: Sleeps,
) -> None:
    from app.core.policies import get_policies

    monkeypatch.setattr(get_policies().linkedin_public, "max_details_per_run", 2)
    _platform(session)
    _enable(session, fetch_detail=True)
    respx.get(lp.SEARCH_URL).mock(side_effect=_pages)
    detail = respx.get(url__regex=r"/jobs-guest/jobs/api/jobPosting/\d+$").mock(
        return_value=httpx.Response(200, text=_html("detail.html"))
    )

    result = run()

    # Solo las nuevas que pasan el filtro, y hasta el límite.
    assert [str(c.request.url).rsplit("/", 1)[1] for c in detail.calls] == [
        "3901234567",
        "3901234570",
    ]
    assert len(sleeps) == result.requests - 1 == 3
    assert (result.created, result.summaries) == (3, 1)
    assert "details_skipped" in [e.code for e in result.errors]
    full = session.scalars(select(Job).where(Job.external_id == "3901234567")).one()
    assert full.detail_level == "full" and "pipelines de ingesta" in full.raw_text
    assert current_stage(session, full.id) == Stage.PENDING_EXTRACTION


def _blocking(kind: str) -> httpx.Response:
    if kind == "challenge":
        return httpx.Response(200, text=_html("challenge.html"))
    if kind == "redirect":
        return httpx.Response(302, headers={"Location": "https://www.linkedin.com/authwall"})
    return httpx.Response(int(kind))


@pytest.mark.parametrize("kind", ["429", "999", "403", "redirect", "challenge"])
@respx.mock
def test_block_stops_at_once_and_pauses_for_days(
    session: Session,
    with_profile: None,
    run: Callable[..., lp.LinkedInPublicRunResult],
    kind: str,
) -> None:
    _platform(session, [SEARCH, SEARCH_2])
    _enable(session)

    def pages(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("start") == "0" and "Data" in request.url.params["keywords"]:
            return httpx.Response(200, text=_html("search_page1.html"))
        return _blocking(kind)

    route = respx.get(lp.SEARCH_URL).mock(side_effect=pages)
    result = run()

    # Página 1 bien, página 2 bloqueada: ni una petición más (la segunda búsqueda no se lanza).
    assert route.call_count == 2 and result.requests == 2
    assert result.blocked and result.errors[-1].code == "blocked"
    assert "cortó la búsqueda" in result.message
    assert result.created == 2  # lo ya leído se guarda

    view = lp.get_view(session)
    assert view.blocked_at is not None and view.last_run is not None
    assert view.next_run_at is not None and view.next_run_at - view.blocked_at == timedelta(days=3)
    for hours in (21, 24 * 2):
        assert lp.due(session, now=utcnow() + timedelta(hours=hours)) is False
    skipped = run(now=utcnow() + timedelta(days=2))
    assert skipped.skipped is not None and "bloqueó" in skipped.skipped
    assert route.call_count == 2
    assert lp.due(session, now=utcnow() + timedelta(days=3, hours=1)) is True


@respx.mock
def test_block_on_a_detail_keeps_the_rest_as_summaries(
    session: Session, with_profile: None, run: Callable[..., lp.LinkedInPublicRunResult]
) -> None:
    _platform(session)
    _enable(session, fetch_detail=True)
    respx.get(lp.SEARCH_URL).mock(side_effect=_pages)
    detail = respx.get(url__regex=r"/jobPosting/\d+$").mock(return_value=httpx.Response(429))

    result = run()

    assert detail.call_count == 1 and result.blocked
    assert (result.created, result.summaries) == (3, 3)


@respx.mock
def test_server_error_is_a_warning_not_a_block(
    session: Session, with_profile: None, run: Callable[..., lp.LinkedInPublicRunResult]
) -> None:
    _platform(session)
    _enable(session)
    respx.get(lp.SEARCH_URL).mock(return_value=httpx.Response(503))
    result = run()
    assert not result.blocked and [e.code for e in result.errors] == ["http_error"]
    assert lp.get_view(session).blocked_at is None


@respx.mock
def test_unrecognised_page_is_reported(
    session: Session, with_profile: None, run: Callable[..., lp.LinkedInPublicRunResult]
) -> None:
    _platform(session)
    _enable(session)
    respx.get(lp.SEARCH_URL).mock(return_value=httpx.Response(200, text="<div>Nada</div>"))
    result = run()
    assert [e.code for e in result.errors] == ["page_changed"] and not result.blocked


def test_policy_floor_cannot_be_lowered() -> None:
    from pydantic import ValidationError

    from app.core.policies import LinkedInPublicPolicy

    with pytest.raises(ValidationError):
        LinkedInPublicPolicy(delay_seconds=2)
    with pytest.raises(ValidationError):
        LinkedInPublicPolicy(max_pages_per_search=5)
    with pytest.raises(ValidationError):
        LinkedInPublicPolicy(min_hours_between_runs=1)


# --- Worker ------------------------------------------------------------------------------------


@respx.mock
def test_worker_enqueues_only_when_due_and_never_retries(
    session: Session, with_profile: None
) -> None:
    _platform(session)
    assert worker.enqueue_linkedin_public(session) is False
    _enable(session)
    assert worker.enqueue_linkedin_public(session) is True
    assert "run_linkedin_public" in tasks.NO_RETRY_KINDS
    assert session.scalars(select(Task).where(Task.kind == "run_linkedin_public")).one()


# --- API ---------------------------------------------------------------------------------------


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with session_scope() as session:
        profile.import_profile(session, profile.EXAMPLE_PATH)
        _platform(session)
    with TestClient(create_app()) as client:
        yield client


def test_api_requires_the_ui_and_the_risk_confirmation(
    client: TestClient, no_network: respx.Route
) -> None:
    assert client.get("/sources/linkedin-public").json()["enabled"] is False

    url = "/sources/linkedin-public/settings"
    # Otra web abierta en el navegador no puede: otro origen o un cuerpo que no es JSON.
    plain = {"Content-Type": "text/plain"}
    body = '{"enabled": true, "confirm_risk": true}'
    assert client.post(url, content=body, headers=plain).status_code == 403
    other = {**UI, "Origin": "http://evil.example"}
    assert (
        client.post(url, json={"enabled": True, "confirm_risk": True}, headers=other).status_code
        == 403
    )
    no_confirm = client.post(url, json={"enabled": True}, headers=UI)
    assert no_confirm.status_code == 403 and no_confirm.json()["error"]["type"] == "not_allowed"

    off_run = client.post("/sources/linkedin-public/run", json={}, headers=UI)
    assert off_run.status_code == 403 and off_run.json()["error"]["type"] == "not_allowed"

    on = client.post(url, json={"enabled": True, "confirm_risk": True}, headers=UI)
    assert on.status_code == 200 and on.json()["enabled"] is True
    assert on.json()["limits"]["delay_seconds"] == 10
    assert no_network.call_count == 0


# --- CLI ---------------------------------------------------------------------------------------


def test_cli_status_and_run_while_off(isolated_env: Path, no_network: respx.Route) -> None:
    import json

    from typer.testing import CliRunner

    from app import cli

    migrations.upgrade()
    with session_scope() as session:
        _platform(session)
    runner = CliRunner()
    status = runner.invoke(cli.app, ["sources", "linkedin-public", "status", "--json"])
    assert status.exit_code == 0, status.output
    assert json.loads(status.output)["enabled"] is False

    ran = runner.invoke(cli.app, ["sources", "linkedin-public", "run", "--json"])
    assert ran.exit_code == 1
    assert json.loads(ran.output)["error"]["type"] == "not_allowed"
    assert no_network.call_count == 0
