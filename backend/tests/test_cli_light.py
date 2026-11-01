"""`cai --help`, el supervisor de `cai start` y la API no cargan los comandos pesados de la CLI."""

import subprocess
import sys
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from app import cli
from app.core import migrations
from app.core.config import REPO_ROOT

# Lo que cuesta décimas de segundo y decenas de MB, y el supervisor no usa.
HEAVY = ("sqlalchemy", "httpx", "docx", "alembic", "fastapi", "rapidfuzz", "app.cli_commands")


def loaded_after(code: str) -> list[str]:
    """Qué módulos de `HEAVY` quedan cargados tras ejecutar `code` en un Python limpio."""
    check = f"{code}\nimport sys\nprint([m for m in {HEAVY!r} if m in sys.modules])"
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", check],
        cwd=REPO_ROOT / "backend",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",  # la ayuda sale con la codificación de la consola
        check=True,
    )
    return eval(result.stdout.strip().splitlines()[-1])  # noqa: S307 - lo ha impreso el propio test


@pytest.mark.parametrize(
    "code",
    [
        "import app.cli",
        "from app.cli import app\n"
        "try:\n    app(['--help'], prog_name='cai')\nexcept SystemExit:\n    pass",
        "import app.services.launcher",
    ],
    ids=["import", "help", "launcher"],
)
def test_the_cli_root_and_the_supervisor_stay_light(code: str) -> None:
    assert loaded_after(code) == []


def test_the_help_table_matches_the_real_commands() -> None:
    """`COMMANDS` es lo que lista `cai --help` sin cargar los comandos: debe ser lo de verdad."""
    from app.cli_commands import app as commands_app

    group = typer.main.get_group(commands_app)
    real = {
        name: cli.first_paragraph(command.help)
        for name in group.list_commands(None)  # type: ignore[arg-type]
        if not (command := group.commands[name]).hidden
    }
    assert real == cli.COMMANDS, "actualiza `COMMANDS` en app/cli.py con lo de `real`"


def test_help_lists_every_command_and_they_still_run() -> None:
    runner = CliRunner()
    help_text = runner.invoke(cli.app, ["--help"]).output
    for name in ("start", "serve", "paths", "doctor", "jobs", "received-offers", "followups"):
        assert name in help_text
    assert "pnpm gen:api" in help_text  # la línea de `openapi`, sacada de la tabla
    assert runner.invoke(cli.app, ["jobs", "--help"]).exit_code == 0
    unknown = runner.invoke(cli.app, ["no-existe"])
    assert unknown.exit_code == 2 and "no-existe" in unknown.output


def test_serve_migrates_only_when_start_asks(monkeypatch: pytest.MonkeyPatch) -> None:
    """`cai start` no migra: se lo pide a la API (`--migrate`). A mano, `serve` solo comprueba."""
    import uvicorn

    steps: list[str] = []
    monkeypatch.setattr(uvicorn, "run", lambda *_a, **_kw: steps.append("run"))
    monkeypatch.setattr(migrations, "upgrade", lambda: steps.append("upgrade"))
    monkeypatch.setattr(migrations, "ensure_current", lambda: steps.append("check"))
    runner = CliRunner()

    def serve(*args: str) -> Any:
        steps.clear()
        result = runner.invoke(cli.app, ["serve", "--port", "8123", *args])
        assert result.exit_code == 0, result.output
        return list(steps)

    assert serve("--migrate") == ["upgrade", "run"]
    assert serve() == ["check", "run"]
