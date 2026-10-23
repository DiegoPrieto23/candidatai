"""`CHANGELOG.md` y las notas de release que salen de él (fase 25.6)."""

import importlib.util
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest

from app.core.config import REPO_ROOT


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "release_notes", REPO_ROOT / "scripts" / "release_notes.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["release_notes"] = module
    spec.loader.exec_module(module)
    return module


notes = _load_script()
CHANGELOG = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")

GOOD = """# Changelog

## [Sin publicar]

### Añadido
- Algo nuevo.

## [0.2.0] - 2026-11-01

### Añadido
- Una cosa.

### Corregido
- Un fallo.

## [0.1.0] - 2026-10-16

### Añadido
- La primera.

[Sin publicar]: https://example.com/compare/v0.2.0...HEAD
[0.2.0]: https://example.com/compare/v0.1.0...v0.2.0
[0.1.0]: https://example.com/releases/tag/v0.1.0
"""


def test_the_changelog_has_the_expected_structure() -> None:
    assert notes.check(CHANGELOG) == []
    sections, _ = notes.parse(CHANGELOG)
    assert sections[0].name == "Sin publicar"
    # Fase 28.1: la primera release publicada, 0.1.0, recoge todo lo anterior (fases 01-28.1).
    first = next(s for s in sections if s.name == "0.1.0")
    for mark in ("OpenCode", "Personio", "expand", "cai stats story", "SHA-256", "Docker"):
        assert mark in first.text(), mark


def test_the_latest_version_is_the_one_in_pyproject() -> None:
    sections, _ = notes.parse(CHANGELOG)
    released = [s.name for s in sections if s.name != "Sin publicar"]
    pyproject = tomllib.loads((REPO_ROOT / "backend" / "pyproject.toml").read_text("utf-8"))
    assert released[0] == pyproject["project"]["version"]


def test_notes_for_a_tag_are_its_section() -> None:
    assert notes.check(GOOD) == []
    body = notes.notes_for("v0.2.0", GOOD)
    assert body == "### Añadido\n- Una cosa.\n\n### Corregido\n- Un fallo.\n"
    assert notes.notes_for("0.1.0", GOOD) == "### Añadido\n- La primera.\n"


@pytest.mark.parametrize(
    ("tag", "message"),
    [("v0.3.0", "no hay sección"), ("prueba", "versión semántica"), ("v1.2", "versión semántica")],
)
def test_notes_fail_without_a_section(tag: str, message: str) -> None:
    with pytest.raises(notes.ChangelogError, match=message):
        notes.notes_for(tag, GOOD)


@pytest.mark.parametrize(
    ("broken", "message"),
    [
        (GOOD.replace("## [Sin publicar]\n", ""), "primera sección"),
        (GOOD.replace("### Corregido", "### Arreglos"), "grupos desconocidos"),
        (GOOD.replace("## [0.2.0] - 2026-11-01", "## [0.0.9] - 2026-11-01"), "más nueva"),
        (GOOD.replace("[0.1.0]: https://example.com/releases/tag/v0.1.0\n", ""), "enlace"),
        (GOOD.replace("## [0.1.0] - 2026-10-16", "## 0.1.0"), "no es «## [Sin publicar]»"),
        (GOOD.replace("- Una cosa.\n", "").replace("- Un fallo.\n", ""), "ninguna entrada"),
    ],
)
def test_check_explains_what_is_wrong(broken: str, message: str) -> None:
    errors = notes.check(broken)
    assert any(message in error for error in errors), errors


def test_cli_writes_the_notes_and_fails_without_section(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "CHANGELOG.md"
    path.write_text(GOOD, encoding="utf-8")
    assert notes.main(["v0.2.0", "--changelog", str(path)]) == 0
    assert capsys.readouterr().out.startswith("### Añadido\n- Una cosa.")
    assert notes.main(["v0.3.0", "--changelog", str(path)]) == 1
    assert "no hay sección" in capsys.readouterr().err
    assert notes.main(["--check", "--changelog", str(path)]) == 0
