"""Botones «en tu agente» (ADR-024): órdenes cerradas, comando desde el manifiesto, y la API solo
desde la UI. Ningún test abre una terminal de verdad: `_open_terminal` se sustituye."""

from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models.base import utcnow
from app.services import agent_launch, events, process
from app.services.agent_launch import LaunchError
from app.services.pipeline import Stage
from tests.replies_support import add_applied_job
from tests.test_api_triage import add_extracted, import_profile

JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


@pytest.fixture
def opened(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Windows con `claude` instalado; registra las terminales que se abrirían."""
    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(agent_launch.sys, "platform", "win32")
    monkeypatch.setattr(agent_launch.shutil, "which", lambda name: f"C:/bin/{name}.exe")
    monkeypatch.setattr(agent_launch, "_open_terminal", lambda t, c: calls.append((t, c)))
    return calls


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


# --- Servicio ----------------------------------------------------------------------------------


def test_prompts_are_fixed_and_only_take_a_job_id() -> None:
    assert agent_launch.prompt_for("search-jobs").startswith("Usa el skill search-jobs")
    assert agent_launch.prompt_for("generate-cv", 42) == (
        "Usa el skill generate-cv de CandidatAI para la oferta 42."
    )
    with pytest.raises(LaunchError, match="necesita una oferta"):
        agent_launch.prompt_for("generate-cv")


def test_skills_page_prompts_carry_no_skill_names() -> None:
    """Fase 14: los nombres de las skills vienen de las ofertas; el agente los lee de las marcas."""
    assert agent_launch.prompt_for("add-skills").startswith("Usa el skill update-profile")
    assert "get_skill_gaps" in agent_launch.prompt_for("add-skills")
    assert agent_launch.prompt_for("training-plan").startswith("Usa el skill training-plan")
    for action in ("add-skills", "training-plan"):
        assert agent_launch.ACTIONS[action].needs_job is False


def test_replies_prompt_carries_no_mail_text() -> None:
    """Fase 15: el agente lee los correos con `list_replies`; la orden no lleva nada de ellos."""
    prompt = agent_launch.prompt_for("review-replies")
    assert prompt.startswith("Usa el skill review-replies")
    assert agent_launch.ACTIONS["review-replies"].needs_job is False


def test_followup_prompts() -> None:
    """Fase 15: con oferta, solo para una candidatura enviada y abierta."""
    assert agent_launch.prompt_for("draft-follow-up", 7) == (
        "Usa el skill draft-follow-up de CandidatAI para la oferta 7."
    )
    assert agent_launch.ACTIONS["draft-follow-up"].stages == agent_launch.SENT_STAGES
    assert "draft-follow-up" in agent_launch.prompt_for("draft-follow-ups")


def test_outreach_and_research_prompts() -> None:
    """Fase 18: mensaje desde que la oferta está aprobada; dosier también para triarla."""
    assert agent_launch.prompt_for("draft-message", 7) == (
        "Usa el skill draft-message de CandidatAI para la oferta 7."
    )
    assert agent_launch.prompt_for("research-company", 7) == (
        "Usa el skill research-company de CandidatAI para la empresa de la oferta 7."
    )
    outreach = agent_launch.ACTIONS["draft-message"].stages
    research = agent_launch.ACTIONS["research-company"].stages
    assert Stage.APPROVED in outreach and Stage.PENDING_TRIAGE not in outreach
    assert Stage.PENDING_TRIAGE in research and Stage.CLOSED not in research


def test_launchers_come_from_the_manifest() -> None:
    launchers = {launcher.agent: launcher for launcher in agent_launch._launchers()}
    assert launchers["claude"].command == ["claude", "{prompt}"]
    assert launchers["claude"].unset_env == ["ANTHROPIC_API_KEY"]
    assert "codex" in launchers


def test_powershell_command_unsets_api_keys_and_quotes_the_prompt() -> None:
    launcher = agent_launch._Launcher("claude", ["claude", "{prompt}"], ["ANTHROPIC_API_KEY"])
    command = agent_launch.powershell_command(launcher, "Usa 'esto'; y aquello")
    assert command == (
        "Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue; "
        "& 'claude' 'Usa ''esto''; y aquello'"
    )


def test_info_without_windows_or_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(agent_launch.sys, "platform", "linux")
    assert agent_launch.info().available is False
    monkeypatch.setattr(agent_launch.sys, "platform", "win32")
    monkeypatch.setattr(agent_launch.shutil, "which", lambda name: None)
    info = agent_launch.info()
    assert info.available is False and "PATH" in (info.reason or "")


def test_cai_agent_picks_the_agent(
    opened: list[tuple[str, str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAI_AGENT", "codex")
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert agent_launch.info().agent == "codex"
    monkeypatch.setenv("CAI_AGENT", "otro")
    get_settings.cache_clear()
    assert "CAI_AGENT=otro" in (agent_launch.info().reason or "")


# --- API ---------------------------------------------------------------------------------------


def test_get_lists_agent_and_actions(client: TestClient, opened: list[tuple[str, str]]) -> None:
    body = client.get("/agent").json()
    assert body["available"] is True and body["agent"] == "claude"
    actions = {a["id"]: a for a in body["actions"]}
    assert set(actions) == {
        "search-jobs",
        "process-jobs",
        "assess-fit",
        "generate-cv",
        "add-skills",
        "training-plan",
        "review-replies",
        "draft-follow-ups",
        "draft-follow-up",
        "broaden-search",
        "prepare-interview",
        "mock-interview",
        "debrief-interview",
        "offer-questions",
        "prepare-negotiation",
        "draft-message",
        "research-company",
        "handle-requests",
        "review-search",
    }
    assert actions["generate-cv"]["needs_job"] is True and actions["generate-cv"]["prompt"] is None
    assert actions["debrief-interview"]["needs_milestone"] is True
    assert actions["offer-questions"]["needs_milestone"] is False
    assert "search-jobs" in actions["search-jobs"]["prompt"]


def test_launch_opens_a_terminal(client: TestClient, opened: list[tuple[str, str]]) -> None:
    response = client.post("/agent/launch", json={"action": "search-jobs"}, headers=JSON)
    assert response.status_code == 202
    assert response.json()["agent"] == "claude"
    [(title, command)] = opened
    assert title == "CandidatAI · Buscar ofertas"
    assert "& 'claude' 'Usa el skill search-jobs" in command


def test_generate_cv_needs_an_approved_job(
    client: TestClient, opened: list[tuple[str, str]]
) -> None:
    import_profile()
    job_id = add_extracted("Data Engineer", "Acme")
    body = {"action": "generate-cv", "job_id": job_id}
    response = client.post("/agent/launch", json=body, headers=JSON)
    assert response.status_code == 422
    assert "aprobada" in response.json()["error"]["message"]

    client.post(f"/jobs/{job_id}/events", json={"type": "approved"})
    response = client.post("/agent/launch", json=body, headers=JSON)
    assert response.status_code == 202
    assert opened[-1][1].endswith(f"para la oferta {job_id}.'")

    missing = client.post("/agent/launch", json={**body, "job_id": 999}, headers=JSON)
    assert missing.status_code == 404


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://example.com", "Content-Type": "application/json"},
        {"Origin": UI_ORIGIN, "Content-Type": "text/plain"},
    ],
)
def test_only_the_ui_can_launch(
    client: TestClient, opened: list[tuple[str, str]], headers: dict[str, str]
) -> None:
    response = client.post("/agent/launch", content='{"action": "search-jobs"}', headers=headers)
    assert response.status_code == 403
    assert opened == []


def test_unavailable_returns_the_prompt_to_copy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(agent_launch.sys, "platform", "linux")
    response = client.post("/agent/launch", json={"action": "process-jobs"}, headers=JSON)
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["type"] == "agent_unavailable"
    assert error["details"][0]["field"] == "prompt"
    assert error["details"][0]["received"].startswith("Usa el skill process-jobs")


def test_shell_args_carry_no_characters_wt_would_split() -> None:
    import base64

    launcher = agent_launch._Launcher("claude", ["claude", "{prompt}"], ["ANTHROPIC_API_KEY"])
    command = agent_launch.powershell_command(launcher, agent_launch.prompt_for("generate-cv", 7))
    args = agent_launch.shell_args(command)
    # `wt` parte su línea de comandos por cada `;`: ninguno puede llegarle.
    assert not any(";" in arg for arg in args)
    assert args[:4] == ["powershell", "-NoLogo", "-NoExit", "-EncodedCommand"]
    assert base64.b64decode(args[4]).decode("utf-16-le") == command


# --- Entrevistas (fase 17) ----------------------------------------------------------------------


def _interview(hours: int, kind: str = "interview") -> tuple[int, int]:
    """Oferta enviada con un hito que empieza dentro de `hours` horas (negativo: ya empezó)."""
    with session_scope() as session:
        job = add_applied_job(
            session, f"Empresa {kind} {hours}", applied_at=utcnow() - timedelta(days=9)
        )
        row = process.create_milestone(
            session,
            job.id,
            process.MilestoneCreate(
                kind=kind,  # type: ignore[arg-type]
                starts_at=utcnow() + timedelta(hours=hours),
                occurred_at=utcnow() - timedelta(days=8),
            ),
        )
        return job.id, row.id


def test_interview_prompts_carry_only_ids() -> None:
    assert agent_launch.prompt_for("debrief-interview", 4, 9) == (
        "Usa el skill debrief-interview de CandidatAI para repasar la entrevista 9 de la oferta 4."
    )
    with pytest.raises(LaunchError, match="necesita una entrevista"):
        agent_launch.prompt_for("prepare-interview", 4)


@pytest.mark.parametrize("action", ["prepare-interview", "mock-interview"])
def test_prepare_and_mock_need_an_upcoming_interview(
    client: TestClient, opened: list[tuple[str, str]], action: str
) -> None:
    job_id, upcoming = _interview(48)
    _, past = _interview(-2)
    response = client.post(
        "/agent/launch", json={"action": action, "milestone_id": upcoming}, headers=JSON
    )
    assert response.status_code == 202
    assert opened[-1][1].endswith(f"entrevista {upcoming} de la oferta {job_id}.'")

    response = client.post(
        "/agent/launch", json={"action": action, "milestone_id": past}, headers=JSON
    )
    assert response.status_code == 422
    assert "programada" in response.json()["error"]["message"]


def test_debrief_needs_a_started_interview_of_that_job(
    client: TestClient, opened: list[tuple[str, str]]
) -> None:
    job_id, past = _interview(-2)
    other_job, upcoming = _interview(48)
    _, test_id = _interview(-2, kind="test")
    body = {"action": "debrief-interview", "milestone_id": past}

    assert client.post("/agent/launch", json=body, headers=JSON).status_code == 202
    assert opened[-1][1].endswith(f"repasar la entrevista {past} de la oferta {job_id}.'")
    for changes, code in (
        ({"milestone_id": upcoming}, 422),
        ({"job_id": other_job}, 422),
        ({"milestone_id": test_id}, 422),
        ({"milestone_id": 999}, 404),
    ):
        response = client.post("/agent/launch", json={**body, **changes}, headers=JSON)
        assert response.status_code == code, changes
    assert len(opened) == 1


def test_offer_doubts_need_an_offer(client: TestClient, opened: list[tuple[str, str]]) -> None:
    job_id, _ = _interview(-48)
    body = {"action": "offer-questions", "job_id": job_id}
    response = client.post("/agent/launch", json=body, headers=JSON)
    assert response.status_code == 422
    assert "propuesta recibida" in response.json()["error"]["message"]

    with session_scope() as session:
        events.record(session, job_id, "offer_received", "user")
    assert client.post("/agent/launch", json=body, headers=JSON).status_code == 202
    assert opened[-1][1].endswith(f"antes de aceptar la oferta {job_id}.'")


def test_negotiation_needs_an_offer_and_opens_a_terminal(
    client: TestClient, opened: list[tuple[str, str]]
) -> None:
    job_id, _ = _interview(-48)
    body = {"action": "prepare-negotiation", "job_id": job_id}
    assert client.post("/agent/launch", json=body, headers=JSON).status_code == 422

    with session_scope() as session:
        events.record(session, job_id, "offer_received", "user")
    assert client.post("/agent/launch", json=body, headers=JSON).status_code == 202
    assert f"prepare-negotiation de CandidatAI para la oferta {job_id}" in opened[-1][1]
    assert agent_launch.ACTIONS["prepare-negotiation"].background == ()


def test_unavailable_interview_action_returns_the_prompt_with_its_job(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    job_id, past = _interview(-2)
    monkeypatch.setattr(agent_launch.sys, "platform", "linux")
    response = client.post(
        "/agent/launch", json={"action": "debrief-interview", "milestone_id": past}, headers=JSON
    )
    assert response.status_code == 503
    prompt = response.json()["error"]["details"][0]["received"]
    assert prompt.endswith(f"entrevista {past} de la oferta {job_id}.")
