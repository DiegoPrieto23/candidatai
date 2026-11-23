"""El idioma del portal en lo que lanza el agente (fase 47.3): la orden, la ventana, lo que se lanza
sin la UI y la consola de `cai start`. Ningún test abre una terminal de verdad."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import session_scope
from app.services import agent_launch, agent_runner, launcher, ui_language
from app.services.agent_actions import ACTIONS, ENGLISH, ENGLISH_REPLY
from tests.test_agent_launch import JSON, client, opened  # noqa: F401 - fixtures
from tests.test_agent_runs import db, fake, run_row, start  # noqa: F401 - fixtures

PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _saved() -> ui_language.Lang | None:
    with session_scope() as session:
        return ui_language.saved(session)


def _save(lang: ui_language.Lang) -> None:
    with session_scope() as session:
        ui_language.save(session, lang)


def test_every_order_has_an_english_version_with_the_same_placeholders() -> None:
    assert set(ENGLISH) == set(ACTIONS)
    for action, spec in ACTIONS.items():
        label, prompt = ENGLISH[action]
        assert label and prompt.startswith("Use the CandidatAI "), action
        assert set(PLACEHOLDER.findall(prompt)) == set(PLACEHOLDER.findall(spec.prompt)), action
        # El mismo skill en los dos idiomas.
        skill = re.search(r"skill ([a-z-]+)", spec.prompt)
        assert skill and f"{skill.group(1)} skill" in prompt, action


def test_prompt_in_each_language() -> None:
    assert agent_launch.prompt_for("generate-cv", 42) == (
        "Usa el skill generate-cv de CandidatAI para la oferta 42."
    )
    english = agent_launch.prompt_for("generate-cv", 42, lang="en")
    assert english == "Use the CandidatAI generate-cv skill for job 42." + ENGLISH_REPLY
    assert "Talk to me in English" in english and "language of the job posting" in english


def test_priority_saved_then_cai_lang_then_system(
    db: None,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with session_scope() as session:
        assert ui_language.current(session) == "es"  # `CAI_LANG=es` en los tests
        monkeypatch.setenv("CAI_LANG", "en")
        get_settings.cache_clear()
        assert ui_language.current(session) == "en"
        monkeypatch.delenv("CAI_LANG")
        get_settings.cache_clear()
        monkeypatch.setattr(ui_language.locale, "getlocale", lambda: ("es_ES", "UTF-8"))
        assert ui_language.current(session) == "es"
        ui_language.save(session, "en")
        assert ui_language.current(session) == "en"  # la guardada manda sobre el sistema
        ui_language.save(session, "es")
        assert ui_language.saved(session) == "es"


def test_launch_in_english_saves_the_language(
    client: TestClient,  # noqa: F811
    opened: list[tuple[str, str]],  # noqa: F811
) -> None:
    response = client.post(
        "/agent/launch", json={"action": "search-jobs", "lang": "en"}, headers=JSON
    )
    assert response.status_code == 202, response.text
    assert response.json()["prompt"].startswith("Use the CandidatAI search-jobs skill")
    [(title, command)] = opened
    assert title == "CandidatAI · Search for jobs"
    assert "Talk to me in English" in command
    assert _saved() == "en"

    # Sin `lang`, la guardada; con `lang: es`, vuelve al español.
    client.post("/agent/launch", json={"action": "search-jobs"}, headers=JSON)
    assert opened[-1][0] == "CandidatAI · Search for jobs"
    client.post("/agent/launch", json={"action": "search-jobs", "lang": "es"}, headers=JSON)
    assert opened[-1][0] == "CandidatAI · Buscar ofertas"
    assert _saved() == "es"


def test_one_off_search_in_english(
    client: TestClient,  # noqa: F811
    opened: list[tuple[str, str]],  # noqa: F811
) -> None:
    body = {"action": "search-jobs", "lang": "en", "search": {"role": "Data Engineer"}}
    response = client.post("/agent/launch", json=body, headers=JSON)
    assert response.status_code == 202, response.text
    assert "This is a one-off search: role «Data Engineer»." in response.json()["prompt"]


def test_ui_language_endpoint_and_copied_prompts(client: TestClient) -> None:  # noqa: F811
    assert client.put("/agent/language", json={"lang": "en"}, headers=JSON).json() == {"lang": "en"}
    actions = {a["id"]: a for a in client.get("/agent").json()["actions"]}
    assert actions["search-jobs"]["prompt"].startswith("Use the CandidatAI search-jobs skill")
    assert client.put("/agent/language", json={"lang": "fr"}, headers=JSON).status_code == 422
    other = {"Origin": "https://example.com", "Content-Type": "application/json"}
    assert client.put("/agent/language", json={"lang": "es"}, headers=other).status_code == 403
    assert _saved() == "en"


def test_background_run_and_request_follow_the_saved_language(
    db: None,  # noqa: F811
    fake: Path,  # noqa: F811
) -> None:
    _save("en")
    row = run_row(start())
    assert row.prompt.startswith("Use the CandidatAI process-jobs skill")
    assert "QUESTION:" in row.prompt and "in the background" in row.prompt
    assert "When assessing (step 2)" in row.prompt
    assert "PREGUNTA" not in row.prompt and "Usa el skill" not in row.prompt

    from app.services import agent_requests

    with session_scope() as session:
        request = agent_requests.create(session, "review-replies")
    assert request.prompt.startswith("Use the CandidatAI review-replies skill")


def test_worker_reads_questions_in_both_languages() -> None:
    text = "Done.\nPREGUNTA: ¿Remoto?\n**QUESTION:** Which city?\nquestion: Salary?"
    assert agent_runner.questions_in(text) == ["¿Remoto?", "Which city?", "Salary?"]


def test_cai_start_console_uses_the_saved_language(
    db: None,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_settings.cache_clear()
    assert launcher.console_language() == "es"  # sin guardar: `CAI_LANG`
    _save("en")
    assert launcher.console_language() == "en"
    assert launcher.message("closing") == "Closing CandidatAI…"
