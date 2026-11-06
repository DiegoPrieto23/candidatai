"""Comprueba que no queda ningún medio provisional en los README, las guías ni la web.

Uso (desde la raíz): uv run --no-project python scripts/check_media_final.py [--list]

Una captura, una animación o una ilustración que aún no es la definitiva lleva justo antes el
marcador `<!-- media:provisional -->`. Este script busca los marcadores en `README.md`,
`README.es.md`, los `.md` de `docs/` y los ficheros de `site/` (si existe):

- sin opciones, falla (código 1) si queda alguno y dice dónde;
- con `--list`, solo los lista con el medio al que acompañan, y sale con código 0. Sirve de lista de
  tareas al rehacer los medios.

No forma parte de la CI de cada cambio: los medios provisionales están permitidos mientras se
preparan los definitivos, pero no en una versión publicada.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "<!-- media:provisional -->"
READMES = ("README.md", "README.es.md")
SITE_SUFFIXES = {".html", ".css", ".js", ".md"}
# Lo que se reconoce como medio en las líneas que siguen al marcador.
MEDIA = re.compile(r"""(?:src|srcset|href)="([^"]+)"|\]\(([^)\s]+)\)|url\(["']?([^"')]+)""")
MEDIA_SUFFIXES = (".webp", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".mp4", ".webm")
LOOKAHEAD = 4  # líneas tras el marcador en las que buscar el medio


@dataclass(frozen=True)
class Marker:
    path: str
    line: int
    media: str


def files(root: Path) -> list[Path]:
    found = [root / name for name in READMES if (root / name).is_file()]
    docs = root / "docs"
    if docs.is_dir():
        found += sorted(docs.rglob("*.md"))
    site = root / "site"
    if site.is_dir():
        found += sorted(p for p in site.rglob("*") if p.suffix in SITE_SUFFIXES and p.is_file())
    return found


def _media_after(lines: list[str], index: int, column: int) -> str:
    """El primer medio que aparece tras el marcador (en su línea o en las siguientes)."""
    chunks = [lines[index][column:], *lines[index + 1 : index + 1 + LOOKAHEAD]]
    for chunk in chunks:
        for match in MEDIA.finditer(chunk):
            target = next(group for group in match.groups() if group)
            if target.split("?")[0].split("#")[0].lower().endswith(MEDIA_SUFFIXES):
                return target
    return "?"


def find_markers(root: Path) -> list[Marker]:
    markers: list[Marker] = []
    for path in files(root):
        lines = path.read_text(encoding="utf-8").splitlines()
        rel = path.relative_to(root).as_posix()
        for index, line in enumerate(lines):
            start = 0
            while (column := line.find(MARKER, start)) != -1:
                start = column + len(MARKER)
                markers.append(Marker(rel, index + 1, _media_after(lines, index, start)))
    return markers


def main(argv: list[str] | None = None, root: Path = ROOT) -> int:
    args = sys.argv[1:] if argv is None else argv
    listing = "--list" in args
    markers = find_markers(root)
    for marker in markers:
        print(f"{marker.path}:{marker.line}: {marker.media}")
    if listing:
        print(f"{len(markers)} medios provisionales.")
        return 0
    if markers:
        print(f"Quedan {len(markers)} medios provisionales: sustitúyelos y quita su marcador.")
        return 1
    print("Ningún medio provisional.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.exit(main())
