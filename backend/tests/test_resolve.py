"""Alta de una empresa por la dirección de su web de empleo (`ingestion/resolve.py` y el servicio).

Sin red: las webs y las APIs de los ATS se simulan con respx y fixtures HTML inventados."""

from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from app import cli
from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import Company, Source
from app.schemas.sources import SourceInput
from app.services import profile
from app.services.ingestion import resolve
from app.services.ingestion import service as sources
from tests.sources_support import GREENHOUSE_URL, mock_greenhouse, mock_lever

PAGES = Path(__file__).parent / "fixtures" / "careers"
CAREERS = "https://careers.acmedatos.example"
GH_BOARD = "https://boards-api.greenhouse.io/v1/boards"


def _page(name: str, url: str = f"{CAREERS}/") -> respx.Route:
    html = (PAGES / name).read_text(encoding="utf-8")
    return respx.get(url).mock(return_value=httpx.Response(200, html=html))


def _not_found_by_default() -> None:
    respx.route().mock(return_value=httpx.Response(404, json={"error": "not found"}))


@pytest.fixture
def with_profile(session: Session) -> None:
    profile.import_profile(session, profile.EXAMPLE_PATH)
    session.flush()


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resolve.time, "sleep", lambda _s: None)


# --- Direcciones de ATS ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("url", "kind", "slug", "region"),
    [
        ("https://boards.greenhouse.io/acmedatos", "greenhouse", "acmedatos", "global"),
        (
            "https://job-boards.greenhouse.io/acmedatos/jobs/123",
            "greenhouse",
            "acmedatos",
            "global",
        ),
        (
            "https://boards.greenhouse.io/embed/job_board?for=acmedatos",
            "greenhouse",
            "acmedatos",
            "global",
        ),
        ("https://jobs.lever.co/acmedatos", "lever", "acmedatos", "global"),
        ("https://jobs.eu.lever.co/acmedatos/abc", "lever", "acmedatos", "eu"),
        ("https://jobs.ashbyhq.com/acmedatos", "ashby", "acmedatos", "global"),
        ("https://acmedatos.jobs.personio.de/", "personio", "acmedatos", "global"),
        ("https://acmedatos.jobs.personio.com/job/1", "personio", "acmedatos", "global"),
        ("https://acmedatos.teamtailor.com/jobs", "teamtailor", "acmedatos", "global"),
        ("https://acmedatos.recruitee.com/o/data", "recruitee", "acmedatos", "global"),
        ("https://apply.workable.com/acmedatos/", "workable", "acmedatos", "global"),
        ("https://careers.smartrecruiters.com/AcmeDatos", "smartrecruiters", "AcmeDatos", "global"),
        (
            "https://jobs.smartrecruiters.com/AcmeDatos/123",
            "smartrecruiters",
            "AcmeDatos",
            "global",
        ),
    ],
)
def test_board_from_an_ats_url(url: str, kind: str, slug: str, region: str) -> None:
    assert resolve.board_from_url(url) == resolve.Board(kind, slug, region)


@pytest.mark.parametrize(
    "url",
    [
        "https://www.greenhouse.io/careers",
        "https://jobs.lever.co/",
        "https://www.teamtailor.com/es/",
        "https://app.recruitee.com/login",
        "https://careers.acmedatos.example/jobs",
    ],
)
def test_urls_that_are_not_a_board(url: str) -> None:
    assert resolve.board_from_url(url) is None


@respx.mock
def test_ats_url_is_resolved_without_downloading_anything() -> None:
    found = resolve.resolve("Acme Datos", "boards.greenhouse.io/acmedatos")

    assert (found.how, found.board) == ("url", resolve.Board("greenhouse", "acmedatos"))
    assert found.website is None  # el dominio del ATS no sirve para el logo
    assert not respx.calls


# --- Web de la empresa -----------------------------------------------------------------------


@respx.mock
def test_greenhouse_embedded_in_the_company_page() -> None:
    _page("greenhouse_embed.html")

    found = resolve.resolve("Acme Datos", f"{CAREERS}/")

    assert (found.how, found.board) == ("page", resolve.Board("greenhouse", "acmedatos"))
    assert found.website == "https://acmedatos.example"


@respx.mock
def test_lever_linked_picks_the_board_with_most_offers() -> None:
    _page("lever_links.html")

    found = resolve.resolve("Acme Datos", f"{CAREERS}/")

    assert found.board == resolve.Board("lever", "acmedatos")


@respx.mock
def test_ashby_embed_script_and_escaped_json() -> None:
    _page("ashby_embed.html")

    assert resolve.resolve("Acme Datos", f"{CAREERS}/").board == resolve.Board("ashby", "acmedatos")


@respx.mock
def test_company_page_that_redirects_to_its_ats() -> None:
    respx.get(f"{CAREERS}/").mock(
        return_value=httpx.Response(302, headers={"Location": "https://jobs.lever.co/acmedatos"})
    )
    respx.get("https://jobs.lever.co/acmedatos").mock(return_value=httpx.Response(200, html=""))

    found = resolve.resolve("Acme Datos", f"{CAREERS}/")

    assert (found.how, found.board) == ("page", resolve.Board("lever", "acmedatos"))


@respx.mock
def test_page_without_ats_falls_back_to_searching_by_name() -> None:
    _page("no_ats.html")
    respx.get(f"{GH_BOARD}/acmedatos").mock(
        return_value=httpx.Response(200, json={"name": "Acme Datos"})
    )
    mock_greenhouse()
    _not_found_by_default()

    found = resolve.resolve("Acme Datos", f"{CAREERS}/")

    assert (found.how, found.board) == ("search", resolve.Board("greenhouse", "acmedatos"))


@respx.mock
def test_search_also_tries_the_domain() -> None:
    """«Datos Acme» no da el slug, pero el dominio `acmedatos.example` sí."""
    _page("no_ats.html", "https://careers.acmedatos.example/")
    respx.get(f"{GH_BOARD}/acmedatos").mock(
        return_value=httpx.Response(200, json={"name": "Acme Datos"})
    )
    mock_greenhouse()
    _not_found_by_default()

    found = resolve.resolve("Acme", "https://careers.acmedatos.example/")

    assert found.board is not None and found.board.slug == "acmedatos"


@respx.mock
def test_nothing_recognizable() -> None:
    _page("no_ats.html")
    _not_found_by_default()

    found = resolve.resolve("Acme Datos", f"{CAREERS}/")

    assert (found.how, found.board) == ("none", None)


@respx.mock
def test_unreachable_page_still_searches_and_says_why() -> None:
    respx.get(f"{CAREERS}/").mock(return_value=httpx.Response(403))
    _not_found_by_default()

    found = resolve.resolve("Acme Datos", f"{CAREERS}/")

    assert found.board is None
    assert found.issues == ["La web respondió con HTTP 403."]


# --- Direcciones que no se abren ----------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/careers",
        "http://localhost:8000/",
        "http://192.168.1.10/empleo",
        "ftp://x.es",
    ],
)
def test_local_or_odd_addresses_are_rejected(url: str) -> None:
    with pytest.raises(resolve.ResolveError):
        resolve.resolve("Acme Datos", url)


def test_linkedin_is_not_a_careers_site() -> None:
    with pytest.raises(resolve.ResolveError, match="LinkedIn"):
        resolve.resolve("Acme Datos", "https://www.linkedin.com/company/acme/jobs/")


@respx.mock
def test_redirect_to_a_private_address_is_not_followed() -> None:
    respx.get(f"{CAREERS}/").mock(
        return_value=httpx.Response(302, headers={"Location": "http://192.168.1.1/admin"})
    )
    private = respx.get("http://192.168.1.1/admin").mock(return_value=httpx.Response(200))
    _not_found_by_default()

    found = resolve.resolve("Acme Datos", f"{CAREERS}/")

    assert not private.called
    assert found.board is None and found.issues


def test_domain_that_points_to_the_local_network(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import liveness

    monkeypatch.setattr(liveness, "_resolve", lambda _host: ["10.0.0.5"])
    with respx.mock:
        _not_found_by_default()
        found = resolve.resolve("Acme Datos", f"{CAREERS}/")
    assert found.issues and "local" in found.issues[0]


# --- Filtros de la dirección -------------------------------------------------------------------


def test_url_filters() -> None:
    assert resolve.url_filters(
        "https://cabify.careers/es/jobs?search=&office=Madrid&department="
    ) == (["Madrid"], [])
    assert resolve.url_filters("https://careers.datadoghq.com/madrid/") == ([], ["madrid"])
    assert resolve.url_filters("https://x.example/jobs?location=Madrid,Barcelona") == (
        ["Madrid", "Barcelona"],
        [],
    )
    # Un id no es un lugar; `/es/` y `/jobs/` tampoco.
    assert resolve.url_filters("https://x.example/es/jobs?locationId=8f3a-11") == ([], [])
    assert resolve.url_filters("https://x.example/san-sebastian/") == ([], ["san sebastian"])


def test_company_website_and_platform_id() -> None:
    assert resolve.company_website("https://careers.datadoghq.com/madrid/") == (
        "https://datadoghq.com"
    )
    assert resolve.company_website("https://cabify.careers/es/jobs") == "https://cabify.careers"
    assert resolve.company_website("https://jobs.lever.co/acme") is None
    assert resolve.platform_id("https://cabify.careers/es/jobs") == "cabify"
    assert resolve.platform_id("https://careers.datadoghq.com/") == "datadoghq"


# --- Servicio: prueba y alta -----------------------------------------------------------------


@respx.mock
def test_preview_by_url_says_what_it_found(session: Session, with_profile: None) -> None:
    _page("greenhouse_embed.html", f"{CAREERS}/?office=Vigo")
    mock_greenhouse()

    result = sources.preview_source(
        session, SourceInput(name="Acme Datos", url=f"{CAREERS}/?office=Vigo")
    )

    assert result.resolution is not None
    assert (result.resolution.how, result.resolution.kind, result.resolution.slug) == (
        "page",
        "greenhouse",
        "acmedatos",
    )
    assert result.resolution.locations == ["Vigo"]
    passing = [j.title for j in result.jobs if j.passed]
    # La remota pasa: «Solo Vigo» no quita las remotas si aceptas remoto.
    assert passing == ["Data Engineer", "Senior Data Engineer (m/f/d)"]
    assert result.after_filters == 2


@respx.mock
def test_place_in_the_path_counts_if_the_board_has_it(session: Session) -> None:
    route = mock_greenhouse()

    result = sources.preview_source(
        session,
        SourceInput(name="Acme Datos", url="https://boards.greenhouse.io/acmedatos/vigo/"),
    )

    assert result.resolution is not None and result.resolution.locations == ["Vigo"]
    assert route.call_count == 1  # lo descargado para confirmar el lugar se reutiliza
    assert [j.title for j in result.jobs if j.passed] == [
        "Data Engineer",
        "Senior Data Engineer (m/f/d)",
    ]


@respx.mock
def test_place_in_the_path_that_the_board_does_not_have_is_ignored(session: Session) -> None:
    mock_greenhouse()

    result = sources.preview_source(
        session,
        SourceInput(name="Acme Datos", url="https://boards.greenhouse.io/acmedatos/engineering"),
    )

    assert result.resolution is not None and result.resolution.locations == []
    assert result.after_filters == 5


@respx.mock
def test_add_by_url_keeps_the_address_and_the_places(session: Session) -> None:
    _page("greenhouse_embed.html", f"{CAREERS}/?office=Madrid")

    view = sources.add_source(
        session, SourceInput(name="Acme Datos", url=f"{CAREERS}/?office=Madrid")
    )

    assert view.kind == "greenhouse"
    assert view.config == {
        "slug": "acmedatos",
        "region": "global",
        "title_keywords": [],
        "website": "https://acmedatos.example",
        "careers_url": f"{CAREERS}/?office=Madrid",
        "locations": ["Madrid"],
    }
    company = session.scalars(select(Company)).one()
    assert (company.watchlist, company.ats_kind, company.ats_slug) == (
        True,
        "greenhouse",
        "acmedatos",
    )


def test_add_with_kind_and_url_does_not_resolve(session: Session) -> None:
    """Lo que manda la UI tras «Probar» o «Más opciones»: no vuelve a descargar nada."""
    view = sources.add_source(
        session,
        SourceInput(
            kind="lever",
            name="Acme Datos",
            slug="acmedatos",
            url="https://careers.acmedatos.example/madrid/",
            locations=["Madrid"],
        ),
    )
    assert view.config["careers_url"] == "https://careers.acmedatos.example/madrid/"
    assert view.config["locations"] == ["Madrid"]
    assert view.website == "https://acmedatos.example"


@respx.mock
def test_site_without_ats_becomes_a_platform_for_the_agent(session: Session) -> None:
    url = "https://acmedatos.example/empleo?office=Madrid"
    _page("no_ats.html", url)
    _not_found_by_default()

    preview = sources.preview_source(session, SourceInput(name="Acme Datos", url=url))
    assert preview.kind == "agent_browse" and preview.resolution is not None
    assert preview.resolution.how == "none"

    view = sources.add_source(session, SourceInput(name="Acme Datos", url=url))

    assert view.kind == "agent_browse"
    assert view.browse is not None
    assert (view.browse.platform, view.browse.search_urls) == ("acmedatos", [url])
    assert view.browse.allow_agent_browsing is True
    assert session.scalars(select(Company)).one().watchlist is True


def test_input_needs_a_kind_or_an_address() -> None:
    with pytest.raises(ValueError, match="url"):
        SourceInput(name="Acme Datos")
    with pytest.raises(ValueError, match="solo se usan en las empresas"):
        SourceInput(kind="infojobs", name="Datos", query="data", url="https://x.example")


# --- Lugares de una empresa ya guardada ---------------------------------------------------------


@respx.mock
def test_run_applies_the_places_of_the_source(session: Session) -> None:
    source = sources.add_source(
        session,
        SourceInput(kind="greenhouse", name="Acme Datos", slug="acmedatos", locations=["Madrid"]),
    )
    mock_greenhouse()
    respx.get(url__startswith=f"{GREENHOUSE_URL}/").mock(return_value=httpx.Response(404))

    result = sources.run_source(session, source.id)

    assert (result.found, result.after_filters) == (5, 3)  # las dos de Madrid y la remota


def test_set_locations(session: Session) -> None:
    source = sources.add_source(
        session, SourceInput(kind="lever", name="Acme Datos", slug="acmedatos")
    )
    view = sources.set_locations(session, source.id, [" Madrid ", "Madrid", "Vigo"])
    assert view.config["locations"] == ["Madrid", "Vigo"]
    view = sources.set_locations(session, source.id, [])
    assert "locations" not in view.config


def test_set_locations_only_for_companies(session: Session) -> None:
    source = sources.add_source(
        session, SourceInput(kind="manfred", name="Datos", query="data engineer")
    )
    with pytest.raises(sources.NotAConnectorError):
        sources.set_locations(session, source.id, ["Madrid"])


# --- API y CLI -------------------------------------------------------------------------------


@pytest.fixture
def client(isolated_env: Path) -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture
def db(isolated_env: Path) -> None:
    migrations.upgrade()


@respx.mock
def test_api_add_by_url_and_change_places(client: TestClient) -> None:
    response = client.post(
        "/sources", json={"name": "Acme Datos", "url": "https://jobs.lever.co/acmedatos"}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["kind"], body["config"]["slug"]) == ("lever", "acmedatos")

    response = client.post(f"/sources/{body['id']}/locations", json={"locations": ["Madrid"]})
    assert response.status_code == 200
    assert response.json()["config"]["locations"] == ["Madrid"]


def test_api_rejects_a_local_address(client: TestClient) -> None:
    response = client.post("/sources/test", json={"name": "Acme", "url": "http://127.0.0.1/"})
    assert response.status_code == 422
    assert "local" in response.json()["error"]["message"]


runner = CliRunner()


@respx.mock
def test_cli_add_and_test_by_url(db: None) -> None:
    mock_lever()
    result = runner.invoke(
        cli.app,
        ["sources", "test", "--name", "Acme Datos", "--url", "https://jobs.lever.co/acmedatos"],
    )
    assert result.exit_code == 0, result.output
    assert "Detectado: Lever · acmedatos (por la dirección)." in result.stdout

    result = runner.invoke(
        cli.app,
        [
            "sources",
            "add",
            "--name",
            "Acme Datos",
            "--url",
            "https://jobs.lever.co/acmedatos",
            "--locations",
            "Madrid",
            "--json",
        ],
    )
    assert result.exit_code == 0, result.output
    with session_scope() as session:
        source = session.scalars(select(Source)).one()
        assert source.config["locations"] == ["Madrid"]


# --- Casos de la revisión ----------------------------------------------------------------------


def test_places_keep_remote_jobs_and_apply_without_profile() -> None:
    from app.services.ingestion.prefilter import Prefilter

    prefilter = Prefilter(None, [], ["Madrid"])
    assert prefilter.check("Data Engineer", "Madrid, Spain", None).passed
    assert not prefilter.check("Data Engineer", "Vigo, Spain", None).passed
    assert prefilter.check("Data Engineer", "Remote - Spain", None).passed
    assert prefilter.check("Data Engineer", "Spain", True).passed
    assert prefilter.check("Data Engineer", None, None).passed


@respx.mock
def test_place_in_query_and_path_is_not_repeated(session: Session) -> None:
    mock_greenhouse()
    result = sources.preview_source(
        session,
        SourceInput(
            name="Acme Datos", url="https://boards.greenhouse.io/acmedatos/madrid?office=Madrid"
        ),
    )
    assert result.resolution is not None and result.resolution.locations == ["Madrid"]


def test_kind_and_url_take_the_places_of_the_address(session: Session) -> None:
    view = sources.add_source(
        session,
        SourceInput(
            kind="lever",
            name="Acme Datos",
            slug="acmedatos",
            url="https://careers.acmedatos.example/jobs?office=Madrid",
        ),
    )
    assert view.config["locations"] == ["Madrid"]


def test_address_with_credentials_is_rejected() -> None:
    with pytest.raises(ValueError, match="usuario ni contraseña"):
        SourceInput(name="Acme Datos", url="https://user:secret@careers.acmedatos.example/")


@respx.mock
def test_big_page_is_cut(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resolve, "MAX_PAGE_BYTES", 1000)
    filler = "<p>x</p>" * 500
    respx.get(f"{CAREERS}/").mock(
        return_value=httpx.Response(
            200, html=filler + '<a href="https://jobs.lever.co/acmedatos">x</a>'
        )
    )
    html, _ = resolve.fetch_html(f"{CAREERS}/", 5)
    assert len(html) <= 1000 and "lever" not in html
