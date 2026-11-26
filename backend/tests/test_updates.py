"""Versiones nuevas: el aviso de Inicio y «Actualizar ahora» (`services/updates.py`)."""

import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import VERSION
from app.agent_interface.errors import ToolError
from app.api.main import create_app
from app.core import migrations
from app.core.config import INSTALL_MARKER, get_settings
from app.services import launcher, updates

LOCAL = "http://127.0.0.1:8000"
NEWER = "99.0.0"


@pytest.fixture(autouse=True)
def _fresh_cache() -> Iterator[None]:
    updates.reset_cache()
    yield
    updates.reset_cache()


@pytest.fixture
def checks_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAI_UPDATE_CHECK", "auto")
    get_settings.cache_clear()


def _release(tag: str = f"v{NEWER}", **extra: Any) -> dict[str, Any]:
    return {
        "tag_name": tag,
        "html_url": f"https://github.com/{updates.REPOSITORY}/releases/tag/{tag}",
        **extra,
    }


@pytest.fixture
def installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Una instalación de Windows abierta con `cai start`: `<carpeta>/app` con su marca."""
    app = tmp_path / "CandidatAI" / "app"
    app.mkdir(parents=True)
    (app.parent / INSTALL_MARKER).touch()
    (app / "install.ps1").write_text("# instalador\n", encoding="utf-8")
    uv = tmp_path / "uv.exe"
    uv.touch()
    monkeypatch.setenv("UV_PATH", str(uv))
    monkeypatch.setenv(launcher.SUPERVISOR_PID_ENV, "4242")
    return app


# --- Versiones ------------------------------------------------------------------------------------


def test_versions_compare_as_numbers() -> None:
    assert updates.parse_version("v1.10.0") == (1, 10, 0)
    assert updates.is_newer("1.10.0", "1.9.3")
    assert updates.is_newer("v1.0.2", "1.0.1")
    assert not updates.is_newer("1.0.1", "1.0.1")
    assert not updates.is_newer("1.0.0", "1.0.1")
    # Lo que no es una versión publicada no avisa de nada.
    for odd in ("v1.1.0-rc1", "latest", "", "1.1"):
        assert updates.parse_version(odd) is None
        assert not updates.is_newer(odd, "1.0.0")


def test_fetch_latest_reads_the_tag_and_sends_no_user_data() -> None:
    with respx.mock(assert_all_called=True) as mock:
        route = mock.get(updates.LATEST_URL).mock(return_value=httpx.Response(200, json=_release()))
        release = updates.fetch_latest()
    assert release == updates.Release(
        version=NEWER, url=f"https://github.com/{updates.REPOSITORY}/releases/tag/v{NEWER}"
    )
    headers = route.calls.last.request.headers
    assert headers["user-agent"] == f"CandidatAI/{VERSION}"
    assert "authorization" not in headers and "cookie" not in headers


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(404, json={"message": "Not Found"}),
        httpx.Response(200, json=_release(tag="nightly")),
        httpx.Response(200, json=["no", "es", "un", "objeto"]),
        httpx.Response(200, text="<html>"),
        httpx.ConnectError("sin red"),
    ],
)
def test_fetch_latest_gives_up_quietly(response: Any) -> None:
    with respx.mock:
        route = respx.get(updates.LATEST_URL)
        if isinstance(response, Exception):
            route.mock(side_effect=response)
        else:
            route.mock(return_value=response)
        assert updates.fetch_latest() is None


@respx.mock
def test_a_release_link_outside_the_repository_is_not_shown() -> None:
    respx.get(updates.LATEST_URL).mock(
        return_value=httpx.Response(200, json=_release(html_url="https://ejemplo.com/phishing"))
    )
    release = updates.fetch_latest()
    assert release is not None
    assert release.url == f"https://github.com/{updates.REPOSITORY}/releases/latest"


@respx.mock
def test_github_is_asked_at_most_every_few_hours() -> None:
    route = respx.get(updates.LATEST_URL)
    route.mock(side_effect=httpx.ConnectError("sin red"))
    clock = [1000.0]
    assert updates.latest_release(now=lambda: clock[0]) is None
    clock[0] += updates.RETRY_AFTER - 1
    assert updates.latest_release(now=lambda: clock[0]) is None
    assert route.call_count == 1  # un fallo se recuerda un rato
    route.side_effect = None
    route.return_value = httpx.Response(200, json=_release())
    clock[0] += 2
    assert updates.latest_release(now=lambda: clock[0]) is not None
    clock[0] += updates.CHECK_EVERY - 1
    assert updates.latest_release(now=lambda: clock[0]) is not None
    assert route.call_count == 2


# --- Estado ---------------------------------------------------------------------------------------


@respx.mock(assert_all_mocked=True)
def test_with_checks_off_github_is_never_asked(installed: Path) -> None:
    """`CAI_UPDATE_CHECK=off` (la de los tests): ni una petición; un intento fallaría aquí."""
    report = updates.status(platform="win32", repo_root=installed)
    assert report.latest is None and not report.available and not report.can_apply
    assert report.current == VERSION and report.install == "installer"


@respx.mock(assert_all_mocked=True)
def test_the_demo_never_asks_github(
    installed: Path, checks_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    (get_settings().data_dir / ".demo").touch()
    report = updates.status(platform="win32", repo_root=installed)
    assert report.latest is None and not report.can_apply


@respx.mock
def test_a_newer_release_can_be_applied_from_the_windows_installer(
    installed: Path, checks_on: None
) -> None:
    respx.get(updates.LATEST_URL).mock(return_value=httpx.Response(200, json=_release()))
    report = updates.status(platform="win32", repo_root=installed)
    assert report.available and report.can_apply
    assert report.latest == NEWER and report.release_url and NEWER in report.release_url
    assert report.command == updates.WINDOWS_COMMAND


@respx.mock
def test_without_cai_start_or_uv_the_button_gives_way_to_the_command(
    installed: Path, checks_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    respx.get(updates.LATEST_URL).mock(return_value=httpx.Response(200, json=_release()))
    monkeypatch.delenv(launcher.SUPERVISOR_PID_ENV)
    report = updates.status(platform="win32", repo_root=installed)
    assert report.available and not report.can_apply and report.command == updates.WINDOWS_COMMAND
    monkeypatch.setenv(launcher.SUPERVISOR_PID_ENV, "4242")
    for name in ("UV_PATH", "UV"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(updates.shutil, "which", lambda _name: None)
    assert not updates.status(platform="win32", repo_root=installed).can_apply


@respx.mock
def test_same_version_is_not_news(installed: Path, checks_on: None) -> None:
    respx.get(updates.LATEST_URL).mock(
        return_value=httpx.Response(200, json=_release(tag=f"v{VERSION}"))
    )
    report = updates.status(platform="win32", repo_root=installed)
    assert report.latest == VERSION and not report.available and not report.can_apply


def test_each_installation_gets_its_own_way_to_update(
    tmp_path: Path, installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = get_settings()
    assert updates.install_kind(settings, installed) == "installer"
    assert updates.manual_command("installer", "darwin") == updates.UNIX_COMMAND
    assert updates.manual_command("installer", "linux") == updates.UNIX_COMMAND
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    assert updates.install_kind(settings, repo) == "repository"
    assert updates.manual_command("repository") is None  # varios pasos: la guía
    assert updates.install_kind(settings, tmp_path / "suelta") == "other"
    monkeypatch.setenv("CAI_IN_DOCKER", "true")
    get_settings.cache_clear()
    assert updates.install_kind(get_settings(), installed) == "docker"
    assert updates.manual_command("docker") == updates.DOCKER_COMMAND
    # Solo la instalación de Windows se actualiza desde la app.
    for platform in ("darwin", "linux"):
        assert not updates.status(platform=platform, repo_root=installed).can_apply


def test_the_windows_command_fits_the_run_dialog_and_survives_powershell() -> None:
    """Se pega en Windows+R (259 caracteres como mucho), en cmd o en PowerShell: sin `$`, que
    PowerShell sustituiría al pegarla, y con el instalador ejecutado como fichero (`iex` no
    admite su `param` con `[CmdletBinding()]`)."""
    command = updates.WINDOWS_COMMAND
    assert len(command) <= 259
    assert "$" not in command and "iex" not in command
    assert f"{updates.RAW_URL}/install.ps1" in command and ".\\cai-install.ps1" in command
    for doc in ("README.md", "README.es.md", "docs/GUIA.md", "docs/GUIDE.md", "docs/EMPEZAR.md",
                "docs/START_HERE.md"):  # fmt: skip
        text = (Path(__file__).resolve().parents[2] / doc).read_text(encoding="utf-8")
        assert command in text, doc
    # La web pone su idioma, para que el instalador hable en el mismo.
    for doc, lang in (("site/index.html", "es"), ("site/en/index.html", "en")):
        site_command = command.removesuffix('"') + f' -Lang {lang}"'
        assert len(site_command) <= 259
        text = (Path(__file__).resolve().parents[2] / doc).read_text(encoding="utf-8")
        assert site_command in text, doc


# --- Actualizar desde la app ----------------------------------------------------------------------


@respx.mock
def test_apply_opens_the_updater_outside_the_app_and_closes_it(
    installed: Path, checks_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    respx.get(updates.LATEST_URL).mock(return_value=httpx.Response(200, json=_release()))
    monkeypatch.setenv("CAI_DATA_DIR", str(get_settings().data_dir))
    spawned: list[tuple[list[str], Path, dict[str, str]]] = []
    exits: list[bool] = []
    started = updates.apply(
        "en",
        f"v{NEWER}",
        platform="win32",
        repo_root=installed,
        spawn=lambda argv, cwd, env: spawned.append((argv, cwd, env)),
        exit_soon=lambda: exits.append(True),
    )
    assert started.version == NEWER and exits == [True]
    [(argv, cwd, env)] = spawned
    try:
        # Fuera de la carpeta de la app, que se sustituye entera (Windows no deja con algo dentro).
        assert not cwd.is_relative_to(installed) and cwd.name.startswith("candidatai-update-")
        assert (cwd / "update_windows.ps1").read_bytes() == updates.UPDATER.read_bytes()
        assert (cwd / "install.ps1").read_text(encoding="utf-8") == "# instalador\n"
        assert argv[argv.index("-File") + 1] == str(cwd / "update_windows.ps1")
        assert argv[argv.index("-InstallDir") + 1] == str(installed.parent)
        assert argv[argv.index("-Installer") + 1] == str(cwd / "install.ps1")
        assert argv[argv.index("-WaitPid") + 1] == "4242"
        assert argv[argv.index("-Lang") + 1] == "en"
        # La app que vuelve a abrir usa los datos de su `.env`, no los de esta ejecución.
        assert "CAI_DATA_DIR" not in env and launcher.SUPERVISOR_PID_ENV not in env
    finally:
        shutil.rmtree(cwd, ignore_errors=True)


@respx.mock
def test_apply_refuses_what_it_cannot_update(
    installed: Path, tmp_path: Path, checks_on: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    route = respx.get(updates.LATEST_URL).mock(return_value=httpx.Response(200, json=_release()))

    def apply(expected: str = NEWER, **kwargs: Any) -> None:
        options: dict[str, Any] = {"platform": "win32", "repo_root": installed}
        options.update(kwargs)
        updates.apply(
            "es",
            expected,
            spawn=lambda *_a: pytest.fail("no debe abrir nada"),
            exit_soon=lambda: pytest.fail("no debe cerrarse"),
            **options,
        )

    with pytest.raises(ToolError, match="Windows"):
        apply(platform="darwin")
    with pytest.raises(ToolError, match="Windows"):
        apply(repo_root=tmp_path)  # el repositorio: con la guía
    monkeypatch.delenv(launcher.SUPERVISOR_PID_ENV)
    with pytest.raises(ToolError, match="acceso directo"):
        apply()
    monkeypatch.setenv(launcher.SUPERVISOR_PID_ENV, "4242")
    # Lo confirmado era otra versión (salió una nueva con el aviso abierto): se vuelve a preguntar.
    with pytest.raises(ToolError, match="otra versión") as conflict:
        apply(expected="98.0.0")
    assert conflict.value.info.type == "conflict"
    route.mock(return_value=httpx.Response(200, json=_release(tag=f"v{VERSION}")))
    updates.reset_cache()
    with pytest.raises(ToolError, match="versión nueva"):
        apply()


# --- API ------------------------------------------------------------------------------------------


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app(), base_url=LOCAL) as client:
        yield client


def test_api_reports_the_version_and_only_the_ui_can_apply(client: TestClient) -> None:
    report = client.get("/updates")
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["current"] == VERSION and body["available"] is False and body["latest"] is None
    # Sin cuerpo JSON (un formulario de otra web, p. ej.), nada.
    assert client.post("/updates/apply").status_code == 403
    refused = client.post("/updates/apply", json={"version": NEWER})
    assert refused.status_code == 422 and refused.json()["error"]["type"] == "invalid_request"
    other_site = client.get("/updates", headers={"Origin": "https://ejemplo.com"})
    assert other_site.status_code == 403


# --- El script del actualizador -------------------------------------------------------------------


def _powershell() -> str:
    found = shutil.which("powershell")
    if found is None:
        pytest.skip("sin PowerShell")
    return found


@pytest.mark.skipif(sys.platform != "win32", reason="el actualizador es para Windows")
def test_updater_waits_for_programs_using_the_app_and_then_installs(tmp_path: Path) -> None:
    """Con algo abierto desde la carpeta de la app (como el servidor MCP de un agente), espera a
    que se cierre; después ejecuta el instalador con la carpeta de instalación."""
    powershell = _powershell()
    install_dir = tmp_path / "CandidatAI"
    app = install_dir / "app"
    app.mkdir(parents=True)
    busy_exe = app / "ocupado.exe"
    shutil.copyfile(Path(shutil.which("cmd") or "cmd.exe"), busy_exe)
    marker = tmp_path / "instalado.txt"
    installer = tmp_path / "install.ps1"
    installer.write_text(
        "param([string]$InstallDir, [string]$Lang, [switch]$NoLaunch)\n"
        f"Set-Content -LiteralPath '{marker}' -Value \"$InstallDir|$Lang|$NoLaunch\"\n",
        encoding="utf-8",
    )
    busy = subprocess.Popen(  # noqa: S603 - unos segundos ocupando la carpeta
        [str(busy_exe), "/c", "ping", "-n", "4", "127.0.0.1"], stdout=subprocess.DEVNULL
    )
    try:
        result = subprocess.run(  # noqa: S603
            [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(updates.UPDATER),
             "-InstallDir", str(install_dir), "-Installer", str(installer), "-NoRestart"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )  # fmt: skip
        assert result.returncode == 0, result.stdout + result.stderr
        assert busy.poll() is not None  # no instaló hasta que se cerró
        assert "ocupado" in result.stdout
        # En el idioma de la app y sin abrirla: la abre el actualizador al terminar.
        assert marker.read_text(encoding="utf-8").strip() == f"{install_dir}|es|True"
    finally:
        busy.kill()


@pytest.mark.skipif(sys.platform != "win32", reason="el actualizador es para Windows")
def test_updater_reports_a_failed_installation(tmp_path: Path) -> None:
    powershell = _powershell()
    installer = tmp_path / "install.ps1"
    installer.write_text('throw "sin red"\n', encoding="utf-8")
    result = subprocess.run(  # noqa: S603
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(updates.UPDATER),
         "-InstallDir", str(tmp_path / "CandidatAI"), "-Installer", str(installer), "-NoRestart"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )  # fmt: skip
    assert result.returncode == 1
    assert "sin red" in result.stdout


def test_updater_script_is_saved_with_bom() -> None:
    """PowerShell 5.1 lee como ANSI un `.ps1` sin BOM: las tildes y «» saldrían rotas."""
    assert updates.UPDATER.read_bytes().startswith(b"\xef\xbb\xbf")
