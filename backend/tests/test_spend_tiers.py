"""Niveles de gasto (fase 24.6): propuesta desde el manifiesto, editar, aplicar con un clic y
deshacer. Por la API, con agentes falsos en el `PATH` (nunca se abre ninguno)."""

from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import AgentPreference
from app.services import agent_launch, agent_prefs, spend_tiers
from app.services.agent_prefs import ActionPref, Preferences

JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


@pytest.fixture
def installed(monkeypatch: pytest.MonkeyPatch) -> Callable[..., None]:
    """`installed("claude", "opencode")`: solo esos programas están en el `PATH`."""

    def set_(*names: str) -> None:
        programs = {"claude": "claude", "codex": "codex", "opencode": "opencode", "qwen": "qwen"}
        found = {programs[n] for n in names}
        monkeypatch.setattr(
            agent_launch.shutil, "which", lambda p: f"C:/bin/{p}.exe" if p in found else None
        )

    set_("claude", "opencode")
    return set_


@pytest.fixture
def client(installed: Any) -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


def _tiers(client: TestClient) -> dict[str, Any]:
    body = client.get("/agent/tiers").json()
    return {t["id"]: t for t in body["tiers"]} | {"_can_undo": body["can_undo"]}


def _pref(agent: str, model: str | None = None, preset: str | None = None) -> dict[str, Any]:
    return {"agent": agent, "model": model, "preset": preset}


def test_proposal(client: TestClient) -> None:
    tiers = _tiers(client)
    economy = tiers["economy"]["actions"]
    for action in spend_tiers.CLOSED_ACTIONS:
        assert economy[action] == _pref("opencode")  # local, con segundo plano; sin modelo
    assert economy["generate-cv"] == _pref("claude")
    assert tiers["economy"]["notes"] == ["needs_local_model"]
    # Equilibrado: el modelo rápido del manifiesto, no un nombre escrito en el código.
    assert tiers["balanced"]["actions"]["process-jobs"] == _pref("claude", "haiku")
    assert tiers["balanced"]["actions"]["generate-cv"] == _pref("claude")
    assert all(p == _pref("claude") for p in tiers["max"]["actions"].values())
    assert not any(tiers[t]["custom"] or tiers[t]["active"] for t in spend_tiers.TIERS)
    assert tiers["_can_undo"] is False


def test_proposal_uses_local_preset(client: TestClient, installed: Any) -> None:
    installed("claude", "codex")  # Codex: modelos locales con el preset `local`
    economy = _tiers(client)["economy"]
    assert economy["actions"]["process-jobs"] == _pref("codex", preset="local")
    assert economy["notes"] == []


def test_proposal_without_local_agent(client: TestClient, installed: Any) -> None:
    installed("claude")
    economy = _tiers(client)["economy"]
    assert economy["actions"]["assess-fit"] == _pref("claude", "haiku")
    assert economy["notes"] == ["no_local_agent"]


def test_apply_and_undo(client: TestClient) -> None:
    before = Preferences(
        default_agent="claude",
        actions={
            "research-company": ActionPref(agent="claude", model="opus"),
            "assess-fit": ActionPref(agent="codex"),
        },
    )
    assert (
        client.put("/agent/preferences", json=before.model_dump(), headers=JSON).status_code == 200
    )
    applied = client.post("/agent/tiers/balanced/apply", json={}, headers=JSON)
    assert applied.status_code == 200, applied.text
    tiers = {t["id"]: t for t in applied.json()["tiers"]}
    assert tiers["balanced"]["active"] and not tiers["max"]["active"]
    assert applied.json()["can_undo"]

    with session_scope() as session:
        prefs = agent_prefs.get_preferences(session)
    assert prefs.default_agent == "claude"  # no se toca
    assert prefs.actions["research-company"].model == "opus"  # fuera del nivel: no se toca
    assert prefs.actions["assess-fit"] == ActionPref(agent="claude", model="haiku")
    assert prefs.actions["generate-cv"] == ActionPref(agent="claude")
    # El agente efectivo de la acción cambia.
    effective = {e["action"]: e for e in client.get("/agent/agents").json()["effective"]}
    assert effective["process-jobs"]["terminal"]["model"] == "haiku"

    undone = client.post("/agent/tiers/undo", json={}, headers=JSON)
    assert undone.status_code == 200 and not undone.json()["can_undo"]
    with session_scope() as session:
        assert agent_prefs.get_preferences(session) == before
    again = client.post("/agent/tiers/undo", json={}, headers=JSON)
    assert again.status_code == 422 and "deshacer" in again.json()["error"]["message"]


def test_undo_from_no_preferences(client: TestClient) -> None:
    client.post("/agent/tiers/max/apply", json={}, headers=JSON)
    client.post("/agent/tiers/undo", json={}, headers=JSON)
    with session_scope() as session:
        assert agent_prefs.get_preferences(session) == Preferences()


def test_saving_preferences_keeps_tiers(client: TestClient) -> None:
    body = {"actions": {"process-jobs": _pref("opencode", "ollama/gpt-oss:20b")}}
    assert client.put("/agent/tiers/economy", json=body, headers=JSON).status_code == 200
    client.post("/agent/tiers/economy/apply", json={}, headers=JSON)
    client.put("/agent/preferences", json={"default_agent": "claude"}, headers=JSON)
    with session_scope() as session:
        scopes = {row.scope for row in session.query(AgentPreference)}
    # La copia para deshacer ya no vale tras un cambio a mano: se borra.
    assert {"tier", "default"} <= scopes and "tier_undo" not in scopes
    assert _tiers(client)["_can_undo"] is False


def test_economy_needs_its_local_model(client: TestClient) -> None:
    refused = client.post("/agent/tiers/economy/apply", json={}, headers=JSON)
    assert refused.status_code == 422 and "modelo local" in refused.json()["error"]["message"]
    body = {
        "actions": {a: _pref("opencode", "ollama/gpt-oss:20b") for a in spend_tiers.CLOSED_ACTIONS}
    }
    client.put("/agent/tiers/economy", json=body, headers=JSON)
    applied = client.post("/agent/tiers/economy/apply", json={}, headers=JSON)
    assert applied.status_code == 200, applied.text
    with session_scope() as session:
        prefs = agent_prefs.get_preferences(session)
    assert prefs.actions["assess-fit"] == ActionPref(agent="opencode", model="ollama/gpt-oss:20b")


def test_edit_and_reset(client: TestClient) -> None:
    body = {"actions": {"process-jobs": _pref("opencode", "ollama/gpt-oss:20b")}}
    saved = client.put("/agent/tiers/economy", json=body, headers=JSON)
    assert saved.status_code == 200, saved.text
    economy = {t["id"]: t for t in saved.json()["tiers"]}["economy"]
    assert economy["custom"] and economy["notes"] == []
    assert economy["actions"]["process-jobs"]["model"] == "ollama/gpt-oss:20b"
    assert economy["actions"]["assess-fit"] == _pref("opencode")  # el resto, la propuesta
    reset = client.post("/agent/tiers/economy/reset", json={}, headers=JSON)
    assert not {t["id"]: t for t in reset.json()["tiers"]}["economy"]["custom"]


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"actions": {"process-jobs": _pref("opencode", "sin-proveedor")}}, "actions.process-jobs"),
        ({"actions": {"process-jobs": _pref("nadie")}}, "actions.process-jobs.agent"),
        ({"actions": {"research-company": _pref("claude")}}, "actions.research-company"),
    ],
)
def test_edit_rejects(client: TestClient, body: dict[str, Any], field: str) -> None:
    response = client.put("/agent/tiers/economy", json=body, headers=JSON)
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == field


def test_needs_ui(client: TestClient) -> None:
    assert client.post("/agent/tiers/max/apply", content="{}").status_code == 403
    assert client.get("/agent/tiers/nope").status_code in (404, 405)
