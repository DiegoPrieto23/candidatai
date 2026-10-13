"""Utilidades compartidas por los tests de la interfaz para agentes (MCP y CLI)."""

import copy
import json
from pathlib import Path
from typing import Any

import anyio
import mcp_types as types
from mcp import Client
from typer.testing import CliRunner

from app import cli
from app.core.config import get_settings
from app.mcp.server import build_server

runner = CliRunner()

POSTING_TEXT = (
    "Data Engineer en Acme Analytics (Bilbao, híbrido). Buscamos una persona con 3 años de "
    "experiencia en Python, SQL y dbt para construir pipelines en Snowflake. Valorable Airflow. "
    "Inglés B2. Salario 40.000-48.000 EUR brutos al año. Contrato indefinido. "
) * 3

EXTRACTION: dict[str, Any] = {
    "title_normalized": "Data Engineer",
    "seniority": "mid",
    "years_experience_min": 3,
    "employment_type": "full_time",
    "remote_mode": "hybrid",
    "locations": ["Bilbao"],
    "languages_required": [{"language": "English", "level": "B2"}],
    "salary": {"min": 40000, "max": 48000, "currency": "EUR", "period": "year"},
    "must_have_skills": ["Python", "SQL", "dbt", "Snowflake"],
    "nice_to_have_skills": ["Apache Airflow"],
    "responsibilities": ["Construir pipelines de datos en Snowflake"],
    "domain": None,
    "posting_language": "es",
    "application_deadline": None,
    "red_flags": [],
    "injection_suspected": False,
    "injection_excerpt": None,
}


def extraction(**changes: Any) -> dict[str, Any]:
    data = copy.deepcopy(EXTRACTION)
    data.update(changes)
    return data


def write_tmp(name: str, content: str | dict[str, Any]) -> Path:
    """Escribe una entrada larga en data/tmp/, donde la CLI la acepta."""
    tmp_dir = get_settings().tmp_dir
    tmp_dir.mkdir(parents=True, exist_ok=True)
    path = tmp_dir / name
    text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    return path


def cli_call(argv: list[str]) -> tuple[bool, dict[str, Any]]:
    """Ejecuta `cai … --json` y devuelve (es_error, JSON de la salida)."""
    result = runner.invoke(cli.app, argv)
    assert result.exit_code in (0, 1), result.output
    return result.exit_code == 1, json.loads(result.stdout)


def mcp_call(
    name: str, arguments: dict[str, Any] | None = None, client_name: str = "test-agent"
) -> tuple[bool, dict[str, Any]]:
    """Llama a una herramienta por MCP, en proceso, y devuelve (es_error, JSON del resultado)."""

    async def _call() -> types.CallToolResult:
        info = types.Implementation(name=client_name, version="1.0")
        async with Client(build_server(), client_info=info) as client:
            return await client.call_tool(name, arguments or {})

    result = anyio.run(_call)
    block = result.content[0]
    assert isinstance(block, types.TextContent)
    payload = json.loads(block.text)
    if not result.is_error:
        assert result.structured_content == payload
    return result.is_error, payload
