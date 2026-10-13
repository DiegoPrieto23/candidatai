"""Comandos `cai templates inspect | build-docx | validate | preview` (fase 08.3)."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app import cli
from app.core.config import get_settings
from app.services.documents import pdf
from app.services.documents.importer import paths
from tests.cv_support import fake_converter
from tests.template_support import MAPPING, make_cv

runner = CliRunner()


@pytest.fixture(autouse=True)
def converter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf, "get_converter", lambda: fake_converter())


@pytest.fixture
def source(isolated_env: Path) -> Path:
    paths.uploads_dir().mkdir(parents=True)
    return make_cv(paths.uploads_dir() / "mi-cv.docx")


def _jh(*argv: str) -> tuple[int, dict]:  # type: ignore[type-arg]
    result = runner.invoke(cli.app, list(argv))
    return result.exit_code, json.loads(result.stdout)


def _mapping_file(name: str = "mi-cv-mapping.json") -> Path:
    tmp = get_settings().tmp_dir
    tmp.mkdir(parents=True, exist_ok=True)
    path = tmp / name
    path.write_text(json.dumps(MAPPING), encoding="utf-8")
    return path


def test_inspect_json(source: Path) -> None:
    code, out = _jh("templates", "inspect", str(source), "--json")
    assert code == 0
    assert out["format"] == "docx" and out["pages"] == 1
    assert out["paragraphs"][0]["text"] == "Ana Ficticia Pérez"
    assert [s["section"] for s in out["sections"]][:2] == ["summary", "experience"]


def test_inspect_outside_data_is_invalid_file(tmp_path: Path) -> None:
    outside = make_cv(tmp_path / "fuera.docx")
    code, out = _jh("templates", "inspect", str(outside), "--json")
    assert code == 1 and out["error"]["type"] == "invalid_file"


def test_build_validate_and_preview(source: Path) -> None:
    mapping = _mapping_file()
    code, out = _jh(
        "templates", "build-docx", "--source", str(source), "--mapping", str(mapping),
        "--id", "mi-cv", "--json",
    )  # fmt: skip
    assert code == 0, out
    assert out["template_id"] == "mi-cv" and out["header_paragraphs"] == [0, 1, 2]
    assert not mapping.exists()  # como `--file`: se borra tras procesarse bien

    code, out = _jh("templates", "validate", "mi-cv", "--json")
    assert code == 0 and out["ok"] and out["sections"][0] == "summary"

    code, out = _jh("templates", "preview", "mi-cv", "--json")
    assert code == 0 and out["pages"] == 1 and out["fits"]
    assert out["png_path"] == "templates/mi-cv/preview.png"
    assert (get_settings().data_dir / out["png_path"]).is_file()

    # Ya existe: sin --force es un error `exists`.
    code, out = _jh(
        "templates", "build-docx", "--source", str(source), "--mapping", str(_mapping_file()),
        "--id", "mi-cv", "--json",
    )  # fmt: skip
    assert code == 1 and out["error"]["type"] == "exists"


def test_build_mapping_errors_are_validation_errors(source: Path) -> None:
    tmp = get_settings().tmp_dir
    tmp.mkdir(parents=True)
    bad = tmp / "malo.json"
    bad.write_text(
        json.dumps({"paragraphs": [{"index": 0, "action": "variable", "text": "{{ nombre }}"}]}),
        encoding="utf-8",
    )
    code, out = _jh(
        "templates", "build-docx", "--source", str(source), "--mapping", str(bad),
        "--id", "malo", "--json",
    )  # fmt: skip
    assert code == 1 and out["error"]["type"] == "validation_error"
    assert out["error"]["details"][0]["received"] == "nombre"
    assert bad.exists()  # se queda para corregir y reintentar


def test_preview_of_builtin_goes_to_cache_and_real_needs_profile(isolated_env: Path) -> None:
    code, out = _jh("templates", "preview", "ats-simple", "--json")
    assert code == 0 and out["png_path"].startswith("cache/previews/ats-simple-demo-")

    assert runner.invoke(cli.app, ["db", "upgrade"]).exit_code == 0
    code, out = _jh("templates", "preview", "ats-simple", "--profile", "real", "--json")
    assert code == 1 and out["error"]["type"] == "not_found"

    assert runner.invoke(cli.app, ["profile", "import", "demo/profile.example.yaml"]).exit_code == 0
    code, out = _jh("templates", "preview", "ats-simple", "--profile", "real", "--json")
    assert code == 0 and out["profile"] == "real"


def test_validate_unknown_template() -> None:
    code, out = _jh("templates", "validate", "no-existe", "--json")
    assert code == 1 and out["error"]["type"] == "not_found"
