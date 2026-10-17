"""Conectores de la fase 25.1 (Personio, Teamtailor, Workable, SmartRecruiters, Recruitee,
Manfred y freehire) con respuestas grabadas: forma real, contenido inventado. Sin red: respx."""

from collections.abc import Iterator
from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.schemas.sources import AtsConfig, FreehireConfig, ManfredConfig
from app.services.ingestion import freehire, smartrecruiters, teamtailor
from app.services.ingestion.base import ConnectorError, make_client
from app.services.ingestion.freehire import FreehireConnector
from app.services.ingestion.manfred import ManfredConnector, matches
from app.services.ingestion.personio import PersonioConnector
from app.services.ingestion.recruitee import RecruiteeConnector
from app.services.ingestion.smartrecruiters import SmartRecruitersConnector
from app.services.ingestion.teamtailor import TeamtailorConnector
from app.services.ingestion.workable import WorkableConnector
from tests.sources_support import (
    FREEHIRE_URL,
    MANFRED_JOB_URL,
    MANFRED_URL,
    PERSONIO_URL,
    RECRUITEE_URL,
    SMARTRECRUITERS_URL,
    TEAMTAILOR_URL,
    WORKABLE_JOB_URL,
    WORKABLE_URL,
    load,
    load_text,
    mock_personio,
    mock_smartrecruiters,
    mock_teamtailor,
)

ATS = AtsConfig(slug="acmedatos")


@pytest.fixture
def client() -> Iterator[httpx.Client]:
    with make_client(5) as c:
        yield c


def _not_found(url: str, connector: object, config: object, client: httpx.Client) -> str:
    respx.get(url).mock(return_value=httpx.Response(404, text="Not Found"))
    with pytest.raises(ConnectorError) as exc:
        connector.fetch("Acme Datos", config, client)  # type: ignore[attr-defined]
    assert exc.value.code == "not_found"
    return exc.value.message


# --- Personio ----------------------------------------------------------------------------------


@respx.mock
def test_personio_parses_the_xml_feed(client: httpx.Client) -> None:
    route = mock_personio()
    result = PersonioConnector().fetch("Acme Datos", ATS, client)

    assert route.calls.last.request.url.params["language"] == "es"
    assert [j.external_id for j in result.jobs] == ["1834171", "1834172"]
    first = result.jobs[0]
    assert (first.title, first.company, first.location) == (
        "Data Engineer",
        "Acme Datos",
        "Vigo, A Coruña",
    )
    assert first.url == "https://acmedatos.jobs.personio.de/job/1834171"
    assert first.text.startswith("El puesto\n\nEn Acme Datos construimos pipelines de datos.")
    assert "- Python y SQL\n- Airflow" in first.text
    assert "Contrato: permanent, full-time, experienced (2-5 años de experiencia)" in first.text
    assert "<strong>pipelines de datos</strong>" in (first.html or "")
    assert first.posted_at == datetime(2026, 9, 29, 13, 0, tzinfo=UTC)
    assert first.remote is None and result.jobs[1].remote is True  # «Remote Spain»
    # La posición sin título se salta con un aviso y el resto sigue.
    assert [(i.code, i.item) for i in result.issues] == [("invalid_item", "1834173")]


@respx.mock
def test_personio_tries_english_when_spanish_has_no_descriptions(client: httpx.Client) -> None:
    def by_language(request: httpx.Request) -> httpx.Response:
        name = (
            "personio_feed.xml"
            if request.url.params["language"] == "en"
            else "personio_feed_no_descriptions.xml"
        )
        return httpx.Response(200, text=load_text(name))

    route = respx.get(PERSONIO_URL).mock(side_effect=by_language)
    result = PersonioConnector().fetch("Acme Datos", ATS, client)
    assert [c.request.url.params["language"] for c in route.calls] == ["es", "en"]
    assert "pipelines de datos" in result.jobs[0].text


@respx.mock
def test_personio_without_descriptions_keeps_the_metadata(client: httpx.Client) -> None:
    mock_personio("personio_feed_no_descriptions.xml")
    config = AtsConfig(slug="acmedatos", language="de")
    [job] = PersonioConnector().fetch("Acme Datos", config, client).jobs
    assert job.text == (
        "Departamento: Product and Tech\n\n"
        "Contrato: permanent, full-time, experienced (2-5 años de experiencia)"
    )
    assert job.html is None


@respx.mock
def test_personio_unknown_company_and_bad_xml(client: httpx.Client) -> None:
    message = _not_found(PERSONIO_URL, PersonioConnector(), ATS, client)
    assert "acmedatos" in message and ".jobs.personio.de" in message

    respx.get(PERSONIO_URL).mock(return_value=httpx.Response(200, text="<html><body>hola"))
    with pytest.raises(ConnectorError) as exc:
        PersonioConnector().fetch("Acme Datos", ATS, client)
    assert exc.value.code == "unexpected_format"


@respx.mock
def test_personio_does_not_expand_external_entities(client: httpx.Client) -> None:
    xml = (
        '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]>'
        "<workzag-jobs><position><id>1</id><name>Data &e; Engineer</name>"
        "<createdAt>2026-09-29T13:00:00+00:00</createdAt></position></workzag-jobs>"
    )
    respx.get(PERSONIO_URL).mock(return_value=httpx.Response(200, text=xml))
    result = PersonioConnector().fetch(
        "Acme Datos", AtsConfig(slug="acmedatos", language="es"), client
    )
    assert "root:" not in (result.jobs[0].title if result.jobs else "")


# --- Teamtailor --------------------------------------------------------------------------------


@respx.mock
def test_teamtailor_parses_the_rss(client: httpx.Client) -> None:
    route = mock_teamtailor()
    result = TeamtailorConnector().fetch("Acme Datos", ATS, client)

    assert route.calls.last.request.url.params["per_page"] == "100"
    assert [j.title for j in result.jobs] == ["Data Engineer", "Analytics Engineer"]
    first = result.jobs[0]
    assert first.external_id == "4ff07fd5-3ac0-4333-8f4c-acmedatos0001"
    assert first.url == "https://acmedatos.teamtailor.com/jobs/8118064-data-engineer"
    assert first.location == "Vigo, Spain; A Coruña, Spain"
    assert first.text == (
        "En Acme Datos construimos pipelines de datos.\n\n- Python y SQL\n- Airflow"
    )
    assert "<strong>" in (first.html or "")
    assert first.posted_at == datetime(2026, 9, 29, 13, 0, tzinfo=UTC)
    assert first.remote is None and result.jobs[1].remote is True  # `remoteStatus: fully`
    # El enlace `javascript:` no es una URL http(s): se salta.
    assert [(i.code, i.item) for i in result.issues] == [
        ("invalid_item", "4ff07fd5-3ac0-4333-8f4c-acmedatos0003")
    ]


@respx.mock
def test_teamtailor_paginates(client: httpx.Client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(teamtailor, "PAGE_SIZE", 3)
    rss = load_text("teamtailor_jobs.rss")

    def page(request: httpx.Request) -> httpx.Response:
        offset = request.url.params["offset"]
        if offset == "3":  # la segunda página: otras ofertas (otro guid), y se acaba
            return httpx.Response(200, text=rss.replace("acmedatos0001", "acmedatos0011"))
        return httpx.Response(200, text=rss)

    route = respx.get(TEAMTAILOR_URL).mock(side_effect=page)
    result = TeamtailorConnector().fetch("Acme Datos", ATS, client)
    # Página 3 = la 1 otra vez: nada nuevo, se para sin repetir ofertas.
    assert [c.request.url.params["offset"] for c in route.calls] == ["0", "3", "6"]
    assert [j.external_id[-4:] for j in result.jobs] == ["0001", "0002", "0011"]


@respx.mock
def test_teamtailor_feed_that_ignores_pagination_is_not_repeated(
    client: httpx.Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(teamtailor, "PAGE_SIZE", 3)
    route = mock_teamtailor()  # siempre los mismos 3 ítems
    result = TeamtailorConnector().fetch("Acme Datos", ATS, client)
    assert len(route.calls) == 2
    assert len(result.jobs) == 2


@respx.mock
def test_teamtailor_unknown_company(client: httpx.Client) -> None:
    message = _not_found(TEAMTAILOR_URL, TeamtailorConnector(), ATS, client)
    assert ".teamtailor.com" in message


# --- Workable ----------------------------------------------------------------------------------


@respx.mock
def test_workable_lists_and_completes_the_detail(client: httpx.Client) -> None:
    respx.get(WORKABLE_URL).mock(
        return_value=httpx.Response(200, json=load("workable_widget.json"))
    )
    respx.get(WORKABLE_JOB_URL).mock(
        return_value=httpx.Response(200, json=load("workable_job.json"))
    )
    connector = WorkableConnector()
    result = connector.fetch("Acme Datos", ATS, client)

    assert [j.external_id for j in result.jobs] == ["186545F8C1", "186545F8C2"]
    first = result.jobs[0]
    assert first.needs_detail and first.text == ""
    assert first.location == "Vigo, Spain"  # la sede oculta no se enseña
    assert first.url == "https://apply.workable.com/j/186545F8C1"
    assert result.jobs[1].remote is True and result.jobs[1].location == "Spain"
    assert [(i.code, i.item) for i in result.issues] == [("invalid_item", "2")]  # `../../x`

    job = connector.complete(first, client)
    assert not job.needs_detail
    assert job.text.startswith("En Acme Datos construimos pipelines de datos.")
    assert "Requisitos\n\n- Python y SQL\n- Airflow" in job.text
    assert "Beneficios\n\n- Formación" in job.text
    assert "<h3>Requisitos</h3>" in (job.html or "")


@respx.mock
def test_workable_unknown_account_and_missing_detail(client: httpx.Client) -> None:
    message = _not_found(WORKABLE_URL, WorkableConnector(), ATS, client)
    assert "apply.workable.com/" in message

    respx.get(WORKABLE_URL).mock(
        return_value=httpx.Response(200, json=load("workable_widget.json"))
    )
    respx.get(WORKABLE_JOB_URL).mock(return_value=httpx.Response(404, text="Not Found"))
    connector = WorkableConnector()
    job = connector.fetch("Acme Datos", ATS, client).jobs[0]
    with pytest.raises(ConnectorError) as exc:
        connector.complete(job, client)
    assert exc.value.code == "not_found" and "186545F8C1" in exc.value.message


# --- SmartRecruiters ---------------------------------------------------------------------------


@respx.mock
def test_smartrecruiters_paginates_and_completes(
    client: httpx.Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(smartrecruiters, "PAGE_SIZE", 2)
    route = mock_smartrecruiters()
    connector = SmartRecruitersConnector()
    result = connector.fetch("Acme Datos", ATS, client)

    assert [c.request.url.params["offset"] for c in route.calls] == ["0", "2"]
    assert [j.title for j in result.jobs] == [
        "Data Engineer",
        "Analytics Engineer",
        "Office Manager",
    ]
    assert [(i.code, i.item) for i in result.issues] == [("invalid_item", "744000156074004")]
    first = result.jobs[0]
    assert first.url == "https://jobs.smartrecruiters.com/acmedatos/744000156074001"
    assert (first.location, first.remote) == ("Vigo, ES", None)
    assert result.jobs[1].remote is True
    assert first.posted_at == datetime(2026, 9, 29, 13, 0, tzinfo=UTC)

    job = connector.complete(first, client)
    assert job.text.startswith("Job Description\n\nConstruirás pipelines de datos.")
    assert "Qualifications\n\n- Python y SQL\n- Airflow" in job.text
    assert "Company Description" in job.text and "Videos" not in job.text


@respx.mock
def test_smartrecruiters_unknown_company_warns_without_failing(client: httpx.Client) -> None:
    # SmartRecruiters no da 404 a una empresa que no existe: devuelve una lista vacía.
    respx.get(SMARTRECRUITERS_URL).mock(
        return_value=httpx.Response(
            200, json={"offset": 0, "limit": 100, "totalFound": 0, "content": []}
        )
    )
    result = SmartRecruitersConnector().fetch("Acme Datos", ATS, client)
    assert result.jobs == []
    [issue] = result.issues
    assert issue.code == "empty" and "jobs.smartrecruiters.com/" in issue.message


# --- Recruitee ---------------------------------------------------------------------------------


@respx.mock
def test_recruitee_parses_offers(client: httpx.Client) -> None:
    respx.get(RECRUITEE_URL).mock(
        return_value=httpx.Response(200, json=load("recruitee_offers.json"))
    )
    result = RecruiteeConnector().fetch("Acme Datos", ATS, client)

    assert [j.external_id for j in result.jobs] == ["2783543", "2783544"]  # sin la cerrada
    first = result.jobs[0]
    assert first.url == "https://acmedatos.recruitee.com/o/data-engineer"
    assert first.location == "Vigo, Galicia, Spain"
    assert first.text == (
        "En Acme Datos construimos pipelines de datos.\n\nRequisitos\n\n- Python y SQL\n- Airflow"
    )
    assert first.posted_at == datetime(2026, 9, 29, 9, 31, 36, tzinfo=UTC)
    assert result.jobs[1].remote is True
    assert [(i.code, i.item) for i in result.issues] == [("invalid_item", "2783546")]


@respx.mock
def test_recruitee_unknown_company(client: httpx.Client) -> None:
    message = _not_found(RECRUITEE_URL, RecruiteeConnector(), ATS, client)
    assert ".recruitee.com" in message


# --- Manfred -----------------------------------------------------------------------------------


def test_manfred_query_matches_titles() -> None:
    assert matches("data engineer", "Senior Data Engineer (Python)")
    assert not matches("data engineer", "Data Analyst")
    assert matches("analista, data engineer", "Analista BI")
    assert matches("ingeniería", "Ingenieria de datos")  # sin tildes


@respx.mock
def test_manfred_filters_by_query_and_completes(client: httpx.Client) -> None:
    route = respx.get(MANFRED_URL).mock(
        return_value=httpx.Response(200, json=load("manfred_offers.json"))
    )
    respx.get(MANFRED_JOB_URL).mock(
        return_value=httpx.Response(200, json=load("manfred_offer.json"))
    )
    connector = ManfredConnector()
    result = connector.fetch("Manfred", ManfredConfig(query="data engineer"), client)

    assert route.calls.last.request.url.params["lang"] == "ES"
    assert [j.external_id for j in result.jobs] == ["8510", "8511"]  # ni Frontend ni la cerrada
    first = result.jobs[0]
    assert (first.company, first.location, first.remote) == ("Acme Datos", "Vigo, España", None)
    assert first.url == (
        "https://www.getmanfred.com/ofertas-empleo/8510/acme-datos-data-engineer-oct26"
    )
    assert result.jobs[1].remote is True  # 100 % remoto
    assert first.text == "Salario: 40000–50000 €"
    assert [(i.code, i.item) for i in result.issues] == [("invalid_item", "8514")]

    job = connector.complete(first, client)
    assert job.text.startswith("## Introducción\n\n¿Te gustan los **datos**?")
    assert "## Responsabilidades\n\n- Construir pipelines con Airflow" in job.text
    assert "- Python (imprescindible, advanced)" in job.text
    assert "Salario: 40000–50000 €" in job.text
    # El «scout» de Manfred nunca entra en la oferta.
    assert "Ficticio" not in job.text and "scout@example.com" not in job.text


@respx.mock
def test_manfred_in_english_keeps_the_listed_salary(client: httpx.Client) -> None:
    respx.get(MANFRED_URL).mock(return_value=httpx.Response(200, json=load("manfred_offers.json")))
    detail = load("manfred_offer.json")
    del detail["salaryTo"]  # el detalle no trae salario: vale el del listado
    respx.get(MANFRED_JOB_URL).mock(return_value=httpx.Response(200, json=detail))
    connector = ManfredConnector()
    config = ManfredConfig(query="data engineer", lang="EN")
    first = connector.fetch("Manfred", config, client).jobs[0]
    assert first.url.startswith("https://www.getmanfred.com/en/job-offers/8510/")
    assert first.text == "Salary: 40000–50000 €"

    job = connector.complete(first, client)
    assert job.text.startswith("## Introduction\n\n")
    assert "## What they ask for" in job.text and "- Python (required, advanced)" in job.text
    assert job.text.endswith("Salary: 40000–50000 €")


@respx.mock
def test_manfred_unexpected_format(client: httpx.Client) -> None:
    respx.get(MANFRED_URL).mock(return_value=httpx.Response(200, json={"offers": []}))
    with pytest.raises(ConnectorError) as exc:
        ManfredConnector().fetch("Manfred", ManfredConfig(query="data"), client)
    assert exc.value.code == "unexpected_format"


# --- freehire ----------------------------------------------------------------------------------


@respx.mock
def test_freehire_searches_titles_in_the_country(client: httpx.Client) -> None:
    route = respx.get(FREEHIRE_URL).mock(
        return_value=httpx.Response(200, json=load("freehire_search.json"))
    )
    config = FreehireConfig(query="data engineer", remote_only=True)
    result = FreehireConnector().fetch("freehire", config, client)

    params = route.calls.last.request.url.params
    assert params["q"] == '"data engineer"' and params["q_fields"] == "title"
    assert (params["countries"], params["work_mode"], params["offset"]) == ("ES", "remote", "0")
    assert [j.company for j in result.jobs] == ["Acme Datos", "Beta Software"]  # sin la cerrada
    first = result.jobs[0]
    assert first.external_id == "data-engineer-acme-datos-1a2b"
    assert first.url == "https://boards.greenhouse.io/acmedatos/jobs/1001"
    assert first.text == "Overview\nConstruirás pipelines de datos."
    assert result.jobs[1].remote is True
    assert [i.code for i in result.issues] == ["invalid_item"]


@respx.mock
def test_freehire_paginates_and_uses_the_configured_base_url(
    client: httpx.Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAI_FREEHIRE_BASE_URL", "https://freehire.example/api/v1/")
    get_settings.cache_clear()
    monkeypatch.setattr(freehire, "PAGE_SIZE", 4)
    data = load("freehire_search.json") | {"meta": {"total": 6, "limit": 4, "offset": 0}}
    route = respx.get("https://freehire.example/api/v1/agent/jobs/search").mock(
        return_value=httpx.Response(200, json=data)
    )
    try:
        FreehireConnector().fetch("freehire", FreehireConfig(query="python"), client)
    finally:
        get_settings.cache_clear()
    assert [c.request.url.params["offset"] for c in route.calls] == ["0", "4"]
    assert route.calls.last.request.url.params["q"] == "python"
    assert "work_mode" not in route.calls.last.request.url.params


@respx.mock
def test_freehire_error_message(client: httpx.Client) -> None:
    respx.get(FREEHIRE_URL).mock(return_value=httpx.Response(503, json={"error": "busy"}))
    with pytest.raises(ConnectorError) as exc:
        FreehireConnector().fetch("freehire", FreehireConfig(query="python"), client)
    assert exc.value.code == "http_error" and "freehire" in exc.value.message
