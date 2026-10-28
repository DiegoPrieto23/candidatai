"""Instalar desde la UI el extra `matching` (similitud semántica del score).

La elección se guarda en tu base de datos (`agent_preferences`, `scope="setting"`,
`key="extra_matching"`), así que sobrevive a las actualizaciones: el instalador rehace el entorno
de la app sin el extra y, al arrancar, el worker lo vuelve a instalar (`ensure_installed`).

Lo instala el worker con `uv sync --extra matching --inexact`: solo añade paquetes (nada de lo
instalado se quita ni cambia, porque `uv.lock` resuelve todos los extras juntos) y no reinstala la
app, cuyos ejecutables están en uso mientras corre. Al terminar se encola `rescore_all`: instalarlo
cambia la huella del score (`scoring_key`) y las ofertas abiertas se recalculan con similitud.

En Docker no: el contenedor se rehace desde la imagen y lo instalado se perdería.
"""

import importlib
import os
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.models import AgentPreference, Task
from app.services import container, tasks
from app.services.matching import embeddings

SCOPE, KEY = "setting", "extra_matching"
TASK_KIND = "install_matching"
TIMEOUT_SECONDS = 45 * 60  # torch es grande y la conexión puede ser lenta
_OUTPUT_TAIL = 1500  # lo que se guarda de la salida de uv si falla


class MatchingExtraStatus(BaseModel):
    installed: bool  # sentence-transformers está en el entorno
    wanted: bool  # lo pediste desde la UI: se reinstala si falta
    disabled: bool  # `CAI_EMBEDDINGS=off` en el `.env`: instalado o no, no se usa
    in_docker: bool  # en Docker no se instala desde la UI
    installing: bool  # hay una instalación en cola o en marcha
    error: str | None  # por qué falló la última instalación, si falló


class MatchingInstallError(RuntimeError):
    pass


def _wanted(session: Session) -> bool:
    row = session.scalars(
        select(AgentPreference).where(AgentPreference.scope == SCOPE, AgentPreference.key == KEY)
    ).first()
    return row is not None and row.model == "on"


def _last_task(session: Session) -> Task | None:
    return session.scalars(
        select(Task).where(Task.kind == TASK_KIND).order_by(Task.id.desc()).limit(1)
    ).first()


def status(session: Session) -> MatchingExtraStatus:
    task = _last_task(session)
    installing = task is not None and task.status in ("queued", "running")
    return MatchingExtraStatus(
        installed=embeddings.is_installed(),
        wanted=_wanted(session),
        disabled=get_settings().embeddings == "off",
        in_docker=container.in_docker(),
        installing=installing,
        error=task.last_error if task is not None and task.status == "failed" else None,
    )


def request_install(session: Session) -> MatchingExtraStatus:
    """Guarda la elección y encola la instalación (si hace falta). Solo desde la UI."""
    if container.in_docker():
        raise ValueError(
            "En Docker la similitud semántica no está disponible: la imagen no la trae."
        )
    row = session.scalars(
        select(AgentPreference).where(AgentPreference.scope == SCOPE, AgentPreference.key == KEY)
    ).first()
    if row is None:
        session.add(AgentPreference(scope=SCOPE, key=KEY, model="on"))
    else:
        row.model = "on"
    if not embeddings.is_installed():
        tasks.enqueue(session, TASK_KIND)
    session.flush()
    return status(session)


def ensure_installed(session: Session) -> bool:
    """Al arrancar el worker: si lo pediste y falta (p. ej. tras actualizar la app), lo encola.
    Devuelve si lo ha encolado."""
    if container.in_docker() or not _wanted(session) or embeddings.is_installed():
        return False
    if status(session).installing:
        return False
    tasks.enqueue(session, TASK_KIND)
    return True


def _uv() -> str:
    """El `uv` con el que corre la app (`uv run` lo deja en `UV`), `UV_PATH` o el del PATH."""
    for candidate in (os.environ.get("UV_PATH"), os.environ.get("UV"), shutil.which("uv")):
        if candidate and Path(candidate).exists():
            return candidate
    raise MatchingInstallError("No se encuentra uv. Indica su ruta en UV_PATH, en el .env.")


def install(session: Session) -> dict[str, object]:
    """Lo ejecuta el worker: instala el extra y encola el recálculo de las ofertas abiertas."""
    if embeddings.is_installed():
        tasks.enqueue(session, "rescore_all")
        return {"installed": True, "already": True}
    command = [
        _uv(),
        "sync",
        "--directory",
        str(REPO_ROOT / "backend"),
        "--extra",
        "matching",
        "--inexact",
        "--frozen",
        "--no-install-project",
        "--no-dev",
    ]
    # Mientras dura, el score se calcula como sin el extra (ver `embeddings.is_installed`).
    marker = embeddings.installing_marker()
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()
    try:
        result = subprocess.run(  # noqa: S603
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise MatchingInstallError(
            f"La instalación tardó más de {TIMEOUT_SECONDS // 60} minutos y se ha parado."
        ) from exc
    finally:
        marker.unlink(missing_ok=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip()[-_OUTPUT_TAIL:]
        raise MatchingInstallError(f"uv sync ha fallado ({result.returncode}): {tail}")
    importlib.invalidate_caches()
    if not embeddings.is_installed():
        raise MatchingInstallError("uv terminó bien, pero sentence-transformers no aparece.")
    tasks.enqueue(session, "rescore_all")
    return {"installed": True, "already": False}
