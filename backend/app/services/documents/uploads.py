"""CVs subidos desde la UI para convertirlos en plantilla («Mi CV», fase 08.3).

Se guardan en `data/uploads/` con un nombre saneado y nunca se sobrescriben. Una subida está
«importada» cuando alguna plantilla del usuario tiene como `source.*` un fichero idéntico (mismo
sha256): así no hace falta apuntar el origen en ningún sitio y sobrevive a cambios de nombre.
"""

import hashlib
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from app.core.config import get_settings
from app.services.documents import templates
from app.services.documents.importer import paths

MAX_BYTES = 10 * 1024 * 1024
FORMATS = (".docx", ".pdf", ".png", ".jpg", ".jpeg", ".html")
SUPPORTED_NOW = FORMATS  # desde la 08b: Word con el motor docx; PDF, imagen y HTML con el html
# Firma de los primeros bytes: una extensión cambiada se rechaza al subir, no al importar.
SIGNATURES = {
    ".docx": (b"PK\x03\x04",),
    ".pdf": (b"%PDF",),
    ".png": (b"\x89PNG",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
}
# Nombres de dispositivo de Windows: `con.docx` no es un fichero.
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
             *(f"lpt{i}" for i in range(1, 10))}  # fmt: skip


class UploadTooLargeError(ValueError):
    pass


class InvalidUploadError(ValueError):
    pass


class UploadInfo(BaseModel):
    name: str
    path: str  # como se le pasa al agente: `data/uploads/<nombre>`
    size: int
    format: str
    supported: bool  # se puede importar (todos los formatos admitidos desde la 08b)
    template_id: str | None  # plantilla creada desde este fichero, si la hay
    agent_command: str
    uploaded_at: datetime


def _safe_name(filename: str) -> str:
    raw = Path(filename.replace("\\", "/")).name
    suffix = Path(raw).suffix.casefold()
    if suffix not in FORMATS:
        allowed = ", ".join(FORMATS)
        raise ValueError(f"Formato no admitido: «{suffix or raw}». Se admiten: {allowed}.")
    stem = unicodedata.normalize("NFKD", Path(raw).stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^a-z0-9_-]+", "-", stem.casefold()).strip("-_")[:60] or "cv"
    if stem in _RESERVED:
        stem = f"cv-{stem}"
    return stem + suffix


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sources_by_hash() -> dict[str, str]:
    """sha256 del `source.*` de cada plantilla del usuario → su id."""
    found, _invalid = templates.list_templates()
    user_dir = get_settings().user_templates_dir.resolve()
    result = {}
    for template in found:
        if not template.path.resolve().is_relative_to(user_dir) or not template.meta.source_file:
            continue
        source = template.path / template.meta.source_file
        if source.is_file():
            result[_digest(source)] = template.id
    return result


def _info(path: Path, sources: dict[str, str]) -> UploadInfo:
    stat = path.stat()
    return UploadInfo(
        name=path.name,
        path=f"data/uploads/{path.name}",
        size=stat.st_size,
        format=path.suffix.lstrip(".").casefold(),
        supported=path.suffix.casefold() in SUPPORTED_NOW,
        template_id=sources.get(_digest(path)),
        agent_command=f"import-cv-template data/uploads/{path.name}",
        uploaded_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
    )


def save_upload(filename: str, data: bytes) -> UploadInfo:
    if len(data) > MAX_BYTES:
        raise UploadTooLargeError(
            f"El fichero ocupa {len(data) / 1_048_576:.1f} MB; el máximo es "
            f"{MAX_BYTES // 1_048_576} MB."
        )
    if not data:
        raise ValueError("El fichero está vacío.")
    name = _safe_name(filename)
    signatures = SIGNATURES.get(Path(name).suffix)
    if signatures and not data.startswith(signatures):
        raise InvalidUploadError(
            f"El contenido no parece un {Path(name).suffix}: ¿se cambió la extensión?"
        )
    folder = paths.uploads_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    counter = 2
    while target.exists():  # nunca se sobrescribe una subida anterior
        target = folder / f"{Path(name).stem}-{counter}{Path(name).suffix}"
        counter += 1
    target.write_bytes(data)
    return _info(target, _sources_by_hash())


def list_uploads() -> list[UploadInfo]:
    folder = paths.uploads_dir()
    if not folder.is_dir():
        return []
    sources = _sources_by_hash()
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix.casefold() in FORMATS]
    infos = [_info(p, sources) for p in files]
    return sorted(infos, key=lambda i: i.uploaded_at, reverse=True)


def delete_upload(name: str) -> None:
    """Borra una subida (no la plantilla que se creara desde ella)."""
    folder = paths.uploads_dir().resolve()
    target = (folder / name).resolve()
    if target.parent != folder or not target.is_file():
        raise FileNotFoundError(f"No existe la subida «{name}».")
    target.unlink()
