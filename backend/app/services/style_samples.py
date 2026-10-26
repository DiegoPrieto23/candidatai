"""Muestras de estilo (fase 25.7): textos tuyos que enseñan al agente cómo escribes.

Cartas antiguas, correos, posts… en `data/documentos/estilo/`, subidos desde «Mi perfil». El texto
se extrae al subirlo (`.txt`, `.md`, `.docx`, `.pdf`) y se guarda junto al original, en
`estilo/.texto/<nombre>.txt`.

Son **contexto, no hechos** (POLICIES §1.5): `writer` y `generate-cover-letter` las leen para el
tono, la longitud de las frases, cómo abres y cierras y las palabras que usas; un hecho que solo
esté en una muestra es `blocker` para el `verifier`. Y como pueden traer texto de terceros (una
carta con la oferta pegada, un correo con la respuesta de la empresa), se pasan por la detección de
inyección y se entregan al agente envueltas como contenido no confiable (§6).
"""

import io
import re
import threading
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from app.core import policies
from app.services import context, untrusted
from app.services.context import StyleSampleText
from app.services.documents.uploads import InvalidUploadError, UploadTooLargeError

FORMATS = (".txt", ".md", ".docx", ".pdf")
FOLDER = "estilo"
TEXT_DIR = ".texto"
_SIGNATURES = {".docx": b"PK\x03\x04", ".pdf": b"%PDF"}
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
             *(f"lpt{i}" for i in range(1, 10))}  # fmt: skip


# Dos subidas seguidas no deben elegir el mismo nombre ni pasarse del tope de ficheros.
_LOCK = threading.Lock()


class StyleSampleNotFoundError(LookupError):
    pass


class StyleSampleInfo(BaseModel):
    name: str
    size_bytes: int
    chars: int  # caracteres del texto extraído
    uploaded_at: datetime
    risk_flags: list[str]  # `injection_phrase` si trae frases dirigidas a una IA
    excerpt: str | None  # el trozo que lo marcó


def folder() -> Path:
    return context.documents_dir() / FOLDER


def _text_path(name: str) -> Path:
    return folder() / TEXT_DIR / f"{name}.txt"


def _safe_name(filename: str) -> str:
    raw = Path(filename.replace("\\", "/")).name
    suffix = Path(raw).suffix.casefold()
    if suffix not in FORMATS:
        raise InvalidUploadError(
            f"Formato no admitido: «{suffix or raw}». Se admiten: {', '.join(FORMATS)}."
        )
    stem = unicodedata.normalize("NFKD", Path(raw).stem).encode("ascii", "ignore").decode()
    stem = re.sub(r"[^a-z0-9_-]+", "-", stem.casefold()).strip("-_")[:60] or "muestra"
    if stem in _RESERVED:
        stem = f"muestra-{stem}"
    return stem + suffix


def _available(name: str) -> str:
    target, stem, suffix, n = folder() / name, Path(name).stem, Path(name).suffix, 2
    while target.exists():
        target, n = folder() / f"{stem}-{n}{suffix}", n + 1
    return target.name


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")  # un .txt guardado con el Bloc de notas


def extract_text(suffix: str, data: bytes) -> str:
    if suffix in (".txt", ".md"):
        text = _decode(data)
    elif suffix == ".docx":
        from docx import Document  # python-docx, dependencia de docxtpl

        doc = Document(io.BytesIO(data))
        text = "\n".join(p.text for p in doc.paragraphs)
    else:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    text = "\n".join(line.rstrip() for line in text.replace("\r\n", "\n").split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _info(path: Path) -> StyleSampleInfo:
    text_file = _text_path(path.name)
    text = text_file.read_text(encoding="utf-8") if text_file.is_file() else ""
    risk = untrusted.assess(text)
    return StyleSampleInfo(
        name=path.name,
        size_bytes=path.stat().st_size,
        chars=len(text),
        uploaded_at=datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
        risk_flags=[str(flag) for flag in risk.flags],
        excerpt=risk.excerpt,
    )


def _originals() -> list[Path]:
    base = folder()
    if not base.is_dir():
        return []
    return sorted(p for p in base.iterdir() if p.is_file() and p.suffix.casefold() in FORMATS)


def list_samples() -> list[StyleSampleInfo]:
    return [_info(p) for p in _originals()]


def _existing(name: str) -> Path:
    path = folder() / Path(name).name
    if Path(name).name != name or not path.is_file() or path.suffix.casefold() not in FORMATS:
        raise StyleSampleNotFoundError(f"No existe la muestra de estilo «{name}».")
    return path


def get_text(name: str) -> str:
    _existing(name)
    text_file = _text_path(name)
    return text_file.read_text(encoding="utf-8") if text_file.is_file() else ""


def save_sample(filename: str, data: bytes) -> StyleSampleInfo:
    rules = policies.get_policies().profile_editing
    name = _safe_name(filename)
    suffix = Path(name).suffix
    if len(data) > rules.style_max_upload_mb * 1024 * 1024:
        raise UploadTooLargeError(
            f"La muestra pasa de {rules.style_max_upload_mb:g} MB: sube un fragmento."
        )
    with _LOCK:
        return _save_locked(name, suffix, data)


def _save_locked(name: str, suffix: str, data: bytes) -> StyleSampleInfo:
    rules = policies.get_policies().profile_editing
    if len(_originals()) >= rules.style_max_files:
        raise InvalidUploadError(
            f"Ya tienes {rules.style_max_files} muestras de estilo: borra alguna antes de subir "
            "otra."
        )
    signature = _SIGNATURES.get(suffix)
    if signature and not data.startswith(signature):
        raise InvalidUploadError(f"El fichero no parece un {suffix} de verdad.")
    try:
        text = extract_text(suffix, data)
    except Exception as exc:  # un .docx o .pdf dañado: la librería lanza lo que sea
        raise InvalidUploadError(f"No se pudo leer el texto del {suffix}: {exc}") from exc
    if not text:
        raise InvalidUploadError(
            "No tiene texto que se pueda leer (¿es un PDF escaneado?). Sube el texto en .txt."
        )
    base = folder()
    (base / TEXT_DIR).mkdir(parents=True, exist_ok=True)
    name = _available(name)
    (base / name).write_bytes(data)
    _text_path(name).write_text(text, encoding="utf-8")
    return _info(base / name)


def delete_sample(name: str) -> None:
    path = _existing(name)
    path.unlink()
    _text_path(name).unlink(missing_ok=True)


def for_agent() -> list[StyleSampleText]:
    """Las muestras para `get_context`, envueltas y recortadas a `style_max_text_kb` en total."""
    budget = policies.get_policies().profile_editing.style_max_text_kb * 1024
    out: list[StyleSampleText] = []
    for path in _originals():
        text = get_text(path.name)
        if not text:
            continue
        data = text.encode("utf-8")
        truncated = len(data) > budget
        if truncated:
            text = data[: max(budget, 0)].decode("utf-8", errors="ignore")
        budget -= len(text.encode("utf-8"))
        flags = [str(flag) for flag in untrusted.assess(text).flags]
        out.append(
            StyleSampleText(
                name=path.name,
                text=untrusted.wrap_untrusted_style(path.name, text, flags),
                risk_flags=flags,
                truncated=truncated,
            )
        )
        if budget <= 0:
            break
    return out
