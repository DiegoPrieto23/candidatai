"""Fase 23.4: la API sirve la UI compilada, `require_ui` acepta su mismo origen local y `cai start`
arranca y para sus procesos."""

import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.api.ui import UI_ROUTES
from app.core import migrations
from app.core.config import REPO_ROOT, get_settings
from app.services import launcher

APP_TSX = REPO_ROOT / "frontend" / "src" / "App.tsx"


@pytest.fixture
def ui_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    folder = tmp_path / "dist"
    (folder / "assets").mkdir(parents=True)
    (folder / "index.html").write_text("<!doctype html><title>CandidatAI</title>", encoding="utf-8")
    (folder / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (folder / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    monkeypatch.setenv("CAI_UI_DIR", str(folder))
    get_settings.cache_clear()
    return folder


@pytest.fixture
def client(ui_dir: Path) -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app(), base_url="http://127.0.0.1:8000") as client:
        yield client


HTML = {"Accept": "text/html,application/xhtml+xml"}


# --- La API sirve la UI ------------------------------------------------------------------------


def test_ui_pages_get_index_and_the_api_still_answers(client: TestClient) -> None:
    for path in ("/", "/bandeja", "/jobs/7", "/fuentes/plataformas", "/por-revisar?x=1"):
        page = client.get(path, headers=HTML)
        assert page.status_code == 200 and "<title>CandidatAI" in page.text, path
        assert page.headers["cache-control"] == "no-cache"
    # La misma ruta pedida por la UI con fetch es la API.
    api = client.get("/jobs/7", headers={"Accept": "application/json"})
    assert api.status_code == 404 and api.json()["error"]["type"] == "not_found"
    assert client.get("/status", headers=HTML).json()["total"] == 0
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/favicon.svg").text == "<svg/>"
    # Un fichero suelto no admite elegir otro por parámetro.
    assert client.get("/favicon.svg", params={"file": str(Path(__file__))}).text == "<svg/>"


def test_without_a_built_ui_nothing_is_served(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAI_UI_DIR", str(tmp_path / "no-existe"))
    get_settings.cache_clear()
    migrations.upgrade()
    with TestClient(create_app()) as client:
        assert client.get("/", headers=HTML).status_code == 404
        assert client.get("/status").status_code == 200


def test_every_ui_route_is_known_to_the_api() -> None:
    """Las rutas de `App.tsx` llegan a `index.html` al recargar la página."""
    paths = re.findall(r'path="([^"]+)"', APP_TSX.read_text(encoding="utf-8"))
    assert paths
    for path in paths:
        if path == "*":
            continue
        url = "/" + path.replace(":id", "7")
        nested = "/fuentes" + url
        assert UI_ROUTES.match(url) or UI_ROUTES.match(nested), path


# --- require_ui: también el mismo origen, solo en local ---------------------------------------


@pytest.mark.parametrize(
    ("base", "origin", "allowed"),
    [
        ("http://127.0.0.1:8000", UI_ORIGIN, True),
        ("http://127.0.0.1:8000", "http://127.0.0.1:8000", True),
        ("http://localhost:8123", "http://localhost:8123", True),
        ("http://127.0.0.1:8000", "http://127.0.0.1:9999", False),
        ("http://127.0.0.1:8000", "https://evil.example", False),
        # DNS rebinding: una web que apunta su dominio a 127.0.0.1 es «su mismo origen».
        ("http://evil.example:8000", "http://evil.example:8000", False),
    ],
)
def test_require_ui_accepts_the_same_local_origin(
    ui_dir: Path, base: str, origin: str, allowed: bool
) -> None:
    migrations.upgrade()
    with TestClient(create_app(), base_url=base) as client:
        response = client.post(
            "/agent/requests/999/cancel",
            json={},
            headers={"Origin": origin, "Content-Type": "application/json"},
        )
    if allowed:
        assert response.status_code not in (400, 403), response.text
    else:
        # 403 por `require_ui`; 400 si ni siquiera es un host local (`TrustedHostMiddleware`).
        assert response.status_code in (400, 403)


def test_reads_from_another_host_are_refused(ui_dir: Path) -> None:
    """DNS rebinding también en las lecturas: con otro `Host`, ni el perfil ni la UI."""
    migrations.upgrade()
    with TestClient(create_app(), base_url="http://evil.example:8000") as client:
        assert client.get("/status").status_code == 400
        assert client.get("/", headers=HTML).status_code == 400
    with TestClient(create_app(), base_url="http://localhost:8000") as client:
        assert client.get("/status").status_code == 200


# --- cai start ---------------------------------------------------------------------------------


@respx.mock
def test_probe_tells_ours_from_others() -> None:
    url = "http://127.0.0.1:8000/status"
    busy = lambda _port: False  # noqa: E731
    respx.get(url).mock(return_value=httpx.Response(200, json={"total": 0, "by_stage": {}}))
    assert launcher.probe(8000, is_free=busy) == "candidatai"
    respx.get(url).mock(return_value=httpx.Response(200, text="<html>otra cosa</html>"))
    assert launcher.probe(8000, is_free=busy) == "other"
    respx.get(url).mock(side_effect=httpx.ConnectTimeout("no responde"))
    assert launcher.probe(8000, is_free=busy) == "other"
    assert launcher.probe(8000, is_free=lambda _port: True) == "free"


def test_port_free_detects_a_listening_socket() -> None:
    import socket

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        port = sock.getsockname()[1]
        assert launcher.port_free(port) is False
    assert launcher.port_free(port) is True


def test_plan_needs_the_built_ui(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAI_UI_DIR", str(tmp_path / "no-existe"))
    get_settings.cache_clear()
    with pytest.raises(launcher.LaunchError, match="pnpm build"):
        launcher.plan(get_settings(), 8000)


def test_plan_runs_api_and_worker_with_the_same_python(ui_dir: Path) -> None:
    launch = launcher.plan(get_settings(), 8123)
    assert launch.url == "http://127.0.0.1:8123"
    assert [c.name for c in launch.children] == ["api", "worker"]
    assert launch.children[0].command == [sys.executable, "-m", "app", "serve", "--port", "8123"]
    assert launch.children[1].command == [sys.executable, "-m", "app", "worker"]


def _child(name: str, code: str, tmp_path: Path) -> launcher.Child:
    return launcher.Child(name, [sys.executable, "-c", code], tmp_path)


def test_when_one_child_ends_the_others_are_stopped(tmp_path: Path) -> None:
    launch = launcher.Launch(
        url="http://x",
        children=[
            _child("api", "import time; time.sleep(120)", tmp_path),
            _child("worker", "import sys; sys.exit(3)", tmp_path),
        ],
    )
    for child in launch.children:
        launcher._spawn(child, tmp_path / "logs")
    try:
        assert launcher.supervise(launch, sleep=lambda _s: None) == "worker"
    finally:
        launcher.stop(launch)
    api = launch.children[0].process
    assert api is not None and api.poll() is not None  # parado, sin huérfanos
    assert (tmp_path / "logs" / "start-api.log").exists()


def test_wait_ready_fails_with_the_name_of_the_child_that_died(tmp_path: Path) -> None:
    launch = launcher.Launch(
        url="http://x", children=[_child("api", "import sys; sys.exit(1)", tmp_path)]
    )
    launcher._spawn(launch.children[0], tmp_path / "logs")
    launch.children[0].process.wait()  # type: ignore[union-attr]
    try:
        with pytest.raises(launcher.LaunchError, match="«api» se ha cerrado"):
            launcher.wait_ready("http://127.0.0.1:1", launch, timeout=5, sleep=lambda _s: None)
    finally:
        launcher.stop(launch)


def test_start_when_already_running_just_opens_the_browser(
    ui_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(launcher, "probe", lambda _port: "candidatai")
    opened: list[str] = []
    lines: list[str] = []
    launcher.start(get_settings(), 8000, say=lines.append, browser=opened.append)
    assert opened == ["http://127.0.0.1:8000"] and "ya está en marcha" in lines[0]


def test_start_refuses_a_port_used_by_something_else(
    ui_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(launcher, "probe", lambda _port: "other")
    with pytest.raises(launcher.LaunchError, match="otro programa"):
        launcher.start(get_settings(), 8000, say=lambda _s: None, browser=lambda _u: None)


# --- Instalador y releases ---------------------------------------------------------------------


@pytest.mark.skipif(sys.platform != "win32", reason="install.ps1 es para Windows")
def test_installer_whatif_changes_nothing(tmp_path: Path) -> None:
    import shutil
    import subprocess
    import zipfile

    powershell = shutil.which("powershell")
    if powershell is None:
        pytest.skip("sin PowerShell")
    release = tmp_path / "candidatai.zip"
    with zipfile.ZipFile(release, "w") as zf:
        zf.writestr("candidatai/backend/pyproject.toml", '[project]\nname = "candidatai"\n')
    target = tmp_path / "instalacion"
    for extra in ([], ["-Uninstall"]):
        result = subprocess.run(  # noqa: S603
            [
                powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(REPO_ROOT / "install.ps1"),
                "-WhatIf", "-Source", str(release), "-InstallDir", str(target), *extra,
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )  # fmt: skip
        assert result.returncode == 0, result.stdout + result.stderr
    assert not target.exists()  # -WhatIf no crea ni borra nada


def test_release_workflow_builds_the_ui_and_publishes_the_zip() -> None:
    import yaml

    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    )
    # PyYAML lee la clave `on` como el booleano True.
    trigger = workflow.get("on", workflow.get(True))
    assert trigger["push"] == {"tags": ["v*"]}
    # Fase 25.6: publicar, solo con la etiqueta. Fase 26.4: el disparo manual prueba las notas y
    # el zip, y lo deja como artefacto.
    assert set(trigger) == {"push", "workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    notes = " ".join(str(step.get("run", "")) for step in workflow["jobs"]["notes"]["steps"])
    assert "scripts/release_notes.py" in notes and "gh release" not in notes
    # El zip se hace y se comprueba sin permiso de escritura; publicar es otro job, solo con push.
    package = workflow["jobs"]["package"]
    assert package["needs"] == "notes" and "permissions" not in package and "if" not in package
    uploads = [str(step.get("uses", "")) for step in package["steps"]]
    assert any(use.startswith("actions/upload-artifact@") for use in uploads)
    release = workflow["jobs"]["release"]
    assert release["needs"] == "package" and release["if"] == "github.event_name == 'push'"
    assert release["permissions"] == {"contents": "write"}
    steps = " ".join(str(step.get("run", "")) for step in [*package["steps"], *release["steps"]])
    assert "pnpm build" in steps and "git archive" in steps
    assert "frontend/dist" in steps and "gh release create" in steps
    assert "--notes-file release-notes.md" in steps and "--generate-notes" not in steps
    # El zip lleva lo que el instalador espera.
    installer = (REPO_ROOT / "install.ps1").read_text(encoding="utf-8-sig")
    assert "releases/latest/download/candidatai.zip" in installer
    assert r"backend\pyproject.toml" in installer
    # Fase 26.2: también install.sh, con los iconos de sus accesos directos.
    assert "candidatai/install.sh" in steps and "candidatai.icns" in steps
    assert 'zipinfo candidatai.zip candidatai/install.sh | grep -q "^-rwx"' in steps
    # Fase 28.1: la suma se publica con el zip y los instaladores la comprueban.
    assert "sha256sum candidatai.zip > candidatai.zip.sha256" in steps
    assert 'gh release create "$GITHUB_REF_NAME" candidatai.zip candidatai.zip.sha256' in steps
    artifact = next(s for s in package["steps"] if "upload-artifact" in str(s.get("uses")))
    assert "candidatai.zip.sha256" in artifact["with"]["path"]
    assert "SHA256]::Create()" in installer and '"$Source.sha256"' in installer
    assert '"$SOURCE.sha256"' in (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
    unix = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
    assert "releases/latest/download/candidatai.zip" in unix
    assert "backend/pyproject.toml" in unix


@pytest.mark.skipif(sys.platform != "win32", reason="install.ps1 es para Windows")
def test_installer_accepts_a_local_checkout_with_the_built_ui(tmp_path: Path) -> None:
    import shutil
    import subprocess

    powershell = shutil.which("powershell")
    if powershell is None:
        pytest.skip("sin PowerShell")
    checkout = tmp_path / "repo"
    (checkout / "backend").mkdir(parents=True)
    (checkout / "backend" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

    def run() -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            [
                powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(REPO_ROOT / "install.ps1"), "-WhatIf",
                "-Source", str(checkout), "-InstallDir", str(tmp_path / "instalacion"),
            ],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )  # fmt: skip

    without_ui = run()
    assert without_ui.returncode != 0 and "pnpm build" in without_ui.stdout + without_ui.stderr
    (checkout / "frontend" / "dist").mkdir(parents=True)
    (checkout / "frontend" / "dist" / "index.html").write_text("<html></html>", encoding="utf-8")
    assert run().returncode == 0
    assert not (tmp_path / "instalacion").exists()


def _installer(*args: str) -> subprocess.CompletedProcess[str]:
    import shutil
    import subprocess

    powershell = shutil.which("powershell")
    if powershell is None:
        pytest.skip("sin PowerShell")
    return subprocess.run(  # noqa: S603
        [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(REPO_ROOT / "install.ps1"), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
    )  # fmt: skip


@pytest.mark.skipif(sys.platform != "win32", reason="install.ps1 es para Windows")
def test_installer_refuses_protected_folders() -> None:
    for folder in (str(Path.home()), Path.home().anchor):
        result = _installer("-WhatIf", "-InstallDir", folder)
        assert result.returncode != 0
        assert "puede ser" in result.stdout + result.stderr


@pytest.mark.skipif(sys.platform != "win32", reason="install.ps1 es para Windows")
def test_installer_never_replaces_a_folder_that_is_not_candidatai(tmp_path: Path) -> None:
    import zipfile

    release = tmp_path / "candidatai.zip"
    with zipfile.ZipFile(release, "w") as zf:
        zf.writestr("candidatai/backend/pyproject.toml", '[project]\nname = "candidatai"\n')
    target = tmp_path / "instalacion"
    (target / "app").mkdir(parents=True)
    (target / "app" / "mis-cosas.txt").write_text("no es CandidatAI", encoding="utf-8")
    for args in (("-Source", str(release), "-NoShortcuts"), ("-Uninstall",)):
        result = _installer("-InstallDir", str(target), *args)
        output = result.stdout + result.stderr
        assert result.returncode != 0
        # PowerShell escribe en la página de códigos de la consola: sin tildes en lo que se busca.
        assert "CandidatAI" in output and ("otra carpeta" in output or "no se borra" in output)
    assert (target / "app" / "mis-cosas.txt").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="install.ps1 es para Windows")
def test_installer_never_removes_data_of_a_folder_that_is_not_candidatai(tmp_path: Path) -> None:
    """Fase 26.2: -RemoveData solo borra `data` si la carpeta es de CandidatAI (marca o app)."""
    target = tmp_path / "trabajo"
    (target / "data").mkdir(parents=True)
    (target / "data" / "informe.txt").write_text("mío", encoding="utf-8")
    result = _installer("-InstallDir", str(target), "-Uninstall", "-RemoveData")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / "data" / "informe.txt").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="install.ps1 es para Windows")
def test_installer_checks_the_zip_against_its_sha256(tmp_path: Path) -> None:
    """Fase 28.1: con un `<zip>.sha256` al lado, una suma que no coincide no instala nada."""
    import hashlib
    import zipfile

    release = tmp_path / "candidatai.zip"
    with zipfile.ZipFile(release, "w") as zf:
        zf.writestr("candidatai/backend/pyproject.toml", '[project]\nname = "candidatai"\n')
    checksum = tmp_path / "candidatai.zip.sha256"
    checksum.write_text(f"{'0' * 64}  candidatai.zip\n", encoding="utf-8")
    target = tmp_path / "instalacion"
    result = _installer("-Source", str(release), "-InstallDir", str(target), "-NoShortcuts")
    assert result.returncode != 0 and "SHA-256" in result.stdout + result.stderr
    assert not target.exists()
    digest = hashlib.sha256(release.read_bytes()).hexdigest()
    checksum.write_text(f"{digest.upper()}  candidatai.zip\r\n", encoding="utf-8")
    result = _installer("-WhatIf", "-Source", str(release), "-InstallDir", str(target))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SHA-256 comprobada" in result.stdout
    assert not target.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="install.ps1 es para Windows")
def test_installer_downloads_its_sha256_unless_skipped() -> None:
    """Sin red: -WhatIf anuncia la comprobación al descargar, y -SkipChecksum la quita."""
    result = _installer("-WhatIf")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "suma SHA-256" in result.stdout
    result = _installer("-WhatIf", "-SkipChecksum")
    assert result.returncode == 0 and "-SkipChecksum" in result.stdout


def test_installers_prepare_your_database_even_with_the_demo_open() -> None:
    """Fase 28.1: un `CAI_DATA_DIR` de la terminal (la demo) no desvía `cai db upgrade`, y en
    Windows la variable vuelve a quedar como estaba."""
    windows = (REPO_ROOT / "install.ps1").read_text(encoding="utf-8-sig")
    unix = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
    names = ("CAI_DATA_DIR", "JH_DATA_DIR", "CAI_DB_URL", "JH_DB_URL")
    clear = windows.index('foreach ($name in "CAI_DATA_DIR"')
    assert all(f'"{name}"' in windows[clear : clear + 120] for name in names)
    assert (
        clear
        < windows.index("cai db upgrade")
        < windows.index("SetEnvironmentVariable($name, $saved")
    )
    assert unix.index("unset " + " ".join(names)) < unix.index("cai db upgrade </dev/null")


def test_ci_tests_the_three_systems_the_installer_and_docker() -> None:
    """Fase 26.4: backend en Windows y Linux en cada push, y macOS en `main`, etiquetas y a mano;
    install.sh en Linux (y macOS); la imagen de Docker en Linux."""
    import yaml

    text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load(text)
    trigger = workflow.get("on", workflow.get(True))
    assert set(trigger) == {"push", "pull_request", "workflow_dispatch"}
    jobs = workflow["jobs"]
    assert set(jobs) == {"backend", "installer", "docker", "frontend", "agents"}
    full = '["windows-latest", "ubuntu-latest", "macos-latest"]'
    backend = jobs["backend"]["strategy"]["matrix"]["os"]
    assert full in backend and '["windows-latest", "ubuntu-latest"]' in backend
    assert "refs/heads/main" in backend and "workflow_dispatch" in backend
    assert jobs["backend"]["strategy"]["fail-fast"] is False
    runs = " ".join(str(step.get("run", "")) for step in jobs["backend"]["steps"])
    assert "--cov-fail-under=85" in runs and "cai demo seed" in runs
    assert "playwright install --with-deps chromium" in runs
    uses = [step for step in jobs["backend"]["steps"] if "uses" in step]
    caches = [step for step in uses if step["uses"].startswith("actions/cache@")]
    assert caches and "playwright" in caches[0]["with"]["key"]
    installer = " ".join(str(step.get("run", "")) for step in jobs["installer"]["steps"])
    assert "shellcheck install.sh" in installer and "--dry-run" in installer
    assert "--uninstall" in installer and "--no-setup" in installer
    docker = " ".join(str(step.get("run", "")) for step in jobs["docker"]["steps"])
    assert "docker compose up -d" in docker and "/status" in docker and "cai demo seed" in docker
