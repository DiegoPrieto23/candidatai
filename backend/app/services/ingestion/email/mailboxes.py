"""Lectura de correos de alertas sin modificar nunca el buzón.

- **IMAP**: la carpeta se abre con `EXAMINE` (`select(readonly=True)`) y los mensajes se leen con
  `BODY.PEEK[]`, que no marca como leído. Solo se usan `LOGIN`, `EXAMINE`, `UID SEARCH`,
  `UID FETCH` (con `PEEK`) y `LOGOUT`: nada de `STORE`, `COPY`, `MOVE`, `EXPUNGE`, `APPEND`,
  `DELETE` ni `CLOSE`. Primero se piden solo los `Message-ID` y luego el cuerpo de los nuevos.
- **Carpeta local**: `data/inbox/*.eml` y `*.mbox` (sin subcarpetas: `samples/` no se lee). Los
  ficheros no se mueven ni se borran.
"""

import base64
import contextlib
import imaplib
import mailbox
import re
import ssl
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from email import message_from_bytes, policy
from pathlib import Path

from app.core.config import Settings

IMAP_TIMEOUT = 30
FETCH_CHUNK = 50
MAX_MESSAGE_BYTES = 10_000_000
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_UID = re.compile(rb"UID (\d+)")

ImapFactory = Callable[[str, int, float], imaplib.IMAP4]


class MailboxError(Exception):
    """No se pudo leer el buzón. `code`: `imap_auth`, `imap_folder`, `imap_error`, `network`."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class RawMail:
    raw: bytes
    origin: str  # «IMAP UID 123» o el nombre del fichero; para los avisos


def tls_context() -> ssl.SSLContext:
    """Contexto TLS que verifica certificado y nombre del servidor. `IMAP4_SSL` sin contexto no
    los verifica en Python 3.12, y un intermediario podría leer la contraseña."""
    return ssl.create_default_context()


def _ssl_factory(host: str, port: int, timeout: float) -> imaplib.IMAP4:
    return imaplib.IMAP4_SSL(host, port, ssl_context=tls_context(), timeout=timeout)


def imap_utf7(folder: str) -> str:
    """Nombre de carpeta en UTF-7 modificado de IMAP (RFC 3501 §5.1.3), entre comillas."""
    out, pending = [], ""

    def flush() -> None:
        nonlocal pending
        if pending:
            encoded = base64.b64encode(pending.encode("utf-16-be")).decode("ascii")
            out.append("&" + encoded.rstrip("=").replace("/", ",") + "-")
            pending = ""

    for char in folder:
        if 0x20 <= ord(char) <= 0x7E:
            flush()
            out.append("&-" if char == "&" else char)
        else:
            pending += char
    flush()
    name = "".join(out).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{name}"'


def _imap_date(day: date) -> str:
    return f"{day.day:02d}-{_MONTHS[day.month - 1]}-{day.year}"


def _ok(typ: str, what: str, code: str = "imap_error") -> None:
    if typ != "OK":
        raise MailboxError(code, f"El servidor IMAP rechazó {what}.")


def _header_ids(data: list[object]) -> dict[str, str]:
    """UID -> Message-ID a partir de la respuesta de `UID FETCH … HEADER.FIELDS (MESSAGE-ID)`."""
    result: dict[str, str] = {}
    for entry in data:
        if not isinstance(entry, tuple) or len(entry) < 2:
            continue
        meta, header = entry[0], entry[1]
        match = _UID.search(meta) if isinstance(meta, bytes) else None
        if match is None or not isinstance(header, bytes):
            continue
        parsed = message_from_bytes(header, policy=policy.default)
        result[match.group(1).decode()] = str(parsed.get("Message-ID", "")).strip()
    return result


def _bodies(data: list[object]) -> Iterator[tuple[str, bytes]]:
    for entry in data:
        if not isinstance(entry, tuple) or len(entry) < 2:
            continue
        meta, body = entry[0], entry[1]
        match = _UID.search(meta) if isinstance(meta, bytes) else None
        if match is not None and isinstance(body, bytes):
            yield match.group(1).decode(), body


def connect_imap(
    settings: Settings, factory: ImapFactory = _ssl_factory, folder: str | None = None
) -> imaplib.IMAP4:
    """Login y `EXAMINE` de la carpeta (por defecto, la de las alertas). Lanza `MailboxError` con
    un mensaje claro."""
    folder = folder or settings.imap_folder
    if not settings.imap_configured:
        raise MailboxError("imap_error", "IMAP no está configurado.")
    assert settings.imap_host and settings.imap_user and settings.imap_password
    try:
        conn = factory(settings.imap_host, settings.imap_port, IMAP_TIMEOUT)
    except (OSError, imaplib.IMAP4.error) as exc:
        raise MailboxError(
            "network",
            f"No se pudo conectar con {settings.imap_host}:{settings.imap_port} "
            f"({type(exc).__name__}).",
        ) from None
    try:
        try:
            conn.login(settings.imap_user, settings.imap_password.get_secret_value())
        except imaplib.IMAP4.error:
            raise MailboxError(
                "imap_auth",
                "El servidor IMAP rechazó el usuario o la contraseña. En Gmail hace falta una "
                "contraseña de aplicación (con la verificación en dos pasos activada).",
            ) from None
        try:
            typ, _ = conn.select(imap_utf7(folder), readonly=True)
        except imaplib.IMAP4.error:
            typ = "NO"
        _ok(typ, f"abrir la carpeta «{folder}»", "imap_folder")
    except BaseException:
        _logout(conn)
        raise
    return conn


def _logout(conn: imaplib.IMAP4) -> None:
    with contextlib.suppress(OSError, imaplib.IMAP4.error):
        conn.logout()


def read_imap(
    settings: Settings,
    is_known: Callable[[str], bool],
    since_days: int,
    factory: ImapFactory = _ssl_factory,
    today: date | None = None,
) -> Iterator[RawMail]:
    """Correos de la carpeta de los últimos `since_days` días cuyo `Message-ID` no se conoce."""
    conn = connect_imap(settings, factory)
    try:
        since = (today or date.today()) - timedelta(days=since_days)
        typ, data = conn.uid("SEARCH", "SINCE", _imap_date(since))
        _ok(typ, "la búsqueda de correos")
        uids = (data[0] or b"").split() if data else []
        for start in range(0, len(uids), FETCH_CHUNK):
            chunk = b",".join(uids[start : start + FETCH_CHUNK]).decode()
            typ, data = conn.uid("FETCH", chunk, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID)])")
            _ok(typ, "la lectura de cabeceras")
            ids = _header_ids(list(data or []))
            new = [uid for uid, mid in ids.items() if not (mid and is_known(mid))]
            if not new:
                continue
            typ, data = conn.uid("FETCH", ",".join(new), "(BODY.PEEK[])")
            _ok(typ, "la lectura de correos")
            for uid, body in _bodies(list(data or [])):
                if len(body) <= MAX_MESSAGE_BYTES:
                    yield RawMail(body, f"IMAP UID {uid}")
    except (TimeoutError, OSError) as exc:
        name = type(exc).__name__
        raise MailboxError("network", f"Se cortó la conexión IMAP ({name}).") from None
    except imaplib.IMAP4.error as exc:
        raise MailboxError("imap_error", f"Error del servidor IMAP: {exc}") from None
    finally:
        _logout(conn)


# Cabeceras con las que se decide si un correo es de uno de tus procesos (fase 15).
REPLY_HEADERS = "FROM DATE MESSAGE-ID SUBJECT"


def _headers(data: list[object]) -> dict[str, bytes]:
    """UID -> cabeceras pedidas con `BODY.PEEK[HEADER.FIELDS (…)]`."""
    return dict(_bodies(data))


def read_imap_matching(
    settings: Settings,
    folder: str,
    since: date,
    wanted: Callable[[bytes], bool],
    factory: ImapFactory = _ssl_factory,
) -> Iterator[RawMail]:
    """Correos de `folder` desde `since` cuyas cabeceras (`REPLY_HEADERS`) acepta `wanted`.

    Primero se piden solo esas cabeceras y luego el cuerpo de los aceptados, siempre con
    `BODY.PEEK`. De los demás no sale nada de aquí.
    """
    conn = connect_imap(settings, factory, folder)
    try:
        typ, data = conn.uid("SEARCH", "SINCE", _imap_date(since))
        _ok(typ, "la búsqueda de correos")
        uids = (data[0] or b"").split() if data else []
        for start in range(0, len(uids), FETCH_CHUNK):
            chunk = b",".join(uids[start : start + FETCH_CHUNK]).decode()
            typ, data = conn.uid("FETCH", chunk, f"(BODY.PEEK[HEADER.FIELDS ({REPLY_HEADERS})])")
            _ok(typ, "la lectura de cabeceras")
            accepted = [uid for uid, header in _headers(list(data or [])).items() if wanted(header)]
            if not accepted:
                continue
            typ, data = conn.uid("FETCH", ",".join(accepted), "(BODY.PEEK[])")
            _ok(typ, "la lectura de correos")
            for uid, body in _bodies(list(data or [])):
                if len(body) <= MAX_MESSAGE_BYTES:
                    yield RawMail(body, f"IMAP UID {uid}")
    except (TimeoutError, OSError) as exc:
        name = type(exc).__name__
        raise MailboxError("network", f"Se cortó la conexión IMAP ({name}).") from None
    except imaplib.IMAP4.error as exc:
        raise MailboxError("imap_error", f"Error del servidor IMAP: {exc}") from None
    finally:
        _logout(conn)


def read_local(inbox: Path) -> Iterator[RawMail]:
    """Correos de `data/inbox/` (`.eml` y `.mbox`), sin tocarlos."""
    if not inbox.is_dir():
        return
    for path in sorted(inbox.iterdir()):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix == ".eml":
            if path.stat().st_size <= MAX_MESSAGE_BYTES:
                yield RawMail(path.read_bytes(), path.name)
        elif suffix == ".mbox":
            box = mailbox.mbox(path, create=False)
            try:
                for key in box.iterkeys():
                    raw = box.get_bytes(key)
                    if len(raw) <= MAX_MESSAGE_BYTES:
                        yield RawMail(raw, f"{path.name} #{key}")
            finally:
                box.close()


def has_local_mail(inbox: Path) -> bool:
    return inbox.is_dir() and any(
        p.is_file() and p.suffix.lower() in {".eml", ".mbox"} for p in inbox.iterdir()
    )
