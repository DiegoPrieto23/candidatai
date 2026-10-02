"""Conectores de ATS y portales con respuestas grabadas (inventadas). Sin red: respx."""

import base64
from collections.abc import Iterator
from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.schemas.sources import AdzunaConfig, AtsConfig, InfoJobsConfig
from app.services.ingestion.adzuna import AdzunaConnector
from app.services.ingestion.ashby import AshbyConnector
from app.services.ingestion.base import (
    ConnectorError,
    MissingKeysError,
    html_fragment_to_text,
    make_client,
    parse_datetime,
)
from app.services.ingestion.greenhouse import GreenhouseConnector
from app.services.ingestion.infojobs import InfoJobsConnector
from app.services.ingestion.lever import LeverConnector
from tests.sources_support import (
    ADZUNA_URL,
    ASHBY_URL,
    GREENHOUSE_URL,
    INFOJOBS_DETAIL_URL,
    INFOJOBS_SEARCH_URL,
    LEVER_EU_URL,
    load,
    mock_ashby,
    mock_greenhouse,
    mock_lever,
)

ATS = AtsConfig(slug="acmedatos")


@pytest.fixture
def client() -> Iterator[httpx.Client]:
    with make_client(5) as c:
        yield c


# --- Greenhouse ------------------------------------------------------------------------------


@respx.mock
def test_greenhouse_parses_jobs_and_unescapes_content(client: httpx.Client) -> None:
    route = mock_greenhouse()
    result = GreenhouseConnector().fetch("Acme Datos", ATS, client)

    assert route.calls.last.request.url.params["content"] == "true"
    assert [j.external_id for j in result.jobs] == ["1001", "1002", "1003", "1004", "1006"]
    first = result.jobs[0]
    assert first.title == "Data Engineer"
    assert first.company == "Acme Datos"
    assert first.location == "Vigo, Spain"
    assert first.url == "https://boards.greenhouse.io/acmedatos/jobs/1001"
    assert first.text.startswith("En Acme Datos construimos pipelines de datos.")
    assert "- Python y SQL\n- Airflow" in first.text
    assert "&lt;" not in (first.html or "") and "<p>" in (first.html or "")
    assert first.posted_at == datetime(2026, 9, 29, 13, 0, tzinfo=UTC)
    assert result.jobs[1].remote is True  # «Remote - Spain»
    # La oferta sin título se salta con un aviso y el resto sigue.
    assert [(i.code, i.item) for i in result.issues] == [("invalid_item", "1005")]
    assert "title" in result.issues[0].message


@respx.mock
def test_greenhouse_unknown_board_is_a_clear_error(client: httpx.Client) -> None:
    mock_greenhouse(data={"status": 404, "error": "Job not found"}, status=404)
    with pytest.raises(ConnectorError) as exc:
        GreenhouseConnector().fetch("Acme Datos", ATS, client)
    assert exc.value.code == "not_found"
    assert "acmedatos" in exc.value.message and "slug" in exc.value.message


@pytest.mark.parametrize(
    ("status", "code"),
    [(500, "http_error"), (503, "http_error"), (429, "rate_limited"), (403, "unauthorized")],
)
@respx.mock
def test_http_errors_become_connector_errors(client: httpx.Client, status: int, code: str) -> None:
    mock_greenhouse(data={}, status=status)
    with pytest.raises(ConnectorError) as exc:
        GreenhouseConnector().fetch("Acme Datos", ATS, client)
    assert exc.value.code == code


@respx.mock
def test_timeout_and_network_errors(client: httpx.Client) -> None:
    respx.get(GREENHOUSE_URL).mock(side_effect=httpx.ReadTimeout("lento"))
    with pytest.raises(ConnectorError) as exc:
        GreenhouseConnector().fetch("Acme Datos", ATS, client)
    assert exc.value.code == "timeout"

    respx.get(GREENHOUSE_URL).mock(side_effect=httpx.ConnectError("sin red"))
    with pytest.raises(ConnectorError) as exc:
        GreenhouseConnector().fetch("Acme Datos", ATS, client)
    assert exc.value.code == "network"


@pytest.mark.parametrize("body", [{"jobs": "no"}, {"otra": []}, [], "texto"])
@respx.mock
def test_greenhouse_unexpected_json(client: httpx.Client, body: object) -> None:
    mock_greenhouse(data=body)
    with pytest.raises(ConnectorError) as exc:
        GreenhouseConnector().fetch("Acme Datos", ATS, client)
    assert exc.value.code == "unexpected_format"
    assert "API haya cambiado" in exc.value.message


@respx.mock
def test_not_json_at_all(client: httpx.Client) -> None:
    respx.get(GREENHOUSE_URL).mock(return_value=httpx.Response(200, text="<html>hola</html>"))
    with pytest.raises(ConnectorError) as exc:
        GreenhouseConnector().fetch("Acme Datos", ATS, client)
    assert exc.value.code == "unexpected_format"


# --- Lever -----------------------------------------------------------------------------------


@respx.mock
def test_lever_parses_postings(client: httpx.Client) -> None:
    route = mock_lever()
    result = LeverConnector().fetch("Acme Datos", ATS, client)

    assert route.calls.last.request.url.params["mode"] == "json"
    assert [j.title for j in result.jobs] == [
        "Data Engineer",
        "Analytics Engineer",
        "Office Manager",
    ]
    first = result.jobs[0]
    assert first.external_id == "5f1c2b9e-0001-4a6b-9c1d-acmedatos0001"
    assert first.location == "A Coruña"
    assert first.url.startswith("https://jobs.lever.co/acmedatos/")
    assert "Requisitos\n\n- Python\n- SQL\n- Airflow" in first.text
    assert first.text.endswith("Contrato indefinido.")
    assert first.posted_at == datetime(2025, 10, 1, 10, 0, tzinfo=UTC)
    assert first.remote is None and result.jobs[1].remote is True
    assert [i.code for i in result.issues] == ["invalid_item"]  # el texto suelto


@respx.mock
def test_lever_eu_region_and_404(client: httpx.Client) -> None:
    mock_lever(url=LEVER_EU_URL)
    result = LeverConnector().fetch("Acme Datos", AtsConfig(slug="acmedatos", region="eu"), client)
    assert len(result.jobs) == 3

    mock_lever(data={"ok": False}, status=404)
    with pytest.raises(ConnectorError) as exc:
        LeverConnector().fetch("Acme Datos", ATS, client)
    assert exc.value.code == "not_found" and "región `eu`" in exc.value.message


@respx.mock
def test_lever_expects_a_list(client: httpx.Client) -> None:
    mock_lever(data={"postings": []})
    with pytest.raises(ConnectorError, match="lista de ofertas"):
        LeverConnector().fetch("Acme Datos", ATS, client)


# --- Ashby -----------------------------------------------------------------------------------


@respx.mock
def test_ashby_skips_unlisted_and_falls_back_to_url_id(client: httpx.Client) -> None:
    mock_ashby()
    result = AshbyConnector().fetch("Acme Datos", ATS, client)

    assert [j.title for j in result.jobs] == ["Data Engineer", "Data Analyst"]
    assert result.jobs[0].external_id == "8d1f6a50-aaaa-4c3e-9f00-acmedatos0001"
    assert result.jobs[1].external_id == "0b7e2c11-bbbb-4c3e-9f00-acmedatos0002"
    assert result.jobs[1].remote is True
    assert result.jobs[1].text == "Cuadros de mando y SQL."  # sin texto plano: desde el HTML
    assert result.issues == []


@respx.mock
def test_ashby_unexpected_json_and_404(client: httpx.Client) -> None:
    mock_ashby(data={"apiVersion": "1"})
    with pytest.raises(ConnectorError, match="`jobs`"):
        AshbyConnector().fetch("Acme Datos", ATS, client)
    respx.get(ASHBY_URL).mock(return_value=httpx.Response(404, json={}))
    with pytest.raises(ConnectorError) as exc:
        AshbyConnector().fetch("Acme Datos", ATS, client)
    assert exc.value.code == "not_found"


# --- InfoJobs --------------------------------------------------------------------------------


@pytest.fixture
def infojobs_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JH_INFOJOBS_CLIENT_ID", "id-demo")
    monkeypatch.setenv("JH_INFOJOBS_CLIENT_SECRET", "secreto-demo")
    get_settings.cache_clear()


def test_infojobs_without_keys_is_skipped(client: httpx.Client) -> None:
    with pytest.raises(MissingKeysError, match="JH_INFOJOBS_CLIENT_ID"):
        InfoJobsConnector().fetch("InfoJobs", InfoJobsConfig(query="data engineer"), client)


@respx.mock
def test_infojobs_search_and_detail(client: httpx.Client, infojobs_keys: None) -> None:
    search = respx.get(INFOJOBS_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=load("infojobs_search.json"))
    )
    detail = respx.get(INFOJOBS_DETAIL_URL).mock(
        return_value=httpx.Response(200, json=load("infojobs_offer.json"))
    )
    config = InfoJobsConfig(query="data engineer", province="a-coruna")
    connector = InfoJobsConnector()
    result = connector.fetch("InfoJobs", config, client)

    request = search.calls.last.request
    expected = base64.b64encode(b"id-demo:secreto-demo").decode()
    assert request.headers["Authorization"] == f"Basic {expected}"
    assert request.url.params["q"] == "data engineer"
    assert request.url.params["province"] == "a-coruna"
    assert request.url.params["sinceDate"] == "_7_DAYS"
    job = result.jobs[0]
    assert (job.company, job.location, job.needs_detail) == (
        "Datos Gallegos Demo",
        "A Coruña",
        True,
    )
    assert result.jobs[1].location == "Ferrol, A Coruña"

    completed = connector.complete(job, client)
    assert detail.called
    assert completed.needs_detail is False
    assert "Buscamos Data Engineer" in completed.text and "Experiencia con dbt." in completed.text


@respx.mock
def test_infojobs_bad_keys(client: httpx.Client, infojobs_keys: None) -> None:
    respx.get(INFOJOBS_SEARCH_URL).mock(return_value=httpx.Response(401))
    with pytest.raises(ConnectorError) as exc:
        InfoJobsConnector().fetch("InfoJobs", InfoJobsConfig(query="x"), client)
    assert exc.value.code == "unauthorized" and "claves" in exc.value.message


# --- Adzuna ----------------------------------------------------------------------------------


def test_adzuna_without_keys_is_skipped(client: httpx.Client) -> None:
    with pytest.raises(MissingKeysError, match="JH_ADZUNA_APP_ID"):
        AdzunaConnector().fetch("Adzuna", AdzunaConfig(query="data"), client)


@respx.mock
def test_adzuna_search(client: httpx.Client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JH_ADZUNA_APP_ID", "app-demo")
    monkeypatch.setenv("JH_ADZUNA_APP_KEY", "key-demo")
    get_settings.cache_clear()
    route = respx.get(ADZUNA_URL).mock(
        return_value=httpx.Response(200, json=load("adzuna_search.json"))
    )
    result = AdzunaConnector().fetch(
        "Adzuna", AdzunaConfig(query="data engineer", where="Vigo"), client
    )

    params = route.calls.last.request.url.params
    assert (params["app_id"], params["what"], params["where"]) == (
        "app-demo",
        "data engineer",
        "Vigo",
    )
    assert [j.title for j in result.jobs] == ["Data Engineer"]  # sin <strong>
    assert result.jobs[0].company == "Mar de Datos Demo"
    assert [i.code for i in result.issues] == ["invalid_item"]  # sin empresa


# --- Utilidades ------------------------------------------------------------------------------


def test_html_fragment_to_text_keeps_structure() -> None:
    text = html_fragment_to_text("<h2>Qué harás</h2><ul><li>Uno</li><li>Dos</li></ul><p>Fin</p>")
    assert text == "Qué harás\n\n- Uno\n- Dos\nFin"
    assert html_fragment_to_text("") == ""
    assert html_fragment_to_text("<script>alert(1)</script>Hola") == "Hola"


def test_parse_datetime_variants() -> None:
    assert parse_datetime("2026-09-30T08:00:00Z") == datetime(2026, 9, 30, 8, tzinfo=UTC)
    assert parse_datetime("2026-09-30T08:00:00") == datetime(2026, 9, 30, 8, tzinfo=UTC)
    assert parse_datetime(1759312800000) == datetime(2025, 10, 1, 10, tzinfo=UTC)
    assert parse_datetime("ayer") is None
    assert parse_datetime(None) is None
    assert parse_datetime(True) is None
