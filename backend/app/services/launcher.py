"""`cai start` (fase 23.4): la app entera con un solo comando.

Abre enseguida en el navegador la página «Arrancando CandidatAI…» (`starting.html` de la UI
compilada), que pasa sola a la app cuando responde: así se ve algo desde el primer momento. Luego
aplica las migraciones, arranca la API (que sirve también la UI compilada) y, cuando ya responde,
el worker, como dos procesos hijos: el worker no hace falta para abrir la app y en un equipo con
pocos núcleos le quitaría CPU a la API mientras arranca. Ctrl+C (o cerrar la ventana) para los
dos. Si uno de los dos se cae, se para el otro: mejor nada que media app.

La salida de cada hijo va a `data/logs/start-<nombre>.log`; en la consola solo se ven unas líneas
de estado. `--dev` arranca además Vite (`pnpm dev`) para desarrollar con recarga en caliente.

En macOS y Linux (fase 26.1) cada hijo va en su propio grupo de procesos, para pararlo con todo lo
que lance, y `SIGTERM` o `SIGHUP` (cerrar la terminal) paran todo como Ctrl+C.
"""

import contextlib
import locale
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import webbrowser
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from types import FrameType
from typing import IO, Any, Literal

import httpx

from app.core import migrations
from app.core.config import REPO_ROOT, Settings, get_settings
from app.services.agent_runner import _kill_tree

HOST = "127.0.0.1"
DEFAULT_PORT = 8000  # el de `starting.html` y el acceso directo
DEV_UI_URL = "http://127.0.0.1:5173"
READY_TIMEOUT = 60.0  # la primera vez la API puede tardar (importa mucho)

PortState = Literal["free", "candidatai", "other"]


# Lo que se ve en la terminal, en español o en inglés (`console_language`).
Lang = Literal["es", "en"]
MESSAGES: dict[str, dict[Lang, str]] = {
    "already_running": {
        "es": "CandidatAI ya está en marcha en {url}: abro el navegador.",
        "en": "CandidatAI is already running at {url}: opening the browser.",
    },
    "port_busy": {
        "es": "El puerto {port} lo usa otro programa. Ciérralo o usa `cai start --port <otro>`.",
        "en": "Port {port} is used by another program. Close it or use `cai start --port <other>`.",
    },
    "starting": {"es": "Arrancando CandidatAI…", "en": "Starting CandidatAI…"},
    "running": {"es": "CandidatAI en marcha: {url}", "en": "CandidatAI is running: {url}"},
    "keep_open": {
        "es": "Deja esta ventana abierta mientras la uses. "
        "Para cerrar: Ctrl+C o cierra la ventana.",
        "en": "Keep this window open while you use it. To quit: Ctrl+C or close the window.",
    },
    "child_ended": {
        "es": "«{name}» se ha cerrado: paro el resto. Detalles en data/logs/start-{name}.log.",
        "en": "“{name}” has stopped: stopping the rest. Details in data/logs/start-{name}.log.",
    },
    "closing": {"es": "Cerrando CandidatAI…", "en": "Closing CandidatAI…"},
    "no_browser": {
        "es": "No he podido abrir el navegador: abre {url} en el tuyo.",
        "en": "Couldn't open the browser: open {url} in yours.",
    },
    "no_ui": {
        "es": "No está la UI compilada en {ui_dir}. Si has clonado el repositorio, compílala una "
        "vez: `cd frontend; pnpm install; pnpm build` (o usa `cai start --dev`). Con el "
        "instalador ya viene compilada.",
        "en": "The built UI is not in {ui_dir}. If you cloned the repository, build it once: "
        "`cd frontend; pnpm install; pnpm build` (or use `cai start --dev`). The installer "
        "already includes it.",
    },
    "no_pnpm": {
        "es": "`--dev` necesita pnpm (y Node) para arrancar Vite.",
        "en": "`--dev` needs pnpm (and Node) to run Vite.",
    },
    "child_died": {
        "es": "«{name}» se ha cerrado al arrancar (código {code}). "
        "Mira data/logs/start-{name}.log.",
        "en": "“{name}” stopped while starting (code {code}). See data/logs/start-{name}.log.",
    },
    "timeout": {
        "es": "La API no respondió en {seconds:g} s. Mira data/logs/start-api.log.",
        "en": "The API did not answer within {seconds:g} s. See data/logs/start-api.log.",
    },
}


def console_language() -> Lang:
    """`CAI_LANG` si está; si no, español con el sistema en español e inglés con cualquier otro."""
    chosen = get_settings().lang
    if chosen is not None:
        return chosen
    system = (locale.getlocale()[0] or "").lower()
    return "es" if system.startswith(("es", "spanish")) else "en"


def message(key: str, **values: Any) -> str:
    return MESSAGES[key][console_language()].format(**values)


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


def starting_page(settings: Settings, port: int, *, dev: bool = False) -> str | None:
    """La página «Arrancando…» (`file://`), si se puede usar: solo con la UI compilada y el puerto
    de siempre, que es al que pregunta (con otro, o con Vite, se abre la app cuando responde)."""
    page = settings.ui_dir / "starting.html"
    if dev or port != DEFAULT_PORT or not page.is_file():
        return None
    return page.resolve().as_uri()


def _open(
    browser: Callable[[str], object], url: str, say: Callable[[str], None], app_url: str
) -> None:
    """Abre `url`; si el sistema no tiene con qué (`webbrowser` devuelve False), dice la dirección
    de la app para abrirla a mano."""
    if browser(url) is False:
        say(message("no_browser", url=app_url))


def plan(settings: Settings, port: int, *, dev: bool = False) -> Launch:
    """Qué se va a arrancar (sin arrancar nada)."""
    backend = REPO_ROOT / "backend"
    if not dev and not ui_built(settings):
        raise LaunchError(message("no_ui", ui_dir=settings.ui_dir))
    children = [
        Child("api", _python_command("serve", "--port", str(port)), backend),
        Child("worker", _python_command("worker"), backend),
    ]
    url = f"http://{HOST}:{port}"
    if dev:
        pnpm = shutil.which("pnpm")
        if pnpm is None:
            raise LaunchError(message("no_pnpm"))
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
    kwargs: dict[str, Any] = {}
    if sys.platform != "win32":
        kwargs["start_new_session"] = True  # `_kill_tree` para el grupo entero (`killpg`)
    child.process = subprocess.Popen(  # noqa: S603
        child.command,
        cwd=child.cwd,
        stdout=child.log,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        **kwargs,
    )


STOP_SIGNALS = ("SIGTERM", "SIGHUP")
SIGKILL = getattr(signal, "SIGKILL", 9)  # no existe en Windows, donde no se usa


def _interrupt(signum: int, frame: FrameType | None) -> None:
    # Solo la primera: cerrar la terminal manda SIGHUP y SIGTERM seguidos, y la segunda cortaría
    # la limpieza (`stop`, `stop_active`) a medias.
    for name in STOP_SIGNALS:
        signal.signal(getattr(signal, name), signal.SIG_IGN)
    raise KeyboardInterrupt


@contextmanager
def stop_on_signals() -> Iterator[None]:
    """Fuera de Windows, `SIGTERM` y `SIGHUP` (cerrar la terminal) paran como Ctrl+C. Con los
    hijos en su propio grupo, la señal de la terminal ya no les llega: los para `stop`."""
    previous: dict[signal.Signals, Any] = {}
    if sys.platform != "win32":
        for name in STOP_SIGNALS:
            sig = getattr(signal, name)
            previous[sig] = signal.signal(sig, _interrupt)
    try:
        yield
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


STOP_GRACE_SECONDS = 10.0


def _terminate(process: "subprocess.Popen[str]") -> None:
    """Fuera de Windows, `SIGTERM` al grupo del hijo: el worker para antes sus ejecuciones en
    segundo plano, que van en su propio grupo y `killpg` no alcanzaría. En Windows no hace falta:
    `taskkill /T` para todos los descendientes."""
    if sys.platform == "win32" or process.poll() is not None:
        return
    with contextlib.suppress(OSError):
        os.killpg(process.pid, signal.SIGTERM)


def stop(launch: Launch, grace: float = STOP_GRACE_SECONDS) -> None:
    """Para todos los hijos con lo que hayan lanzado (el árbol entero) y cierra sus logs."""
    running = [c.process for c in launch.children if c.process is not None]
    for process in running:
        _terminate(process)
    if sys.platform != "win32":
        deadline = time.monotonic() + grace
        for process in running:
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=max(0.0, deadline - time.monotonic()))
            # Aunque el hijo ya haya salido, lo que quede de su grupo (Vite bajo pnpm) también.
            with contextlib.suppress(OSError):
                os.killpg(process.pid, SIGKILL)
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
                    code = child.process.returncode
                    raise LaunchError(message("child_died", name=child.name, code=code))
            try:
                if client.get(f"{url}/status").status_code == 200:
                    return
            except httpx.HTTPError:
                pass
            sleep(0.5)
    raise LaunchError(message("timeout", seconds=timeout))


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
        say(message("already_running", url=f"http://{HOST}:{port}"))
        if open_browser:
            url = f"http://{HOST}:{port}"
            _open(browser, url, say, url)
        return
    if state == "other":
        raise LaunchError(message("port_busy", port=port))
    launch = plan(settings, port, dev=dev)
    say(message("starting"))
    waiting_page = starting_page(settings, port, dev=dev) if open_browser else None
    if waiting_page is not None:
        _open(browser, waiting_page, say, launch.url)
    migrations.upgrade()
    with stop_on_signals():
        try:
            later = [c for c in launch.children if c.name == "worker"]
            for child in launch.children:
                if child not in later:
                    _spawn(child, settings.logs_dir)
            wait_ready(f"http://{HOST}:{port}", launch)
            for child in later:
                _spawn(child, settings.logs_dir)
            say(message("running", url=launch.url))
            say(message("keep_open"))
            if open_browser and waiting_page is None:
                _open(browser, launch.url, say, launch.url)
            ended = supervise(launch)
            say(message("child_ended", name=ended))
        except KeyboardInterrupt:
            say(message("closing"))
        finally:
            stop(launch)
