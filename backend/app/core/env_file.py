"""Contraseñas de los buzones en `.env` (fase 27.4, ADR-045).

Solo se tocan las líneas de las variables que se piden; el resto del fichero queda igual. Se
escribe de forma atómica (fichero temporal en la misma carpeta y `os.replace`) y, en macOS y
Linux, con permisos 600. Los valores nunca se registran en logs.

`CAI_ENV_FILE` cambia el fichero (los tests lo llevan a una carpeta temporal).
"""

import contextlib
import os
import re
import sys
import tempfile
import threading
from pathlib import Path

from dotenv import dotenv_values

from app.core.config import REPO_ROOT, get_settings

_NAME = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
# Solo estos parten una línea de `.env` (`str.splitlines` partiría también por `\x85`,
# `\u2028`…, que pueden ir dentro de un valor).
_LINE_BREAK = re.compile(r"\r\n|\n|\r")
_LOCK = threading.Lock()  # dos altas a la vez no pierden una línea


class SecretNotWritableError(Exception):
    """La app no puede guardar la contraseña (Docker): hay que añadir la línea a mano."""

    def __init__(self, name: str) -> None:
        super().__init__(
            f"En Docker la app no puede guardar contraseñas: añade a tu .env la línea "
            f"`{name}=…` con la contraseña y recrea el contenedor (`docker compose up -d`)."
        )
        self.name = name


def env_path() -> Path:
    return Path(os.environ.get("CAI_ENV_FILE") or REPO_ROOT / ".env")


def can_write() -> bool:
    """En Docker, `.env` entra como variables y no como fichero: escribirlo no serviría."""
    return not get_settings().in_docker


def read_secret(name: str) -> str | None:
    """El valor de la variable: el del entorno manda (como en `Settings`); si no, el de `.env`,
    leído en el momento para ver lo que se acaba de guardar desde la UI."""
    if name in os.environ:
        return os.environ[name] or None
    path = env_path()
    if not path.is_file():
        return None
    return dotenv_values(path, interpolate=False).get(name) or None


def _quoted(value: str) -> str:
    # Entre comillas simples: python-dotenv no expande `${…}` y solo interpreta `\\` y `\'`.
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _line_of(name: str) -> re.Pattern[str]:
    return re.compile(rf"^\s*(?:export\s+)?{re.escape(name)}\s*=")


def write_secret(name: str, value: str | None) -> None:
    """Pone (o quita, con `None`) la línea `name=…` de `.env`."""
    if not _NAME.match(name):
        raise ValueError(f"Nombre de variable no válido: {name}.")
    if not can_write():
        raise SecretNotWritableError(name)
    with _LOCK:
        _write(name, value)


def is_defined(name: str) -> bool:
    """Si la variable ya existe (en el entorno o en `.env`), aunque no sea de ningún buzón."""
    path = env_path()
    return name in os.environ or (path.is_file() and name in dotenv_values(path))


def _write(name: str, value: str | None) -> None:
    path = env_path()
    text = ""
    if path.is_file():
        with path.open(encoding="utf-8", newline="") as handle:  # conserva los CRLF
            text = handle.read()
    newline = "\r\n" if "\r\n" in text else "\n"
    pattern = _line_of(name)
    lines = [line for line in _LINE_BREAK.split(text) if not pattern.match(line)]
    while lines and lines[-1] == "":
        lines.pop()
    if value is not None:
        lines.append(f"{name}={_quoted(value)}")
    content = newline.join(lines) + (newline if lines else "")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".env.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if sys.platform != "win32":
            os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
    # Si la variable ya estaba en el entorno del proceso, mandaría sobre el fichero.
    if name in os.environ:
        if value is None:
            del os.environ[name]
        else:
            os.environ[name] = value
