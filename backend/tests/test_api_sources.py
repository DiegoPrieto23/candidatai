"""API de fuentes (`/sources`) para la página «Dónde buscar → Empresas objetivo» de la UI."""

from collections.abc import Iterator

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.services import profile
from tests.sources_support import GREENHOUSE_URL, mock_greenhouse

BODY = {"kind": "greenhouse", "name": "Acme Datos", "slug": "acmedatos"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with session_scope() as session:
        profile.import_profile(session, profile.EXAMPLE_PATH)
    with TestClient(create_app()) as client:
        yield client


def test_add_and_list(client: TestClient) -> None:
    created = client.post("/sources", json=BODY)
    assert created.status_code == 201
    assert created.json()["config"]["slug"] == "acmedatos"
    listed = client.get("/sources").json()["sources"]
    assert [s["name"] for s in listed] == ["Acme Datos"]
    assert client.get("/sources", params={"kind": "lever"}).json()["sources"] == []


def test_add_errors(client: TestClient) -> None:
    client.post("/sources", json=BODY)
    again = client.post("/sources", json=BODY)
    assert again.status_code == 409 and again.json()["error"]["type"] == "exists"

    bad = client.post("/sources", json={"kind": "greenhouse", "name": "X", "slug": "a/b"})
    assert bad.status_code == 422
    assert bad.json()["error"]["details"][0]["field"] == "slug"

    missing = client.post("/sources", json={"kind": "greenhouse", "name": "X"})
    assert missing.status_code == 422
    assert "Falta el slug" in missing.json()["error"]["details"][0]["reason"]


@respx.mock
def test_preview_new_and_saved(client: TestClient) -> None:
    mock_greenhouse()
    preview = client.post("/sources/test", json=BODY).json()
    assert preview["message"] == "5 ofertas encontradas, 3 tras filtros"
    assert client.get("/sources").json()["sources"] == []  # no guarda la fuente

    source_id = client.post("/sources", json=BODY).json()["id"]
    saved = client.post(f"/sources/{source_id}/test").json()
    assert (saved["found"], saved["after_filters"]) == (5, 3)


@respx.mock
def test_preview_of_a_broken_source_is_200_with_errors(client: TestClient) -> None:
    respx.get(GREENHOUSE_URL).mock(return_value=httpx.Response(404))
    response = client.post("/sources/test", json=BODY)
    assert response.status_code == 200
    assert response.json()["errors"][0]["code"] == "not_found"


@respx.mock
def test_run_and_toggle(client: TestClient) -> None:
    mock_greenhouse()
    source_id = client.post("/sources", json=BODY).json()["id"]

    run = client.post(f"/sources/{source_id}/run").json()
    assert (run["created"], len(run["job_ids"])) == (3, 3)
    stages = {client.get(f"/jobs/{j}").json()["stage"] for j in run["job_ids"]}
    assert stages == {"pending_extraction"}
    again = client.post(f"/sources/{source_id}/run").json()
    assert (again["created"], again["existing"]) == (0, 3)

    last = client.get("/sources").json()["sources"][0]["last_run"]
    assert (last["found"], last["after_filters"], last["created"]) == (5, 3, 0)

    paused = client.post(f"/sources/{source_id}/active", json={"active": False})
    assert paused.json()["active"] is False
    assert client.post("/sources/99/run").status_code == 404


# --- Plataformas (búsqueda con navegador, fase 09b) --------------------------------------------

LINKEDIN_PLATFORM = {
    "name": "LinkedIn",
    "platform": "linkedin",
    "search_urls": ["https://www.linkedin.com/jobs/search/?keywords=data"],
    "allow_agent_browsing": False,
}


def _linkedin_id() -> int:
    from app.schemas.sources import AgentBrowseSource
    from app.services.ingestion import browse

    with session_scope() as session:
        data = AgentBrowseSource.model_validate(LINKEDIN_PLATFORM)
        return browse.save_source(session, data).source_id


def test_platforms_listed_with_limits(client: TestClient) -> None:
    source_id = _linkedin_id()
    body = client.get("/sources", params={"kind": "agent_browse"}).json()

    assert body["agent_browse"] == {
        "max_result_pages": 2,
        "delay_seconds": 5.0,
        "default_max_offers": 15,
    }
    [platform] = body["sources"]
    assert platform["id"] == source_id
    assert platform["browse"]["allow_agent_browsing"] is False


def test_enable_linkedin_needs_confirm_risk(client: TestClient) -> None:
    source_id = _linkedin_id()
    url = f"/sources/{source_id}/browse"

    refused = client.post(url, json={"allow_agent_browsing": True})
    assert refused.status_code == 403
    assert refused.json()["error"]["type"] == "not_allowed"

    enabled = client.post(url, json={"allow_agent_browsing": True, "confirm_risk": True})
    assert enabled.status_code == 200
    assert enabled.json()["browse"]["allow_agent_browsing"] is True

    changed = client.post(url, json={"priority": 1, "access": "login"}).json()
    assert (changed["browse"]["priority"], changed["browse"]["access"]) == (1, "login")


def test_browse_settings_validation(client: TestClient) -> None:
    source_id = _linkedin_id()
    assert client.post(f"/sources/{source_id}/browse", json={"priority": 0}).status_code == 422
    assert client.post(f"/sources/{source_id}/browse", json={"x": 1}).status_code == 422
    assert client.post("/sources/99/browse", json={"priority": 1}).status_code == 404
    assert client.post(f"/sources/{source_id}/browse", json={"max_offers": 0}).status_code == 422
    changed = client.post(f"/sources/{source_id}/browse", json={"max_offers": 30}).json()
    assert changed["browse"]["max_offers"] == 30


def test_set_website(client: TestClient) -> None:
    source_id = client.post("/sources", json=BODY).json()["id"]
    url = f"/sources/{source_id}/website"

    saved = client.post(url, json={"website": "acmedatos.example"})
    assert saved.status_code == 200 and saved.json()["website"] == "https://acmedatos.example"
    assert client.post(url, json={"website": "nada"}).status_code == 422
    assert client.post(url, json={"website": None}).json()["website"] is None
    assert client.post("/sources/99/website", json={"website": None}).status_code == 404


PLATFORM = {
    "name": "Mi portal",
    "platform": "miportal",
    "search_urls": ["https://www.miportal.example/empleo?q=data"],
    "access": "login",
    "priority": 1,
}


def test_add_platform_from_the_ui(client: TestClient) -> None:
    created = client.post("/sources/platforms", json=PLATFORM)
    assert created.status_code == 201
    body = created.json()
    assert body["created"] is True and body["allow_agent_browsing"] is True
    listed = client.get("/sources", params={"kind": "agent_browse"}).json()["sources"]
    assert [(s["name"], s["browse"]["access"], s["browse"]["priority"]) for s in listed] == [
        ("Mi portal", "login", 1)
    ]
    again = client.post("/sources/platforms", json={**PLATFORM, "name": " mi  portal "})
    assert again.status_code == 409 and again.json()["error"]["type"] == "exists"
    other = client.post(
        "/sources/platforms", json={**PLATFORM, "name": "Otro", "search_urls": ["ftp://x"]}
    )
    assert other.status_code == 422


def test_edit_a_platform_name_and_searches(client: TestClient) -> None:
    """«Editar» cambia el nombre y las búsquedas y conserva lo demás (acceso, prioridad…)."""
    first = client.post("/sources/platforms", json=PLATFORM).json()["source_id"]
    client.post(
        "/sources/platforms",
        json={
            **PLATFORM,
            "name": "InfoJobs",
            "platform": "infojobs",
            "priority": None,
            "search_urls": ["https://www.infojobs.net/ofertas-trabajo?keyword=data"],
        },
    )
    url = f"/sources/{first}/platform"
    searches = ["https://www.miportal.example/empleo?q=bi", "https://miportal.example/x?q=ml"]
    edited = client.put(url, json={"name": " Mi portal  nuevo ", "search_urls": searches})
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert body["name"] == "Mi portal nuevo" and body["browse"]["search_urls"] == searches
    assert (body["browse"]["access"], body["browse"]["priority"]) == ("login", 1)

    clash = client.put(url, json={"name": "infojobs", "search_urls": searches})
    assert clash.status_code == 409 and clash.json()["error"]["type"] == "exists"
    other_site = client.put(
        url, json={"name": "Mi portal", "search_urls": ["https://otro.example/q"]}
    )
    assert other_site.status_code == 422
    assert (
        client.put("/sources/999/platform", json={"name": "X", "search_urls": searches}).status_code
        == 404
    )


def test_platform_priority_swaps_and_stale_ui_is_a_conflict(client: TestClient) -> None:
    """Fase 27.3: un puesto ocupado se intercambia; si la UI ve un puesto que ya no es, 409."""
    first = client.post("/sources/platforms", json=PLATFORM).json()["source_id"]
    second = client.post(
        "/sources/platforms",
        json={
            **PLATFORM,
            "name": "Otro",
            "priority": None,
            "search_urls": ["https://www.miportal.example/empleo?q=bi"],
        },
    ).json()
    assert second["priority"] == 2

    url = f"/sources/{first}/browse"
    moved = client.post(url, json={"priority": 2, "expected_priority": 1})
    assert moved.status_code == 200 and moved.json()["browse"]["priority"] == 2
    listed = client.get("/sources", params={"kind": "agent_browse"}).json()["sources"]
    assert {s["name"]: s["browse"]["priority"] for s in listed} == {"Mi portal": 2, "Otro": 1}

    stale = client.post(url, json={"priority": 1, "expected_priority": 1})
    assert stale.status_code == 409 and stale.json()["error"]["type"] == "conflict"
    out = client.post(url, json={"priority": 3})
    assert out.status_code == 422 and "entre 1 y 2" in out.json()["error"]["message"]
    inserted = client.post(
        "/sources/platforms",
        json={
            **PLATFORM,
            "name": "Tercero",
            "priority": 5,
            "search_urls": ["https://www.miportal.example/empleo?q=ml"],
        },
    )
    assert inserted.status_code == 422 and "entre 1 y 3" in inserted.json()["error"]["message"]


def test_add_linkedin_platform_is_always_created_disabled(client: TestClient) -> None:
    body = {
        "name": "LinkedIn",
        "platform": "linkedin",
        "search_urls": ["https://www.linkedin.com/jobs/search/?keywords=data"],
        "allow_agent_browsing": True,
    }
    created = client.post("/sources/platforms", json=body)
    assert created.status_code == 201 and created.json()["allow_agent_browsing"] is False
