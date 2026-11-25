"""Versiones nuevas de CandidatAI: el aviso de Inicio y el botón «Actualizar ahora».

- **Comprobar:** se pregunta a GitHub cuál es la última release publicada (una petición sin datos
  del usuario, como mucho cada `CHECK_EVERY`; si falla, se reintenta pasada `RETRY_AFTER`). No se
  pregunta con `CAI_UPDATE_CHECK=off` ni en una demo.
- **Actualizar desde la app:** solo con el instalador de Windows y la app abierta con `cai start`
  (el acceso directo). Se copian `update_windows.ps1` y el `install.ps1` de la app a una carpeta
  temporal (la de la app se sustituye entera), se abren en una ventana nueva y la API sale con
  `launcher.EXIT_FOR_UPDATE`: `cai start` cierra el resto y termina sin error, y el script espera a
  que no quede nada abierto, instala la última versión (con su suma SHA-256) y vuelve a abrir
  la app.
- **El resto** (macOS, Linux, Docker, el repositorio) recibe la orden para actualizar a mano.

Los datos no se tocan: el instalador solo sustituye la carpeta `app/`.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from app import VERSION
from app.agent_interface.errors import ToolError
from app.core.config import REPO_ROOT, Settings, get_settings, installed_app
from app.services import container
from app.services.launcher import EXIT_FOR_UPDATE, SUPERVISOR_PID_ENV

REPOSITORY = "DiegoPrieto23/candidatai"
LATEST_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
RAW_URL = f"https://raw.githubusercontent.com/{REPOSITORY}/main"
TIMEOUT_SECONDS = 5.0
CHECK_EVERY = 12 * 3600.0
RETRY_AFTER = 3600.0

# Las órdenes de la guía para actualizar a mano. La de Windows cabe en «Ejecutar» (Windows+R, 259
# caracteres como mucho) y funciona igual pegada en PowerShell o en cmd: no lleva `$`, que
# PowerShell sustituiría antes de pasársela.
WINDOWS_COMMAND = (
    'powershell -ExecutionPolicy Bypass -NoExit -Command "cd ([IO.Path]::GetTempPath()); '
    f'iwr -useb {RAW_URL}/install.ps1 -OutFile cai-install.ps1; .\\cai-install.ps1"'
)
UNIX_COMMAND = f"curl -fsSL {RAW_URL}/install.sh | bash"
DOCKER_COMMAND = "git pull && docker compose up -d --build"

UPDATER = Path(__file__).with_name("update_windows.ps1")
# Lo que no debe heredar la ventana del actualizador: abre la app con los datos de su `.env`.
UNSET_ENV = (
    "CAI_DATA_DIR", "JH_DATA_DIR", "CAI_DB_URL", "JH_DB_URL", SUPERVISOR_PID_ENV, "VIRTUAL_ENV",
)  # fmt: skip

InstallKind = Literal["installer", "docker", "repository", "other"]
_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


class UpdateStatus(BaseModel):
    current: str = Field(description="La versión en uso.")
    latest: str | None = Field(
        description="La última publicada; vacía si no se ha comprobado o no se ha podido."
    )
    available: bool = Field(description="Hay una versión más nueva que la que se usa.")
    release_url: str | None = Field(description="Las novedades de la última versión.")
    install: InstallKind = Field(
        description="Cómo está instalada: `installer`, `docker`, `repository` u `other`."
    )
    can_apply: bool = Field(description="Se puede actualizar desde la app («Actualizar ahora»).")
    command: str | None = Field(
        description="La orden para actualizar a mano, si la hay (en el repositorio, la guía)."
    )


class UpdateStarted(BaseModel):
    version: str = Field(description="La versión que se va a instalar.")


@dataclass(frozen=True)
class Release:
    version: str
    url: str


def parse_version(text: str) -> tuple[int, int, int] | None:
    """`v1.2.3` o `1.2.3`; cualquier otra cosa (una prerelease, un nombre raro), `None`."""
    match = _VERSION_RE.match(text.strip())
    return (int(match[1]), int(match[2]), int(match[3])) if match else None


def is_newer(latest: str, current: str) -> bool:
    new, old = parse_version(latest), parse_version(current)
    return new is not None and old is not None and new > old


# --- Comprobar ----------------------------------------------------------------------------------


@dataclass
class _Cached:
    at: float
    release: Release | None


_cache: _Cached | None = None
_lock = threading.Lock()


def reset_cache() -> None:
    global _cache
    with _lock:
        _cache = None


def fetch_latest(client: httpx.Client | None = None) -> Release | None:
    """La última release publicada en GitHub (sin borradores ni prereleases), o `None` si no se
    puede saber. Solo se manda la versión de la app como `User-Agent`."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": f"CandidatAI/{VERSION}"}
    try:
        with client or httpx.Client(timeout=TIMEOUT_SECONDS) as http:
            response = http.get(LATEST_URL, headers=headers)
        if response.status_code != 200:
            return None
        data = response.json()
    except (httpx.HTTPError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    tag, url = data.get("tag_name"), data.get("html_url")
    if not isinstance(tag, str) or parse_version(tag) is None:
        return None
    version = tag.strip().removeprefix("v")
    if not isinstance(url, str) or not url.startswith(f"https://github.com/{REPOSITORY}/"):
        url = f"https://github.com/{REPOSITORY}/releases/latest"
    return Release(version=version, url=url)


def latest_release(now: Callable[[], float] = time.monotonic) -> Release | None:
    """La última release, preguntada como mucho cada `CHECK_EVERY` (`RETRY_AFTER` si falló)."""
    global _cache
    with _lock:
        cached = _cache
        if cached is not None:
            wait = CHECK_EVERY if cached.release is not None else RETRY_AFTER
            if now() - cached.at < wait:
                return cached.release
        release = fetch_latest()
        _cache = _Cached(at=now(), release=release)
        return release


def checks_enabled(settings: Settings) -> bool:
    return settings.update_check != "off" and not settings.demo_mode


def install_kind(settings: Settings, repo_root: Path = REPO_ROOT) -> InstallKind:
    if container.in_docker(settings):
        return "docker"
    if installed_app(repo_root):
        return "installer"
    if (repo_root / ".git").exists():
        return "repository"
    return "other"


def manual_command(kind: InstallKind, platform: str = sys.platform) -> str | None:
    if kind == "installer":
        return WINDOWS_COMMAND if platform == "win32" else UNIX_COMMAND
    if kind == "docker":
        return DOCKER_COMMAND
    return None  # en el repositorio hay más de un paso: la guía


def _uv() -> str | None:
    """El `uv` con el que corre la app (`uv run` lo deja en `UV`), `UV_PATH` o el del PATH."""
    for candidate in (os.environ.get("UV_PATH"), os.environ.get("UV"), shutil.which("uv")):
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _supervisor_pid() -> int | None:
    value = os.environ.get(SUPERVISOR_PID_ENV, "")
    return int(value) if value.isdigit() else None


def _apply_problem(
    settings: Settings, kind: InstallKind, platform: str, repo_root: Path
) -> str | None:
    """Por qué no se puede actualizar desde la app (o `None` si se puede)."""
    if platform != "win32" or kind != "installer":
        return "Desde la app solo se actualiza la instalación de Windows: hay que usar la orden."
    if settings.demo_mode:
        return "En la demo no se actualiza: hay que cerrarla y abrir CandidatAI."
    if _supervisor_pid() is None:
        return "La app no se ha abierto con su acceso directo (`cai start`): hay que usar la orden."
    if _uv() is None:
        return "No se encuentra uv. Hay que indicar su ruta en UV_PATH, en el .env."
    if not (repo_root / "install.ps1").is_file():
        return "Falta install.ps1 en la carpeta de la app: hay que usar la orden de la guía."
    return None


def status(
    settings: Settings | None = None,
    *,
    platform: str = sys.platform,
    repo_root: Path = REPO_ROOT,
) -> UpdateStatus:
    settings = settings or get_settings()
    kind = install_kind(settings, repo_root)
    release = latest_release() if checks_enabled(settings) else None
    available = release is not None and is_newer(release.version, VERSION)
    problem = _apply_problem(settings, kind, platform, repo_root)
    return UpdateStatus(
        current=VERSION,
        latest=release.version if release else None,
        available=available,
        release_url=release.url if release else None,
        install=kind,
        can_apply=available and problem is None,
        command=manual_command(kind, platform),
    )


# --- Actualizar desde la app --------------------------------------------------------------------

Lang = Literal["es", "en"]
Spawn = Callable[[list[str], Path, dict[str, str]], None]


def _spawn_window(argv: list[str], cwd: Path, env: dict[str, str]) -> None:
    """Una ventana nueva que no depende de la app: fuera de su job si lo hay, para que siga
    abierta cuando la app se cierre."""
    new_console = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    breakaway = getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0)
    try:
        subprocess.Popen(argv, cwd=cwd, env=env, creationflags=new_console | breakaway)  # noqa: S603
    except OSError:  # un job que no deja salir: sin salir de él (así funciona fuera de uno)
        subprocess.Popen(argv, cwd=cwd, env=env, creationflags=new_console)  # noqa: S603


def _exit_soon(delay: float = 1.0) -> None:
    """Sale de la API cuando ya ha respondido: `cai start` lo ve y cierra el resto."""
    threading.Timer(delay, os._exit, args=(EXIT_FOR_UPDATE,)).start()


def apply(
    lang: Lang,
    expected: str,
    *,
    settings: Settings | None = None,
    platform: str = sys.platform,
    repo_root: Path = REPO_ROOT,
    spawn: Spawn = _spawn_window,
    exit_soon: Callable[[], None] = _exit_soon,
) -> UpdateStarted:
    """Abre el actualizador en una ventana y cierra la app. Solo desde la UI, tras confirmar en el
    aviso la versión `expected`: si entretanto ha salido otra, se vuelve a preguntar."""
    settings = settings or get_settings()
    kind = install_kind(settings, repo_root)
    problem = _apply_problem(settings, kind, platform, repo_root)
    if problem is not None:
        raise ToolError("invalid_request", problem)
    release = latest_release() if checks_enabled(settings) else None
    if release is None or not is_newer(release.version, VERSION):
        raise ToolError("invalid_request", "No hay una versión nueva que instalar.")
    if release.version != expected.strip().removeprefix("v"):
        raise ToolError(
            "conflict", f"Ya hay otra versión ({release.version}): hay que recargar la página."
        )
    folder = Path(tempfile.gettempdir()) / f"candidatai-update-{uuid.uuid4().hex}"
    folder.mkdir()
    updater = folder / UPDATER.name
    installer = folder / "install.ps1"
    shutil.copyfile(UPDATER, updater)
    shutil.copyfile(repo_root / "install.ps1", installer)
    env = {k: v for k, v in os.environ.items() if k.upper() not in UNSET_ENV}
    argv = [
        "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(updater),
        "-InstallDir", str(repo_root.parent), "-Installer", str(installer),
        "-WaitPid", str(_supervisor_pid()), "-Uv", str(_uv()), "-Lang", lang,
    ]  # fmt: skip
    spawn(argv, folder, env)
    exit_soon()
    return UpdateStarted(version=release.version)
