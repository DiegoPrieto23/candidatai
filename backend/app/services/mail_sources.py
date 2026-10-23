"""Buzones de los que se leen alertas y respuestas (fase 27.4, ADR-045).

Un buzón es IMAP (siempre en solo lectura, ver `mailboxes.py`) o una carpeta `data/inbox/<nombre>/`
de `.eml`/`.mbox`. La cuenta `CAI_IMAP_*` de `.env` aparece sola como «Principal» (`from_env`):
servidor, usuario y carpetas se siguen leyendo de `.env` y se cambian ahí.

Las contraseñas viven solo en `.env` (`core/env_file.py`); aquí solo se guarda el nombre de la
variable. Nunca salen en una vista, un error ni un log.
"""

import ipaddress
import logging
import re
import socket
import unicodedata
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import env_file
from app.core.config import get_settings
from app.models import MailSource, MailSourceChange
from app.models.base import utcnow
from app.schemas.mail_sources import (
    MailError,
    MailSaveResult,
    MailSourceInput,
    MailSourceList,
    MailSourcePatch,
    MailSourceView,
    MailTestResult,
)
from app.services.ingestion.email.mailboxes import (
    ImapAccount,
    ImapFactory,
    MailboxError,
    connect_imap,
)

logger = logging.getLogger(__name__)

ENV_SECRET = "CAI_IMAP_PASSWORD"
PRINCIPAL = "Principal"
# Lo que de la cuenta de `.env` se cambia en `.env`, no aquí.
_ENV_FIELDS = ("host", "port", "security", "user", "folder", "replies_folder", "allow_private")

Purpose = Literal["alerts", "replies"]


class MailSourceNotFoundError(LookupError):
    pass


class MailSourceExistsError(ValueError):
    pass


class MailSourceNotAllowedError(ValueError):
    """Un cambio que no se hace aquí (p. ej. el servidor de la cuenta de `.env`)."""


# --- La cuenta de `.env` -----------------------------------------------------------------------


def _env_configured() -> bool:
    settings = get_settings()
    return bool(settings.imap_host and settings.imap_user) and not settings.demo_mode


def _unique_label(session: Session, wanted: str) -> str:
    taken = {label.casefold() for label in session.scalars(select(MailSource.label))}
    label, n = wanted, 2
    while label.casefold() in taken:
        label, n = f"{wanted} {n}", n + 1
    return label


def sync_env_source(session: Session) -> MailSource | None:
    """Crea el buzón «Principal» la primera vez que se ve `CAI_IMAP_*` en `.env`."""
    row = session.scalars(select(MailSource).where(MailSource.from_env.is_(True))).first()
    if row is not None or not _env_configured():
        return row
    settings = get_settings()
    row = MailSource(
        label=_unique_label(session, PRINCIPAL),
        kind="imap",
        security="ssl",
        folder=settings.imap_folder,
        replies_folder=settings.imap_replies_folder,
        enabled=True,
        read_replies=True,
        secret_ref=ENV_SECRET,
        from_env=True,
        allow_private=True,  # lo configuraste a mano en `.env`, como hasta ahora
    )
    session.add(row)
    session.flush()
    _audit(session, row, "created", ["from_env"])
    return row


def _visible(session: Session) -> list[MailSource]:
    """Los buzones que cuentan: la cuenta de `.env` solo si sigue configurada."""
    sync_env_source(session)
    env_ok = _env_configured()
    rows = session.scalars(select(MailSource).order_by(MailSource.id))
    return [row for row in rows if env_ok or not row.from_env]


# --- Vistas --------------------------------------------------------------------------------------


def effective(row: MailSource) -> dict[str, object]:
    """Servidor, usuario y carpetas: los de `.env` en la cuenta heredada."""
    if not row.from_env:
        return {
            "host": row.host,
            "port": row.port,
            "user": row.user,
            "folder": row.folder,
            "replies_folder": row.replies_folder,
        }
    settings = get_settings()
    return {
        "host": settings.imap_host,
        "port": settings.imap_port,
        "user": settings.imap_user,
        "folder": settings.imap_folder,
        "replies_folder": settings.imap_replies_folder,
    }


def _view(row: MailSource) -> MailSourceView:
    fields = effective(row)
    error = MailError.model_validate(row.last_error) if row.last_error else None
    return MailSourceView(
        id=row.id,
        label=row.label,
        kind=row.kind,  # type: ignore[arg-type]
        security=row.security,  # type: ignore[arg-type]
        enabled=row.enabled,
        read_replies=row.read_replies,
        allow_private=row.allow_private,
        from_env=row.from_env,
        has_password=bool(row.secret_ref and env_file.read_secret(row.secret_ref)),
        secret_ref=row.secret_ref,
        path=f"data/inbox/{row.folder}/" if row.kind == "folder" else None,
        last_polled_at=row.last_polled_at,
        last_error=error,
        **fields,  # type: ignore[arg-type]
    )


def list_mail_sources(session: Session) -> MailSourceList:
    return MailSourceList(
        sources=[_view(row) for row in _visible(session)],
        demo=get_settings().demo_mode,
        can_store_passwords=env_file.can_write(),
    )


def _get(session: Session, source_id: int) -> MailSource:
    row = session.get(MailSource, source_id)
    if row is None or row not in _visible(session):
        raise MailSourceNotFoundError(f"No existe el buzón {source_id}.")
    return row


def get_mail_source(session: Session, source_id: int) -> MailSourceView:
    return _view(_get(session, source_id))


# --- Altas, cambios y bajas ----------------------------------------------------------------------


def _audit(session: Session, row: MailSource, action: str, fields: list[str]) -> None:
    session.add(
        MailSourceChange(
            mail_source_id=row.id, label=row.label, action=action, fields=sorted(set(fields))
        )
    )


def _check_label(session: Session, label: str, exclude: int | None = None) -> str:
    label = " ".join(label.split())
    for row in session.scalars(select(MailSource)):
        if row.id != exclude and row.label.casefold() == label.casefold():
            raise MailSourceExistsError(f"Ya hay un buzón «{row.label}»: elige otro nombre.")
    return label


def _secret_name(session: Session, label: str) -> str:
    ascii_label = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^A-Z0-9]+", "_", ascii_label.upper()).strip("_")[:40] or "BUZON"
    taken = set(session.scalars(select(MailSource.secret_ref)))
    name, n = f"CAI_IMAP_{slug}_PASSWORD", 2
    while name in taken or name == ENV_SECRET or env_file.is_defined(name):
        name, n = f"CAI_IMAP_{slug}_{n}_PASSWORD", n + 1
    return name


def _store_password(row: MailSource, password: str) -> str | None:
    """Guarda la contraseña en `.env`. En Docker no se puede: la línea que tiene que añadir."""
    assert row.secret_ref
    try:
        env_file.write_secret(row.secret_ref, password)
    except env_file.SecretNotWritableError:
        return f"{row.secret_ref}=…"
    return None


def create_mail_source(session: Session, data: MailSourceInput) -> MailSaveResult:
    label = _check_label(session, data.label)
    row = MailSource(
        label=label,
        kind=data.kind,
        host=data.host,
        port=data.port if data.kind == "imap" else None,
        security=data.security,
        user=data.user,
        folder=data.folder,
        replies_folder=data.replies_folder,
        enabled=data.enabled,
        read_replies=data.read_replies,
        allow_private=data.allow_private,
        from_env=False,
    )
    if data.kind == "imap":
        row.secret_ref = _secret_name(session, label)
    session.add(row)
    session.flush()
    env_line = None
    if data.password is not None:
        env_line = _store_password(row, data.password.get_secret_value())
    if data.kind == "folder":
        (get_settings().inbox_dir / data.folder).mkdir(parents=True, exist_ok=True)
    _audit(session, row, "created", list(data.model_fields_set) + ["label", "kind"])
    message = f"Buzón «{label}» añadido."
    if env_line:
        message += f" Falta su contraseña: añade a tu .env la línea `{env_line}` y recrea Docker."
    elif data.kind == "imap" and data.password is None:
        message += f" Falta su contraseña (variable {row.secret_ref} de .env)."
    return MailSaveResult(source=_view(row), message=message, env_line=env_line)


def update_mail_source(session: Session, source_id: int, patch: MailSourcePatch) -> MailSaveResult:
    row = _get(session, source_id)
    changes = patch.model_dump(exclude_unset=True, exclude={"password"})
    if row.from_env and (blocked := [f for f in _ENV_FIELDS if f in changes]):
        raise MailSourceNotAllowedError(
            f"«{row.label}» es la cuenta de .env: {', '.join(blocked)} se cambian en .env "
            "(CAI_IMAP_*)."
        )
    if "label" in changes:
        changes["label"] = _check_label(session, changes["label"], exclude=row.id)
    if not row.from_env:
        # Se valida el buzón entero, con las mismas reglas que al darlo de alta.
        current = {
            "label": row.label,
            "kind": row.kind,
            "host": row.host,
            "port": row.port or 993,
            "security": row.security,
            "user": row.user,
            "folder": row.folder,
            "replies_folder": row.replies_folder,
            "enabled": row.enabled,
            "read_replies": row.read_replies,
            "allow_private": row.allow_private,
        }
        merged = MailSourceInput.model_validate({**current, **changes})
        changes = {k: getattr(merged, k) for k in changes}
    for key, value in changes.items():
        setattr(row, key, value)
    env_line = None
    fields = list(changes)
    if patch.password is not None:
        if row.secret_ref is None:
            raise MailSourceNotAllowedError("Una carpeta de .eml no lleva contraseña.")
        env_line = _store_password(row, patch.password.get_secret_value())
        fields.append("password")
    if row.kind == "folder":
        (get_settings().inbox_dir / row.folder).mkdir(parents=True, exist_ok=True)
    session.flush()
    if fields:
        _audit(session, row, "updated", fields)
    message = f"Buzón «{row.label}» actualizado."
    if env_line:
        message += f" Falta su contraseña: añade a tu .env la línea `{env_line}` y recrea Docker."
    return MailSaveResult(source=_view(row), message=message, env_line=env_line)


def delete_mail_source(session: Session, source_id: int) -> str:
    """Quita el buzón y su línea de `.env`. Los correos ya leídos y sus ofertas se quedan."""
    row = _get(session, source_id)
    if row.from_env:
        raise MailSourceNotAllowedError(
            f"«{row.label}» es la cuenta de .env: para quitarla, borra CAI_IMAP_HOST, "
            "CAI_IMAP_USER y CAI_IMAP_PASSWORD de .env, o desactívala aquí."
        )
    message = f"Buzón «{row.label}» quitado."
    if row.secret_ref:
        try:
            env_file.write_secret(row.secret_ref, None)
        except env_file.SecretNotWritableError:
            message += f" Quita también la línea {row.secret_ref} de tu .env."
    if row.kind == "folder":
        message += f" La carpeta data/inbox/{row.folder}/ se queda como está."
    _audit(session, row, "deleted", [])
    session.delete(row)
    session.flush()
    return message


# --- Conexión ------------------------------------------------------------------------------------


def check_host(host: str, allow_private: bool) -> None:
    """Rechaza un servidor que resuelve a una dirección privada, local o reservada, salvo que el
    buzón lo permita (un servidor propio). Se comprueba al conectar."""
    if allow_private:
        return
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        raise MailboxError("network", f"No se encuentra el servidor {host}.") from None
    for info in infos:
        address = str(info[4][0]).split("%", 1)[0]
        if not ipaddress.ip_address(address).is_global:
            raise MailboxError(
                "host_not_allowed",
                f"{host} es una dirección privada o local. Si es tu propio servidor, "
                "marca «Servidor en mi equipo o mi red».",
            )


def _account(
    host: str | None,
    port: int | None,
    user: str | None,
    password: str | None,
    folder: str,
    security: str,
    allow_private: bool,
    secret_ref: str | None,
) -> ImapAccount:
    if get_settings().demo_mode:
        raise MailboxError("demo", "En la demo no se lee ningún buzón real.")
    if not host or not user:
        raise MailboxError("imap_error", "Faltan el servidor o el usuario.")
    if not password:
        where = f" (variable {secret_ref} de .env)" if secret_ref else ""
        raise MailboxError("no_password", f"Falta la contraseña{where}.")
    check_host(host, allow_private)
    return ImapAccount(
        host,
        port or 993,
        user,
        password,
        folder,
        "starttls" if security == "starttls" else "ssl",
    )


def account_of(row: MailSource, purpose: Purpose = "alerts") -> ImapAccount:
    """La cuenta de un buzón IMAP, con su contraseña leída de `.env`. `MailboxError` si falta
    algo o el servidor no está permitido."""
    fields = effective(row)
    folder = str(fields["replies_folder" if purpose == "replies" else "folder"])
    password = env_file.read_secret(row.secret_ref) if row.secret_ref else None
    return _account(
        fields["host"],  # type: ignore[arg-type]
        fields["port"],  # type: ignore[arg-type]
        fields["user"],  # type: ignore[arg-type]
        password,
        folder,
        row.security,
        row.allow_private or row.from_env,
        row.secret_ref,
    )


def _try(account: ImapAccount, factory: ImapFactory | None) -> MailTestResult:
    conn = connect_imap(account, factory)
    try:
        conn.logout()
    except Exception:  # noqa: BLE001 - ya se comprobó lo que importa
        logger.debug("Logout IMAP fallido tras la prueba", exc_info=True)
    return MailTestResult(
        ok=True, message=f"Conectado: carpeta «{account.folder}» abierta en solo lectura."
    )


def _folder_test(folder: str) -> MailTestResult:
    path = get_settings().inbox_dir / folder
    if not path.is_dir():
        return MailTestResult(
            ok=False, code="inbox_error", message=f"No existe la carpeta data/inbox/{folder}/."
        )
    count = sum(1 for p in path.iterdir() if p.suffix.lower() in {".eml", ".mbox"})
    return MailTestResult(
        ok=True, message=f"Carpeta data/inbox/{folder}/ lista: {count} ficheros de correo."
    )


def probe_mail_source(
    session: Session, source_id: int, factory: ImapFactory | None = None
) -> MailTestResult:
    """Login y `EXAMINE` de su carpeta de alertas (sin leer correos), o que exista su carpeta."""
    row = _get(session, source_id)
    if row.kind == "folder":
        return _folder_test(row.folder)
    try:
        return _try(account_of(row), factory)
    except MailboxError as exc:
        return MailTestResult(ok=False, code=exc.code, message=exc.message)


def probe_new_mail_source(
    data: MailSourceInput, factory: ImapFactory | None = None
) -> MailTestResult:
    """La misma prueba, antes de guardar el buzón (con la contraseña que se acaba de escribir)."""
    if data.kind == "folder":
        return MailTestResult(
            ok=True, message=f"Se leerán los .eml y .mbox de data/inbox/{data.folder}/."
        )
    password = data.password.get_secret_value() if data.password else None
    try:
        account = _account(
            data.host,
            data.port,
            data.user,
            password,
            data.folder,
            data.security,
            data.allow_private,
            None,
        )
        return _try(account, factory)
    except MailboxError as exc:
        return MailTestResult(ok=False, code=exc.code, message=exc.message)


# --- Lectura -------------------------------------------------------------------------------------


def active_sources(session: Session, purpose: Purpose = "alerts") -> list[MailSource]:
    """Los buzones activos que se leen para alertas o, con `read_replies`, para respuestas. En
    una demo, solo las carpetas."""
    demo = get_settings().demo_mode
    rows = [row for row in _visible(session) if row.enabled and not (demo and row.kind == "imap")]
    if purpose == "replies":
        rows = [row for row in rows if row.kind == "imap" and row.read_replies]
    return rows


def mark(row: MailSource, error: MailboxError | None) -> None:
    row.last_polled_at = utcnow()
    row.last_error = {"code": error.code, "message": error.message} if error else None
