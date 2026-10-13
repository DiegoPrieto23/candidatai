"""Rutas de la importación: los comandos solo leen y escriben dentro de `data/`.

El original va en `data/uploads/` (lo deja la UI) o en `data/tmp/`; el mapeo, en `data/tmp/`. Una
ruta relativa vale desde el directorio actual o desde la raíz del repo, como `--file` (con
`uv run --directory backend cai …` el proceso corre en `backend/`).
"""

from pathlib import Path

from app.core.config import REPO_ROOT, get_settings


class OutsideDataError(ValueError):
    pass


def uploads_dir() -> Path:
    return get_settings().data_dir / "uploads"


def resolve_inside(path: Path, roots: list[Path], what: str) -> Path:
    """Ruta absoluta de `path` si cae dentro de alguna de `roots`; si no, `OutsideDataError`."""
    resolved_roots = [r.resolve() for r in roots]
    candidates = [path] if path.is_absolute() else [Path.cwd() / path, REPO_ROOT / path]
    for candidate in candidates:
        resolved = candidate.resolve()
        if any(resolved.is_relative_to(root) for root in resolved_roots):
            return resolved
    allowed = " o ".join(str(r) for r in resolved_roots)
    raise OutsideDataError(f"{what} debe estar dentro de {allowed}.")


def source_file(path: Path) -> Path:
    """El CV original: en `data/uploads/` o `data/tmp/`, y que exista."""
    settings = get_settings()
    resolved = resolve_inside(path, [uploads_dir(), settings.tmp_dir], "El fichero original")
    if not resolved.is_file():
        raise FileNotFoundError(f"No existe el fichero {resolved}.")
    return resolved


def mapping_file(path: Path) -> Path:
    resolved = resolve_inside(path, [get_settings().tmp_dir], "El mapeo")
    if not resolved.is_file():
        raise FileNotFoundError(f"No existe el fichero {resolved}.")
    return resolved
