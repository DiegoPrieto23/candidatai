"""Fase 48.1a: el botón principal lanza sin ventana y se sigue en el portal, salvo que se elija
«Abrir en una ventana»."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core.db import session_scope
from app.services import launch_window
from tests.test_agent_runs import JSON, db, fake  # noqa: F401 - fixtures


@pytest.fixture
def client(db: None) -> Iterator[TestClient]:  # noqa: F811
    with TestClient(create_app()) as test_client:
        yield test_client


def actions(client: TestClient) -> dict[str, dict[str, object]]:
    body = client.get("/agent").json()
    return {a["id"]: a for a in body["actions"]}


def test_portal_by_default_only_where_background_is_possible(
    client: TestClient,
    fake: Path,  # noqa: F811
) -> None:
    listed = actions(client)
    assert client.get("/agent").json()["open_in_window"] is False
    assert listed["generate-cv"]["portal"] is True
    assert listed["mock-interview"]["portal"] is False  # pregunta: sigue en una ventana
    assert listed["search-jobs"]["portal"] is False


def test_open_in_window_turns_the_portal_off(client: TestClient, fake: Path) -> None:  # noqa: F811
    saved = client.put("/agent/window-preference", json={"open_in_window": True}, headers=JSON)
    assert saved.status_code == 200 and saved.json() == {"open_in_window": True}
    assert client.get("/agent").json()["open_in_window"] is True
    assert actions(client)["generate-cv"]["portal"] is False
    client.put("/agent/window-preference", json={"open_in_window": False}, headers=JSON)
    assert actions(client)["generate-cv"]["portal"] is True


def test_only_the_ui_saves_it(client: TestClient) -> None:
    headers = {"Origin": "https://example.com", "Content-Type": "application/json"}
    sent = client.put(
        "/agent/window-preference", content='{"open_in_window": true}', headers=headers
    )
    assert sent.status_code == 403
    with session_scope() as session:
        assert launch_window.get(session).open_in_window is False


def test_agent_preferences_do_not_touch_it(client: TestClient, fake: Path) -> None:  # noqa: F811
    client.put("/agent/window-preference", json={"open_in_window": True}, headers=JSON)
    prefs = client.get("/agent/agents").json()["preferences"]
    assert client.put("/agent/preferences", json=prefs, headers=JSON).status_code == 200
    assert client.get("/agent").json()["open_in_window"] is True
