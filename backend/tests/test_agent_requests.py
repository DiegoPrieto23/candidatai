"""Cola de encargos (fase 19): la UI deja la orden de un skill para la próxima sesión del agente,
que la lee con `list_agent_requests` y la cierra con `complete_agent_request`."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.services import agent_requests, status
from app.services.agent_launch import LaunchError
from tests.test_api_triage import add_extracted, import_profile

JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


def test_create_dedupes_and_validates(client: TestClient) -> None:
    with session_scope() as session:
        first = agent_requests.create(session, "buscar-ofertas")
        assert agent_requests.create(session, "buscar-ofertas").id == first.id
        assert first.prompt.startswith("Usa el skill buscar-ofertas")
        assert "segundo plano" not in first.prompt  # es para una sesión interactiva
        with pytest.raises(LaunchError, match="necesita una oferta"):
            agent_requests.create(session, "generar-cv")
        with pytest.raises(LaunchError, match="no puede ser un encargo"):
            agent_requests.create(session, "atender-encargos")
        assert status.get_status(session).agent_requests == 1


def test_complete_and_cancel(client: TestClient) -> None:
    with session_scope() as session:
        one = agent_requests.create(session, "procesar-ofertas")
        two = agent_requests.create(session, "evaluar-encaje")
        result = agent_requests.complete(session, one.id, "  Procesadas 3. ", "claude-code")
        assert result.message == "Encargo 1 («Procesar ofertas») cerrado."
        agent_requests.cancel(session, two.id)
        with pytest.raises(agent_requests.RequestClosedError):
            agent_requests.complete(session, two.id, "x")
        listed = agent_requests.list_requests(session, None)
    assert listed.pending == 0
    done = {r.id: r for r in listed.requests}
    assert done[one.id].status == "done" and done[one.id].summary == "Procesadas 3."
    assert done[one.id].agent_name == "claude-code" and done[one.id].completed_at
    assert done[two.id].status == "cancelled"


def test_api_create_list_and_cancel(client: TestClient) -> None:
    import_profile()
    job_id = add_extracted("Data Engineer", "Acme")
    body = {"action": "investigar-empresa", "job_id": job_id}
    created = client.post("/agent/requests", json=body, headers=JSON)
    assert created.status_code == 201
    request = created.json()
    assert request["prompt"] == (
        f"Usa el skill investigar-empresa de CandidatAI para la empresa de la oferta {job_id}."
    )
    listed = client.get("/agent/requests", params={"status": "pending"}).json()
    assert listed["pending"] == 1 and listed["requests"][0]["id"] == request["id"]
    assert client.get("/status").json()["agent_requests"] == 1

    wrong = client.post(
        "/agent/requests", json={"action": "generar-cv", "job_id": job_id}, headers=JSON
    )
    assert wrong.status_code == 422 and "aprobada" in wrong.json()["error"]["message"]

    cancelled = client.post(f"/agent/requests/{request['id']}/cancel", json={}, headers=JSON)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    again = client.post(f"/agent/requests/{request['id']}/cancel", json={}, headers=JSON)
    assert again.status_code == 422
    assert client.post("/agent/requests/99/cancel", json={}, headers=JSON).status_code == 404


@pytest.mark.parametrize("path", ["/agent/requests", "/agent/requests/1/cancel"])
def test_only_the_ui_creates_or_cancels(client: TestClient, path: str) -> None:
    headers = {"Origin": "https://example.com", "Content-Type": "application/json"}
    response = client.post(path, content='{"action": "buscar-ofertas"}', headers=headers)
    assert response.status_code == 403
    assert client.get("/agent/requests").json()["requests"] == []
