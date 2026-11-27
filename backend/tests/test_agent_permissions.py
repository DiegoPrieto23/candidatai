"""Fase 48.1b: preguntas y permisos de una ejecución sin ventana, contestados en el portal."""

import json
import threading
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.agent_interface.tools import TOOLS_BY_NAME
from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.mcp import server as mcp_server
from app.models import AgentPermissionRule, AgentRun, UserPrompt
from app.services import agent_permissions, prompts
from tests.test_agent_runs import JSON

BASH = {"command": "mkdir -p tmp/x", "description": "crear carpeta"}


@pytest.fixture
def run_id(monkeypatch: pytest.MonkeyPatch) -> int:
    """Una ejecución en curso, la del entorno del agente (`CAI_RUN_ID`)."""
    migrations.upgrade()
    with session_scope() as session:
        row = AgentRun(
            action="generate-cv",
            agent="claude",
            status="running",
            prompt="orden",
            command=["claude"],
            output_format="claude-stream-json",
        )
        session.add(row)
        session.flush()
        run = row.id
    monkeypatch.setenv(agent_permissions.RUN_ENV, str(run))
    return run


def answer_when_asked(choice: str | None, outcome: prompts.Outcome = "done") -> threading.Thread:
    """Contesta desde «la UI» el primer permiso pendiente, como el panel."""

    def work() -> None:
        for _ in range(200):
            with session_scope() as session:
                pending = session.scalars(
                    select(UserPrompt).where(
                        UserPrompt.kind == "permission", UserPrompt.status == "pending"
                    )
                ).first()
                if pending is not None:
                    prompts.answer(session, pending.id, outcome, choice)
                    return
            time.sleep(0.02)

    thread = threading.Thread(target=work)
    thread.start()
    return thread


def ask(timeout: float = 5) -> agent_permissions.PermissionDecision:
    return agent_permissions.request("Bash", BASH, timeout=timeout, poll=0.02)


def test_describe_picks_what_it_wants_to_do() -> None:
    assert agent_permissions.describe("Bash", BASH) == "mkdir -p tmp/x"
    assert agent_permissions.describe("Read", {"file_path": "C:/x.txt"}) == "C:/x.txt"
    assert agent_permissions.describe("Raro", {"b": 1, "a": "x"}) == '{"a": "x", "b": 1}'
    assert agent_permissions.describe("Vacía", {}) == "Vacía"
    assert len(agent_permissions.describe("Bash", {"command": "x" * 2000})) == 500


@pytest.mark.parametrize(("choice", "behavior"), [("once", "allow"), ("deny", "deny")])
def test_allow_once_or_deny(run_id: int, choice: str, behavior: str) -> None:
    thread = answer_when_asked(choice)
    decision = ask()
    thread.join()
    assert decision.behavior == behavior
    if behavior == "allow":
        assert decision.updatedInput == BASH
    else:
        assert decision.message and "Denegado desde el portal" in decision.message
    with session_scope() as session:
        row = session.scalars(select(UserPrompt)).one()
        # Queda registrado: qué pidió, con qué herramienta, de qué ejecución y la respuesta.
        assert (row.kind, row.tool, row.message, row.run_id) == (
            "permission",
            "Bash",
            "mkdir -p tmp/x",
            run_id,
        )
        assert row.answer == choice and row.answered_at is not None
        assert session.scalars(select(AgentPermissionRule)).first() is None


def test_skipping_a_permission_denies_it(run_id: int) -> None:
    thread = answer_when_asked(None, outcome="skipped")
    assert ask().behavior == "deny"
    thread.join()


READ = {"file_path": "C:/notas/fuera.txt"}


def read(timeout: float = 5) -> agent_permissions.PermissionDecision:
    return agent_permissions.request("Read", READ, timeout=timeout, poll=0.02)


def test_always_is_remembered_and_not_asked_again(run_id: int) -> None:
    thread = answer_when_asked("always")
    assert read().behavior == "allow"
    thread.join()
    with session_scope() as session:
        rules = agent_permissions.list_rules(session).rules
    assert [(r.tool, r.detail) for r in rules] == [("Read", "C:/notas/fuera.txt")]
    began = time.monotonic()
    assert read().behavior == "allow"  # sin preguntar
    assert time.monotonic() - began < 1
    with session_scope() as session:
        assert len(session.scalars(select(UserPrompt)).all()) == 1
        # Al quitar la regla, se vuelve a preguntar.
        agent_permissions.delete_rule(session, rules[0].id)
    assert read(timeout=0.1).behavior == "deny"
    # Otro fichero sí se pregunta.
    other = agent_permissions.request("Read", {"file_path": "C:/otro"}, timeout=0.1, poll=0.02)
    assert other.behavior == "deny"


@pytest.mark.parametrize(
    ("tool", "tool_input", "offered"),
    [
        ("Read", {"file_path": "C:/x.txt"}, True),
        ("Skill", {"skill": "generate-cv"}, True),
        # Fuera del techo sin ventana (una petición inventada, p. ej.): solo una vez.
        ("Bash", {"command": "ls"}, False),
        ("Edit", {"file_path": "C:/x.txt", "old_string": "a", "new_string": "b"}, False),
        # Que no cabe entero: la regla cubriría más de lo que se vio.
        ("Read", {"file_path": "C:/" + "x" * 600}, False),
        ("Read", {"file_path": "C:/x.txt", "offset": 3}, False),
    ],
)
def test_always_is_offered_only_when_it_covers_exactly_what_was_seen(
    run_id: int, tool: str, tool_input: dict[str, object], offered: bool
) -> None:
    assert agent_permissions.can_always(tool, tool_input) is offered
    agent_permissions.request(tool, tool_input, timeout=0.05, poll=0.02)
    with session_scope() as session:
        row = session.scalars(select(UserPrompt)).one()
        assert ("always" in (row.options or [])) is offered
        if not offered:
            row.status = "pending"
            with pytest.raises(ValueError, match="once, deny"):
                prompts.answer(session, row.id, "done", "always")


def test_stopping_the_run_denies_a_pending_permission(run_id: int) -> None:
    def stop() -> None:
        time.sleep(0.2)
        with session_scope() as session:
            run = session.get(AgentRun, run_id)
            assert run is not None
            run.status = "cancelled"

    thread = threading.Thread(target=stop)
    thread.start()
    began = time.monotonic()
    assert ask(timeout=10).behavior == "deny"
    thread.join()
    assert time.monotonic() - began < 5
    with session_scope() as session:
        assert session.scalars(select(UserPrompt)).one().status == "expired"


def test_no_answer_in_time_denies(run_id: int) -> None:
    decision = ask(timeout=0.2)
    assert decision.behavior == "deny" and "a tiempo" in (decision.message or "")
    with session_scope() as session:
        assert session.scalars(select(UserPrompt)).one().status == "expired"


def test_without_a_running_run_it_denies(run_id: int, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(agent_permissions.RUN_ENV, "999")
    assert ask().behavior == "deny"
    monkeypatch.delenv(agent_permissions.RUN_ENV)
    assert ask().behavior == "deny"
    with session_scope() as session:
        assert session.scalars(select(UserPrompt)).first() is None  # nada que enseñar


def test_a_permission_answer_must_be_one_of_the_three(run_id: int) -> None:
    with session_scope() as session:
        prompt = UserPrompt(
            kind="permission",
            message="x",
            tool="Bash",
            run_id=run_id,
            status="pending",
            created_at=prompts.utcnow(),
            expires_at=prompts.utcnow() + prompts.timedelta(minutes=5),
        )
        session.add(prompt)
        session.flush()
        with pytest.raises(ValueError, match="once"):
            prompts.answer(session, prompt.id, "done", "sí")


def test_questions_from_a_run_carry_it(run_id: int) -> None:
    with session_scope() as session:
        view = prompts.ask(session, "¿Con foto?", ["Sí", "No"], run_id=run_id)
    assert view.run_id == run_id and view.kind == "question"


def test_mcp_returns_a_single_text_block(run_id: int) -> None:
    """Claude Code solo acepta un bloque de texto, sin `structuredContent` ni esquema de salida
    (comprobado con 2.1.332)."""
    spec = TOOLS_BY_NAME["request_permission"]
    assert spec.text_only
    assert mcp_server._tool_definition(spec).output_schema is None
    with session_scope() as session:
        session.add(AgentPermissionRule(tool="Read", detail="C:/notas/fuera.txt"))

    async def call() -> object:
        params = mcp_server.types.CallToolRequestParams(
            name="request_permission", arguments={"tool_name": "Read", "input": READ}
        )

        class Ctx:
            class session:  # noqa: N801
                client_params = None

        return await mcp_server._call_tool(Ctx(), params)  # type: ignore[arg-type]

    import anyio

    result = anyio.run(call)
    assert result.structured_content is None  # type: ignore[attr-defined]
    (block,) = result.content  # type: ignore[attr-defined]
    assert json.loads(block.text) == {"behavior": "allow", "updatedInput": READ}


@pytest.fixture
def client(run_id: int) -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client


def test_api_lists_and_removes_always_rules(client: TestClient) -> None:
    with session_scope() as session:
        session.add(AgentPermissionRule(tool="Read", detail="C:/x.txt"))
    rules = client.get("/agent/permission-rules").json()["rules"]
    assert [(r["tool"], r["detail"]) for r in rules] == [("Read", "C:/x.txt")]
    removed = client.delete(f"/agent/permission-rules/{rules[0]['id']}", headers=JSON)
    assert removed.status_code == 200 and removed.json() == {"rules": []}
    assert client.delete("/agent/permission-rules/999", headers=JSON).status_code == 404


def test_only_the_ui_answers_a_permission(client: TestClient, run_id: int) -> None:
    """Otra web no. Un proceso local sí podría (las cabeceras se falsean): lo que lo impide es que
    sin ventana el agente no tiene terminal ni web (`--tools Skill,Agent,Read`)."""
    with session_scope() as session:
        prompt = UserPrompt(
            kind="permission",
            message="C:/x.txt",
            tool="Read",
            run_id=run_id,
            options=["once", "always", "deny"],
            status="pending",
            created_at=prompts.utcnow(),
            expires_at=prompts.utcnow() + prompts.timedelta(minutes=5),
        )
        session.add(prompt)
        session.flush()
        prompt_id = prompt.id
    body = '{"outcome": "done", "answer": "always"}'
    evil = {"Origin": "https://example.com", "Content-Type": "application/json"}
    assert (
        client.post(f"/prompts/{prompt_id}/answer", content=body, headers=evil).status_code == 403
    )
    with session_scope() as session:
        assert session.get(UserPrompt, prompt_id).status == "pending"  # type: ignore[union-attr]
    answered = client.post(f"/prompts/{prompt_id}/answer", content=body, headers=JSON)
    assert answered.status_code == 200 and answered.json()["answer"] == "always"
