"""Propuestas del agente para el perfil (fase 41.2): el resumen en inglés se propone, no se escribe.

El agente deja la traducción con `save_profile_suggestion`; la UI la usa o la descarta, y el perfil
solo cambia con «Guardar».
"""
# ruff: noqa: F811 - los fixtures importados se usan como parámetros

import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from app import cli
from app.agent_interface.tools import TOOLS_BY_NAME
from app.api.main import create_app
from app.core.config import get_settings
from app.core.db import session_scope
from app.services import profile, profile_suggestions
from app.services.agent_actions import ACTIONS
from tests.test_agent_runs import JSON, db  # noqa: F401
from tests.test_api_triage import import_profile

EN = "Data engineer with seven years building pipelines."


@pytest.fixture
def client(db: None) -> Iterator[TestClient]:
    # Lecturas solo para la UI: hace falta un host local.
    with TestClient(create_app(), base_url="http://127.0.0.1:8000") as client:
        yield client


def suggest(text: str = EN, agent: str | None = "claude") -> int:
    data = profile_suggestions.SuggestionInput(field="summary.en", text=text)
    with session_scope() as session:
        return profile_suggestions.save(session, data, agent).suggestion_id


def test_translate_summary_only_reads_the_profile_and_leaves_a_suggestion() -> None:
    spec = ACTIONS["translate-summary"]
    assert set(spec.background) == {"get_profile", "save_profile_suggestion"}
    assert set(spec.background) <= set(TOOLS_BY_NAME)
    assert spec.skill == "update-profile" and not spec.roles
    # La orden es fija: nada del perfil va en ella.
    assert "{" not in spec.prompt


def test_without_profile_or_spanish_summary_there_is_nothing_to_translate(db: None) -> None:
    with pytest.raises(profile.ProfileNotFoundError):
        suggest()
    import_profile()
    with session_scope() as session:
        stored = profile.current(session)
        data = stored.profile.model_dump(mode="json", exclude_none=True)
    data["summary"] = {"en": "Only English."}
    path = get_settings().data_dir / "solo-en.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    import yaml

    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with session_scope() as session:
        profile.import_profile(session, path)
    with pytest.raises(ValueError, match="resumen en español"):
        suggest()


def test_a_new_suggestion_replaces_the_pending_one_and_keeps_its_source(db: None) -> None:
    import_profile()
    first = suggest("First try.")
    second = suggest()
    with session_scope() as session:
        pending = profile_suggestions.pending(session).suggestions
        source = (profile.current(session).profile.summary.es or "").strip()
    assert [s.id for s in pending] == [second] and first != second
    assert pending[0].text == EN and pending[0].source == source
    assert pending[0].agent_name == "claude"


def test_profile_does_not_change_until_the_user_saves(db: None) -> None:
    import_profile()
    with session_scope() as session:
        before = profile.current(session).profile_version_id
    suggest()
    with session_scope() as session:
        assert profile.current(session).profile_version_id == before


def test_api_lists_uses_and_discards(client: TestClient) -> None:
    import_profile()
    used = suggest()
    response = client.get("/profile/suggestions", headers=JSON)
    assert response.status_code == 200, response.text
    listed = response.json()["suggestions"]
    assert [s["id"] for s in listed] == [used]
    assert client.post(f"/profile/suggestions/{used}/used", json={}, headers=JSON).json() == {
        "suggestions": []
    }
    # Ya resuelta: ni usarla ni descartarla otra vez.
    again = client.post(f"/profile/suggestions/{used}/discard", json={}, headers=JSON)
    assert again.status_code == 409 or again.json()["error"]["type"] == "not_allowed"
    assert client.post("/profile/suggestions/999/discard", json={}, headers=JSON).status_code == 404

    discarded = suggest()
    client.post(f"/profile/suggestions/{discarded}/discard", json={}, headers=JSON)
    assert client.get("/profile/suggestions", headers=JSON).json()["suggestions"] == []


def test_only_the_ui_resolves_suggestions(client: TestClient) -> None:
    import_profile()
    suggestion = suggest()
    other = {"Origin": "https://evil.example", "Content-Type": "application/json"}
    response = client.post(f"/profile/suggestions/{suggestion}/used", json={}, headers=other)
    assert response.status_code == 403


def test_cli_and_mcp_validate_the_same(db: None) -> None:
    import_profile()
    tmp = get_settings().tmp_dir
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "en.txt").write_text(EN, encoding="utf-8")
    result = CliRunner().invoke(
        cli.app,
        ["profile", "suggest", "--field", "summary.en", "--file", str(tmp / "en.txt"), "--json"],
    )
    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["ok"] is True
    # El `--file` se consume al leerlo: otro para el segundo intento.
    (tmp / "en.txt").write_text(EN, encoding="utf-8")
    bad = CliRunner().invoke(
        cli.app,
        ["profile", "suggest", "--field", "headline", "--file", str(tmp / "en.txt"), "--json"],
    )
    assert bad.exit_code != 0
    assert json.loads(bad.stdout)["error"]["type"] == "validation_error"
