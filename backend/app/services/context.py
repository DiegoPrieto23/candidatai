"""Contexto del candidato (`data/contexto/*.md`) y carpetas de documentos (`data/documentos/`).

El contexto es texto libre que escribe el usuario: cómo escribe, cómo trabaja, qué busca y qué no
acepta, y su historia. Orienta a los skills (tono, riesgos, entrevistas) pero **nunca respalda un
hecho**: lo que dice un CV o una carta sale de `data/profile.yaml` (`docs/POLICIES.md` §1).

Las plantillas son las de la candidata demo (`demo/contexto/`): `init` copia de ellas solo los
encabezados y los comentarios-guía, sin su contenido.
"""

import hashlib
import re
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, get_args

from pydantic import BaseModel, Field

from app.core.config import REPO_ROOT, get_settings

ContextSection = Literal["estilo-redaccion", "perfil-conductual", "criterios", "narrativa"]
SECTIONS: tuple[ContextSection, ...] = get_args(ContextSection)
TEMPLATES_DIR = REPO_ROOT / "demo" / "contexto"
MAX_BYTES = 20 * 1024  # por fichero: lo que pase se recorta y se avisa
# `estilo` (fase 25.7): muestras de cómo escribes, que se suben desde «Mi perfil».
DocumentFolder = Literal["cv", "linkedin", "titulos", "referencias", "candidaturas", "estilo"]
DOCUMENT_FOLDERS: tuple[DocumentFolder, ...] = get_args(DocumentFolder)

_LOCK = threading.Lock()  # guardar desde la UI (fase 25.7)

NOTE = (
    "Indicaciones del usuario: orientan el tono, los riesgos y la preparación de entrevistas, "
    "pero nunca respaldan un hecho. Lo que afirme un CV o una carta tiene que estar en el perfil."
)
# Un comentario sin cerrar llega hasta el final del fichero, como lo pinta un visor de Markdown.
_COMMENT = re.compile(r"<!--.*?(?:-->|\Z)", re.DOTALL)
_BLANKS = re.compile(r"\n{3,}")


class ContextFileInfo(BaseModel):
    section: ContextSection
    path: str  # relativo a la carpeta de datos: `contexto/criterios.md`
    exists: bool
    empty: bool  # sin nada más que encabezados y comentarios-guía (False si no se puede leer)
    size_bytes: int
    modified_at: datetime | None
    hash: str | None  # sha256 del fichero tal cual
    warnings: list[str]


class ContextFile(ContextFileInfo):
    text: str  # sin los comentarios-guía (vacío si no hay contenido); recortado a `MAX_BYTES`
    truncated: bool


class StyleSampleText(BaseModel):
    """Una muestra de estilo para el agente (fase 25.7): envuelta como contenido no confiable."""

    name: str
    text: str  # dentro de <untrusted_style_sample>
    risk_flags: list[str]
    truncated: bool


class ContextView(BaseModel):
    """Lo que devuelve `get_context`."""

    note: str
    files: list[ContextFile]
    # Fase 25.7: textos tuyos para el tono; nunca respaldan un hecho. Recortados entre todos.
    style_samples: list[StyleSampleText] = Field(default_factory=list)


class ContextDocument(BaseModel):
    """Un fichero de contexto tal cual, comentarios-guía incluidos, para editarlo en la UI."""

    section: ContextSection
    path: str
    exists: bool  # si no existe, `text` es la plantilla vacía de `cai context init`
    file_hash: str | None  # sha256 de los bytes del fichero: vuelve en el guardado
    text: str
    size_bytes: int
    max_bytes: int


class ContextTooLargeError(ValueError):
    pass


class DocumentFolderInfo(BaseModel):
    name: DocumentFolder
    exists: bool
    files: int  # ficheros dentro, en cualquier nivel


class ContextStatus(BaseModel):
    """Estado para la UI («Mi perfil»): sin el texto de los ficheros."""

    context_dir: str
    documents_dir: str
    files: list[ContextFileInfo]
    folders: list[DocumentFolderInfo]


class InitResult(BaseModel):
    created: list[str]  # rutas relativas a la carpeta de datos
    existing: list[str]


def context_dir() -> Path:
    return get_settings().data_dir / "contexto"


def documents_dir() -> Path:
    return get_settings().data_dir / "documentos"


def file_name(section: ContextSection) -> str:
    return f"{section}.md"


def strip_guides(text: str) -> str:
    """El texto sin los comentarios `<!-- -->` ni líneas en blanco repetidas."""
    text = _COMMENT.sub("", text.replace("\r\n", "\n"))
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return _BLANKS.sub("\n\n", text).strip()


def is_empty(text: str) -> bool:
    """Vacío si, sin comentarios, solo quedan encabezados (`#`) o líneas en blanco."""
    lines = strip_guides(text).split("\n")
    return all(not line.strip() or line.lstrip().startswith("#") for line in lines)


def skeleton(text: str) -> str:
    """La plantilla sin datos: solo encabezados, comentarios-guía y líneas en blanco."""
    kept: list[str] = []
    in_comment = False
    for line in text.replace("\r\n", "\n").split("\n"):
        if not in_comment and "<!--" in line:
            line = line[line.index("<!--") :]  # sin el texto de antes del comentario
            in_comment = True
        if in_comment:
            if "-->" in line:
                line = line[: line.index("-->") + 3]  # sin el texto de después
                in_comment = False
            kept.append(line.rstrip())
        elif line.lstrip().startswith("#") or not line.strip():
            kept.append(line.rstrip())
    return _BLANKS.sub("\n\n", "\n".join(kept)).strip() + "\n"


def _truncate(text: str) -> tuple[str, bool]:
    data = text.encode("utf-8")
    if len(data) <= MAX_BYTES:
        return text, False
    return data[:MAX_BYTES].decode("utf-8", errors="ignore"), True


def _read(section: ContextSection) -> ContextFile:
    path = context_dir() / file_name(section)
    relative = f"contexto/{file_name(section)}"
    if not path.is_file():
        return ContextFile(
            section=section,
            path=relative,
            exists=False,
            empty=True,
            size_bytes=0,
            modified_at=None,
            hash=None,
            warnings=[],
            text="",
            truncated=False,
        )
    raw = path.read_bytes()
    stat = path.stat()
    warnings: list[str] = []
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = ""
        warnings.append("invalid_encoding: no está en UTF-8; guárdalo como UTF-8 en tu editor.")
    empty = is_empty(content) and not warnings  # ilegible no es vacío
    text, truncated = _truncate("" if empty else strip_guides(content))
    if truncated:
        warnings.append(
            f"too_large: pasa de {MAX_BYTES // 1024} KB; solo se usan los primeros. Acórtalo."
        )
    return ContextFile(
        section=section,
        path=relative,
        exists=True,
        empty=empty,
        size_bytes=len(raw),
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
        hash=hashlib.sha256(raw).hexdigest(),
        warnings=warnings,
        text=text,
        truncated=truncated,
    )


def get_context(sections: list[ContextSection] | None = None) -> ContextView:
    """El texto de los ficheros de contexto pedidos (todos por defecto), con su hash, y las
    muestras de estilo (fase 25.7)."""
    from app.services import style_samples  # importa este módulo

    wanted = [s for s in SECTIONS if sections is None or s in sections]
    samples = style_samples.for_agent()
    return ContextView(
        note=NOTE, files=[_read(section) for section in wanted], style_samples=samples
    )


def _template(section: ContextSection) -> str:
    return skeleton((TEMPLATES_DIR / file_name(section)).read_text(encoding="utf-8"))


def get_document(section: ContextSection) -> ContextDocument:
    """El fichero para el editor de «Mi perfil» (fase 25.7)."""
    path = context_dir() / file_name(section)
    raw = path.read_bytes() if path.is_file() else None
    text = _template(section) if raw is None else raw.decode("utf-8-sig", errors="replace")
    return ContextDocument(
        section=section,
        path=f"contexto/{file_name(section)}",
        exists=raw is not None,
        file_hash=None if raw is None else hashlib.sha256(raw).hexdigest(),
        text=text.replace("\r\n", "\n"),
        size_bytes=0 if raw is None else len(raw),
        max_bytes=MAX_BYTES,
    )


def save_document(
    section: ContextSection, text: str, expected_hash: str | None
) -> tuple[ContextDocument, str | None]:
    """Guarda el fichero desde la UI. `expected_hash`: el que leyó (None si no existía).

    Devuelve el documento nuevo y el hash de antes. Lanza `ContextTooLargeError` por encima de
    `MAX_BYTES` (antes de escribir) y `ProfileConflictError` si el fichero cambió."""
    from app.services.profile_editor import ProfileConflictError, atomic_write

    path = context_dir() / file_name(section)
    data = text.replace("\r\n", "\n").encode("utf-8")
    if len(data) > MAX_BYTES:
        raise ContextTooLargeError(
            f"{file_name(section)} pasaría de {MAX_BYTES // 1024} KB ({len(data) // 1024} KB): "
            "acórtalo, el agente solo leería el principio."
        )
    with _LOCK:
        raw = path.read_bytes() if path.is_file() else None
        before = None if raw is None else hashlib.sha256(raw).hexdigest()
        if expected_hash != before:
            raise ProfileConflictError(before, f"contexto/{file_name(section)}")
        out = data.decode("utf-8")
        if not out.endswith("\n"):
            out += "\n"
        atomic_write(path, out)
    return get_document(section), before


def _count_files(folder: Path) -> int:
    return sum(1 for p in folder.rglob("*") if p.is_file()) if folder.is_dir() else 0


def get_status() -> ContextStatus:
    files = [
        ContextFileInfo.model_validate(f.model_dump(exclude={"text", "truncated"}))
        for f in get_context().files
    ]
    docs = documents_dir()
    folders = [
        DocumentFolderInfo(
            name=name, exists=(docs / name).is_dir(), files=_count_files(docs / name)
        )
        for name in DOCUMENT_FOLDERS
    ]
    return ContextStatus(
        context_dir=str(context_dir()),
        documents_dir=str(docs),
        files=files,
        folders=folders,
    )


def init() -> InitResult:
    """Crea los ficheros de contexto que falten (sin datos) y las carpetas de documentos.

    Nunca sobrescribe un fichero que ya existe.
    """
    target = context_dir()
    target.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    existing: list[str] = []
    for section in SECTIONS:
        path = target / file_name(section)
        relative = f"contexto/{file_name(section)}"
        if path.exists():
            existing.append(relative)
            continue
        template = (TEMPLATES_DIR / file_name(section)).read_text(encoding="utf-8")
        path.write_text(skeleton(template), encoding="utf-8")
        created.append(relative)
    for name in DOCUMENT_FOLDERS:
        (documents_dir() / name).mkdir(parents=True, exist_ok=True)
    return InitResult(created=created, existing=existing)
