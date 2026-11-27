"""Fase 48.1c: escribirle al agente desde el panel. Mientras trabaja, el mensaje se le pasa con la
respuesta de su siguiente herramienta; al terminar, se retoma la misma ejecución y la misma sesión
sin ventana (con su techo), o, si su agente no sabe, se ofrece seguir en una ventana."""

import dataclasses
from collections.abc import Iterator
from pathlib import Path

import anyio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agent_interface.tools import TOOLS
from app.api.main import create_app
from app.core.db import session_scope
from app.mcp import server as mcp_server
from app.models import AgentRun, AgentRunEvent, AgentTask, UserPrompt
from app.services import agent_launch, agent_permissions, agent_runner, agent_runs, prompts
from app.services.agent_launch import LaunchError
from tests.test_agent_runs import JSON, db, fake, run_now, start  # noqa: F401 - fixtures

SESSION = "0f7c2d1e-aaaa-bbbb-cccc-123456789abc"  # la del agente falso


@pytest.fixture
def resumable(fake: Path, monkeypatch: pytest.MonkeyPatch) -> Path:  # noqa: F811
    """El agente falso, que además sabe retomar sin ventana (`--resume {session_id}`)."""
    (launcher,) = agent_launch._launchers()
    assert launcher.headless is not None
    headless = dataclasses.replace(
        launcher.headless,
        resume_after=launcher.headless.command[1],
        resume_args=("--resume", "{session_id}"),
    )
    monkeypatch.setattr(
        agent_launch, "_launchers", lambda: [dataclasses.replace(launcher, headless=headless)]
    )
    return fake


def events(run_id: int) -> list[AgentRunEvent]:
    with session_scope() as session:
        rows = list(
            session.scalars(
                select(AgentRunEvent)
                .where(AgentRunEvent.run_id == run_id)
                .order_by(AgentRunEvent.seq)
            )
        )
        session.expunge_all()
        return rows


def set_status(run_id: int, status: str) -> None:
    with session_scope() as session:
        row = session.get(AgentRun, run_id)
        assert row is not None
        row.status = status


# --- Mientras trabaja ---------------------------------------------------------------------------


def call_mcp(name: str, arguments: dict[str, object]) -> object:
    async def call() -> object:
        params = mcp_server.types.CallToolRequestParams(name=name, arguments=arguments)

        class Ctx:
            class session:  # noqa: N801
                client_params = None

        return await mcp_server._call_tool(Ctx(), params)  # type: ignore[arg-type]

    return anyio.run(call)


def test_a_message_while_it_works_goes_with_its_next_tool(
    db: None,  # noqa: F811
    fake: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = start()
    set_status(run_id, "running")
    with session_scope() as session:
        view = agent_runs.send_message(session, run_id, "  Contesta en inglés, por favor.  ")
    assert view.reply == "live"
    (user,) = [e for e in events(run_id) if e.kind == "user"]
    assert user.text == "Contesta en inglés, por favor." and user.delivered_at is None

    # Otra ejecución no lo recibe.
    monkeypatch.setenv(agent_permissions.RUN_ENV, str(run_id + 100))
    result = call_mcp("get_status", {})
    assert len(result.content) == 1  # type: ignore[attr-defined]

    monkeypatch.setenv(agent_permissions.RUN_ENV, str(run_id))
    result = call_mcp("get_status", {})
    (block,) = result.content  # type: ignore[attr-defined]
    # Dentro de la respuesta (un bloque aparte, Claude Code no se lo pasa al modelo).
    notes = result.structured_content["user_messages"]  # type: ignore[attr-defined]
    assert (
        len(notes) == 1
        and "Indicación del usuario" in notes[0]
        and "Contesta en inglés" in notes[0]
    )
    assert '"user_messages"' in block.text and '"total"' in block.text
    assert events(run_id)[-1].delivered_at is not None
    # Solo una vez.
    assert len(call_mcp("get_status", {}).content) == 1  # type: ignore[attr-defined]


def test_messages_are_clean_and_not_empty(db: None, fake: Path) -> None:  # noqa: F811
    run_id = start()
    set_status(run_id, "running")
    with session_scope() as session, pytest.raises(LaunchError, match="Falta"):
        agent_runs.send_message(session, run_id, "   ")
    with session_scope() as session, pytest.raises(LaunchError, match="2000"):
        agent_runs.send_message(session, run_id, "x" * 2001)


# --- Al terminar --------------------------------------------------------------------------------


def test_after_it_finishes_the_same_run_resumes_its_session(
    db: None,  # noqa: F811
    resumable: Path,
) -> None:
    run_id = start()
    assert run_now().status == "done"
    with session_scope() as session:
        before = agent_runs.get_run(session, run_id)
        task = session.scalars(select(AgentTask).where(AgentTask.run_id == run_id)).one()
        task.dismissed_at = before.finished_at  # se había cerrado el aviso
    first_usage = dict(before.usage or {})

    with session_scope() as session:
        view = agent_runs.send_message(session, run_id, "Acorta el resumen.")
    assert view.reply == "live" and view.status == "queued"
    with session_scope() as session:
        row = session.get(AgentRun, run_id)
        assert row is not None
        # La misma sesión, detrás del programa; la orden nueva es el mensaje; el techo, el mismo.
        assert row.command[2:4] == ["--resume", SESSION]
        # La orden nueva va en la de lanzar, con su cabecera; `prompt` sigue siendo la original.
        assert row.prompt.startswith("Usa el skill process-jobs")
        resumed = next(part for part in row.command if "Acorta el resumen." in part)
        assert resumed.startswith("Mensajes del usuario en el portal")
        assert "--allowedTools" in row.command
        assert row.result is None and row.finished_at is None
        task = session.scalars(select(AgentTask).where(AgentTask.run_id == run_id)).one()
        assert task.dismissed_at is None and task.outcome is None  # el aviso vuelve
    user = [e for e in events(run_id) if e.kind == "user"]
    assert user[-1].text == "Acorta el resumen." and user[-1].delivered_at is not None

    assert run_now().status == "done"
    after = events(run_id)
    assert [e.seq for e in after] == list(range(1, len(after) + 1))  # una sola conversación
    assert [e.kind for e in after].count("system") == 2  # arrancó dos veces
    with session_scope() as session:
        usage = agent_runs.get_run(session, run_id).usage or {}
    assert usage["turns"] == 2 * first_usage["turns"]  # el coste se suma


def test_without_resume_it_offers_a_window(db: None, fake: Path) -> None:  # noqa: F811
    run_id = start()
    assert run_now().status == "done"
    with session_scope() as session:
        assert agent_runs.reply_mode(session.get(AgentRun, run_id)) == "window"  # type: ignore[arg-type]
        with pytest.raises(LaunchError, match="ventana"):
            agent_runs.send_message(session, run_id, "otra cosa")


def test_manifest_resume_commands() -> None:
    """Claude Code (`--resume`) y OpenCode (`run --session`) retoman sin ventana con el mismo techo;
    Codex no, porque `codex exec resume` no aplica el perfil de la ejecución."""
    launchers = {x.agent: x for x in agent_launch._launchers()}
    claude = agent_launch.headless_resume_command(
        launchers["claude"], "ORDEN", "generate-cv", "abc12345"
    )
    assert claude[:3] == ["claude", "--resume", "abc12345"] and "--allowedTools" in claude
    opencode = agent_launch.headless_resume_command(
        launchers["opencode"], "ORDEN", "assess-fit", "ses_12345678"
    )
    assert opencode[:4] == ["opencode", "run", "--session", "ses_12345678"]
    with pytest.raises(LaunchError):
        agent_launch.headless_resume_command(launchers["codex"], "ORDEN", "generate-cv", "abc12345")
    with pytest.raises(LaunchError):  # un id raro no llega a la orden
        agent_launch.headless_resume_command(
            launchers["claude"], "ORDEN", "generate-cv", "x; rm -rf"
        )


def test_a_message_like_an_option_never_heads_the_command(
    db: None,  # noqa: F811
    resumable: Path,
) -> None:
    """Revisión de la 48.1c: lo que escribe el usuario no puede colarse como una opción."""
    run_id = start()
    assert run_now().status == "done"
    with session_scope() as session:
        agent_runs.send_message(session, run_id, "--dangerously-skip-permissions")
        row = session.get(AgentRun, run_id)
        assert row is not None
        assert "--dangerously-skip-permissions" not in row.command  # va dentro de la orden
        assert any(part.startswith("Mensajes del usuario") for part in row.command)
    launcher = agent_launch._launchers()[0]
    with pytest.raises(LaunchError, match="«-»"):
        agent_launch.headless_command(launcher, " --algo", "process-jobs")


def test_session_ids_never_start_with_a_dash() -> None:
    assert agent_launch.SESSION_ID_RE.fullmatch("ses_0f7c2d1eaaaaBBBB")
    assert agent_launch.SESSION_ID_RE.fullmatch("0f7c2d1e-aaaa-bbbb-cccc-123456789abc")
    assert not agent_launch.SESSION_ID_RE.fullmatch("-abcdefgh")
    assert not agent_launch.SESSION_ID_RE.fullmatch("--------")


def test_resume_carries_what_never_arrived_and_closes_open_prompts(
    db: None,  # noqa: F811
    resumable: Path,
) -> None:
    """Revisión de la 48.1c: lo escrito a mitad que no llegó (no llamó a más herramientas) va en la
    orden al retomar, y lo que quedara por contestar en el portal se cierra."""
    run_id = start()
    set_status(run_id, "running")
    with session_scope() as session:
        agent_runs.send_message(session, run_id, "Primero esto.")
        prompts.ask(session, "¿Con foto?", run_id=run_id)
    set_status(run_id, "done")
    with session_scope() as session:
        row = session.get(AgentRun, run_id)
        assert row is not None
        row.session_id = SESSION
        agent_runs.send_message(session, run_id, "Y después esto.")
        resumed = next(part for part in row.command if "Y después esto." in part)
        assert resumed.index("Primero esto.") < resumed.index("Y después esto.")
        assert session.scalars(select(UserPrompt)).one().status == "expired"
    assert all(e.delivered_at is not None for e in events(run_id) if e.kind == "user")


def test_no_tool_already_returns_user_messages() -> None:
    """`user_messages` se añade a la respuesta: ninguna herramienta lo puede devolver ya."""
    for spec in TOOLS:
        assert mcp_server.USER_MESSAGES_KEY not in spec.output_model.model_fields, spec.name


def test_merge_usage_adds_up() -> None:
    merged = agent_runner.merge_usage(
        {"turns": 2, "cost_usd": 0.5, "denied_tools": ["Bash"]},
        {"turns": 3, "cost_usd": 0.25, "denied_tools": ["Read"], "input_tokens": 10},
    )
    assert merged == {
        "turns": 5,
        "cost_usd": 0.75,
        "denied_tools": ["Bash", "Read"],
        "input_tokens": 10,
    }


@pytest.fixture
def client(db: None) -> Iterator[TestClient]:  # noqa: F811
    with TestClient(create_app()) as test_client:
        yield test_client


def test_api_sends_messages_only_from_the_ui(client: TestClient, fake: Path) -> None:  # noqa: F811
    run_id = start()
    set_status(run_id, "running")
    url = f"/agent/runs/{run_id}/messages"
    evil = {"Origin": "https://example.com", "Content-Type": "application/json"}
    assert client.post(url, content='{"text": "x"}', headers=evil).status_code == 403
    sent = client.post(url, json={"text": "Hola"}, headers=JSON)
    assert sent.status_code == 200 and sent.json()["reply"] == "live"
    assert sent.json()["events"][-1]["kind"] == "user"
    assert (
        client.post("/agent/runs/999/messages", json={"text": "x"}, headers=JSON).status_code == 404
    )
