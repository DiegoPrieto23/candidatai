"""`scripts/build_faq.py` pasa las preguntas de la ayuda del portal a `docs/`.

Las preguntas frecuentes se escriben una vez, en los textos de la UI: lo que hay en `docs/` tiene
que ser lo que sale de ellos, en los dos idiomas."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

from app.core.config import REPO_ROOT


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "build_faq", REPO_ROOT / "scripts" / "build_faq.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["build_faq"] = module
    spec.loader.exec_module(module)
    return module


build_faq = _load()


def _repo(tmp_path: Path) -> Path:
    topics = {
        "groups": ["start", "other"],
        "topics": [
            {"id": "two", "group": "other", "screen": None},
            {"id": "one", "group": "start", "screen": "home"},
        ],
    }
    texts = {
        "screens": {"home": "Inicio"},
        "groups": {"start": "Primeros pasos", "other": "Otras"},
        "faq": {
            "one": {"q": "¿Uno?", "a": "Respuesta uno.", "keywords": "no sale"},
            "two": {"q": "¿Dos?", "a": "Respuesta dos.", "keywords": "tampoco"},
        },
    }
    (tmp_path / "frontend/src/lib").mkdir(parents=True)
    (tmp_path / "frontend/src/lib/helpTopics.json").write_text(json.dumps(topics), "utf-8")
    for language in ("es", "en"):
        folder = tmp_path / "frontend/src/locales" / language
        folder.mkdir(parents=True)
        (folder / "help.json").write_text(json.dumps(texts), "utf-8")
    (tmp_path / "docs").mkdir()
    return tmp_path


def test_the_published_faq_is_up_to_date() -> None:
    assert build_faq.outdated(REPO_ROOT) == []


def test_questions_follow_the_group_order_with_their_screen(tmp_path: Path) -> None:
    text = build_faq.render(_repo(tmp_path), build_faq.PAGES[0])
    assert text.startswith("# Preguntas frecuentes\n")
    assert text.index("## Primeros pasos") < text.index("### ¿Uno?") < text.index("## Otras")
    assert "Respuesta uno.\n\nDónde: «Inicio»." in text
    assert "Respuesta dos.\n" in text
    assert "no sale" not in text
    assert text.endswith("Respuesta dos.\n")


def test_check_detects_a_missing_or_edited_file(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    assert build_faq.outdated(root) == ["docs/PREGUNTAS.md", "docs/FAQ.md"]
    for page in build_faq.PAGES:
        (root / page.path).write_text(build_faq.render(root, page), "utf-8", newline="\n")
    assert build_faq.outdated(root) == []
    (root / "docs/FAQ.md").write_text("otra cosa", "utf-8")
    assert build_faq.outdated(root) == ["docs/FAQ.md"]
