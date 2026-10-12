"""Abrir una carpeta de datos en el explorador de archivos (botones «Abrir carpeta» de la UI).

Lista cerrada: el contexto, los documentos, los dosieres de entrevista y la carpeta archivada de
una candidatura. Nunca una ruta que llegue de fuera. Solo Windows de momento (`os.startfile`); en
otro sistema, o si falla, se devuelve la ruta para que la UI la copie.
"""

import os
import sys
from typing import Literal

from pydantic import BaseModel

from app.services import application_archive, context, interviews

FolderKind = Literal["contexto", "documentos", "entrevistas", "candidatura"]


class FolderNotFoundError(FileNotFoundError):
    pass


class OpenFolderResult(BaseModel):
    path: str
    opened: bool  # False: no se pudo abrir aquí; la UI enseña la ruta para copiarla


def resolve(kind: FolderKind, job_id: int | None = None) -> str:
    if kind == "contexto":
        path = context.context_dir()
    elif kind == "documentos":
        path = context.documents_dir()
    elif kind == "entrevistas":  # dosieres de `preparar-entrevista` (fase 17)
        path = interviews.interviews_dir()
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
    else:
        if job_id is None:
            raise ValueError("La carpeta de una candidatura necesita `job_id`.")
        found = application_archive.find_folder(job_id)
        if found is None:
            raise FolderNotFoundError(f"La oferta {job_id} aún no tiene carpeta archivada.")
        return str(found)
    # Se crean al abrirlos: así el usuario encuentra los ficheros de contexto listos para rellenar
    # y las carpetas de documentos donde dejar los suyos.
    context.init()
    return str(path)


def open_folder(kind: FolderKind, job_id: int | None = None) -> OpenFolderResult:
    path = resolve(kind, job_id)
    if sys.platform != "win32":
        return OpenFolderResult(path=path, opened=False)
    try:
        os.startfile(path)  # type: ignore[attr-defined]  # solo existe en Windows
    except OSError:
        return OpenFolderResult(path=path, opened=False)
    return OpenFolderResult(path=path, opened=True)
