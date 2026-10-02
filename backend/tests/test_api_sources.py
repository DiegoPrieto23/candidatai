"""API de fuentes (`/sources`) para la pantalla «Empresas» de la UI."""

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
    assert client.get("/sources", params={"kind": "lever"}).json() == {"sources": []}


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
    assert client.get("/sources").json() == {"sources": []}  # no guarda la fuente

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
