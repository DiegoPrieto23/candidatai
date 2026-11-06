"""Arma la web del proyecto en `_site/` a partir de `site/`, lista para GitHub Pages.

Uso (desde la raíz):
    uv run --no-project python scripts/build_site.py            # arma _site/
    uv run --no-project python scripts/build_site.py --serve    # y la sirve en http://127.0.0.1:8001

Lo usan igual la previsualización en local y el flujo de Pages:

- copia `site/` (sin sus `.md`);
- copia de `docs/img/` y `docs/brand/` **solo** las imágenes que la web referencia, para no
  duplicarlas en git: en `site/`, `img/…` y `brand/…` son esas carpetas;
- sustituye `{{version}}` por la versión de `backend/pyproject.toml`, para no escribirla a mano;
- falla (código 1) si falta una imagen o un fichero referenciado, o si queda un `{{…}}` sin
  sustituir.
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import http.server
import re
import shutil
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = "site"
OUT = "_site"
# URL pública: las metas de Open Graph necesitan rutas absolutas (lo demás es relativo).
BASE_URL = "https://diegoprieto23.github.io/candidatai/"
# Carpetas de la web que salen de docs/ al armarla: `site/img/x` es `docs/img/x`.
MOUNTS = {"img": "docs/img", "brand": "docs/brand"}
TEXT_SUFFIXES = {".html", ".css", ".js"}
PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")
# `content=` solo cuenta con la URL de la web (og:image…): el resto de metas no son rutas.
REF = re.compile(
    r"""\b(?:src|href)="([^"]+)"|\bcontent="(https://diegoprieto23\.github\.io/candidatai/[^"]*)\""""
    r"""|\bsrcset="([^"]+)"|url\(\s*["']?([^"')]+)["']?\s*\)"""
)


def version(root: Path = ROOT) -> str:
    with (root / "backend" / "pyproject.toml").open("rb") as fh:
        return str(tomllib.load(fh)["project"]["version"])


def mounted(rel: str, root: Path = ROOT) -> Path | None:
    """El fichero de docs/ que corresponde a una ruta de la web relativa a su raíz, o None."""
    first, _, rest = rel.partition("/")
    if first in MOUNTS and rest:
        return root / MOUNTS[first] / rest
    return None


def references(text: str) -> list[str]:
    """Rutas a las que apunta un HTML o CSS (enlaces, imágenes, `srcset`, `url()`, metas)."""
    found: list[str] = []
    for match in REF.finditer(text):
        plain, meta, srcset, url = match.groups()
        if srcset:
            found += [part.strip().split()[0] for part in srcset.split(",") if part.strip()]
        else:
            found.append(plain or meta or url)
    return found


def local_target(ref: str, page_rel: str) -> str | None:
    """Ruta relativa a la raíz de la web de una referencia local, o None si es externa o un ancla.

    Las URLs con `BASE_URL` (las metas de Open Graph) cuentan como locales."""
    if ref.startswith(BASE_URL):
        rel = ref[len(BASE_URL) :]
    elif re.match(r"^(?:[a-z][a-z0-9+.-]*:|#|//)", ref, re.I) or " " in ref.strip():
        return None
    else:
        base = page_rel.rsplit("/", 1)[0] if "/" in page_rel else ""
        rel = f"{base}/{ref}" if base else ref
    rel = rel.split("#")[0].split("?")[0]
    parts: list[str] = []
    for part in rel.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(part)
    if not parts:
        return "index.html"
    joined = "/".join(parts)
    return f"{joined}/index.html" if rel.endswith("/") else joined


def _disposable(folder: Path) -> bool:
    """Si se puede borrar para volver a armarla: vacía o armada antes por este script."""
    if not folder.is_dir():
        return False
    return not any(folder.iterdir()) or (folder / ".nojekyll").is_file()


def build(root: Path = ROOT, out: Path | None = None) -> tuple[Path, list[str]]:
    """Arma la web. Devuelve la carpeta y la lista de errores (vacía si todo fue bien)."""
    src = root / SITE
    dest = out or root / OUT
    if dest.exists():
        if not _disposable(dest):
            return dest, [f"{dest} no es una web armada antes: no se borra (usa una carpeta nueva)"]
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    values = {"version": version(root)}
    errors: list[str] = []
    wanted: set[str] = set()

    for path in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = path.relative_to(src).as_posix()
        if path.suffix == ".md":
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix not in TEXT_SUFFIXES:
            shutil.copy2(path, target)
            continue
        text = path.read_text(encoding="utf-8")

        def fill(match: re.Match[str], rel: str = rel) -> str:
            key = match.group(1)
            if key not in values:
                errors.append(f"{SITE}/{rel}: marcador sin valor {{{{{key}}}}}")
                return match.group(0)
            return values[key]

        text = PLACEHOLDER.sub(fill, text)
        target.write_text(text, encoding="utf-8", newline="\n")
        for ref in references(text):
            resolved = local_target(ref, rel)
            if resolved is not None:
                wanted.add(resolved)
                if not ((src / resolved).is_file() or mounted(resolved, root)):
                    errors.append(f"{SITE}/{rel}: no existe {ref}")

    for rel in sorted(wanted):
        origin = mounted(rel, root)
        if origin is None:
            continue
        if not origin.is_file():
            errors.append(f"falta {origin.relative_to(root).as_posix()} (para {rel})")
            continue
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, dest / rel)
    # Marca la carpeta como armada por este script: solo así se deja borrar al volver a armarla.
    (dest / ".nojekyll").write_text("", encoding="utf-8")
    return dest, errors


def serve(folder: Path, port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(folder))
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as server:
        print(f"Web en http://127.0.0.1:{port}/ (Ctrl+C para parar)")
        with contextlib.suppress(KeyboardInterrupt):
            server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Arma la web del proyecto en _site/.")
    parser.add_argument("--out", type=Path, help="carpeta de salida (por defecto, _site/)")
    parser.add_argument("--serve", action="store_true", help="servirla después en local")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args(argv)
    dest, errors = build(ROOT, args.out)
    for line in errors:
        print(line)
    if errors:
        print(f"{len(errors)} errores: la web no está lista.")
        return 1
    files = sum(1 for p in dest.rglob("*") if p.is_file())
    print(f"Web armada en {dest} ({files} ficheros, versión {version(ROOT)}).")
    if args.serve:
        serve(dest, args.port)
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.exit(main())
