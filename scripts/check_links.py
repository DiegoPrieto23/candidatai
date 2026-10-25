"""Comprueba que existen los enlaces e imágenes relativos de los Markdown del repositorio.

Uso (desde la raíz): uv run --no-project python scripts/check_links.py
Revisa los `.md` de la raíz, `docs/`, `demo/`, `extension/`, `scripts/` y `.agents/`:
enlaces `[…](ruta)`, `src="…"`, `srcset="…"` y `href="…"`. Ignora URLs externas, anclas sueltas
y el código. Sale con código 1 si falta
alguno.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ("docs", "demo", "extension", "scripts", ".agents")
SKIP = ("node_modules",)
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
ATTR = re.compile(r"\b(?:src|srcset|href)=\"([^\"]+)\"")
FENCE = re.compile(r"```.*?```", re.S)
INLINE = re.compile(r"`[^`\n]*`")


def targets(text: str) -> list[str]:
    text = INLINE.sub("", FENCE.sub("", text))
    found = [m.group(1) for m in LINK.finditer(text)] + [m.group(1) for m in ATTR.finditer(text)]
    return [t.split()[0] for t in found]


def is_local(target: str) -> bool:
    return not re.match(r"^(?:[a-z][a-z0-9+.-]*:|#|//)", target, re.I)


def main() -> int:
    files = sorted(ROOT.glob("*.md"))
    for folder in FOLDERS:
        files += sorted((ROOT / folder).rglob("*.md"))
    missing: list[str] = []
    for md in files:
        if any(part in SKIP for part in md.parts):
            continue
        for target in targets(md.read_text(encoding="utf-8")):
            if not is_local(target):
                continue
            path = target.split("#")[0].split("?")[0]
            if not path:
                continue
            resolved = (md.parent / path).resolve()
            if not resolved.exists():
                missing.append(f"{md.relative_to(ROOT)}: {target}")
    for line in missing:
        print("falta", line)
    print(f"{len(files)} ficheros revisados, {len(missing)} enlaces rotos.")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
