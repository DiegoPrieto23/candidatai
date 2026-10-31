"""Arnés de las pruebas de extremo a extremo: la app compilada de verdad (`cai start`) sobre una
carpeta de datos temporal, recorrida con el Chromium de Playwright.

Sin Playwright aquí: lo usan también los tests de la guarda, que corren en la suite normal.

La guarda (`check_data_dir`) va antes de sembrar o arrancar nada: estas pruebas ejecutan la app
entera, y una carpeta mal resuelta escribiría en los datos reales de quien las pasa.
"""

import contextlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.core.config import REPO_ROOT, installed_data_dir

BACKEND = REPO_ROOT / "backend"
UI_DIST = REPO_ROOT / "frontend" / "dist"
LOCALES = REPO_ROOT / "frontend" / "src" / "locales"
ARTIFACTS = BACKEND / ".e2e-artifacts"
READY_TIMEOUT = 90.0  # la primera vez la API importa mucho; en la CI, más
# Un puerto donde no escucha nada: con él de proxy, cualquier petición a internet de la app (¿sigue
# abierta?, fuentes) falla al momento en vez de salir. Lo local va directo (`NO_PROXY`).
DEAD_PROXY = "http://127.0.0.1:9"


class UnsafeDataDir(RuntimeError):
    """La carpeta de datos de una E2E es (o está dentro de) una carpeta real del usuario."""


def _inside(path: Path, parent: Path) -> bool:
    return path == parent or path.is_relative_to(parent)


def _resolve(path: Path) -> Path:
    # `resolve` expande también los nombres cortos de Windows (`DIEGOP~1`) de lo que ya existe.
    return Path(os.path.normcase(path.expanduser().resolve()))


def check_data_dir(
    data_dir: Path,
    *,
    repo_data: Path = REPO_ROOT / "data",
    installed: Path | None = None,
    home: Path | None = None,
    temp: Path | None = None,
) -> Path:
    """Devuelve la carpeta resuelta o falla si es o cuelga de `data/` del repo, de la carpeta de
    datos de la app instalada o de la carpeta personal (salvo la temporal, que en Windows está
    dentro de ella). También si es una carpeta que las contiene (la raíz del disco o la del repo):
    la app escribiría su base al lado o `copytree` encima."""
    resolved = _resolve(data_dir)
    installed = installed if installed is not None else installed_data_dir()
    home = _resolve(home if home is not None else Path.home())
    temp = _resolve(temp if temp is not None else Path(tempfile.gettempdir()))
    forbidden = {
        "la carpeta data/ del repositorio": _resolve(repo_data),
        "la carpeta de datos de la app instalada": _resolve(installed),
    }
    for name, folder in forbidden.items():
        if _inside(resolved, folder) or _inside(folder, resolved):
            raise UnsafeDataDir(
                f"Las E2E no arrancan sobre {name} ({folder}) ni sobre lo que la contiene: usarían "
                f"tus datos reales. La carpeta de datos tiene que ser temporal ({data_dir})."
            )
    if temp == home or any(_inside(temp, f) for f in forbidden.values()):
        raise UnsafeDataDir(f"La carpeta temporal ({temp}) no puede ser tu carpeta personal.")
    if _inside(home, resolved) or (_inside(resolved, home) and not _inside(resolved, temp)):
        raise UnsafeDataDir(
            f"Las E2E no arrancan dentro de tu carpeta personal ({home}) salvo en la temporal "
            f"({temp}): {data_dir}"
        )
    return resolved


def ui_built() -> bool:
    return (UI_DIST / "index.html").is_file()


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def app_env(data_dir: Path, base: Mapping[str, str] | None = None) -> dict[str, str]:
    """El entorno de la app de una E2E: la carpeta temporal y nada heredado de quien las pasa (su
    `.env` lo leería la app, pero las variables mandan sobre él)."""
    env = {
        k: v
        for k, v in (base if base is not None else os.environ).items()
        if not k.upper().startswith(("CAI_", "JH_"))
    }
    env.update(
        {
            "CAI_DATA_DIR": str(data_dir),
            "CAI_ENV_FILE": str(data_dir.parent / ".env"),
            "CAI_EMBEDDINGS": "off",
            "CAI_LANG": "es",
            "CAI_OLLAMA_URL": "http://127.0.0.1:9",
            "CAI_IMAP_HOST": "",
            "CAI_IMAP_USER": "",
            "CAI_IMAP_PASSWORD": "",
            "CAI_BROWSER_HEADLESS": "true",
            "HTTP_PROXY": DEAD_PROXY,
            "HTTPS_PROXY": DEAD_PROXY,
            "ALL_PROXY": DEAD_PROXY,
            "NO_PROXY": "127.0.0.1,localhost",
            "PYTHONUTF8": "1",
        }
    )
    return env


def _cai(*args: str, python: str = sys.executable) -> list[str]:
    return [python, "-m", "app", *args]


def run_cai(data_dir: Path, *args: str, timeout: float = 300) -> "subprocess.CompletedProcess[str]":
    """Un comando `cai` sobre la carpeta (que se comprueba antes), sin lanzar si falla."""
    data_dir = check_data_dir(data_dir)
    return subprocess.run(  # noqa: S603
        _cai(*args),
        cwd=BACKEND,
        env=app_env(data_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )


def seed_demo(data_dir: Path) -> dict[str, Any]:
    """`cai demo seed --dir` en la carpeta (que se comprueba antes)."""
    data_dir = check_data_dir(data_dir)
    result = run_cai(data_dir, "demo", "seed", "--dir", str(data_dir), "--json")
    if result.returncode != 0:
        raise RuntimeError(f"cai demo seed falló:\n{result.stdout}\n{result.stderr}")
    summary: dict[str, Any] = json.loads(result.stdout)
    return summary


def copy_data(source: Path, target: Path) -> Path:
    """Una copia de una carpeta ya sembrada (sembrar cuesta medio minuto; copiar, nada). La base no
    guarda rutas absolutas: la copia funciona igual."""
    target = check_data_dir(target)
    shutil.copytree(source, target)
    return target


@dataclass
class AppServer:
    """Una app arrancada con `cai start`."""

    data_dir: Path
    port: int
    process: "subprocess.Popen[bytes]"
    startup_seconds: float
    job: "WindowsJob | None" = None

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def logs(self) -> str:
        parts = []
        for path in sorted((self.data_dir / "logs").glob("start-*.log")):
            with contextlib.suppress(OSError):
                text = path.read_text(encoding="utf-8", errors="replace")
                parts.append(f"--- {path.name}\n{text}")
        return "\n".join(parts)


class WindowsJob:
    """Un Job Object de Windows con «matar al cerrar»: lo que lance un proceso de dentro (la API, el
    worker, sus navegadores) queda dentro, y cerrarlo los para a todos, aunque `cai start` ya haya
    salido o pytest se caiga a medias. `taskkill /T` no basta: con el padre muerto no llega a los
    hijos."""

    _KILL_ON_JOB_CLOSE = 0x2000
    _EXTENDED_LIMIT_INFORMATION = 9

    def __init__(self) -> None:
        import ctypes
        from ctypes import wintypes

        class Basic(ctypes.Structure):
            _fields_ = [  # noqa: RUF012 - JOBOBJECT_BASIC_LIMIT_INFORMATION
                ("PerProcessUserTimeLimit", ctypes.c_int64),
                ("PerJobUserTimeLimit", ctypes.c_int64),
                ("LimitFlags", wintypes.DWORD),
                ("MinimumWorkingSetSize", ctypes.c_size_t),
                ("MaximumWorkingSetSize", ctypes.c_size_t),
                ("ActiveProcessLimit", wintypes.DWORD),
                ("Affinity", ctypes.c_size_t),
                ("PriorityClass", wintypes.DWORD),
                ("SchedulingClass", wintypes.DWORD),
            ]

        class Extended(ctypes.Structure):
            _fields_ = [  # noqa: RUF012 - JOBOBJECT_EXTENDED_LIMIT_INFORMATION
                ("BasicLimitInformation", Basic),
                ("IoInfo", ctypes.c_uint64 * 6),
                ("ProcessMemoryLimit", ctypes.c_size_t),
                ("JobMemoryLimit", ctypes.c_size_t),
                ("PeakProcessMemoryUsed", ctypes.c_size_t),
                ("PeakJobMemoryUsed", ctypes.c_size_t),
            ]

        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._ntdll = ctypes.WinDLL("ntdll")
        self._kernel32.CreateJobObjectW.restype = wintypes.HANDLE
        self._kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self._kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self._kernel32.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self._kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self._ntdll.NtResumeProcess.argtypes = [wintypes.HANDLE]
        handle = self._kernel32.CreateJobObjectW(None, None)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.handle: int | None = handle
        info = Extended()
        info.BasicLimitInformation.LimitFlags = self._KILL_ON_JOB_CLOSE
        ok = self._kernel32.SetInformationJobObject(
            handle, self._EXTENDED_LIMIT_INFORMATION, ctypes.byref(info), ctypes.sizeof(info)
        )
        if not ok:
            raise ctypes.WinError(ctypes.get_last_error())

    def adopt_and_resume(self, process: "subprocess.Popen[bytes]") -> None:
        """Mete en el Job un proceso creado suspendido y lo reanuda: así ni el lanzador del venv
        llega a crear un hijo fuera."""
        import ctypes

        process_handle = int(process._handle)  # type: ignore[attr-defined]  # noqa: SLF001
        if not self._kernel32.AssignProcessToJobObject(self.handle, process_handle):
            raise ctypes.WinError(ctypes.get_last_error())
        self._ntdll.NtResumeProcess(process_handle)

    def close(self) -> None:
        if self.handle is None:
            return
        self._kernel32.TerminateJobObject(self.handle, 1)
        self._kernel32.CloseHandle(self.handle)
        self.handle = None


CREATE_SUSPENDED = 0x4


def spawn(
    command: list[str],
    *,
    env: Mapping[str, str],
    popen: Callable[..., "subprocess.Popen[bytes]"] = subprocess.Popen,
    **kwargs: Any,
) -> "tuple[subprocess.Popen[bytes], WindowsJob | None]":
    """Lanza un proceso de la app que `stop_app` podrá parar con todo lo que lance. En Windows, en
    un Job Object; fuera, en su propio grupo."""
    if sys.platform != "win32":
        return popen(command, env=env, start_new_session=True, **kwargs), None
    job = WindowsJob()
    try:
        process = popen(command, env=env, creationflags=CREATE_SUSPENDED, **kwargs)
        job.adopt_and_resume(process)
    except BaseException:
        job.close()
        raise
    return process, job


def start_app(
    data_dir: Path,
    *,
    popen: Callable[..., "subprocess.Popen[bytes]"] = subprocess.Popen,
    timeout: float = READY_TIMEOUT,
    python: str = sys.executable,
    cwd: Path = BACKEND,
    extra_env: Mapping[str, str] | None = None,
) -> AppServer:
    """Arranca `cai start --no-browser` en un puerto libre y espera a que `/status` responda.

    `python` y `cwd`, para arrancar otra copia de la app (la instalada); `extra_env`, para lo que
    necesite un test (un proxy local, la candidatura asistida contra 127.0.0.1)."""
    data_dir = check_data_dir(data_dir)  # antes de crear nada
    data_dir.mkdir(parents=True, exist_ok=True)
    port = free_port()
    started = time.monotonic()
    env = app_env(data_dir)
    env.update(extra_env or {})
    process, job = spawn(
        _cai("start", "--port", str(port), "--no-browser", python=python),
        env=env,
        popen=popen,
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    server = AppServer(data_dir, port, process, 0.0, job)
    try:
        _wait_ready(server, started + timeout)
    except BaseException:
        stop_app(server)
        raise
    server.startup_seconds = time.monotonic() - started
    return server


def _wait_ready(server: AppServer, deadline: float) -> None:
    while time.monotonic() < deadline:
        if server.process.poll() is not None:
            raise RuntimeError(f"cai start salió con {server.process.returncode}:\n{server.logs()}")
        with contextlib.suppress(httpx.HTTPError):
            # Sin el proxy de quien pasa los tests: 127.0.0.1 va directo.
            if httpx.get(f"{server.url}/status", timeout=2, trust_env=False).status_code == 200:
                return
        time.sleep(0.3)
    raise TimeoutError(f"cai start no respondió en {server.url}:\n{server.logs()}")


def _posix_app_processes(data_dir: Path) -> list[int]:
    """Los procesos con el `CAI_DATA_DIR` de esta app: `cai start` pone a la API y al worker en su
    propio grupo, y un huérfano pasa a colgar de `init`; su entorno sigue diciendo de quién es."""
    if not Path("/proc").is_dir():
        return []  # macOS: basta el grupo de `cai start`, que para a sus hijos al recibir SIGTERM
    marker = f"CAI_DATA_DIR={data_dir}".encode()
    found = []
    for proc in Path("/proc").glob("[0-9]*"):
        with contextlib.suppress(OSError, ValueError):
            if marker in (proc / "environ").read_bytes().split(b"\0"):
                found.append(int(proc.name))
    return [pid for pid in found if pid != os.getpid()]


def stop_app(server: AppServer, grace: float = 15.0) -> None:
    """Para `cai start` con la API y el worker, aunque `cai start` ya haya salido.

    En Windows se cierra su Job Object. Fuera, primero `SIGTERM`, que `cai start` atiende parando a
    sus hijos, y luego `SIGKILL` a lo que quede con su carpeta de datos."""
    process = server.process
    if server.job is not None:
        server.job.close()
    elif sys.platform != "win32":
        if process.poll() is None:
            with contextlib.suppress(OSError):
                os.killpg(process.pid, signal.SIGTERM)
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=grace)
        with contextlib.suppress(OSError):
            os.killpg(process.pid, signal.SIGKILL)
        for pid in _posix_app_processes(server.data_dir):
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGKILL)
    else:
        process.kill()
    with contextlib.suppress(subprocess.TimeoutExpired):
        process.wait(timeout=grace)


def remove_dir(path: Path, attempts: int = 10) -> None:
    """Borra la carpeta temporal. En Windows, SQLite puede tardar un instante en soltarla."""
    for _ in range(attempts):
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError:
            time.sleep(0.5)
    shutil.rmtree(path, ignore_errors=True)


# --- Textos de la UI ----------------------------------------------------------------------------


def _texts(lang: str, namespace: str) -> dict[str, Any]:
    path = LOCALES / lang / f"{namespace}.json"
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def t(key: str, lang: str = "es", **values: object) -> str:
    """El texto de la UI `<zona>.<clave>` (`t("inbox.title")`), leído de `frontend/src/locales`,
    con sus `{{valores}}`. Así un cambio de redacción no rompe las E2E."""
    namespace, _, path = key.partition(".")
    node: Any = _texts(lang, namespace)
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"{key} no está en frontend/src/locales/{lang}/{namespace}.json")
        node = node[part]
    if not isinstance(node, str):
        raise KeyError(f"{key} no es un texto")
    missing = set(re.findall(r"\{\{\s*(\w+)\s*\}\}", node)) - set(values)
    if missing:
        raise KeyError(f"{key} necesita {sorted(missing)}")
    return re.sub(r"\{\{\s*(\w+)\s*\}\}", lambda m: str(values[m.group(1)]), node)
