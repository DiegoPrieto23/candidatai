"""Fase 26.1: la app en macOS y Linux. Terminales de los botones «en tu agente», entrecomillado,
LibreOffice, carpeta de datos de la app instalada, `cai start` y procesos en segundo plano.

Casi todo simula el sistema (`sys.platform`, `shutil.which`, el entorno). Lo que necesita un shell
o procesos de verdad solo corre en macOS y Linux."""

import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app.cli import app as cli_app
from app.core.config import get_settings, installed_data_dir
from app.services import agent_runner, launcher, terminals
from app.services.documents import pdf

posix_only = pytest.mark.skipif(sys.platform == "win32", reason="necesita macOS o Linux")
WEIRD = "Usa 'esto'; y \"aquello\" $HOME `id` \\ ñandú & | > *"


@pytest.fixture
def linux(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Linux con pantalla y sin terminal elegida; `which` encuentra lo que haya en el dict."""
    found: dict[str, str] = {}
    monkeypatch.setattr(terminals.sys, "platform", "linux")
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.delenv("TERMINAL", raising=False)
    monkeypatch.delenv("CAI_TERMINAL", raising=False)
    get_settings.cache_clear()
    monkeypatch.setattr(terminals.shutil, "which", found.get)
    monkeypatch.setattr(terminals, "_realpath", lambda path: path)
    return found


# --- Qué terminal se elige ---------------------------------------------------------------------


def test_linux_picks_the_first_known_terminal(linux: dict[str, str]) -> None:
    linux.update({"kitty": "/usr/bin/kitty", "konsole": "/usr/bin/konsole"})
    assert terminals.find() == terminals.Terminal("konsole", "/usr/bin/konsole")


def test_linux_without_any_terminal_or_display(
    linux: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    found = terminals.find()
    assert isinstance(found, str) and "CAI_TERMINAL" in found
    linux["kitty"] = "/usr/bin/kitty"
    monkeypatch.delenv("DISPLAY")
    assert terminals.find() == terminals.NO_DISPLAY
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
    assert terminals.find() == terminals.Terminal("kitty", "/usr/bin/kitty")


def test_terminal_variable_and_cai_terminal_take_precedence(
    linux: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    linux.update({"gnome-terminal": "/usr/bin/gnome-terminal", "wezterm": "/usr/bin/wezterm"})
    monkeypatch.setenv("TERMINAL", "wezterm")
    assert terminals.find() == terminals.Terminal("wezterm", "/usr/bin/wezterm")
    monkeypatch.setenv("CAI_TERMINAL", "alacritty")
    get_settings.cache_clear()
    found = terminals.find()  # elegida y no está: se dice, no se cambia por otra
    assert isinstance(found, str) and "alacritty" in found
    linux["alacritty"] = "/opt/bin/alacritty"
    assert terminals.find() == terminals.Terminal("alacritty", "/opt/bin/alacritty")


def test_x_terminal_emulator_uses_the_form_of_its_target(
    linux: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    linux["x-terminal-emulator"] = "/usr/bin/x-terminal-emulator"
    monkeypatch.setattr(terminals, "_realpath", lambda path: "/usr/bin/xfce4-terminal")
    found = terminals.find()
    assert found == terminals.Terminal("xfce4-terminal", "/usr/bin/x-terminal-emulator")


def test_macos_uses_terminal_app_or_iterm(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(terminals.sys, "platform", "darwin")
    monkeypatch.setattr(terminals.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.delenv("CAI_TERMINAL", raising=False)
    get_settings.cache_clear()
    assert terminals.find() == terminals.Terminal("terminal", "/usr/bin/osascript")
    monkeypatch.setenv("CAI_TERMINAL", "iterm")
    get_settings.cache_clear()
    monkeypatch.setattr(terminals, "ITERM_APPS", (tmp_path / "iTerm.app",))
    found = terminals.find()
    assert isinstance(found, str) and "iterm" in found
    (tmp_path / "iTerm.app").mkdir()
    assert terminals.find() == terminals.Terminal("iterm", "/usr/bin/osascript")


# --- Cómo se le pasa la orden ------------------------------------------------------------------

CWD = Path("/home/ana/candidatai")
INNER = ["/bin/bash", "-c", "echo hola"]


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("gnome-terminal", ["--working-directory", str(CWD), "--", *INNER]),
        ("konsole", ["--workdir", str(CWD), "-e", *INNER]),
        ("xfce4-terminal", ["--title", "T", "--working-directory", str(CWD), "-x", *INNER]),
        ("kitty", ["--title", "T", "--directory", str(CWD), *INNER]),
        ("wezterm", ["start", "--cwd", str(CWD), "--", *INNER]),
        ("alacritty", ["--title", "T", "--working-directory", str(CWD), "-e", *INNER]),
        ("x-terminal-emulator", ["-e", *INNER]),
        ("/opt/xterm", ["-e", *INNER]),
    ],
)
def test_each_linux_terminal_gets_its_arguments(name: str, expected: list[str]) -> None:
    argv = terminals.Terminal(name, "/x").argv("T", CWD, "echo hola", "/bin/bash")
    assert argv == ["/x", *expected]


def test_applescript_is_escaped() -> None:
    argv = terminals.Terminal("terminal", "/usr/bin/osascript").argv(
        'Tí"tulo', CWD, 'echo "a\\b"', "/bin/zsh"
    )
    command = shlex.join(["/bin/zsh", "-c", 'echo "a\\b"'])
    escaped = command.replace("\\", "\\\\").replace('"', '\\"')
    assert argv[2] == f'tell application "Terminal" to set t to do script "{escaped}"'
    assert argv[4].endswith('to "Tí\\"tulo"')
    iterm = terminals.Terminal("iterm", "/usr/bin/osascript").argv("T", CWD, "x", "/bin/zsh")
    assert 'write text "/bin/zsh -c x"' in iterm[8]


def test_posix_script_quotes_everything() -> None:
    script = terminals.posix_script(
        ["claude", WEIRD],
        unset_env=["ANTHROPIC_API_KEY"],
        env={"CAI_CLIENT_NAME": "claude"},
        cwd=Path("/home/ana/mi repo"),
        shell_path="/bin/zsh",
    )
    assert script == (
        "cd '/home/ana/mi repo' || exit 1; unset ANTHROPIC_API_KEY; "
        f"export CAI_CLIENT_NAME=claude; claude {shlex.quote(WEIRD)}; exec /bin/zsh"
    )
    with pytest.raises(ValueError, match="no válido"):
        terminals.posix_script(
            ["x"], unset_env=["A; rm -rf ~"], env={}, cwd=CWD, shell_path="/bin/bash"
        )


def test_shell_is_bash_or_zsh(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    zsh = tmp_path / "zsh"
    zsh.write_text("", encoding="utf-8")
    monkeypatch.setenv("SHELL", str(zsh))
    assert terminals.shell() == str(zsh)
    monkeypatch.setenv("SHELL", "/usr/bin/fish")
    monkeypatch.setattr(terminals.shutil, "which", lambda name: "/usr/bin/bash")
    assert terminals.shell() == "/usr/bin/bash"


def test_open_terminal_fails_if_it_exits_with_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class Quick:
        def __init__(self, code: int) -> None:
            self.code = code

        def wait(self, timeout: float) -> int:
            return self.code

    terminal = terminals.Terminal("kitty", "/usr/bin/kitty")
    monkeypatch.setattr(terminals.subprocess, "Popen", lambda *a, **k: Quick(0))
    terminals.open_terminal(terminal, "T", CWD, "x")
    monkeypatch.setattr(terminals.subprocess, "Popen", lambda *a, **k: Quick(1))
    with pytest.raises(OSError, match="código 1"):
        terminals.open_terminal(terminal, "T", CWD, "x")


@posix_only
def test_posix_script_runs_in_a_real_shell(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Lo que llega al programa es exactamente lo que se quería, sin la clave y con el cliente."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secreta")
    printer = 'printf "%s|%s|%s|%s" "$1" "${ANTHROPIC_API_KEY-sin}" "$CAI_CLIENT_NAME" "$PWD"'
    script = terminals.posix_script(
        ["sh", "-c", printer, "sh", WEIRD],
        unset_env=["ANTHROPIC_API_KEY"],
        env={"CAI_CLIENT_NAME": "claude"},
        cwd=tmp_path,
        shell_path="true",
    )
    bash = shutil.which("bash") or "/bin/sh"
    out = subprocess.run([bash, "-c", script], capture_output=True, text=True, check=True).stdout
    assert out.split("|") == [WEIRD, "sin", "claude", str(tmp_path.resolve())]


# --- LibreOffice -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("platform", "typical"),
    [
        ("win32", pdf.WINDOWS_SOFFICE_PATHS[0]),
        ("darwin", pdf.MACOS_SOFFICE_PATHS[0]),
        ("linux", pdf.LINUX_SOFFICE_PATHS[0]),
    ],
)
def test_find_soffice_in_each_system(
    monkeypatch: pytest.MonkeyPatch, platform: str, typical: Path
) -> None:
    monkeypatch.setattr(pdf.sys, "platform", platform)
    monkeypatch.setattr(pdf.shutil, "which", lambda name: None)
    monkeypatch.setattr(Path, "is_file", lambda self: self == typical)
    assert pdf.find_soffice(None) == typical


def test_find_soffice_skips_snap_and_flatpak(monkeypatch: pytest.MonkeyPatch) -> None:
    """Su sandbox no ve el /tmp donde se convierte: mejor Chromium que un PDF que no sale."""
    monkeypatch.setattr(pdf.sys, "platform", "linux")
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    monkeypatch.setattr(pdf.shutil, "which", {"libreoffice": "/snap/bin/libreoffice"}.get)
    assert pdf.find_soffice(None) is None


def test_find_soffice_prefers_configured_then_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdf.sys, "platform", "linux")
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    monkeypatch.setattr(pdf.shutil, "which", {"libreoffice": "/usr/bin/libreoffice"}.get)
    assert pdf.find_soffice(None) == Path("/usr/bin/libreoffice")
    assert pdf.find_soffice(Path("/opt/lo/soffice")) == Path("/opt/lo/soffice")


# --- Carpeta de datos de la app instalada ------------------------------------------------------


def test_installed_data_dir_per_system(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    assert installed_data_dir("win32") == tmp_path / "Local" / "CandidatAI" / "data"
    assert installed_data_dir("darwin") == (
        tmp_path / "Library" / "Application Support" / "CandidatAI"
    )
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert installed_data_dir("linux") == tmp_path / ".local" / "share" / "candidatai"
    monkeypatch.setenv("XDG_DATA_HOME", "relativa")  # XDG: una ruta relativa no vale
    assert installed_data_dir("linux") == tmp_path / ".local" / "share" / "candidatai"
    xdg = tmp_path / "xdg"
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg))
    assert installed_data_dir("linux") == xdg / "candidatai"


def test_cai_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    result = CliRunner().invoke(cli_app, ["paths", "--json"])
    assert result.exit_code == 0, result.output
    found = json.loads(result.output)
    assert found["installed_data_dir"] == str(installed_data_dir())
    assert Path(found["data_dir"]) == get_settings().data_dir


# --- `cai start` -------------------------------------------------------------------------------


def test_start_children_get_their_own_group_outside_windows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    seen: list[dict[str, object]] = []
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *a, **k: seen.append(k))
    child = launcher.Child("api", ["x"], tmp_path)
    monkeypatch.setattr(launcher.sys, "platform", "linux")
    launcher._spawn(child, tmp_path / "logs")
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    launcher._spawn(launcher.Child("worker", ["x"], tmp_path), tmp_path / "logs")
    assert seen[0].get("start_new_session") is True
    assert "start_new_session" not in seen[1]
    assert child.log is not None
    child.log.close()


def test_stop_sends_sigterm_first_outside_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[int, int]] = []

    class Proc:
        pid = 4242
        returncode = None

        def poll(self) -> None:
            return None

        def wait(self, timeout: float) -> int:
            return 0

    monkeypatch.setattr(launcher.sys, "platform", "linux")
    monkeypatch.setattr(
        launcher.os, "killpg", lambda pid, sig: sent.append((pid, sig)), raising=False
    )
    killed: list[object] = []
    monkeypatch.setattr(launcher, "_kill_tree", killed.append)
    launch = launcher.Launch(url="u", children=[launcher.Child("worker", ["x"], Path())])
    launch.children[0].process = Proc()  # type: ignore[assignment]
    launcher.stop(launch, grace=0.1)
    assert sent == [(4242, signal.SIGTERM), (4242, launcher.SIGKILL)]
    assert killed == [launch.children[0].process]


@posix_only
def test_sigterm_stops_like_ctrl_c_and_a_second_signal_does_not_cut_the_cleanup() -> None:
    before = signal.getsignal(signal.SIGTERM)
    cleaned = False
    with pytest.raises(KeyboardInterrupt), launcher.stop_on_signals():
        try:
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(1)
        finally:
            os.kill(os.getpid(), signal.SIGHUP)  # al cerrar la terminal llegan las dos
            time.sleep(0.2)
            cleaned = True
    assert cleaned
    assert signal.getsignal(signal.SIGTERM) == before


# --- Procesos en segundo plano (en el sistema real) --------------------------------------------


@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (["/usr/local/bin/claude", "-p", "x"], True),
        (["node", "/usr/lib/node_modules/@openai/codex/bin/codex.js"], True),
        (["vim", "claude.md"], False),  # un pid reutilizado por otro programa
        (["node", "server.js", "claude"], False),
        ([], False),
    ],
)
def test_alive_as_checks_the_program_not_any_argument(
    monkeypatch: pytest.MonkeyPatch, args: list[str], expected: bool
) -> None:
    monkeypatch.setattr(agent_runner.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(agent_runner.os, "getpgid", lambda pid: pid, raising=False)
    monkeypatch.setattr(agent_runner, "_args_of", lambda pid: args)
    program = "codex" if "codex" in " ".join(args) else "claude"
    assert agent_runner._alive_as_posix(4242, program) is expected


def test_alive_as_ignores_a_process_that_is_not_its_group_leader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(agent_runner.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(agent_runner.os, "getpgid", lambda pid: 1, raising=False)
    monkeypatch.setattr(agent_runner, "_args_of", lambda pid: ["claude"])
    assert agent_runner._alive_as_posix(4242, "claude") is False


@posix_only
def test_alive_as_and_kill_tree_on_posix(tmp_path: Path) -> None:
    """Un `sleep` en su grupo (como `_popen`) con un hijo: es «sleep», no «claude», y al parar el
    grupo no queda ninguno."""
    child_pid = tmp_path / "child.pid"
    script = f"sleep 60 & echo $! > {shlex.quote(str(child_pid))}; exec sleep 60"
    proc = subprocess.Popen(["/bin/sh", "-c", script], start_new_session=True)
    try:
        for _ in range(50):
            if child_pid.is_file() and child_pid.read_text().strip():
                break
            time.sleep(0.05)
        child = int(child_pid.read_text())
        time.sleep(0.2)  # a que el `exec` cambie el programa
        assert agent_runner._alive_as(proc.pid, "sleep")
        assert not agent_runner._alive_as(proc.pid, "claude")
        assert not agent_runner._alive_as(child, "sleep")  # no es jefe de su grupo
        agent_runner._kill_pid_tree(proc.pid)
        proc.wait(timeout=10)
        for _ in range(50):
            try:
                os.kill(child, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            pytest.fail("el hijo sigue vivo")
        assert not agent_runner._alive_as(proc.pid, "sleep")
    finally:
        if proc.poll() is None:
            proc.kill()
