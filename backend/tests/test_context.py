"""Contexto del candidato (`data/contexto/`): lectura, límites, plantillas e `init` (fase 13)."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.services import context

runner = CliRunner()


def _copy_demo() -> Path:
    target = context.context_dir()
    target.mkdir(parents=True, exist_ok=True)
    for path in context.TEMPLATES_DIR.glob("*.md"):
        (target / path.name).write_bytes(path.read_bytes())
    return target


def test_demo_templates_cover_every_section() -> None:
    names = {p.stem for p in context.TEMPLATES_DIR.glob("*.md")}
    assert names == set(context.SECTIONS)


def test_get_context_returns_demo_files_without_guides() -> None:
    _copy_demo()
    view = context.get_context()
    assert [f.section for f in view.files] == list(context.SECTIONS)
    assert "nunca respaldan un hecho" in view.note
    criterios = next(f for f in view.files if f.section == "criterios")
    assert criterios.exists and not criterios.empty and not criterios.truncated
    assert criterios.path == "contexto/criterios.md"
    assert "Guardias de fin de semana fijas" in criterios.text
    assert "<!--" not in criterios.text
    raw = (context.context_dir() / "criterios.md").read_bytes()
    assert criterios.size_bytes == len(raw)
    assert criterios.hash is not None and len(criterios.hash) == 64
    assert criterios.modified_at is not None and criterios.modified_at.tzinfo is not None


def test_get_context_filters_sections_in_canonical_order() -> None:
    _copy_demo()
    view = context.get_context(["narrativa", "estilo-redaccion"])
    assert [f.section for f in view.files] == ["estilo-redaccion", "narrativa"]


def test_missing_files_are_reported_not_failed() -> None:
    view = context.get_context()
    assert all(not f.exists and f.empty and f.text == "" and f.hash is None for f in view.files)


def test_hash_changes_with_content() -> None:
    target = _copy_demo()
    before = context.get_context(["criterios"]).files[0].hash
    path = target / "criterios.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n- Nada de turnos de noche.\n", "utf-8")
    after = context.get_context(["criterios"]).files[0]
    assert after.hash != before
    assert "turnos de noche" in after.text


def test_large_file_is_truncated_with_warning() -> None:
    target = context.context_dir()
    target.mkdir(parents=True)
    (target / "narrativa.md").write_text("# Narrativa\n\n" + "ñ" * context.MAX_BYTES, "utf-8")
    item = context.get_context(["narrativa"]).files[0]
    assert item.truncated
    assert len(item.text.encode("utf-8")) <= context.MAX_BYTES
    assert item.warnings and item.warnings[0].startswith("too_large")


def test_non_utf8_file_warns() -> None:
    target = context.context_dir()
    target.mkdir(parents=True)
    (target / "criterios.md").write_bytes("Viajes: máximo 10 %".encode("cp1252"))
    item = context.get_context(["criterios"]).files[0]
    assert item.exists and item.text == ""
    assert item.warnings[0].startswith("invalid_encoding")


def test_init_creates_skeletons_without_demo_data() -> None:
    result = context.init()
    assert result.created == [f"contexto/{s}.md" for s in context.SECTIONS]
    assert result.existing == []
    for section in context.SECTIONS:
        demo = (context.TEMPLATES_DIR / f"{section}.md").read_text(encoding="utf-8")
        created = (context.context_dir() / f"{section}.md").read_text(encoding="utf-8")
        assert context.is_empty(created)
        assert created.startswith("# ")
        assert "<!--" in created
        demo_lines = {
            line.strip()
            for line in context.strip_guides(demo).splitlines()
            if line.strip() and not line.startswith("#")
        }
        assert demo_lines, section
        assert not any(line in created for line in demo_lines), section
    assert "Lucía" not in "".join(
        p.read_text(encoding="utf-8") for p in context.context_dir().glob("*.md")
    )
    for folder in context.DOCUMENT_FOLDERS:
        assert (context.documents_dir() / folder).is_dir()


def test_init_never_overwrites() -> None:
    target = context.context_dir()
    target.mkdir(parents=True)
    (target / "criterios.md").write_text("# Mis criterios\n\nSin guardias.\n", "utf-8")
    result = context.init()
    assert result.existing == ["contexto/criterios.md"]
    assert "contexto/criterios.md" not in result.created
    assert (target / "criterios.md").read_text("utf-8") == "# Mis criterios\n\nSin guardias.\n"
    assert context.init().created == []


@pytest.mark.parametrize(
    ("text", "empty"),
    [
        ("", True),
        ("# Título\n\n<!-- guía\nen dos líneas -->\n\n## Sección\n", True),
        ("# Título\n\nAlgo mío.\n", False),
        ("<!-- solo guía -->", True),
    ],
)
def test_is_empty(text: str, empty: bool) -> None:
    assert context.is_empty(text) is empty


def test_status_counts_document_files() -> None:
    _copy_demo()
    context.init()
    (context.documents_dir() / "cv" / "cv-2025.pdf").write_bytes(b"%PDF")
    status = context.get_status()
    assert [f.section for f in status.files] == list(context.SECTIONS)
    assert not any(hasattr(f, "text") for f in status.files)
    folders = {f.name: f for f in status.folders}
    assert folders["cv"].files == 1 and folders["cv"].exists
    assert folders["linkedin"].files == 0


def test_cli_init_and_show() -> None:
    out = runner.invoke(app, ["context", "init", "--json"])
    assert out.exit_code == 0, out.output
    assert len(json.loads(out.output)["created"]) == len(context.SECTIONS)
    assert runner.invoke(app, ["db", "upgrade"]).exit_code == 0
    shown = runner.invoke(app, ["context", "show", "--sections", "criterios"])
    assert shown.exit_code == 0, shown.output
    assert "## criterios (vacío)" in shown.output


def test_unclosed_comment_is_not_returned_as_text() -> None:
    assert context.strip_guides("# T\n\nMío.\n<!-- guía sin cerrar\nmás guía") == "# T\n\nMío."


def test_skeleton_drops_text_around_comments() -> None:
    text = "# T\nDato <!-- guía --> otro dato\n<!-- empieza\nsigue --> cola\nfin\n"
    assert context.skeleton(text) == "# T\n<!-- guía -->\n<!-- empieza\nsigue -->\n"


def test_unreadable_file_is_not_empty() -> None:
    target = context.context_dir()
    target.mkdir(parents=True)
    (target / "criterios.md").write_bytes("# Criterios\n\nViajes: máximo 10 %".encode("cp1252"))
    item = context.get_context(["criterios"]).files[0]
    assert not item.empty
