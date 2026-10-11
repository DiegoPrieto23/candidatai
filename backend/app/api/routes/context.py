"""«Mi perfil» (fase 13): estado del contexto y de los documentos, y abrir sus carpetas.

La UI no enseña ni edita el texto del contexto: se edita en el editor del usuario. Abrir una
carpeta lanza el explorador de archivos, así que, como `POST /agent/launch` (ADR-024), solo lo
puede pedir la UI y solo para una lista cerrada de carpetas.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.routes.agent import require_ui
from app.services import context, folders

router = APIRouter(tags=["context"])


@router.get("/context", operation_id="get_context_status")
def get_context_status() -> context.ContextStatus:
    """Ficheros de `data/contexto/` (vacío o con contenido, tamaño, fecha) y carpetas de
    `data/documentos/` con cuántos ficheros tienen. Sin el texto."""
    return context.get_status()


class OpenFolderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folder: folders.FolderKind
    job_id: int | None = Field(default=None, ge=1)


@router.post("/folders/open", operation_id="open_folder", dependencies=[Depends(require_ui)])
def open_folder(body: OpenFolderBody) -> folders.OpenFolderResult:
    """Abre la carpeta en el explorador; si no se puede, devuelve la ruta para copiarla."""
    return folders.open_folder(body.folder, body.job_id)
