"""Secretos de la app: contraseñas de los buzones y claves de los portales (fase 41.5).

Se guardan en el almacén del sistema operativo con `keyring` (Administrador de credenciales en
Windows, Llavero en macOS y Secret Service en Linux). La base de datos y `.env` solo guardan una
referencia: el nombre del secreto (`CAI_IMAP_GMAIL_PASSWORD`, `CAI_ADZUNA_APP_KEY`…).

Al leer un secreto, por orden:
1. el entorno del proceso: una variable con su nombre o, en Docker, un secreto montado en
   `/run/secrets/<nombre>` (`CAI_SECRETS_DIR` cambia la carpeta);
2. el llavero del sistema;
3. `.env`, como se guardaban antes de esta fase (se ofrece moverlos al llavero).

Al guardar, va al llavero si lo hay (y se quita su línea de `.env`, si estaba). Donde no lo hay
(Linux sin sesión gráfica, o `CAI_SECRET_STORE=file`), a `.env`, y la UI lo marca como guardado en
un fichero. En Docker no se guarda: se configura como secreto o variable del contenedor.

Los valores nunca se registran en logs ni salen en una vista o un error.
"""

import contextlib
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import keyring
from dotenv import dotenv_values
from keyring.errors import PasswordDeleteError

from app.core import env_file
from app.core.config import ENV_PREFIX, LEGACY_ENV_PREFIX, get_settings

logger = logging.getLogger(__name__)

SERVICE = "CandidatAI"
Location = Literal["keyring", "file", "environment"]

# Los secretos que la app lee de su configuración (además de las contraseñas de los buzones, que
# nombra `MailSource.secret_ref`). La pareja no secreta (usuario, id de la app) sigue en `.env`.
IMAP_PASSWORD = "CAI_IMAP_PASSWORD"
ADZUNA_APP_KEY = "CAI_ADZUNA_APP_KEY"
INFOJOBS_CLIENT_SECRET = "CAI_INFOJOBS_CLIENT_SECRET"
SETTINGS_SECRETS = (IMAP_PASSWORD, ADZUNA_APP_KEY, INFOJOBS_CLIENT_SECRET)

SecretNotWritableError = env_file.SecretNotWritableError


def _aliases(name: str) -> list[str]:
    """`CAI_X` y su nombre de antes de la fase 23 (`JH_X`), que se sigue leyendo."""
    if name.startswith(ENV_PREFIX):
        return [name, LEGACY_ENV_PREFIX + name.removeprefix(ENV_PREFIX)]
    return [name]


# --- El llavero ----------------------------------------------------------------------------------


@lru_cache
def _backend() -> keyring.backend.KeyringBackend | None:
    """El llavero, si lo hay y responde. Se prueba una vez por proceso."""
    mode = (os.environ.get("CAI_SECRET_STORE") or "auto").strip().lower()
    if mode == "file" or get_settings().in_docker:
        return None
    backend = keyring.get_keyring()
    # `fail.Keyring` (ninguno disponible) y `null.Keyring` tienen prioridad 0 o menos.
    if backend.priority <= 0:  # type: ignore[operator]
        return None
    try:
        backend.get_password(SERVICE, "__probe__")
    except Exception as exc:  # noqa: BLE001 - Secret Service sin D-Bus, llavero bloqueado…
        logger.info("Sin llavero del sistema (%s): se usará un fichero.", type(exc).__name__)
        return None
    return backend


def reset() -> None:
    """Vuelve a mirar qué llavero hay (los tests cambian de uno a otro)."""
    _backend.cache_clear()


def keyring_available() -> bool:
    return _backend() is not None


def _keyring_get(name: str) -> str | None:
    backend = _backend()
    if backend is None:
        return None
    try:
        return backend.get_password(SERVICE, name) or None
    except Exception as exc:  # noqa: BLE001 - llavero bloqueado, D-Bus caído, error de Windows…
        logger.warning("No se pudo leer %s del llavero (%s).", name, type(exc).__name__)
        return None


# --- Las otras fuentes ---------------------------------------------------------------------------


def _from_environment(name: str) -> str | None:
    for alias in _aliases(name):
        if value := os.environ.get(alias):
            return value
    docker = "/run/secrets" if get_settings().in_docker else ""
    folder = os.environ.get("CAI_SECRETS_DIR") or docker
    if folder:
        path = Path(folder) / name
        with contextlib.suppress(OSError):
            if path.is_file():
                return path.read_text(encoding="utf-8").rstrip("\r\n") or None
    return None


def _file_values() -> dict[str, str | None]:
    path = env_file.env_path()
    if not path.is_file():
        return {}
    return dotenv_values(path, interpolate=False)


def _from_file(name: str, values: dict[str, str | None] | None = None) -> str | None:
    values = _file_values() if values is None else values
    for alias in _aliases(name):
        if value := values.get(alias):
            return value
    return None


# --- Lo que usa la app ---------------------------------------------------------------------------


def get(name: str) -> str | None:
    """El valor del secreto, de donde esté (ver el orden arriba), o `None`."""
    return _from_environment(name) or _keyring_get(name) or _from_file(name)


def location(name: str) -> Location | None:
    """Dónde está el secreto que se usa, sin leer más de lo necesario."""
    if _from_environment(name):
        return "environment"
    if _keyring_get(name):
        return "keyring"
    if _from_file(name):
        return "file"
    return None


def _remove_from_file(name: str) -> None:
    if not env_file.can_write():
        return
    values = _file_values()
    for alias in _aliases(name):
        if alias in values:
            env_file.write_secret(alias, None)


def _forget_in_process(name: str) -> None:
    """Una variable del proceso con ese nombre (o su alias `JH_`) mandaría sobre lo guardado."""
    for alias in _aliases(name):
        os.environ.pop(alias, None)


def _keyring_delete(backend: keyring.backend.KeyringBackend, name: str) -> None:
    try:
        backend.delete_password(SERVICE, name)
    except PasswordDeleteError:
        pass  # no estaba
    except Exception as exc:  # noqa: BLE001 - ver `_keyring_get`
        logger.warning("No se pudo borrar %s del llavero (%s).", name, type(exc).__name__)


def store(name: str, value: str) -> Location:
    """Guarda el secreto: en el llavero si lo hay; si no (o si falla), en `.env`. En Docker,
    `SecretNotWritableError`."""
    backend = _backend()
    if backend is not None:
        try:
            backend.set_password(SERVICE, name, value)
        except Exception as exc:  # noqa: BLE001 - ver `_keyring_get`
            logger.warning("No se pudo guardar %s en el llavero (%s).", name, type(exc).__name__)
            # Un valor antiguo en el llavero mandaría sobre el que va al fichero.
            _keyring_delete(backend, name)
        else:
            _remove_from_file(name)
            _forget_in_process(name)
            return "keyring"
    env_file.write_secret(name, value)
    return "file"


def delete(name: str) -> None:
    """Quita el secreto del llavero y de `.env`. En Docker, `SecretNotWritableError` si sigue en
    el entorno del contenedor."""
    backend = _backend()
    if backend is not None:
        _keyring_delete(backend, name)
    if not env_file.can_write():
        if _from_environment(name):
            raise SecretNotWritableError(name)
        return
    _remove_from_file(name)
    _forget_in_process(name)


def in_file(names: list[str]) -> list[str]:
    """De esos secretos, los que están guardados en `.env` (en claro)."""
    values = _file_values()
    return [name for name in dict.fromkeys(names) if _from_file(name, values)]


def move_to_keyring(name: str) -> bool:
    """Lleva el secreto de `.env` al llavero y quita su línea. `False` si no se pudo.

    Si el llavero ya tiene uno, es el que se está usando (va antes al leer): se conserva y solo se
    quita la línea. La línea se quita solo después de comprobar que el llavero tiene el valor."""
    backend = _backend()
    value = _from_file(name)
    if backend is None or value is None:
        return False
    if _keyring_get(name) is None:
        try:
            backend.set_password(SERVICE, name, value)
        except Exception as exc:  # noqa: BLE001 - ver `_keyring_get`
            logger.warning("No se pudo mover %s al llavero (%s).", name, type(exc).__name__)
            return False
        if _keyring_get(name) != value:
            return False
    _remove_from_file(name)
    return True
