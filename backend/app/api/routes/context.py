"""«Mi perfil» (fases 13 y 25.7): contexto, muestras de estilo, documentos fuente y abrir sus
carpetas.

Desde la fase 25.7 el texto del contexto también se edita en la UI (matiza la 025), con la
misma concurrencia optimista que el perfil, y se suben las muestras de estilo. Escribir solo lo
puede pedir la UI (`require_ui`). Abrir una carpeta lanza el explorador de archivos, así que, como
`POST /agent/launch`, también solo la UI y para una lista cerrada de carpetas.
"""

import base64
import binascii

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import EmptyBody, SessionDep, require_ui, require_ui_read
from app.services import context, folders, profile_editor, source_documents, style_samples
from app.services.context import ContextSection
from app.services.documents.uploads import InvalidUploadError
from app.services.source_documents import UploadFolder

router = APIRouter(tags=["context"])


@router.get("/context", operation_id="get_context_status")
def get_context_status() -> context.ContextStatus:
    """Ficheros de `data/contexto/` (vacío o con contenido, tamaño, fecha) y carpetas de
    `data/documentos/` con cuántos ficheros tienen. Sin el texto."""
    return context.get_status()


# --- Muestras de estilo y documentos fuente (antes de `/context/{section}`) ---------------


class UploadSampleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=200)
    content_base64: str  # en JSON para que `require_ui` lo compruebe (un formulario no puede)


class SampleText(BaseModel):
    name: str
    text: str


def _decode(content_base64: str) -> bytes:
    try:
        return base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise InvalidUploadError("El fichero no llegó bien (base64 no válido).") from exc


@router.get(
    "/context/style-samples",
    operation_id="list_style_samples",
    dependencies=[Depends(require_ui_read)],
)
def list_style_samples() -> list[style_samples.StyleSampleInfo]:
    """Muestras de `data/documentos/estilo/`, con el tamaño de su texto y si traen frases
    dirigidas a una IA."""
    return style_samples.list_samples()


@router.get(
    "/context/style-samples/{name}/text",
    operation_id="get_style_sample_text",
    dependencies=[Depends(require_ui_read)],
)
def get_style_sample_text(name: str) -> SampleText:
    """El texto que se extrajo de la muestra (lo que leería tu agente)."""
    return SampleText(name=name, text=style_samples.get_text(name))


@router.post(
    "/context/style-samples",
    operation_id="upload_style_sample",
    status_code=201,
    dependencies=[Depends(require_ui)],
)
def upload_style_sample(
    session: SessionDep, body: UploadSampleBody
) -> style_samples.StyleSampleInfo:
    """Sube una muestra (.txt, .md, .docx o .pdf) y extrae su texto."""
    data = _decode(body.content_base64)
    info = style_samples.save_sample(body.filename, data)
    digest = profile_editor.file_hash(data)
    profile_editor.record_edit(session, "style_sample", info.name, "upload", None, digest)
    return info


@router.delete(
    "/context/style-samples/{name}",
    operation_id="delete_style_sample",
    dependencies=[Depends(require_ui)],
)
def delete_style_sample(session: SessionDep, name: str, body: EmptyBody) -> EmptyBody:
    style_samples.delete_sample(name)
    profile_editor.record_edit(session, "style_sample", name, "delete", None, None)
    return EmptyBody()


# --- Documentos fuente: tu CV y tu exportación de LinkedIn ----------------------------------


@router.get(
    "/context/documents/{folder}",
    operation_id="list_source_documents",
    dependencies=[Depends(require_ui_read)],
)
def list_source_documents(folder: UploadFolder) -> list[source_documents.SourceDocumentInfo]:
    """Ficheros de `data/documentos/cv/` o `data/documentos/linkedin/`, del más reciente."""
    return source_documents.list_documents(folder)


@router.post(
    "/context/documents/{folder}",
    operation_id="upload_source_document",
    status_code=201,
    dependencies=[Depends(require_ui)],
)
def upload_source_document(
    session: SessionDep, folder: UploadFolder, body: UploadSampleBody
) -> source_documents.SourceDocumentInfo:
    """Guarda tu CV (.pdf, .docx, .txt, .md) o tu exportación de LinkedIn (.pdf, .zip, .csv),
    máximo 10 MB, para que tu agente cree o amplíe tu perfil a partir de ellos."""
    data = _decode(body.content_base64)
    info = source_documents.save_document(folder, body.filename, data)
    digest = profile_editor.file_hash(data)
    profile_editor.record_edit(session, "document", f"{folder}/{info.name}", "upload", None, digest)
    return info


# --- Ficheros de contexto ------------------------------------------------------------------


class SaveContextBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_hash: str | None  # el que leyó la UI; `null` si el fichero no existía
    text: str


@router.get(
    "/context/{section}",
    operation_id="get_context_document",
    dependencies=[Depends(require_ui_read)],
)
def get_context_document(section: ContextSection) -> context.ContextDocument:
    """El fichero tal cual, comentarios-guía incluidos (o la plantilla vacía si no existe)."""
    return context.get_document(section)


@router.put(
    "/context/{section}", operation_id="save_context_document", dependencies=[Depends(require_ui)]
)
def save_context_document(
    session: SessionDep, section: ContextSection, body: SaveContextBody
) -> context.ContextDocument:
    """Guarda el fichero (máximo 20 KB). `conflict` si cambió desde que lo leíste."""
    document, before = context.save_document(section, body.text, body.file_hash)
    profile_editor.record_edit(session, "context", section, "save", before, document.file_hash)
    return document


class OpenFolderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folder: folders.FolderKind
    job_id: int | None = Field(default=None, ge=1)


@router.post("/folders/open", operation_id="open_folder", dependencies=[Depends(require_ui)])
def open_folder(body: OpenFolderBody) -> folders.OpenFolderResult:
    """Abre la carpeta en el explorador; si no se puede, devuelve la ruta para copiarla."""
    return folders.open_folder(body.folder, body.job_id)
