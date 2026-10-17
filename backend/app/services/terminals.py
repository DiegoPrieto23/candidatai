"""Terminales de macOS y Linux para los botones «en tu agente» (fase 26.1, ADR-024 y ADR-040).

En Windows los abre `agent_launch` como siempre (Windows Terminal o PowerShell). Aquí:

- **macOS:** Terminal.app con `osascript`; iTerm2 si `CAI_TERMINAL=iterm` y está instalado.
- **Linux:** `CAI_TERMINAL`, `$TERMINAL` o la primera que haya de `CANDIDATES`, cada una con su
  forma de pasar la orden. Sin entorno gráfico (`DISPLAY`, `WAYLAND_DISPLAY`) no hay ninguna.
- La orden va en bash o zsh (`$SHELL` si es uno de los dos; si no, bash), con cada parte en
  `shlex.quote`: entra al repositorio, quita las variables de `unset_env`, pone las de `env`,
  ejecuta el agente y deja abierto el shell al terminar, como `-NoExit` en PowerShell.

Si no hay terminal, `find` devuelve el motivo y la UI copia la orden para que la pegues tú.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings

# Linux, en este orden si no se elige ninguna. `x-terminal-emulator` es la de Debian y Ubuntu.
CANDIDATES = (
    "x-terminal-emulator",
    "gnome-terminal",
    "konsole",
    "xfce4-terminal",
    "kitty",
    "wezterm",
    "alacritty",
)
MACOS_TERMINAL = "terminal"
ITERM = "iterm"
ITERM_APPS = (Path("/Applications/iTerm.app"), Path.home() / "Applications" / "iTerm.app")
STARTUP_SECONDS = 1.0  # si la terminal sale antes y con error, no se ha abierto
ENV_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
SHELLS = ("bash", "zsh")

NO_DISPLAY = (
    "No hay entorno gráfico (ni DISPLAY ni WAYLAND_DISPLAY) donde abrir una terminal: copia la "
    "orden y pégala en tu agente."
)
NOT_FOUND = (
    "No encuentro ninguna terminal ({names}). Instala una o elige la tuya con CAI_TERMINAL en "
    ".env; mientras, copia la orden y pégala en tu agente."
)
CHOSEN_NOT_FOUND = (
    "No encuentro la terminal de CAI_TERMINAL ({name}). Corrígela en .env; mientras, copia la "
    "orden y pégala en tu agente."
)


@dataclass(frozen=True)
class Terminal:
    """Una terminal encontrada: `name` decide cómo se le pasa la orden; `exe`, qué se lanza."""

    name: str
    exe: str

    def argv(self, title: str, cwd: Path, script: str, shell: str) -> list[str]:
        """Lo que se lanza para abrir una ventana que ejecute `script` con `shell`."""
        if self.name == MACOS_TERMINAL:
            return _terminal_app(self.exe, title, shlex.join([shell, "-c", script]))
        if self.name == ITERM:
            return _iterm(self.exe, shlex.join([shell, "-c", script]))
        inner = [shell, "-c", script]
        folder = str(cwd)
        match _style(self.name):
            case "gnome-terminal":  # sin título: `--title` no está en todas las versiones
                return [self.exe, "--working-directory", folder, "--", *inner]
            case "konsole":
                return [self.exe, "--workdir", folder, "-e", *inner]
            case "xfce4-terminal":  # `-e` lleva una sola cadena; `-x`, el resto como argumentos
                return [self.exe, "--title", title, "--working-directory", folder, "-x", *inner]
            case "kitty":
                return [self.exe, "--title", title, "--directory", folder, *inner]
            case "wezterm":
                return [self.exe, "start", "--cwd", folder, "--", *inner]
            case "alacritty":
                return [self.exe, "--title", title, "--working-directory", folder, "-e", *inner]
            case _:  # x-terminal-emulator, xterm y la mayoría: `-e programa argumentos…`
                return [self.exe, "-e", *inner]


def _style(name: str) -> str:
    """El nombre conocido de una terminal a partir de su programa (`/usr/bin/kitty` → `kitty`)."""
    base = Path(name).name.lower()
    return next((known for known in CANDIDATES if base == known), base)


def _applescript(value: str) -> str:
    """Literal de AppleScript entre comillas dobles."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _terminal_app(osascript: str, title: str, command: str) -> list[str]:
    return [
        osascript,
        "-e",
        f'tell application "Terminal" to set t to do script {_applescript(command)}',
        "-e",
        f'tell application "Terminal" to set custom title of t to {_applescript(title)}',
        "-e",
        'tell application "Terminal" to activate',
    ]


def _iterm(osascript: str, command: str) -> list[str]:
    return [
        osascript,
        "-e",
        'tell application "iTerm"',
        "-e",
        "activate",
        "-e",
        "set w to (create window with default profile)",
        "-e",
        f"tell current session of w to write text {_applescript(command)}",
        "-e",
        "end tell",
    ]


def shell() -> str:
    """bash o zsh: el de `$SHELL` si es uno de los dos; si no, bash (o `sh` si no hay bash). En
    macOS la línea `shell -c '…'` se escribe en el shell de inicio de Terminal o iTerm2, sea cual
    sea: solo lleva comillas simples, que entienden también fish y csh."""
    current = os.environ.get("SHELL", "")
    if Path(current).name in SHELLS and Path(current).is_file():
        return current
    return shutil.which("bash") or "/bin/sh"


def posix_script(
    parts: Sequence[str],
    *,
    unset_env: Sequence[str],
    env: Mapping[str, str],
    cwd: Path,
    shell_path: str,
) -> str:
    """La orden de la ventana, en una línea: entrar en `cwd`, quitar `unset_env`, poner `env`,
    ejecutar `parts` y quedarse en el shell al terminar."""
    names = [*unset_env, *env]
    if bad := [name for name in names if not ENV_NAME_RE.fullmatch(name)]:
        raise ValueError(f"Nombre de variable de entorno no válido: {bad[0]!r}")
    steps = [f"cd {shlex.quote(cwd.as_posix())} || exit 1"]
    steps += [f"unset {name}" for name in unset_env]
    steps += [f"export {name}={shlex.quote(value)}" for name, value in env.items()]
    steps.append(shlex.join(parts))
    steps.append(f"exec {shlex.quote(shell_path)}")
    return "; ".join(steps)


def _which(name: str) -> str | None:
    """Un programa del `PATH` o una ruta a un ejecutable."""
    if os.sep in name or "/" in name:
        path = Path(name).expanduser()
        return str(path) if path.is_file() and os.access(path, os.X_OK) else None
    return shutil.which(name)


def _macos(chosen: str | None) -> Terminal | str:
    osascript = shutil.which("osascript")
    if osascript is None:
        return NOT_FOUND.format(names="osascript")
    if chosen is not None and chosen.lower() in (ITERM, "iterm2"):
        if not any(app.is_dir() for app in ITERM_APPS):
            return CHOSEN_NOT_FOUND.format(name=chosen)
        return Terminal(ITERM, osascript)
    if chosen is not None and chosen.lower() not in (MACOS_TERMINAL, "terminal.app"):
        return CHOSEN_NOT_FOUND.format(name=chosen)
    return Terminal(MACOS_TERMINAL, osascript)


def _realpath(path: str) -> str:
    return os.path.realpath(path)  # aparte para poder sustituirlo en los tests


def _linux(chosen: str | None) -> Terminal | str:
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return NO_DISPLAY
    if chosen is not None:
        exe = _which(chosen)
        return Terminal(chosen, exe) if exe else CHOSEN_NOT_FOUND.format(name=chosen)
    preferred = os.environ.get("TERMINAL", "").strip()
    for name in [preferred, *CANDIDATES] if preferred else CANDIDATES:
        if exe := _which(name):
            # `x-terminal-emulator` es un enlace: si apunta a una conocida, se usa su forma.
            target = Path(_realpath(exe)).name
            return Terminal(target if target in CANDIDATES else name, exe)
    return NOT_FOUND.format(names=", ".join(CANDIDATES))


def find() -> Terminal | str:
    """La terminal que se abriría (macOS y Linux), o el motivo por el que no hay ninguna."""
    chosen = (get_settings().terminal or "").strip() or None
    if sys.platform == "darwin":
        return _macos(chosen)
    if sys.platform == "win32":
        return "En Windows la terminal la abre agent_launch."
    return _linux(chosen)


def reap(proc: "subprocess.Popen[bytes]") -> None:
    """Recoge el proceso cuando termine, para que no quede como zombi mientras viva la app."""
    threading.Thread(target=proc.wait, daemon=True, name="reap").start()


def open_terminal(terminal: Terminal, title: str, cwd: Path, script: str) -> None:
    """Abre una ventana con `script`. Lanza `OSError` si la terminal no arranca."""
    argv = terminal.argv(title, cwd, script, shell())
    proc = subprocess.Popen(  # noqa: S603 - argumentos construidos aquí, sin shell
        argv,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # la ventana sigue aunque se cierre CandidatAI
    )
    try:
        code = proc.wait(timeout=STARTUP_SECONDS)
    except subprocess.TimeoutExpired:
        reap(proc)  # sigue abierta
        return
    if code != 0:
        raise OSError(f"{terminal.name} terminó con el código {code}")
