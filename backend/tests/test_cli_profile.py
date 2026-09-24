"""Comandos `jh profile validate | import | diff | init | show`."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from app import cli
from app.core.config import REPO_ROOT
from app.services.profile import EXAMPLE_PATH

runner = CliRunner()
EXAMPLE: dict[str, Any] = yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))


def _jh(*argv: str) -> tuple[int, str, str]:
    result = runner.invoke(cli.app, list(argv))
    return result.exit_code, result.stdout, result.stderr


def _write(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    return path


@pytest.fixture
def migrated_db() -> None:
    assert runner.invoke(cli.app, ["db", "upgrade"]).exit_code == 0


def test_validate_example_by_repo_relative_path(monkeypatch: pytest.MonkeyPatch) -> None:
    # Como la ejecutan los agentes: `uv run --directory backend jh …` corre en `backend/`.
    monkeypatch.chdir(REPO_ROOT / "backend")
    code, out, _ = _jh("profile", "validate", "demo/profile.example.yaml")
    assert code == 0
    assert "Perfil válido" in out
    assert "2 experiencias, 5 logros, 12 skills, 2 historias." in out


def test_validate_json() -> None:
    code, out, _ = _jh("profile", "validate", str(EXAMPLE_PATH), "--json")
    assert code == 0
    assert json.loads(out) == {
        "ok": True,
        "path": str(EXAMPLE_PATH),
        "counts": {"experience": 2, "achievements": 5, "skills": 12, "stories": 2},
    }


def test_validate_broken_profile(tmp_path: Path) -> None:
    data = copy.deepcopy(EXAMPLE)
    data["experience"][1]["achievements"][0]["id"] = "A 1"
    data["stories"][0]["evidence"] = ["exp-nope/a1"]  # no llega a comprobarse: hay errores antes
    path = _write(tmp_path / "p.yaml", data)

    code, out, _ = _jh("profile", "validate", str(path), "--json")
    assert code == 1
    error = json.loads(out)["error"]
    assert error["type"] == "validation_error"
    assert error["message"].startswith("Perfil no válido (1 error)")
    [detail] = error["details"]
    assert detail["field"] == "experience[1].achievements[0].id"
    assert detail["received"] == "A 1"

    code, _, err = _jh("profile", "validate", str(path))
    assert code == 1
    assert "experience[1].achievements[0].id" in err
    assert "(recibido: 'A 1')" in err


def test_validate_default_path_missing() -> None:
    code, out, _ = _jh("profile", "validate", "--json")
    assert code == 1
    error = json.loads(out)["error"]
    assert error["type"] == "not_found"
    assert "jh profile init" in error["message"]


def test_init_then_validate_default(isolated_env: Path) -> None:
    code, out, _ = _jh("profile", "init", "--json")
    assert code == 0
    assert json.loads(out) == {"ok": True, "path": str(isolated_env / "profile.yaml")}
    assert _jh("profile", "validate")[0] == 0

    code, out, _ = _jh("profile", "init", "--json")
    assert code == 1
    assert json.loads(out)["error"]["type"] == "exists"


@pytest.mark.usefixtures("migrated_db")
def test_import_twice_and_diff(tmp_path: Path) -> None:
    code, out, _ = _jh("profile", "import", str(EXAMPLE_PATH), "--json")
    assert code == 0
    first = json.loads(out)
    assert first["ok"] is True and first["created"] is True and first["profile_version_id"] == 1

    code, out, _ = _jh("profile", "import", str(EXAMPLE_PATH))
    assert code == 0
    assert "Sin cambios: sigue vigente la versión 1." in out

    code, out, _ = _jh("profile", "diff")
    assert "Solo hay una versión (1)" in out

    data = copy.deepcopy(EXAMPLE)
    data["headline"] = "Data Engineer · Python"
    code, out, _ = _jh("profile", "import", str(_write(tmp_path / "p.yaml", data)))
    assert "Perfil importado: versión 2." in out

    code, out, _ = _jh("profile", "diff")
    assert code == 0
    assert "+headline: Data Engineer · Python" in out

    code, out, _ = _jh("profile", "diff", "--json")
    assert json.loads(out)["from_version"] == 1


def test_import_needs_migrated_db() -> None:
    code, out, _ = _jh("profile", "import", str(EXAMPLE_PATH), "--json")
    assert code == 1
    assert json.loads(out)["error"]["type"] == "database_not_ready"


@pytest.mark.usefixtures("migrated_db")
def test_diff_without_profile() -> None:
    code, out, _ = _jh("profile", "diff", "--json")
    assert code == 1
    assert json.loads(out)["error"]["type"] == "not_found"


@pytest.mark.usefixtures("migrated_db")
def test_show_text_is_public() -> None:
    _jh("profile", "import", str(EXAMPLE_PATH))
    code, out, _ = _jh("profile", "show")
    assert code == 0
    assert "Perfil, versión 1" in out
    assert "Lucía Varela Otero" in out
    assert "lucia.varela@example.com" not in out
    assert "600 000 000" not in out
    assert "salary_floor_eur" not in out
