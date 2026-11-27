"""La conversación de una ejecución en segundo plano, para seguirla en el portal: los lectores
de la salida de cada agente (con salidas reales de Claude Code y Codex, limpias, de la prueba
previa), lo que guarda el runner, su lectura por la API y los pasos del aviso."""

import json
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core.db import session_scope
from app.models import AgentRunEvent, AgentTask, McpCall
from app.models.base import utcnow
from app.services import agent_runner, agent_tasks
from app.services.agent_output import (
    DENIED,
    EVENT_TEXT_CHARS,
    ClaudeStreamParser,
    CodexJsonParser,
    OpenCodeJsonParser,
    StreamParser,
)
from tests.test_agent_runs import db, fake, run_now, start  # noqa: F401 - fixtures

OUTPUTS = Path(__file__).parent / "fixtures" / "agent_output"


def feed(parser: StreamParser, name: str) -> StreamParser:
    for line in (OUTPUTS / name).read_text(encoding="utf-8").splitlines():
        parser.feed(line)
    return parser


def kinds(parser: StreamParser) -> list[tuple[str, str | None]]:
    return [(e.kind, e.tool) for e in parser.state.events]


# --- Lectores ----------------------------------------------------------------------------------


def test_claude_real_output_becomes_a_conversation() -> None:
    parser = feed(ClaudeStreamParser(), "claude_probe_status.jsonl")
    assert kinds(parser) == [
        ("system", None),
        ("tool_start", "get_status"),
        ("tool_result", "get_status"),
        ("text", None),
        ("result", None),
    ]
    events = parser.state.events
    assert events[2].ok is True
    assert events[3].text and events[3].text.startswith("Hay **8 ofertas por revisar**")
    # El resultado repite el último mensaje: no se guarda dos veces.
    assert events[4].text is None and events[4].ok is True
    assert '"demo"' not in json.dumps([e.text for e in events])  # nunca la salida de la herramienta


def test_claude_mid_message_run_keeps_every_tool_in_order() -> None:
    parser = feed(ClaudeStreamParser(), "claude_probe_mid_message.jsonl")
    tools = [e.tool for e in parser.state.events if e.kind == "tool_start"]
    assert tools == ["get_status", "list_jobs"]
    assert parser.state.events[-1].kind == "result"
    assert parser.state.session_id == "2691880c-5b31-40e1-bd11-e71b9ab0db01"


def test_claude_resume_keeps_the_session() -> None:
    parser = feed(ClaudeStreamParser(), "claude_probe_resume.jsonl")
    assert parser.state.session_id == "2691880c-5b31-40e1-bd11-e71b9ab0db01"
    assert [e.kind for e in parser.state.events] == ["system", "text", "result"]


def test_claude_subagents_tool_details_and_denials() -> None:
    parser = ClaudeStreamParser()
    lines = [
        {"type": "system", "subtype": "init", "session_id": "s-1", "mcp_servers": []},
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "tool_use", "id": "a", "name": "Skill", "input": {"skill": "x"}},
                    {
                        "type": "tool_use",
                        "id": "b",
                        "name": "Agent",
                        "input": {"subagent_type": "w"},
                    },
                ]
            },
        },
        {
            "type": "assistant",
            "parent_tool_use_id": "b",
            "message": {
                "content": [
                    {"type": "text", "text": "texto del subagente"},
                    {
                        "type": "tool_use",
                        "id": "c",
                        "name": "mcp__candidatai__get_job",
                        "input": {"job_id": 1, "texto": "TEXTO DE LA OFERTA"},
                    },
                ]
            },
        },
        {
            "type": "user",
            "message": {
                "content": [
                    {"type": "tool_result", "tool_use_id": "c", "is_error": True, "content": "x"},
                    {
                        "type": "tool_result",
                        "tool_use_id": "a",
                        "is_error": True,
                        "content": "Permission denied",
                    },
                ]
            },
        },
    ]
    for line in lines:
        parser.feed(json.dumps(line))
    events = parser.state.events
    assert [(e.kind, e.tool, e.text, e.sub) for e in events[1:4]] == [
        ("tool_start", "Skill", "x", False),
        ("tool_start", "Agent", "w", False),
        ("tool_start", "get_job", None, True),
    ]
    assert not any(e.kind == "text" for e in events)  # el texto de un subagente no se guarda
    assert (events[4].ok, events[4].text, events[4].sub) == (False, None, True)
    assert (events[5].tool, events[5].text) == ("Skill", DENIED)
    assert "TEXTO DE LA OFERTA" not in json.dumps([e.text for e in events])


def test_long_agent_text_is_clipped_but_keeps_lines() -> None:
    parser = ClaudeStreamParser()
    text = "Primera línea\n\n" + "x" * (EVENT_TEXT_CHARS * 2)
    parser.feed(
        json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}})
    )
    said = parser.state.events[0].text or ""
    assert said.startswith("Primera línea\n\n") and len(said) == EVENT_TEXT_CHARS


def test_codex_real_output_becomes_a_conversation() -> None:
    parser = feed(CodexJsonParser(), "codex_probe_status.jsonl")
    assert kinds(parser) == [
        ("system", None),
        ("text", None),
        ("tool_start", "command_execution"),
        ("tool_result", "command_execution"),
        ("tool_start", "command_execution"),
        ("tool_result", "command_execution"),
        ("text", None),
        ("result", None),
    ]
    assert "uv run" not in json.dumps([e.text for e in parser.state.events])  # ni el comando


def test_codex_resume_keeps_the_thread() -> None:
    parser = feed(CodexJsonParser(), "codex_probe_resume.jsonl")
    assert parser.state.session_id == "01a21e2e-4c5b-7261-ae3d-355c2ad341e8"
    assert [e.kind for e in parser.state.events] == ["system", "text", "result"]


def test_codex_failed_turn_is_an_error_event() -> None:
    parser = CodexJsonParser()
    parser.feed(json.dumps({"type": "turn.failed", "error": {"message": "sin cuota"}}))
    assert [(e.kind, e.text) for e in parser.state.events] == [("error", "sin cuota")]


def test_opencode_output_becomes_a_conversation() -> None:
    parser = feed(OpenCodeJsonParser(), "opencode_ok.jsonl")
    events = parser.state.events
    assert events[0].kind == "system" and events[-1].kind == "result"
    starts = [e for e in events if e.kind == "tool_start"]
    assert starts and all(e.tool for e in starts)
    assert any(e.kind == "tool_result" for e in events)


# --- Runner y API ------------------------------------------------------------------------------


def saved(run_id: int) -> list[AgentRunEvent]:
    with session_scope() as session:
        rows = list(
            session.query(AgentRunEvent)
            .filter(AgentRunEvent.run_id == run_id)
            .order_by(AgentRunEvent.seq)
        )
        session.expunge_all()
        return rows


def test_runner_saves_the_conversation(db: None, fake: Path) -> None:  # noqa: F811
    run_id = start()
    assert run_now().status == "done"
    rows = saved(run_id)
    assert [r.seq for r in rows] == list(range(1, len(rows) + 1))
    assert rows[0].kind == "system" and rows[-1].kind == "result"
    assert ("tool_start", "list_jobs", False) in [(r.kind, r.tool, r.sub) for r in rows]
    assert ("tool_start", "get_job", True) in [(r.kind, r.tool, r.sub) for r in rows]
    assert "Voy a procesar las ofertas pendientes." in [r.text for r in rows]
    assert "TEXTO DE LA OFERTA" not in json.dumps([r.text for r in rows])


def test_runner_adds_its_own_errors(
    db: None,  # noqa: F811
    fake: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "crash")
    run_id = start()
    assert run_now().status == "failed"
    last = saved(run_id)[-1]
    assert last.kind == "error" and "boom" in (last.text or "")


def test_agent_error_is_not_repeated(
    db: None,  # noqa: F811
    fake: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAKE_AGENT_MODE", "error")
    run_id = start()
    assert run_now().status == "failed"
    rows = saved(run_id)
    assert rows[-1].kind == "result" and rows[-1].ok is False
    assert not any(r.kind == "error" for r in rows)


def test_a_long_conversation_keeps_room_for_how_it_ended(
    db: None,  # noqa: F811
    fake: Path,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(agent_runner, "MAX_EVENTS", 4)
    run_id = start()
    assert run_now().status == "done"
    rows = saved(run_id)
    # Los dos primeros huecos para la conversación; el resultado entra aunque se haya cortado.
    assert [(r.seq, r.kind) for r in rows] == [(1, "system"), (2, "text"), (3, "result")]


def test_api_reads_the_conversation_from_a_point(db: None, fake: Path) -> None:  # noqa: F811
    run_id = start()
    run_now()
    with TestClient(create_app()) as client:
        everything = client.get(f"/agent/runs/{run_id}/events").json()
        assert everything["status"] == "done"
        total = len(everything["events"])
        assert everything["last_seq"] == total
        rest = client.get(f"/agent/runs/{run_id}/events", params={"after": total - 2}).json()
        assert [e["seq"] for e in rest["events"]] == [total - 1, total]
        nothing = client.get(f"/agent/runs/{run_id}/events", params={"after": total}).json()
        assert nothing["events"] == [] and nothing["last_seq"] == total
        assert client.get("/agent/runs/999/events").status_code == 404


# --- Pasos del aviso ---------------------------------------------------------------------------


def states(action: str, called: set[str], finished: bool = False) -> list[str]:
    return [s.state for s in agent_tasks._steps(action, called, finished)]


def test_steps_follow_the_tools_called() -> None:
    assert states("generate-cv", set()) == ["current"] + ["pending"] * 5
    assert states("generate-cv", {"get_extraction"}) == ["done", "current"] + ["pending"] * 4
    # Un paso posterior da por hechos los anteriores (el agente puede saltarse `check_cv_fit`).
    assert states("generate-cv", {"save_cv_content"}) == ["done"] * 4 + ["current", "pending"]
    assert states("generate-cv", {"save_cv_verification"}) == ["done"] * 5 + ["current"]
    assert states("generate-cv", set(), finished=True) == ["done"] * 6
    assert states("process-jobs", {"list_jobs"}) == []  # sin pasos: solo la actividad


def test_task_view_has_steps_last_tool_and_agent(db: None, fake: Path) -> None:  # noqa: F811
    with session_scope() as session:
        task = AgentTask(
            action="generate-cv", job_id=None, started_at=utcnow() - timedelta(minutes=1)
        )
        session.add(task)
        session.flush()
        for tool in ("get_extraction", "get_profile"):
            session.add(McpCall(channel="mcp", tool=tool, ok=True, called_at=utcnow()))
        session.flush()
        view = agent_tasks.current(session).tasks[-1]
    assert [s.state for s in view.steps] == [
        "done",
        "done",
        "current",
        "pending",
        "pending",
        "pending",
    ]
    assert view.last_tool == "get_profile"
    assert view.agent is None  # en una terminal no hay ejecución
