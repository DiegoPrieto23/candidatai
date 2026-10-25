"""Fase 28.3a: `scripts/check_readme_coverage.py` impide páginas o skills sin contar.

Cada caso copia lo que lee el script (rutas, skills, README y listas) a una carpeta temporal,
estropea una cosa y comprueba que el script lo detecta."""

from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

from app.core.config import REPO_ROOT

FILES = (
    "frontend/src/App.tsx",
    "README.md",
    "README.es.md",
    "docs/FEATURES.md",
    "docs/FUNCIONALIDADES.md",
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "check_readme_coverage", REPO_ROOT / "scripts" / "check_readme_coverage.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_readme_coverage"] = module
    spec.loader.exec_module(module)
    return module


coverage = _load()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for rel in FILES:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_ROOT / rel, tmp_path / rel)
    for skill in (REPO_ROOT / ".agents" / "skills").glob("*/SKILL.md"):
        target = tmp_path / ".agents" / "skills" / skill.parent.name / "SKILL.md"
        target.parent.mkdir(parents=True)
        shutil.copyfile(skill, target)
    return tmp_path


def _replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    assert old in text, f"{old!r} no está en {path.name}"
    path.write_text(text.replace(old, new), encoding="utf-8")


def test_the_repo_is_covered() -> None:
    assert coverage.check() == []


def test_pages_come_from_app_routes_without_redirects() -> None:
    pages = coverage.pages(REPO_ROOT)
    assert {"/", "/bandeja", "/jobs/:id", "/fuentes/plataformas", "/agente"} <= set(pages)
    # Redirecciones, la ruta comodín y la que solo agrupa las pestañas de Fuentes, no.
    assert not {"/triaje", "/empresas", "/plataformas", "/*", "/fuentes"} & set(pages)


def test_route_parser_on_synthetic_routes() -> None:
    source = """
    <Routes>
      <Route element={<Shell />}>
        <Route index element={<Home />} />
        {/* <Route path="vieja" element={<Old />} /> */}
        <Route
          path="lenta"
          element={
            <Suspense fallback={<Spinner />}>
              <Slow />
            </Suspense>
          }
        />
        <Route path="perezosa" lazy={() => import('./Lazy')} />
        <Route path="componente" Component={Page} />
        <Route path="grupo" element={<Tabs />}>
          <Route index element={<Navigate to="/grupo/a" replace />} />
          <Route path="a" element={<A />} />
        </Route>
        <Route path="antes" element={<Navigate to="/lenta" replace />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
    """
    assert coverage.parse_pages(source) == ["/", "/lenta", "/perezosa", "/componente", "/grupo/a"]


def test_unbalanced_routes_fail_clearly() -> None:
    with pytest.raises(ValueError, match="</Route>"):
        coverage.parse_pages('<Route path="a" element={<A />} /></Route>')


def test_new_redirect_needs_no_mention(repo: Path) -> None:
    _replace(
        repo / "frontend/src/App.tsx",
        '<Route path="agente" element={<AgentPage />} />',
        '<Route path="agente" element={<AgentPage />} />\n'
        '        <Route path="agent" element={<Navigate to="/agente" replace />} />',
    )
    assert coverage.check(repo) == []


def test_exceptions_are_exempt(repo: Path) -> None:
    # `implement-phase` existe y no está en las listas; `ats-simple` se cita y no es un skill.
    assert (repo / ".agents/skills/implement-phase/SKILL.md").exists()
    assert "implement-phase" not in (repo / "docs/FEATURES.md").read_text(encoding="utf-8")
    _replace(repo / "README.md", "## Guarantees", "Templates: `ats-simple`.\n\n## Guarantees")
    assert coverage.check(repo) == []


def test_lists_must_match_row_by_row(repo: Path) -> None:
    _replace(repo / "docs/FUNCIONALIDADES.md", "| `mock-interview` |", "| `debrief-interview` |")
    errors = coverage.check(repo)
    assert any("no dicen lo mismo" in e and "mock-interview" in e for e in errors)


def test_lists_with_a_missing_row_fail(repo: Path) -> None:
    path = repo / "docs/FEATURES.md"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    path.write_text("".join(line for line in lines if "`daily-summary`" not in line), "utf-8")
    errors = coverage.check(repo)
    assert "docs/FEATURES.md: falta `daily-summary`" in errors
    assert any("filas" in e for e in errors)


def test_copy_of_the_repo_passes(repo: Path) -> None:
    assert coverage.check(repo) == []


def test_new_page_without_mention_fails(repo: Path) -> None:
    _replace(
        repo / "frontend/src/App.tsx",
        '<Route path="agente" element={<AgentPage />} />',
        '<Route path="agente" element={<AgentPage />} />\n'
        '        <Route path="novedades" element={<NewsPage />} />',
    )
    errors = coverage.check(repo)
    assert "docs/FEATURES.md: falta `/novedades`" in errors
    assert "docs/FUNCIONALIDADES.md: falta `/novedades`" in errors


def test_new_skill_without_mention_fails(repo: Path) -> None:
    (repo / ".agents/skills/write-poem").mkdir()
    (repo / ".agents/skills/write-poem/SKILL.md").write_text("---\nname: write-poem\n---\n")
    errors = coverage.check(repo)
    assert "docs/FEATURES.md: falta `write-poem`" in errors
    assert "docs/FUNCIONALIDADES.md: falta `write-poem`" in errors


def test_skill_missing_in_one_language_fails(repo: Path) -> None:
    _replace(repo / "docs/FUNCIONALIDADES.md", "`training-plan`", "plan de formación")
    errors = coverage.check(repo)
    assert errors[0] == "docs/FUNCIONALIDADES.md: falta `training-plan`"
    assert "no dicen lo mismo" in errors[1] and len(errors) == 2


def test_removed_skill_still_cited_fails(repo: Path) -> None:
    shutil.rmtree(repo / ".agents/skills/generate-cv")
    errors = coverage.check(repo)
    assert any(e.startswith("README.md: cita `generate-cv`") for e in errors)
    assert any(e.startswith("docs/FEATURES.md: cita `generate-cv`") for e in errors)


def test_readme_must_link_its_feature_list(repo: Path) -> None:
    _replace(repo / "README.es.md", "docs/FUNCIONALIDADES.md", "docs/FEATURES.md")
    assert "README.es.md: no enlaza a docs/FUNCIONALIDADES.md" in coverage.check(repo)


def test_readmes_with_different_sections_fail(repo: Path) -> None:
    _replace(repo / "README.md", "## License and credits", "## License\n\n### Credits")
    assert any("secciones distintas" in e for e in coverage.check(repo))


def test_readmes_with_different_details_blocks_fail(repo: Path) -> None:
    _replace(repo / "README.es.md", "<details>", "<div>")
    assert any("bloques <details>" in e for e in coverage.check(repo))
