"""Parar un proceso con todo lo que haya lanzado. Solo biblioteca estándar: lo usa el supervisor
de `cai start`, que no debe cargar el resto de la app."""

import logging
import os
import signal
import subprocess
import sys
from collections.abc import Callable

logger = logging.getLogger(__name__)


def kill_pid_tree(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(  # noqa: S603
            ["taskkill", "/PID", str(pid), "/T", "/F"],  # noqa: S607
            capture_output=True,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        os.killpg(pid, signal.SIGKILL)


def kill_tree(proc: "subprocess.Popen[str]", kill: Callable[[int], None] = kill_pid_tree) -> None:
    """Para el proceso y sus descendientes (en Windows, `taskkill /T`; fuera, su grupo)."""
    if proc.poll() is not None:
        return
    try:
        kill(proc.pid)
    except OSError:
        logger.warning("No se pudo parar el árbol de procesos %s", proc.pid, exc_info=True)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
