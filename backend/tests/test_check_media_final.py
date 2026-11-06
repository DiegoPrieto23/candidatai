"""`scripts/check_media_final.py` encuentra los medios provisionales que quedan por rehacer.

Los casos montan un repositorio pequeño en una carpeta temporal: el script tiene que listar cada
marcador con su medio, fallar mientras quede alguno y pasar cuando no hay ninguno."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from app.core.config import REPO_ROOT

MARKER = "<!-- media:provisional -->"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_media_final", REPO_ROOT / "scripts" / "check_media_final.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_media_final"] = module
    spec.loader.exec_module(module)
    return module


media = _load()


def _write(root: Path, rel: str, text: str) -> None:
    (root / rel).parent.mkdir(parents=True, exist_ok=True)
    (root / rel).write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _write(
        tmp_path,
        "README.md",
        f'# App\n\n{MARKER}\n<img src="docs/img/en/home.webp" alt="Home">\n\n'
        f'<td>{MARKER}<img src="docs/img/en/triage.webp"></td>\n',
    )
    _write(tmp_path, "README.es.md", '# App\n\n<img src="docs/img/es/home.webp" alt="Inicio">\n')
    _write(
        tmp_path,
        "docs/FEATURES.md",
        f"| Inbox | `/bandeja` | {MARKER} [Inbox](img/en/inbox.webp) · "
        f"{MARKER} [▶ Discard](img/en/anim/discard.webp) |\n",
    )
    _write(tmp_path, "docs/sub/OTHER.md", "Sin medios.\n")
    _write(
        tmp_path,
        "site/index.html",
        f'<figure>\n  {MARKER}\n  <img src="img/home.webp" alt="">\n</figure>\n',
    )
    _write(
        tmp_path,
        "site/style.css",
        f'/* {MARKER} */\n.hero {{ background: url("img/hero.png"); }}\n',
    )
    _write(tmp_path, "other/NOTES.md", f"{MARKER}\n![x](a.webp)\n")  # fuera de lo que se revisa
    return tmp_path


def test_lists_every_marker_with_its_media(repo: Path) -> None:
    found = [(m.path, m.line, m.media) for m in media.find_markers(repo)]
    assert found == [
        ("README.md", 3, "docs/img/en/home.webp"),
        ("README.md", 6, "docs/img/en/triage.webp"),
        ("docs/FEATURES.md", 1, "img/en/inbox.webp"),
        ("docs/FEATURES.md", 1, "img/en/anim/discard.webp"),
        ("site/index.html", 2, "img/home.webp"),
        ("site/style.css", 1, "img/hero.png"),
    ]


def test_fails_while_any_marker_is_left(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert media.main([], root=repo) == 1
    assert "Quedan 6 medios provisionales" in capsys.readouterr().out


def test_list_never_fails(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert media.main(["--list"], root=repo) == 0
    out = capsys.readouterr().out
    assert "README.md:3: docs/img/en/home.webp" in out
    assert "6 medios provisionales." in out


def test_passes_without_markers(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _write(tmp_path, "README.md", '<img src="docs/img/en/home.webp">\n')
    assert media.main([], root=tmp_path) == 0
    assert "Ningún medio provisional" in capsys.readouterr().out


def test_a_marker_without_media_is_still_counted(tmp_path: Path) -> None:
    _write(tmp_path, "README.md", f"{MARKER}\nTexto sin imagen.\n")
    assert [(m.line, m.media) for m in media.find_markers(tmp_path)] == [(1, "?")]


def test_the_repo_markers_point_to_existing_files() -> None:
    """Los medios marcados del repositorio existen: un provisional nunca es un enlace roto."""
    for marker in media.find_markers(REPO_ROOT):
        if marker.path.startswith("site/"):
            continue  # la web los toma de docs/img al construirse
        assert marker.media != "?", f"{marker.path}:{marker.line} no acompaña a ningún medio"
        target = (REPO_ROOT / marker.path).parent / marker.media
        assert target.is_file(), f"{marker.path}:{marker.line}: {marker.media} no existe"
