"""Fase 26.2: `install.sh`, el instalador de macOS y Linux.

Los que lo ejecutan necesitan bash y un sistema Unix: con un `HOME` temporal, una release falsa y
`--no-setup` (sin uv sync), nunca tocan la instalación real. Los de la release y git corren en
todos los sistemas."""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from app.core.config import REPO_ROOT, install_dir, installed_data_dir

INSTALLER = REPO_ROOT / "install.sh"
unix_only = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("bash") is None, reason="necesita macOS o Linux"
)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Un `HOME` vacío, también para `Path.home()` de este proceso (el cálculo de config.py)."""
    folder = tmp_path / "home"
    folder.mkdir()
    monkeypatch.setenv("HOME", str(folder))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    return folder


@pytest.fixture
def release(tmp_path: Path) -> Path:
    zip_path = tmp_path / "candidatai.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("candidatai/backend/pyproject.toml", '[project]\nname = "candidatai"\n')
        zf.writestr("candidatai/frontend/public/candidatai.png", b"png")
    return zip_path


def install(*args: str) -> subprocess.CompletedProcess[str]:
    # Sin terminal (`start_new_session`): `--remove-data` no puede pedir confirmación.
    return subprocess.run(  # noqa: S603
        ["bash", str(INSTALLER), *args],  # noqa: S607
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        env={**os.environ},
        timeout=120,
        check=False,
    )


def files_under(folder: Path) -> list[Path]:
    return sorted(folder.rglob("*"))


@unix_only
def test_dry_run_changes_nothing_and_matches_the_app_paths(home: Path, release: Path) -> None:
    for extra in ([], ["--uninstall", "--remove-data"]):
        result = install("--dry-run", "--source", str(release), *extra)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "no se cambia nada" in result.stdout
    assert files_under(home) == []
    # Las rutas que anuncia son las de `cai paths` (config.install_dir).
    result = install("--dry-run", "--source", str(release))
    assert f"datos en {installed_data_dir()} " in result.stdout
    assert f"instalación en {install_dir()}\n" in result.stdout


@unix_only
def test_reinstall_keeps_data_and_env_and_creates_the_shortcut(home: Path, release: Path) -> None:
    first = install("--no-setup", "--source", str(release))
    assert first.returncode == 0, first.stdout + first.stderr
    app, data = install_dir() / "app", installed_data_dir()
    assert (app / "backend" / "pyproject.toml").is_file() and data.is_dir()
    (data / "profile.yaml").write_text("mío", encoding="utf-8")
    with (app / ".env").open("a", encoding="utf-8") as env:
        env.write("CAI_AGENT=opencode\nCAI_DATA_DIR=/otra\n")
    second = install("--no-setup", "--source", str(release))
    assert second.returncode == 0, second.stdout + second.stderr
    assert (data / "profile.yaml").read_text(encoding="utf-8") == "mío"
    env_lines = (app / ".env").read_text(encoding="utf-8").splitlines()
    assert "CAI_AGENT=opencode" in env_lines
    assert [line for line in env_lines if "DATA_DIR" in line] == [f'CAI_DATA_DIR="{data}"']
    assert not (install_dir() / "app.new").exists() and not (install_dir() / "app.old").exists()
    if sys.platform == "darwin":
        bundle = home / "Applications" / "CandidatAI.app" / "Contents"
        assert (bundle / "Info.plist").is_file()
        assert os.access(bundle / "MacOS" / "CandidatAI", os.X_OK)
        launcher = install_dir() / "CandidatAI.command"
    else:
        desktop = (home / ".local/share/applications/candidatai.desktop").read_text("utf-8")
        launcher = install_dir() / "candidatai-start"
        assert f'Exec="{launcher}"' in desktop and "Terminal=true" in desktop
        assert f"Icon={app}/frontend/public/candidatai.png" in desktop
    assert os.access(launcher, os.X_OK)
    assert "cai start" in launcher.read_text(encoding="utf-8")


@unix_only
def test_uninstall_keeps_data_without_confirmation(home: Path, release: Path) -> None:
    assert install("--no-setup", "--source", str(release)).returncode == 0
    (installed_data_dir() / "profile.yaml").write_text("mío", encoding="utf-8")
    result = install("--uninstall", "--remove-data")  # sin terminal: no puede confirmar
    assert result.returncode == 0, result.stdout + result.stderr
    assert "no se borran" in result.stdout
    assert (installed_data_dir() / "profile.yaml").is_file()
    assert not (install_dir() / "app").exists()
    assert not (home / ".local/share/applications/candidatai.desktop").exists()
    assert not (home / "Applications" / "CandidatAI.app").exists()


@unix_only
def test_refuses_protected_folders_and_foreign_apps(home: Path, release: Path) -> None:
    for folder in (str(home), "/", "~", str(home / ".local" / "share")):
        result = install("--dry-run", "--install-dir", folder)
        assert result.returncode != 0 and "no puede ser" in result.stderr, folder
    target = home / "instalacion"
    (target / "app").mkdir(parents=True)
    (target / "app" / "mis-cosas.txt").write_text("no es CandidatAI", encoding="utf-8")
    for args in (("--no-setup", "--source", str(release)), ("--uninstall",)):
        result = install("--install-dir", str(target), "--no-shortcuts", *args)
        assert result.returncode != 0 and "CandidatAI" in result.stderr
    assert (target / "app" / "mis-cosas.txt").is_file()


@unix_only
def test_never_touches_a_folder_that_is_not_candidatai(home: Path, release: Path) -> None:
    """Revisión de la 26.2: una carpeta propia del usuario con su `data/` no se borra ni se usa."""
    mine = home / "trabajo"
    (mine / "data").mkdir(parents=True)
    (mine / "data" / "informe.txt").write_text("mío", encoding="utf-8")
    result = install("--install-dir", str(mine), "--uninstall", "--remove-data")
    assert result.returncode != 0 and "no parece una instalación" in result.stderr
    result = install("--install-dir", str(mine), "--no-setup", "--source", str(release))
    assert result.returncode != 0 and "no es una instalación de CandidatAI" in result.stderr
    assert sorted(p.name for p in mine.rglob("*")) == ["data", "informe.txt"]


@unix_only
def test_paths_are_normalized_and_spaces_are_fine(home: Path, release: Path) -> None:
    for sneaky in (f"{home}/.", f"{home}/x/..", f"{home}//"):
        result = install("--dry-run", "--install-dir", sneaky)
        assert result.returncode != 0 and "no puede ser" in result.stderr, sneaky
    target = home / "Mis Apps" / "CandidatAI"
    result = install("--install-dir", str(target), "--no-setup", "--source", str(release))
    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / ".candidatai").is_file() and (target / "data").is_dir()
    launcher = target / ("CandidatAI.command" if sys.platform == "darwin" else "candidatai-start")
    syntax = subprocess.run(  # noqa: S603
        ["bash", "-n", str(launcher)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    assert syntax.returncode == 0, syntax.stderr
    result = install("--install-dir", str(target), "--uninstall")
    assert result.returncode == 0 and not (target / "app").exists() and (target / "data").is_dir()


@unix_only
def test_remove_data_needs_uninstall(home: Path) -> None:
    result = install("--dry-run", "--remove-data")
    assert result.returncode != 0 and "--uninstall" in result.stderr


def test_the_data_dir_in_env_survives_spaces(tmp_path: Path) -> None:
    """`install.sh` escribe `CAI_DATA_DIR` entre comillas: así se lee con los espacios de macOS."""
    from dotenv import dotenv_values

    env = tmp_path / ".env"
    folder = "/Users/ana/Library/Application Support/CandidatAI/data"
    env.write_text(f'CAI_AGENT=claude\nCAI_DATA_DIR="{folder}"\n', encoding="utf-8")
    assert dotenv_values(env)["CAI_DATA_DIR"] == folder
    assert "printf 'CAI_DATA_DIR=\"%s\"\\n'" in INSTALLER.read_text(encoding="utf-8")


@unix_only
def test_local_checkout_needs_the_built_ui(home: Path, tmp_path: Path) -> None:
    checkout = tmp_path / "repo"
    (checkout / "backend").mkdir(parents=True)
    (checkout / "backend" / "pyproject.toml").write_text(
        '[project]\nname = "candidatai"\n', encoding="utf-8"
    )
    (checkout / "data").mkdir()
    (checkout / "data" / "profile.yaml").write_text("del repo", encoding="utf-8")
    result = install("--no-setup", "--no-shortcuts", "--source", str(checkout))
    assert result.returncode != 0 and "pnpm build" in result.stderr
    (checkout / "frontend" / "dist").mkdir(parents=True)
    (checkout / "frontend" / "dist" / "index.html").write_text("<html>", encoding="utf-8")
    result = install("--no-setup", "--no-shortcuts", "--source", str(checkout))
    assert result.returncode == 0, result.stdout + result.stderr
    app = install_dir() / "app"
    assert (app / "frontend" / "dist" / "index.html").is_file()
    assert not (app / "data").exists()  # tus datos del repositorio no se copian


@unix_only
def test_shellcheck_is_clean() -> None:
    shellcheck = shutil.which("shellcheck")
    if shellcheck is None:
        pytest.skip("sin shellcheck (la CI lo instala)")
    result = subprocess.run(  # noqa: S603
        [shellcheck, str(INSTALLER)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout


# --- En todos los sistemas -----------------------------------------------------------------------


def test_installer_is_bash_with_lf_and_executable_in_git() -> None:
    raw = INSTALLER.read_bytes()
    assert raw.startswith(b"#!/usr/bin/env bash\n")
    assert b"\r\n" not in raw  # con CRLF, bash no lo ejecuta
    assert raw.rstrip().endswith(b'main "$@"')  # con `curl | bash`, nada se ejecuta a medias
    attributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "*.sh text eol=lf" in attributes
    git = shutil.which("git")
    if git is None:
        pytest.skip("sin git")
    staged = subprocess.run(  # noqa: S603
        [git, "ls-files", "-s", "install.sh"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    assert staged.startswith("100755"), staged


def test_icons_for_the_shortcuts_exist() -> None:
    public = REPO_ROOT / "frontend" / "public"
    assert (public / "candidatai.png").read_bytes().startswith(b"\x89PNG")
    assert (public / "candidatai.icns").read_bytes().startswith(b"icns")
