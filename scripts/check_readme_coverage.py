"""Comprueba que el README y la lista de funcionalidades cuentan todo lo que hay (fase 28.3a).

Uso (desde la raíz): uv run --no-project python scripts/check_readme_coverage.py
Falla (código 1) si:
- una página de la UI (las rutas de `frontend/src/App.tsx`, sin redirecciones) o un skill de
  `.agents/skills/` no aparece en `docs/FEATURES.md` y en `docs/FUNCIONALIDADES.md` (la página,
  como `` `/ruta` ``; el skill, como `` `nombre` ``);
- `README.md` no enlaza a `docs/FEATURES.md` o `README.es.md` a `docs/FUNCIONALIDADES.md`;
- un README o una lista cita entre comillas invertidas un nombre con guiones que no es un skill
  (p. ej. un skill renombrado o borrado), salvo las excepciones de `NOT_SKILLS`;
- `FEATURES.md` y `FUNCIONALIDADES.md` no tienen las mismas filas, sección a sección, con lo mismo
  en la columna «Dónde»;
- una página no tiene ninguna fila con captura (una imagen en la columna «Captura») en cada lista;
- `README.md` y `README.es.md` no tienen las mismas secciones (niveles de encabezado en el mismo
  orden) ni el mismo número de bloques desplegables.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LISTS = {"en": "docs/FEATURES.md", "es": "docs/FUNCIONALIDADES.md"}
READMES = {"en": "README.md", "es": "README.es.md"}

# Skills que no son de quien usa la app.
SKIP_SKILLS = {
    "implement-phase": "sirve para desarrollar la app por fases (dev/), no para usarla",
}
# Nombres con guiones que se citan a propósito y no son skills.
NOT_SKILLS = {
    "ats-simple": "plantilla de CV integrada",
    "clasica-foto": "plantilla de CV integrada",
    "moderna-2col": "plantilla de CV integrada",
    "carta-simple": "plantilla de carta integrada",
}

FENCE = re.compile(r"```.*?```", re.S)
HEADING = re.compile(r"^(#{1,6}) ", re.M)
KEBAB = re.compile(r"`([a-z][a-z0-9]*(?:-[a-z0-9]+)+)(?: [^`\n]*)?`")
JSX_COMMENT = re.compile(r"\{/\*.*?\*/\}", re.S)
ROUTE_TAG = re.compile(r"<Route(?=[\s/>])|</Route>")
PAGE_ATTR = re.compile(r"\b(?:element|Component|lazy)=")
ROW = re.compile(r"^\|(?!---)(.*)\|\s*$", re.M)


def _read(root: Path, rel: str) -> str:
    return (root / rel).read_text(encoding="utf-8")


def _route_tags(source: str) -> list[tuple[str, bool]]:
    """Cada `<Route …>` (su texto) y si se cierra solo; los `</Route>`, como ("", False)."""
    source = JSX_COMMENT.sub("", source)
    tags: list[tuple[str, bool]] = []
    for match in ROUTE_TAG.finditer(source):
        if match.group() == "</Route>":
            tags.append(("", False))
            continue
        depth, j = 0, match.end()
        while j < len(source) and not (source[j] == ">" and depth == 0):
            depth += {"{": 1, "}": -1}.get(source[j], 0)
            j += 1
        tags.append((source[match.start() : j + 1], source[j - 1] == "/"))
    return tags


def parse_pages(source: str) -> list[str]:
    """Rutas con página propia: ni redirecciones, ni `*`, ni las que solo agrupan otras (como
    `fuentes`, cuyas pestañas `fuentes/empresas` y `fuentes/plataformas` sí cuentan)."""
    stack: list[str] = []
    found: list[str] = []
    for tag, self_closing in _route_tags(source):
        if not tag:
            if not stack:
                raise ValueError("App.tsx: hay un </Route> sin su <Route>")
            stack.pop()
            continue
        path = re.search(r'\bpath="([^"]*)"', tag)
        segment = path.group(1) if path else ""
        full = "/" + "/".join(s for s in [*stack, segment] if s)
        if not self_closing:
            stack.append(segment)
        elif "<Navigate" not in tag and segment != "*" and PAGE_ATTR.search(tag):
            found.append(full)
    return found


def pages(root: Path) -> list[str]:
    return parse_pages(_read(root, "frontend/src/App.tsx"))


def skills(root: Path) -> list[str]:
    return sorted(p.parent.name for p in (root / ".agents" / "skills").glob("*/SKILL.md"))


def _structure(text: str) -> tuple[list[str], int]:
    text = FENCE.sub("", text)
    return [m.group(1) for m in HEADING.finditer(text)], text.count("<details")


def _rows(text: str) -> list[tuple[int, int, tuple[str, ...]]]:
    """(sección, fila, lo citado en la columna «Dónde») de cada fila de las tablas de una lista."""
    rows: list[tuple[int, int, tuple[str, ...]]] = []
    for number, section in enumerate(re.split(r"^## ", text, flags=re.M)):
        body = [m.group(1).split("|") for m in ROW.finditer(section)][1:]  # sin la cabecera
        rows += [
            (number, i, tuple(re.findall(r"`([^`]+)`", cells[1]))) for i, cells in enumerate(body)
        ]
    return rows


def _captured(text: str) -> set[str]:
    """Las páginas (`/ruta` en «Dónde») con alguna fila que enlaza una imagen en «Captura»."""
    found: set[str] = set()
    for match in ROW.finditer(text):
        cells = match.group(1).split("|")
        if len(cells) > 2 and "img/" in cells[2]:
            found.update(t for t in re.findall(r"`([^`]+)`", cells[1]) if t.startswith("/"))
    return found


def check(root: Path = ROOT) -> list[str]:
    errors: list[str] = []
    all_skills = skills(root)
    wanted = [f"`{p}`" for p in pages(root)]
    wanted += [f"`{s}`" for s in all_skills if s not in SKIP_SKILLS]
    for rel in LISTS.values():
        text = _read(root, rel)
        errors += [f"{rel}: falta {item}" for item in wanted if item not in text]
    en_rows, es_rows = (_rows(_read(root, LISTS[lang])) for lang in ("en", "es"))
    if len(en_rows) != len(es_rows):
        errors.append(f"{LISTS['en']} tiene {len(en_rows)} filas y {LISTS['es']}, {len(es_rows)}")
    for en_row, es_row in zip(en_rows, es_rows, strict=False):
        if en_row != es_row:
            errors.append(
                f"{LISTS['en']} y {LISTS['es']} no dicen lo mismo en la sección {en_row[0]}, "
                f"fila {en_row[1] + 1}: {en_row[2]} frente a {es_row[2]} (columna «Dónde»)"
            )
            break
    for rel in LISTS.values():
        shown = _captured(_read(root, rel))
        errors += [f"{rel}: la página `{p}` no tiene captura" for p in pages(root) if p not in shown]
    for lang, rel in READMES.items():
        if LISTS[lang] not in _read(root, rel):
            errors.append(f"{rel}: no enlaza a {LISTS[lang]}")
    for rel in [*READMES.values(), *LISTS.values()]:
        for name in sorted(set(KEBAB.findall(FENCE.sub("", _read(root, rel))))):
            if name not in all_skills and name not in NOT_SKILLS:
                errors.append(f"{rel}: cita `{name}`, que no es un skill (¿renombrado o borrado?)")
    en, es = (_structure(_read(root, READMES[lang])) for lang in ("en", "es"))
    if en[0] != es[0]:
        errors.append(
            f"README.md y README.es.md tienen secciones distintas: "
            f"{''.join(str(len(h)) for h in en[0])} frente a {''.join(str(len(h)) for h in es[0])} "
            "(nivel de cada encabezado, en orden)"
        )
    if en[1] != es[1]:
        errors.append(f"README.md tiene {en[1]} bloques <details> y README.es.md, {es[1]}")
    return errors


def main() -> int:
    errors = check()
    for line in errors:
        print(line)
    print(f"{len(pages(ROOT))} páginas y {len(skills(ROOT))} skills; {len(errors)} problemas.")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
