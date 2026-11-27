"""La ventana del agente, a mano (fase 48.1d): si sigue abierta y traerla delante.

Al abrirse, la ventana deja el PID de su shell en `data/tmp/windows/<token>.pid` (PowerShell en
Windows, bash o zsh en macOS y Linux). Con él:

- `alive`: si ese proceso sigue vivo. En Windows, además, que sea un PowerShell, para no confundirlo
  con otro programa que haya heredado el número.
- `show` (solo Windows): restaura y pone delante la consola de ese PowerShell. Windows reporta la
  ventana de una consola clásica con el PID del programa que corre en ella, así que se encuentra sin
  depender del título (el agente puede cambiarlo). Si Windows no deja ponerla delante, queda
  restaurada y parpadeando en la barra de tareas. Una pestaña de Windows Terminal es del proceso de
  Windows Terminal y no se puede traer así.

Solo lectura de procesos y ventanas del propio usuario: no se lanza ni se cierra nada.
"""

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings

SHELLS = frozenset({"powershell.exe", "pwsh.exe"})


def pid_dir() -> Path:
    return get_settings().data_dir / "tmp" / "windows"


def pid_file(token: str) -> Path:
    return pid_dir() / f"{token}.pid"


MAX_PID = 2**31 - 1
KEEP_PID_FILES = 7 * 24 * 3600  # una semana: los avisos de antes ya no se siguen


def read_pid(token: str) -> int | None:
    """El PID que dejó la ventana, si ya lo ha dejado. No se borra al leerlo: si no se llegara a
    guardar, se vuelve a leer en el siguiente sondeo (`clean_old` los quita)."""
    try:
        with pid_file(token).open("rb") as handle:
            raw = handle.read(32)
    except OSError:
        return None
    try:
        pid = int(raw.decode("utf-8-sig").strip())
    except (UnicodeDecodeError, ValueError):
        return None
    return pid if 0 < pid <= MAX_PID else None


def clean_old(now: float | None = None) -> None:
    """Quita los ficheros de PID de hace más de una semana."""
    limit = (now if now is not None else time.time()) - KEEP_PID_FILES
    try:
        files = list(pid_dir().glob("*.pid"))
    except OSError:
        return
    for path in files:
        try:
            if path.stat().st_mtime < limit:
                path.unlink(missing_ok=True)
        except OSError:
            continue


@dataclass(frozen=True)
class Shown:
    found: bool  # había una consola de ese proceso
    foreground: bool  # se ha puesto delante (si no, restaurada y parpadeando)


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _user32 = ctypes.WinDLL("user32", use_last_error=True)

    _PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _STILL_ACTIVE = 259
    _SW_RESTORE = 9
    _SW_SHOW = 5
    _FLASHW_ALL = 3
    _FLASHW_TIMERNOFG = 12
    _CONSOLE_CLASS = "ConsoleWindowClass"

    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    _kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    class _FlashInfo(ctypes.Structure):
        _fields_ = [  # noqa: RUF012 - así declara ctypes una estructura
            ("cbSize", wintypes.UINT),
            ("hwnd", wintypes.HWND),
            ("dwFlags", wintypes.DWORD),
            ("uCount", wintypes.UINT),
            ("dwTimeout", wintypes.DWORD),
        ]

    _EnumProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    _user32.EnumWindows.argtypes = [_EnumProc, wintypes.LPARAM]
    _user32.EnumWindows.restype = wintypes.BOOL
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetClassNameW.restype = ctypes.c_int
    _user32.IsIconic.argtypes = [wintypes.HWND]
    _user32.IsIconic.restype = wintypes.BOOL
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.ShowWindow.restype = wintypes.BOOL
    _user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    _user32.SetForegroundWindow.restype = wintypes.BOOL
    _user32.GetForegroundWindow.argtypes = []
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.FlashWindowEx.argtypes = [ctypes.POINTER(_FlashInfo)]
    _user32.FlashWindowEx.restype = wintypes.BOOL

    def alive(pid: int) -> bool:
        handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = wintypes.DWORD()
            if not _kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            if code.value != _STILL_ACTIVE:
                return False
            size = wintypes.DWORD(1024)
            buffer = ctypes.create_unicode_buffer(size.value)
            if not _kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return False
            return Path(buffer.value).name.lower() in SHELLS
        finally:
            _kernel32.CloseHandle(handle)

    def _console_of(pid: int) -> int | None:
        found: list[int] = []

        def check(hwnd: int | None, _: int) -> bool:
            owner = wintypes.DWORD()
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value != pid:
                return True
            name = ctypes.create_unicode_buffer(64)
            _user32.GetClassNameW(hwnd, name, 64)
            if name.value == _CONSOLE_CLASS and hwnd:
                found.append(hwnd)
                return False
            return True

        _user32.EnumWindows(_EnumProc(check), 0)
        return found[0] if found else None

    def show(pid: int) -> Shown:
        """`pid` ya comprobado con `alive`."""
        hwnd = _console_of(pid)
        if hwnd is None:
            return Shown(found=False, foreground=False)
        _user32.ShowWindow(hwnd, _SW_RESTORE if _user32.IsIconic(hwnd) else _SW_SHOW)
        _user32.SetForegroundWindow(hwnd)
        if (_user32.GetForegroundWindow() or 0) == hwnd:
            return Shown(found=True, foreground=True)
        flash = _FlashInfo(ctypes.sizeof(_FlashInfo), hwnd, _FLASHW_ALL | _FLASHW_TIMERNOFG, 0, 0)
        _user32.FlashWindowEx(ctypes.byref(flash))
        return Shown(found=True, foreground=False)

else:

    def alive(pid: int) -> bool:
        """Sin comprobar que sea un shell: en macOS y Linux, un PID reutilizado pronto puede hacer
        que una ventana cerrada parezca abierta (el aviso acaba como «sin noticias»)."""
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True  # existe, aunque sea de otro usuario
        except OSError:
            return False
        return True

    def show(pid: int) -> Shown:
        """macOS y Linux: la app no mueve ventanas de otros programas; el aviso dice su nombre."""
        return Shown(found=False, foreground=False)


def can_show() -> bool:
    return sys.platform == "win32"
