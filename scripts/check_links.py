"""Comprueba que existen los enlaces e imágenes relativos de los Markdown del repositorio.

Uso (desde la raíz): uv run --no-project python scripts/check_links.py
Revisa los `.md` de la raíz, `docs/`, `demo/`, `extension/`, `scripts/` y `.agents/`:
enlaces `[…](ruta)`, `src="…"`, `srcset="…"` y `href="…"`. Ignora URLs externas, anclas sueltas
y el código. Revisa también la web de `site/` (con `build_site.py`, que sabe que su `img/` es
`docs/img/`): cada fichero y cada imagen referenciados, y que cada ancla `#…` exista en su página.
Con `--site`, solo la web. Sale con código 1 si falta alguno.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_site  # noqa: E402

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


ID = re.compile(r'(?<![\w-])id="([^"]+)"')


def site_missing(root: Path = ROOT) -> tuple[int, list[str]]:
    """Enlaces rotos de la web: ficheros, imágenes (montadas desde docs/) y anclas."""
    site = root / build_site.SITE
    if not site.is_dir():
        return 0, []
    pages = sorted(site.rglob("*.html")) + sorted(site.rglob("*.css"))
    ids: dict[str, set[str]] = {}
    for page in pages:
        if page.suffix == ".html":
            rel = page.relative_to(site).as_posix()
            ids[rel] = set(ID.findall(page.read_text(encoding="utf-8")))
    missing: list[str] = []
    for page in pages:
        rel = page.relative_to(site).as_posix()
        for ref in build_site.references(page.read_text(encoding="utf-8")):
            where = f"{build_site.SITE}/{rel}: {ref}"
            if ref.startswith("#"):
                if len(ref) > 1 and ref[1:] not in ids.get(rel, set()):
                    missing.append(where)
                continue
            target = build_site.local_target(ref, rel)
            if target is None:
                continue
            origin = build_site.mounted(target, root) or site / target
            anchor = ref.split("#", 1)[1] if "#" in ref else ""
            if not origin.is_file() or (
                anchor and target.endswith(".html") and anchor not in ids.get(target, set())
            ):
                missing.append(where)
    return len(pages), missing


def main() -> int:
    if "--site" in sys.argv[1:]:  # solo la web (lo usa el flujo de Pages)
        site_files, missing = site_missing()
        for line in missing:
            print("falta", line)
        print(f"{site_files} ficheros de la web revisados, {len(missing)} enlaces rotos.")
        return 1 if missing else 0
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
    site_files, site_broken = site_missing()
    missing += site_broken
    for line in missing:
        print("falta", line)
    print(f"{len(files) + site_files} ficheros revisados, {len(missing)} enlaces rotos.")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
