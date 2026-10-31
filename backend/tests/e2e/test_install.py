"""El instalador de Windows de verdad, en una carpeta temporal: instala desde este repositorio,
arranca la app instalada, abre su primer arranque y desinstala, sin tocar los accesos directos ni
los datos reales.

Tarda (`uv sync` en una carpeta nueva), así que no va en el humo ni en `-m e2e`: `-m e2e_install`.
uv va sin red (`UV_OFFLINE`): si a su caché le falta algo, falla en vez de descargar. El Chromium de
Playwright es el que ya tengas instalado (solo lo descargaría si faltara). Los tiempos de cada paso
quedan en `.e2e-artifacts/instalador-tiempos.json`.
"""

import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect

from app.core.config import REPO_ROOT
from tests.e2e import harness
from tests.e2e.harness import t

pytestmark = [
    pytest.mark.e2e_install,
    pytest.mark.skipif(sys.platform != "win32", reason="install.ps1 es para Windows"),
]

INSTALL_TIMEOUT = 900


def _powershell() -> str:
    found = shutil.which("powershell")
    if found is None:
        pytest.skip("sin PowerShell")
    return found


def _real_shortcuts() -> dict[str, float | None]:
    """Los accesos «CandidatAI» reales del escritorio y del menú Inicio: su fecha, o `None` si no
    existen. Las carpetas, las que use el instalador (`GetFolderPath`, con OneDrive incluido)."""
    script = "[Environment]::GetFolderPath('Desktop'); [Environment]::GetFolderPath('Programs')"
    result = subprocess.run(  # noqa: S603
        [_powershell(), "-NoProfile", "-Command", script],
        capture_output=True, text=True, encoding="utf-8", timeout=60, check=True,
    )  # fmt: skip
    folders = [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]
    assert len(folders) == 2, result.stdout
    shortcuts = {}
    for folder in folders:
        link = folder / "CandidatAI.lnk"
        shortcuts[str(link)] = link.stat().st_mtime if link.exists() else None
    return shortcuts


def _installer(install_dir: Path, *args: str) -> subprocess.CompletedProcess[str]:
    # Sin lo de quien pasa los tests: sus datos (`CAI_*`) ni el entorno de Python del repo (si no,
    # `uv sync` podría preparar ese en vez del de la instalación).
    inherited = ("CAI_", "JH_", "VIRTUAL_ENV", "UV_PROJECT_ENVIRONMENT")
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(inherited)}
    env["UV_OFFLINE"] = "1"  # nada de red: todo sale de las cachés
    return subprocess.run(  # noqa: S603
        [_powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(REPO_ROOT / "install.ps1"), "-InstallDir", str(install_dir), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=INSTALL_TIMEOUT, env=env, check=False,
    )  # fmt: skip


@pytest.fixture
def install_dir(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    root = tmp_path_factory.mktemp("e2e-install")
    yield root / "CandidatAI"
    harness.remove_dir(root)


@pytest.fixture
def real_shortcuts_untouched() -> Iterator[None]:
    """Compara los accesos reales al cerrar, también si el test falla a mitad."""
    before = _real_shortcuts()
    yield
    assert _real_shortcuts() == before, "los accesos directos reales han cambiado"


@pytest.mark.usefixtures("real_shortcuts_untouched")
def test_install_first_start_and_uninstall(browser: Browser, install_dir: Path) -> None:
    if shutil.which("uv") is None:
        pytest.skip("sin uv: el instalador lo descargaría de internet")
    timings: dict[str, float] = {}

    started = time.monotonic()
    result = _installer(install_dir, "-Source", str(REPO_ROOT), "-NoShortcuts")
    timings["instalar"] = time.monotonic() - started
    assert result.returncode == 0, result.stdout + result.stderr
    backend = install_dir / "app" / "backend"
    data_dir = install_dir / "data"
    python = backend / ".venv" / "Scripts" / "python.exe"
    assert python.is_file()
    # El `.env` de la app instalada apunta a sus datos, no a los tuyos.
    assert f"CAI_DATA_DIR={data_dir}" in (install_dir / "app" / ".env").read_text(encoding="utf-8")

    started = time.monotonic()
    server = harness.start_app(data_dir, python=str(python), cwd=backend)
    try:
        timings["arrancar"] = time.monotonic() - started
        started = time.monotonic()
        context = browser.new_context(base_url=server.url, locale="es-ES")
        try:
            page: Page = context.new_page()
            page.goto("/")
            expect(page.get_by_role("region", name=t("home.firstSteps.title"))).to_be_visible()
            page.goto("/bandeja")
            expect(page.get_by_text(t("inbox.empty.title"))).to_be_visible()
        finally:
            context.close()
        timings["primer_arranque_en_el_navegador"] = time.monotonic() - started
    finally:
        harness.stop_app(server)
    assert (data_dir / "candidatai.db").is_file()

    started = time.monotonic()
    result = _installer(install_dir, "-Uninstall")
    timings["desinstalar"] = time.monotonic() - started
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (install_dir / "app").exists()
    assert (data_dir / "candidatai.db").is_file(), "desinstalar no borra tus datos"

    harness.ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (harness.ARTIFACTS / "instalador-tiempos.json").write_text(
        json.dumps({k: round(v, 1) for k, v in timings.items()}, indent=2), encoding="utf-8"
    )
    print("Tiempos del instalador (s):", {k: round(v, 1) for k, v in timings.items()})
