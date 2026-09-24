"""Servidor MCP: herramientas publicadas, auditoría y nombre del cliente."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import anyio
import mcp_types as types
import pytest
from mcp import Client
from sqlalchemy import select
from typer.testing import CliRunner

from app import cli
from app.agent_interface.tools import TOOLS
from app.core.config import REPO_ROOT
from app.core.db import session_scope
from app.mcp.server import build_server
from app.models import Event, McpCall
from app.services.audit import summarize_args
from tests.agent_support import POSTING_TEXT, extraction, mcp_call

runner = CliRunner()


@pytest.fixture(autouse=True)
def migrated_db() -> None:
    assert runner.invoke(cli.app, ["db", "upgrade"]).exit_code == 0


def _list_tools() -> list[types.Tool]:
    async def _list() -> list[types.Tool]:
        async with Client(build_server()) as client:
            return (await client.list_tools()).tools

    return anyio.run(_list)


def test_tools_published_with_schemas() -> None:
    tools = {tool.name: tool for tool in _list_tools()}
    assert list(tools) == [spec.name for spec in TOOLS]
    save = tools["save_extraction"]
    assert save.input_schema["required"] == ["job_id", "extraction"]
    assert save.input_schema["additionalProperties"] is False
    assert "JobExtraction" in save.input_schema["$defs"]
    assert save.output_schema is not None
    assert "untrusted_job_posting" in (tools["get_job"].description or "")


def test_unknown_tool() -> None:
    is_error, out = mcp_call("delete_everything")
    assert is_error
    assert out["error"]["type"] == "unknown_tool"


def test_client_name_goes_to_audit_and_events() -> None:
    _, added = mcp_call(
        "add_job_from_text",
        {"title": "Data Engineer", "company": "Acme", "text": POSTING_TEXT},
        client_name="claude-code",
    )
    job_id = added["job_id"]
    mcp_call("save_extraction", {"job_id": job_id, "extraction": extraction()}, "codex")
    mcp_call("get_job", {"job_id": 999}, "codex")

    with session_scope() as session:
        calls = session.scalars(select(McpCall).order_by(McpCall.id)).all()
        assert [(c.channel, c.client_name, c.tool, c.job_id, c.ok) for c in calls] == [
            ("mcp", "claude-code", "add_job_from_text", job_id, True),
            ("mcp", "codex", "save_extraction", job_id, True),
            ("mcp", "codex", "get_job", 999, False),
        ]
        assert calls[2].error == "not_found: No existe la oferta 999."
        # Nunca texto crudo en la auditoría.
        assert "Buscamos" not in (calls[0].args_summary or "")
        assert json.loads(calls[1].args_summary or "") == {
            "job_id": job_id,
            "extraction": "<objeto: 17 campos>",
        }
        extracted = session.scalars(select(Event).where(Event.type == "extracted")).one()
        assert extracted.agent_name == "codex"


def test_cli_without_json_is_not_audited() -> None:
    assert runner.invoke(cli.app, ["status"]).exit_code == 0
    assert runner.invoke(cli.app, ["status", "--json"]).exit_code == 0
    with session_scope() as session:
        calls = session.scalars(select(McpCall)).all()
        assert [(c.channel, c.client_name) for c in calls] == [("cli", None)]


@pytest.mark.parametrize(
    ("args", "safe", "expected"),
    [
        ({"url": "https://x.example/1"}, ("url",), {"url": "https://x.example/1"}),
        ({"text": "Oferta…", "limit": 5, "ok": True, "n": None}, (),
         {"text": "<texto: 7 caracteres>", "limit": 5, "ok": True, "n": None}),
        ({"items": [1, 2]}, (), {"items": "<lista: 2 elementos>"}),
        ({"sections": ["skills", "stories"]}, ("sections",), {"sections": ["skills", "stories"]}),
        ({"sections": ["skills", 1]}, ("sections",), {"sections": "<lista: 2 elementos>"}),
        ({"tags": ["a"]}, (), {"tags": "<lista: 1 elementos>"}),
        ({"stage": "x" * 500}, ("stage",), {"stage": "x" * 200}),
    ],
)  # fmt: skip
def test_summarize_args(args: dict[str, Any], safe: tuple[str, ...], expected: Any) -> None:
    assert json.loads(summarize_args(args, safe)) == expected


def test_jh_mcp_over_stdio_writes_only_protocol(tmp_path: Path) -> None:
    """El proceso real `jh-mcp`: se inicializa por stdio y lista herramientas (stdout limpio)."""
    from mcp.client.stdio import StdioServerParameters

    env = {"JH_DATA_DIR": str(tmp_path / "stdio"), "PYTHONIOENCODING": "utf-8"}
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from app.mcp.server import main; main()"],
        cwd=str(REPO_ROOT / "backend"),
        env={**_base_env(), **env},
    )

    async def _run() -> tuple[list[str], dict[str, Any]]:
        async with Client(params) as client:
            tools = [t.name for t in (await client.list_tools()).tools]
            result = await client.call_tool("get_status", {})
            block = result.content[0]
            assert isinstance(block, types.TextContent)
            return tools, json.loads(block.text)

    tools, status = anyio.run(_run)
    assert "get_job" in tools
    # BD sin migrar: error legible, no un fallo del protocolo.
    assert status["error"]["type"] == "database_not_ready"
    assert (tmp_path / "stdio" / "logs" / "mcp.log").exists()


def _base_env() -> dict[str, str]:
    import os

    keep = ("PATH", "SYSTEMROOT", "SystemRoot", "TEMP", "TMP", "USERPROFILE", "HOME")
    return {k: v for k, v in os.environ.items() if k in keep}


def test_agents_check_delegates_to_sync_script(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        calls.append(argv)
        assert cwd == REPO_ROOT
        return subprocess.CompletedProcess(argv, 3)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)
    assert runner.invoke(cli.app, ["agents", "check"]).exit_code == 3
    assert runner.invoke(cli.app, ["agents", "sync"]).exit_code == 3
    script = str(REPO_ROOT / "scripts" / "sync_agents.py")
    assert calls == [[sys.executable, script, "--check"], [sys.executable, script]]


def test_agents_check_real() -> None:
    # El repo tiene lo generado al día (CI lo exige): `jh agents check` debe pasar de verdad.
    assert runner.invoke(cli.app, ["agents", "check"]).exit_code == 0
