"""CLI `jh alerts poll | list | expire`."""

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app import cli
from app.core import migrations

FIXTURES = Path(__file__).parent / "fixtures" / "email"
runner = CliRunner()


@pytest.fixture
def inbox(isolated_env: Path) -> Path:
    migrations.upgrade()
    folder = isolated_env / "inbox"
    folder.mkdir()
    shutil.copy(FIXTURES / "linkedin_alert.eml", folder / "a.eml")
    return folder


def test_poll_list_and_expire(inbox: Path) -> None:
    result = runner.invoke(cli.app, ["alerts", "poll"])
    assert result.exit_code == 0, result.output
    assert "1 correo nuevo, 3 ofertas, 3 nuevas (3 como resumen)" in result.output

    result = runner.invoke(cli.app, ["alerts", "poll", "--json"])
    data = json.loads(result.output)
    assert (data["messages"], data["created"]) == (0, 0)

    result = runner.invoke(cli.app, ["alerts", "list", "--json"])
    data = json.loads(result.output)
    assert data["total"] == 3
    assert {j["platform"] for j in data["jobs"]} == {"linkedin"}

    result = runner.invoke(cli.app, ["alerts", "list"])
    assert "3 ofertas resumen, 3 pasan el prefiltro" in result.output  # sin perfil

    result = runner.invoke(cli.app, ["alerts", "expire", "--json"])
    assert json.loads(result.output)["expired"] == []


def test_poll_without_migrations_fails_cleanly(isolated_env: Path) -> None:
    result = runner.invoke(cli.app, ["alerts", "poll", "--json"])
    assert result.exit_code != 0
    assert json.loads(result.output)["ok"] is False
