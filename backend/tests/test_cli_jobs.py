"""Comandos `jh jobs add-url`, `jh jobs add-text` y `jh jobs list`."""

import json
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from app import cli
from app.core.config import get_settings

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"
TEXT = "Buscamos Data Analyst para el equipo de analítica. " * 12


@pytest.fixture(autouse=True)
def migrated_db() -> None:
    assert runner.invoke(cli.app, ["db", "upgrade"]).exit_code == 0


def _write(text: str, encoding: str = "utf-8", name: str = "oferta.txt") -> Path:
    tmp_dir = get_settings().tmp_dir
    tmp_dir.mkdir(parents=True, exist_ok=True)
    path = tmp_dir / name
    path.write_text(text, encoding=encoding)
    return path


@respx.mock
def test_add_url_json() -> None:
    url = "https://careers.example.com/jobs/1"
    html = (FIXTURES / "hidden_ai.html").read_text(encoding="utf-8")
    respx.get(url).mock(return_value=httpx.Response(200, text=html))

    result = runner.invoke(cli.app, ["jobs", "add-url", url, "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "job_id": 1,
        "created": True,
        "duplicate_of": None,
        "risk_flags": ["hidden_text", "injection_phrase"],
    }

    result = runner.invoke(cli.app, ["jobs", "add-url", url])
    assert result.exit_code == 0
    assert "ya existía: 1" in result.stdout


@respx.mock
def test_add_url_text_output_warns() -> None:
    url = "https://careers.example.com/jobs/2"
    html = (FIXTURES / "injection_es.html").read_text(encoding="utf-8")
    respx.get(url).mock(return_value=httpx.Response(200, text=html))

    result = runner.invoke(cli.app, ["jobs", "add-url", url])
    assert result.exit_code == 0, result.output
    assert "Oferta 1 dada de alta." in result.stdout
    assert "injection_phrase" in result.stdout


def test_add_url_linkedin_error() -> None:
    result = runner.invoke(
        cli.app, ["jobs", "add-url", "https://www.linkedin.com/jobs/view/1", "--json"]
    )
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["ok"] is False
    assert data["error"]["type"] == "invalid_request"
    assert "add-text" in data["error"]["message"]


def test_add_text_and_list() -> None:
    # Con BOM, como lo guardan el Bloc de notas o PowerShell.
    path = _write(TEXT, encoding="utf-8-sig")
    args = ["jobs", "add-text", "--title", "Data Analyst", "--company", "Acme", "--file"]

    result = runner.invoke(cli.app, [*args, str(path), "--location", "Bilbao", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["job_id"] == 1
    assert not path.exists()  # procesado bien: se borra

    path = _write(TEXT)
    result = runner.invoke(
        cli.app, ["jobs", "add-text", "--title", "Data Analyst SQL", "--company", "Acme",
                  "--file", str(path)]
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "duplicado de la oferta 1" in result.stdout

    result = runner.invoke(cli.app, ["jobs", "list", "--json"])
    assert result.exit_code == 0, result.output
    jobs = json.loads(result.stdout)["jobs"]
    assert [(j["id"], j["stage"]) for j in jobs] == [(2, "closed"), (1, "pending_extraction")]
    assert jobs[1]["location"] == "Bilbao"
    assert "Buscamos" not in result.stdout  # nunca el texto crudo

    result = runner.invoke(cli.app, ["jobs", "list", "--stage", "pending_extraction", "--json"])
    assert [j["id"] for j in json.loads(result.stdout)["jobs"]] == [1]

    result = runner.invoke(cli.app, ["jobs", "list"])
    assert result.exit_code == 0
    assert "Data Analyst SQL · Acme (duplicado de 1)" in result.stdout


def test_add_text_missing_file() -> None:
    result = runner.invoke(
        cli.app,
        ["jobs", "add-text", "--title", "T", "--company", "C", "--file",
         str(get_settings().tmp_dir / "nope.txt"), "--json"],
    )  # fmt: skip
    assert result.exit_code == 1
    error = json.loads(result.stdout)["error"]
    assert error["type"] == "invalid_file"
    assert "No se pudo leer" in error["message"]


def test_add_text_file_outside_tmp(tmp_path: Path) -> None:
    path = tmp_path / "oferta.txt"
    path.write_text(TEXT, encoding="utf-8")
    args = ["jobs", "add-text", "--title", "T", "--company", "C", "--file", str(path), "--json"]
    result = runner.invoke(cli.app, args)
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["type"] == "invalid_file"
    assert path.exists()

    # Tampoco vale escapar de data/tmp/ con `..`.
    sneaky = get_settings().tmp_dir / ".." / "oferta.txt"
    sneaky.parent.mkdir(parents=True, exist_ok=True)
    sneaky.write_text(TEXT, encoding="utf-8")
    args[-2] = str(sneaky)
    result = runner.invoke(cli.app, args)
    assert json.loads(result.stdout)["error"]["type"] == "invalid_file"


def test_add_text_relative_path_from_repo_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # `uv run --directory backend jh …` corre en backend/, pero la ruta se escribe desde la raíz.
    from app.agent_interface import cli as agent_cli

    monkeypatch.setattr(agent_cli, "REPO_ROOT", tmp_path)  # data/ del test = tmp_path/data
    backend = tmp_path / "backend"
    backend.mkdir()
    monkeypatch.chdir(backend)
    path = _write(TEXT)
    args = ["jobs", "add-text", "--title", "T", "--company", "C", "--json"]
    result = runner.invoke(cli.app, [*args, "--file", f"data/tmp/{path.name}"])
    assert result.exit_code == 0, result.output
    assert not path.exists()


def test_add_text_failure_keeps_file() -> None:
    path = _write("Muy corto.")
    args = ["jobs", "add-text", "--title", "T", "--company", "C", "--file", str(path), "--json"]
    result = runner.invoke(cli.app, [*args, "--url", "ftp://nope"])
    assert result.exit_code == 1
    assert path.exists()  # si falla, el fichero se queda para corregir y reintentar


def test_list_empty_and_invalid_stage() -> None:
    result = runner.invoke(cli.app, ["jobs", "list"])
    assert result.exit_code == 0
    assert "No hay ofertas." in result.stdout

    result = runner.invoke(cli.app, ["jobs", "list", "--stage", "nope", "--json"])
    assert result.exit_code == 1
    error = json.loads(result.stdout)["error"]
    assert error["type"] == "validation_error"
    assert error["details"][0]["field"] == "stage"
    assert error["details"][0]["received"] == "nope"
    assert "pending_triage" in error["details"][0]["reason"]
