"""Documentos fuente que se suben desde «Mi perfil»: tu CV y tu exportación de LinkedIn.

Se guardan tal cual en `data/documentos/cv/` y `data/documentos/linkedin/`, donde el skill
`update-profile` los busca para crear o ampliar el perfil (así quien empieza de cero no tiene que
saber dónde dejarlos). La app no los interpreta: solo comprueba el formato, la firma y el tamaño,
y nunca sobrescribe uno anterior. Lo que el agente lea de ellos es dato, no instrucción
(POLICIES §6).
"""

import re
import threading
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, get_args

from pydantic import BaseModel

from app.services import context
from app.services.documents.uploads import MAX_BYTES, InvalidUploadError, UploadTooLargeError

UploadFolder = Literal["cv", "linkedin"]
UPLOAD_FOLDERS: tuple[UploadFolder, ...] = get_args(UploadFolder)
# LinkedIn exporta tus datos en un .zip de .csv, o el perfil en PDF («Guardar en PDF»).
FORMATS: dict[UploadFolder, tuple[str, ...]] = {
    "cv": (".pdf", ".docx", ".txt", ".md"),
    "linkedin": (".pdf", ".zip", ".csv"),
}
_SIGNATURES = {".pdf": b"%PDF", ".docx": b"PK\x03\x04", ".zip": b"PK\x03\x04"}
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
             *(f"lpt{i}" for i in range(1, 10))}  # fmt: skip

_LOCK = threading.Lock()  # dos subidas seguidas no deben elegir el mismo nombre


class SourceDocumentInfo(BaseModel):
    folder: UploadFolder
    name: str
    size_bytes: int
    uploaded_at: datetime


def folder_path(folder: UploadFolder) -> Path:
    return context.documents_dir() / folder


def _safe_name(folder: UploadFolder, filename: str) -> str:
    raw = Path(filename.replace("\\", "/")).name
    suffix = Path(raw).suffix.casefold()
    if suffix not in FORMATS[folder]:
        raise InvalidUploadError(
            f"Formato no admitido: «{suffix or raw}». Se admiten: {', '.join(FORMATS[folder])}."
        )
    stem = unicodedata.normalize("NFKD", Path(raw).stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^a-z0-9_-]+", "-", stem.casefold()).strip("-_")[:60] or folder
    if stem in _RESERVED:
        stem = f"{folder}-{stem}"
    return stem + suffix


def _info(folder: UploadFolder, path: Path) -> SourceDocumentInfo:
    stat = path.stat()
    return SourceDocumentInfo(
        folder=folder,
        name=path.name,
        size_bytes=stat.st_size,
        uploaded_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
    )


def list_documents(folder: UploadFolder) -> list[SourceDocumentInfo]:
    """Los ficheros de la carpeta (sin subcarpetas ni ocultos), del más reciente al más antiguo."""
    base = folder_path(folder)
    if not base.is_dir():
        return []
    files = [p for p in base.iterdir() if p.is_file() and not p.name.startswith(".")]
    return sorted((_info(folder, p) for p in files), key=lambda i: i.uploaded_at, reverse=True)


def save_document(folder: UploadFolder, filename: str, data: bytes) -> SourceDocumentInfo:
    name = _safe_name(folder, filename)
    if len(data) > MAX_BYTES:
        raise UploadTooLargeError(
            f"El fichero ocupa {len(data) / 1_048_576:.1f} MB; el máximo es "
            f"{MAX_BYTES // 1_048_576} MB."
        )
    if not data:
        raise InvalidUploadError("El fichero está vacío.")
    suffix = Path(name).suffix
    signature = _SIGNATURES.get(suffix)
    if signature and not data.startswith(signature):
        raise InvalidUploadError(f"El fichero no parece un {suffix} de verdad.")
    base = folder_path(folder)
    with _LOCK:
        base.mkdir(parents=True, exist_ok=True)
        target, counter = base / name, 2
        while target.exists():  # nunca se sobrescribe un documento anterior
            target, counter = base / f"{Path(name).stem}-{counter}{suffix}", counter + 1
        target.write_bytes(data)
    return _info(folder, target)
