"""El arnés de las E2E (`tests/e2e/`), sin navegador ni app: van en la suite normal.

- La guarda de datos: se niega a sembrar o arrancar sobre una carpeta real **sin lanzar nada**.
- El humo cubre todas las rutas de `App.tsx`.
- `uv run pytest` sin `-m` no recoge ninguna E2E.
- Los textos se leen de `frontend/src/locales`.
"""

import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest

from app.core.config import REPO_ROOT, install_dir, installed_data_dir
from tests.e2e import harness
from tests.e2e.test_smoke import ROUTES

APP_TSX = REPO_ROOT / "frontend" / "src" / "App.tsx"
BACKEND = REPO_ROOT / "backend"


def _never(*args: Any, **kwargs: Any) -> Any:
    raise AssertionError("la guarda dejó lanzar un proceso")


@pytest.fixture
def no_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "Popen", _never)
    monkeypatch.setattr(subprocess, "run", _never)


REAL_DIRS = {
    "data del repo": REPO_ROOT / "data",
    "dentro de data del repo": REPO_ROOT / "data" / "demo",
    "datos de la app instalada": installed_data_dir(),
    "dentro de la app instalada": installed_data_dir() / "sub",
    "carpeta personal": Path.home(),
    "dentro de la carpeta personal": Path.home() / "Documents" / "cai-e2e",
    # Lo que contiene una carpeta real: la app escribiría al lado o `copytree` encima.
    "raíz del repo": REPO_ROOT,
    "carpeta de la app instalada": install_dir(),
    "raíz del disco": Path(REPO_ROOT.anchor),
}


@pytest.mark.parametrize("target", list(REAL_DIRS.values()), ids=list(REAL_DIRS))
@pytest.mark.usefixtures("no_processes")
def test_the_guard_refuses_real_folders_without_starting_anything(target: Path) -> None:
    with pytest.raises(harness.UnsafeDataDir):
        harness.start_app(target, popen=_never)
    with pytest.raises(harness.UnsafeDataDir):
        harness.seed_demo(target)
    with pytest.raises(harness.UnsafeDataDir):
        harness.copy_data(Path(tempfile.gettempdir()), target)


@pytest.mark.usefixtures("no_processes")
def test_the_guard_resolves_relative_paths_and_dots(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT / "backend")
    for sneaky in (Path("../data"), REPO_ROOT / "backend" / ".." / "data" / "x"):
        with pytest.raises(harness.UnsafeDataDir):
            harness.check_data_dir(sneaky)


@pytest.mark.skipif(sys.platform != "win32", reason="mayúsculas y nombres cortos: Windows")
def test_the_guard_ignores_case_and_short_names_on_windows() -> None:
    with pytest.raises(harness.UnsafeDataDir):
        harness.check_data_dir(Path(str(REPO_ROOT / "data").upper()))
    with pytest.raises(harness.UnsafeDataDir):
        harness.check_data_dir(Path(str(installed_data_dir()).lower()))


def test_the_guard_follows_symlinks(tmp_path: Path) -> None:
    link = tmp_path / "enlace"
    try:
        link.symlink_to(REPO_ROOT / "data", target_is_directory=True)
    except OSError:
        pytest.skip("este sistema no deja crear enlaces simbólicos sin permisos")
    with pytest.raises(harness.UnsafeDataDir):
        harness.check_data_dir(link)
    with pytest.raises(harness.UnsafeDataDir):
        harness.check_data_dir(link / "sub")


def test_the_guard_lets_through_the_temporary_folder(tmp_path: Path) -> None:
    assert harness.check_data_dir(tmp_path / "data") == harness._resolve(tmp_path / "data")


def test_the_guard_works_with_any_layout(tmp_path: Path) -> None:
    """Con las carpetas de otro sistema (Linux: la temporal fuera de la personal)."""
    home, temp, repo = tmp_path / "home", tmp_path / "tmp", tmp_path / "repo"
    paths = {
        "repo_data": repo / "data",
        "installed": home / ".local" / "share" / "candidatai" / "data",
        "home": home,
        "temp": temp,
    }
    assert harness.check_data_dir(temp / "x", **paths)
    assert harness.check_data_dir(tmp_path / "elsewhere", **paths)
    for bad in (repo / "data", paths["installed"], home / "x", repo, tmp_path):
        with pytest.raises(harness.UnsafeDataDir):
            harness.check_data_dir(bad, **paths)
    # Con la temporal en la carpeta personal (`TMP=%USERPROFILE%`) no se libra nada.
    with pytest.raises(harness.UnsafeDataDir):
        harness.check_data_dir(home / "x", **{**paths, "temp": home})


def test_app_env_points_to_the_folder_and_drops_the_users_settings(tmp_path: Path) -> None:
    env = harness.app_env(
        tmp_path / "data",
        {"CAI_DATA_DIR": "C:/real", "CAI_IMAP_HOST": "imap.real", "JH_AGENT": "x", "PATH": "p"},
    )
    assert env["CAI_DATA_DIR"] == str(tmp_path / "data")
    assert env["CAI_IMAP_HOST"] == ""
    assert "JH_AGENT" not in env
    assert env["PATH"] == "p"
    assert env["HTTPS_PROXY"] == harness.DEAD_PROXY  # nada sale a internet
    # Ni el `.env` de la raíz del repo: la app lee el de la carpeta temporal.
    assert Path(env["CAI_ENV_FILE"]).parent == tmp_path


def _alive(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32")
        kernel32.OpenProcess.restype = ctypes.c_void_p
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        code = ctypes.c_ulong()
        try:
            kernel32.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))
        finally:
            kernel32.CloseHandle(ctypes.c_void_p(handle))
        return code.value == 259  # STILL_ACTIVE
    stat = Path(f"/proc/{pid}/stat")
    try:
        return stat.read_text().split(") ")[1][0] != "Z"
    except (OSError, IndexError):
        return False


def _kill(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)  # noqa: S603, S607
    else:
        os.kill(pid, signal.SIGKILL)


@pytest.mark.skipif(
    sys.platform == "darwin", reason="sin /proc: en macOS basta el grupo de `cai start`"
)
def test_stop_app_kills_what_an_exited_cai_start_left_behind(tmp_path: Path) -> None:
    """Un `cai start` que ya salió dejando un hijo vivo (en Windows, `taskkill /T` no lo alcanza
    sin el padre; fuera, el hijo va en su propio grupo): `stop_app` lo para igual."""
    data_dir, pid_file = tmp_path / "data", tmp_path / "pid"
    child = "import time; time.sleep(120)"
    parent = (
        "import subprocess, sys; "
        f"p = subprocess.Popen([sys.executable, '-c', {child!r}], "
        "start_new_session=sys.platform != 'win32'); "
        f"open({str(pid_file)!r}, 'w').write(str(p.pid))"
    )
    process, job = harness.spawn([sys.executable, "-c", parent], env=harness.app_env(data_dir))
    process.wait(timeout=60)
    orphan = int(pid_file.read_text())
    try:
        assert _alive(orphan)
        harness.stop_app(harness.AppServer(data_dir, 0, process, 0.0, job), grace=5)
        deadline = time.monotonic() + 10
        while _alive(orphan) and time.monotonic() < deadline:
            time.sleep(0.2)
        assert not _alive(orphan)
    finally:
        if _alive(orphan):
            _kill(orphan)


def _app_routes() -> list[str]:
    """Las rutas de `App.tsx`, como en `test_start.py`: las anidadas cuelgan de su madre."""
    source = APP_TSX.read_text(encoding="utf-8")
    parents = re.findall(
        r'<Route path="([^"]+)" element=\{<\w+ />\}>(.*?)</Route>', source, flags=re.DOTALL
    )
    assert parents
    urls = []
    for parent, children in parents:
        urls += [f"/{parent}/{child}" for child in re.findall(r'path="([^"]+)"', children)]
        urls.append(f"/{parent}")
        source = source.replace(children, "")
    urls += ["/" + path for path in re.findall(r'path="([^"]+)"', source) if path != "*"]
    return ["/", *sorted(set(urls))]


def test_the_smoke_covers_every_route_of_the_ui() -> None:
    # `*` (página no encontrada) no se abre por URL: la API responde 404 a lo que no es de la UI.
    missing = set(_app_routes()) - {r.path for r in ROUTES}
    assert not missing, f"Rutas de App.tsx sin humo en tests/e2e/test_smoke.py: {sorted(missing)}"


def test_every_smoke_heading_exists_in_both_languages() -> None:
    for route in ROUTES:
        if route.heading:
            assert harness.t(route.heading, "es") and harness.t(route.heading, "en")


def test_t_reads_the_locales_and_fills_values() -> None:
    assert harness.t("inbox.title") == "Bandeja de ofertas"
    assert harness.t("nav.language.button", name="Español") == "Idioma: Español"
    with pytest.raises(KeyError):
        harness.t("inbox.no.existe")
    with pytest.raises(KeyError):
        harness.t("nav.language.button")  # sin `name`


def _collected(*args: str) -> str:
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *args],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=300,
        check=False,
    )
    return result.stdout


def test_a_plain_pytest_collects_no_e2e() -> None:
    out = _collected().replace("\\", "/")
    assert "tests/test_e2e_harness.py" in out, out[-2000:]
    assert "tests/e2e/" not in out, out[-2000:]


class _Config:
    def __init__(self, markexpr: str = "", args: tuple[str, ...] = ("tests",)) -> None:
        self.markexpr, self.args = markexpr, list(args)

    def getoption(self, name: str) -> str:
        return self.markexpr


@pytest.mark.parametrize(
    ("markexpr", "args", "e2e"),
    [
        ("", ("tests",), False),
        ("layout", ("tests",), False),
        ("e2e", ("tests",), True),
        ("e2e and smoke", ("tests",), True),
        ("e2e_install", ("tests",), True),
        ("not e2e_install", ("tests",), False),
        ("", ("tests/e2e/test_smoke.py::test_page_opens",), True),
    ],
)
def test_e2e_only_with_their_marker_or_their_folder(
    markexpr: str, args: tuple[str, ...], e2e: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests import conftest

    monkeypatch.chdir(BACKEND)
    assert conftest._wants_e2e(_Config(markexpr, args)) is e2e  # type: ignore[arg-type]
