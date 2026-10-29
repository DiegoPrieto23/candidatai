"""Abrir una carpeta de datos en el explorador de archivos (botones «Abrir carpeta» de la UI).

Lista cerrada: el contexto, los documentos, los dosieres de entrevista y de empresa, la carpeta
archivada de una candidatura y la de la extensión «Enviar a CandidatAI» (para cargarla en el
navegador). Nunca una ruta que llegue de fuera. En Windows con `os.startfile`;
en macOS con `open` y en Linux con `xdg-open` (fase 26.1). Si no se puede, o si falla, se devuelve
la ruta para que la UI la copie.
"""

import os
import shutil
import subprocess
import sys
from typing import Literal

from pydantic import BaseModel

from app.services import (
    application_archive,
    capture,
    company_research,
    context,
    interviews,
    terminals,
)

FolderKind = Literal[
    "contexto", "documentos", "estilo", "entrevistas", "empresas", "candidatura", "extension"
]


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
    elif kind == "estilo":  # muestras de estilo (fase 25.7)
        path = context.documents_dir() / "estilo"
    elif kind == "extension":
        if not capture.EXTENSION_DIR.is_dir():
            raise FolderNotFoundError(
                f"No está la carpeta de la extensión: {capture.EXTENSION_DIR}"
            )
        return str(capture.EXTENSION_DIR)
    elif kind in ("entrevistas", "empresas"):  # dosieres de las fases 17 y 18
        path = (
            interviews.interviews_dir()
            if kind == "entrevistas"
            else company_research.research_dir()
        )
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
    try:
        opened = _open(path)
    except OSError:
        opened = False
    return OpenFolderResult(path=path, opened=opened)


def _open(path: str) -> bool:
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]  # solo existe en Windows
        return True
    opener = shutil.which("open" if sys.platform == "darwin" else "xdg-open")
    if opener is None:
        return False
    proc = subprocess.Popen(  # noqa: S603 - una carpeta de la lista cerrada, sin shell
        [opener, path],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    terminals.reap(proc)
    return True
