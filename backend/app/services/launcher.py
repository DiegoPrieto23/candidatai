"""`cai start` (fase 23.4): la app entera con un solo comando.

Aplica las migraciones, arranca la API (que sirve también la UI compilada) y el worker como dos
procesos hijos, espera a que la API responda y abre el navegador. Ctrl+C (o cerrar la ventana)
para los dos. Si uno de los dos se cae, se para el otro: mejor nada que media app.

La salida de cada hijo va a `data/logs/start-<nombre>.log`; en la consola solo se ven unas líneas
de estado. `--dev` arranca además Vite (`pnpm dev`) para desarrollar con recarga en caliente.
"""

import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Literal

import httpx

from app.core import migrations
from app.core.config import REPO_ROOT, Settings
from app.services.agent_runner import _kill_tree

HOST = "127.0.0.1"
DEV_UI_URL = "http://127.0.0.1:5173"
READY_TIMEOUT = 60.0  # la primera vez la API puede tardar (importa mucho)

PortState = Literal["free", "candidatai", "other"]


class LaunchError(RuntimeError):
    """No se puede arrancar; el mensaje dice qué hacer."""


@dataclass
class Child:
    name: str
    command: list[str]
    cwd: Path
    process: "subprocess.Popen[str] | None" = None
    log: "IO[str] | None" = None


@dataclass
class Launch:
    url: str
    children: list[Child] = field(default_factory=list)


def ui_built(settings: Settings) -> bool:
    return (settings.ui_dir / "index.html").is_file()


def port_free(port: int) -> bool:
    """Si se puede escuchar en el puerto. Más fiable que conectar: en Windows, una conexión a un
    puerto cerrado tarda unos 2 s en fallar y parecería un programa que no responde."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((HOST, port))
        except OSError:
            return False
    # Windows deja escuchar en 127.0.0.1 aunque otro escuche en 0.0.0.0: además, que nadie conteste.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((HOST, port)) != 0


def probe(
    port: int,
    client: httpx.Client | None = None,
    is_free: Callable[[int], bool] = port_free,
) -> PortState:
    """Qué hay en el puerto: nada, una CandidatAI (su `/status` responde) u otra cosa."""
    if is_free(port):
        return "free"
    owned = client is None
    # Sin proxies del sistema: es una petición a esta misma máquina.
    client = client or httpx.Client(timeout=5.0, trust_env=False)
    try:
        response = client.get(f"http://{HOST}:{port}/status")
    except httpx.HTTPError:
        return "other"
    finally:
        if owned:
            client.close()
    try:
        data = response.json()
    except ValueError:
        return "other"
    is_ours = response.status_code == 200 and isinstance(data, dict) and "by_stage" in data
    return "candidatai" if is_ours else "other"


def _python_command(*args: str) -> list[str]:
    # El mismo intérprete que ejecuta `cai`: el del entorno del backend.
    return [sys.executable, "-m", "app", *args]


def plan(settings: Settings, port: int, *, dev: bool = False) -> Launch:
    """Qué se va a arrancar (sin arrancar nada)."""
    backend = REPO_ROOT / "backend"
    if not dev and not ui_built(settings):
        raise LaunchError(
            f"No está la UI compilada en {settings.ui_dir}. Si has clonado el repositorio, "
            "compílala una vez: `cd frontend; pnpm install; pnpm build` (o usa `cai start --dev`). "
            "Con el instalador ya viene compilada."
        )
    children = [
        Child("api", _python_command("serve", "--port", str(port)), backend),
        Child("worker", _python_command("worker"), backend),
    ]
    url = f"http://{HOST}:{port}"
    if dev:
        pnpm = shutil.which("pnpm")
        if pnpm is None:
            raise LaunchError("`--dev` necesita pnpm (y Node) para arrancar Vite.")
        children.append(Child("ui", [pnpm, "dev"], REPO_ROOT / "frontend"))
        url = DEV_UI_URL
    return Launch(url=url, children=children)


MAX_LOG_BYTES = 5_000_000


def _spawn(child: Child, logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / f"start-{child.name}.log"
    # Se añade a lo anterior, salvo que pase de unos MB: entonces empieza de cero.
    mode = "w" if path.exists() and path.stat().st_size > MAX_LOG_BYTES else "a"
    child.log = path.open(mode, encoding="utf-8")
    child.process = subprocess.Popen(  # noqa: S603
        child.command,
        cwd=child.cwd,
        stdout=child.log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
    )


def stop(launch: Launch) -> None:
    """Para todos los hijos con lo que hayan lanzado (el árbol entero) y cierra sus logs."""
    for child in launch.children:
        if child.process is not None:
            _kill_tree(child.process)
        if child.log is not None:
            child.log.close()


def wait_ready(
    url: str,
    launch: Launch,
    timeout: float = READY_TIMEOUT,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Espera a que la API responda. Si un hijo muere antes, falla con su nombre."""
    deadline = time.monotonic() + timeout
    with httpx.Client(timeout=2.0, trust_env=False) as client:
        while time.monotonic() < deadline:
            for child in launch.children:
                if child.process is not None and child.process.poll() is not None:
                    raise LaunchError(
                        f"«{child.name}» se ha cerrado al arrancar (código "
                        f"{child.process.returncode}). Mira data/logs/start-{child.name}.log."
                    )
            try:
                if client.get(f"{url}/status").status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            sleep(0.5)
    raise LaunchError(f"La API no respondió en {timeout:g} s. Mira data/logs/start-api.log.")


def supervise(launch: Launch, sleep: Callable[[float], None] = time.sleep) -> str:
    """Bloquea hasta que un hijo termine (o Ctrl+C). Devuelve el nombre del que terminó."""
    while True:
        for child in launch.children:
            if child.process is not None and child.process.poll() is not None:
                return child.name
        sleep(1.0)


def start(
    settings: Settings,
    port: int,
    *,
    dev: bool = False,
    open_browser: bool = True,
    say: Callable[[str], None] = print,
    browser: Callable[[str], object] = webbrowser.open,
) -> None:
    """Arranca todo y bloquea hasta Ctrl+C o hasta que un hijo se caiga."""
    state = probe(port)
    if state == "candidatai":
        say(f"CandidatAI ya está en marcha en http://{HOST}:{port}: abro el navegador.")
        if open_browser:
            browser(f"http://{HOST}:{port}")
        return
    if state == "other":
        raise LaunchError(
            f"El puerto {port} lo usa otro programa. Ciérralo o usa `cai start --port <otro>`."
        )
    launch = plan(settings, port, dev=dev)
    migrations.upgrade()
    say("Arrancando CandidatAI…")
    try:
        for child in launch.children:
            _spawn(child, settings.logs_dir)
        wait_ready(f"http://{HOST}:{port}", launch)
        say(f"CandidatAI en marcha: {launch.url}")
        say("Deja esta ventana abierta mientras la uses. Para cerrar: Ctrl+C o cierra la ventana.")
        if open_browser:
            browser(launch.url)
        ended = supervise(launch)
        say(f"«{ended}» se ha cerrado: paro el resto. Detalles en data/logs/start-{ended}.log.")
    except KeyboardInterrupt:
        say("Cerrando CandidatAI…")
    finally:
        stop(launch)
