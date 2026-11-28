"""`get_policies`: las políticas por secciones, para que los roles que redactan y verifican no
tengan que leer ficheros (y quepan en el techo de Codex y OpenCode)."""

from pathlib import Path

import pytest

from app.services import agent_registry, agent_run_config, policies_text
from app.services.agent_actions import ACTIONS, ROLE_EXTRAS

SAMPLE = """# Políticas

Intro que no es una sección.

## 1. Veracidad

Nada inventado.

### Detalle

Más.

## 3. CV

Una página.
"""


def test_reads_the_real_document_by_section() -> None:
    every = policies_text.read()
    assert every.source == "docs/POLICIES.md"
    numbers = [s.number for s in every.sections]
    assert numbers == sorted(numbers) and {1, 3, 4, 7} <= set(numbers)
    picked = policies_text.read([7, 1])
    assert [s.number for s in picked.sections] == [1, 7]  # en el orden del documento
    assert picked.sections[0].text.startswith("## 1. Veracidad")


def test_sections_keep_their_subsections(tmp_path: Path) -> None:
    path = tmp_path / "POLICIES.md"
    path.write_text(SAMPLE, encoding="utf-8")
    view = policies_text.read(path=path)
    assert [(s.number, s.title) for s in view.sections] == [(1, "Veracidad"), (3, "CV")]
    assert "### Detalle" in view.sections[0].text and "Intro" not in view.sections[0].text


def test_unknown_section_says_which_exist(tmp_path: Path) -> None:
    path = tmp_path / "POLICIES.md"
    path.write_text(SAMPLE, encoding="utf-8")
    with pytest.raises(policies_text.UnknownSectionError, match=r"sección 2 .*hay: 1, 3"):
        policies_text.read([1, 2], path=path)


def test_writer_and_verifier_no_longer_read_files() -> None:
    for role in ("writer", "verifier"):
        tools = agent_run_config.role_tools(role)
        assert "read" not in tools and "mcp:get_policies" in tools
        text = (agent_registry.REPO_ROOT / ".agents" / "roles" / f"{role}.md").read_text("utf-8")
        assert "docs/POLICIES.md" not in text  # las pide con `get_policies`


@pytest.mark.parametrize(
    "action", ["generate-cv", "correct-cv", "verify-cv", "generate-cover-letter"]
)
def test_cv_and_letter_fit_a_config_ceiling(action: str) -> None:
    spec = ACTIONS[action]  # type: ignore[index]
    assert set(ROLE_EXTRAS) <= set(spec.background)
    assert len(spec.background) == len(set(spec.background))  # sin repetir
    assert "get_job" not in spec.background
    assert agent_run_config.ceiling_problem(action) is None  # type: ignore[arg-type]
