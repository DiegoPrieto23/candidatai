"""Buzones de los que se leen alertas (fase 27.4, ADR-045). La contraseña solo entra, nunca sale."""

import ipaddress
import re
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, SecretStr, model_validator

MailKind = Literal["imap", "folder"]
MailSecurity = Literal["ssl", "starttls"]

# Un nombre de servidor: etiquetas DNS, o una IP. Sin esquema, puerto, ruta ni usuario.
_HOSTNAME = re.compile(r"^(?=.{1,253}$)([A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.?)+$")
# Carpeta de `data/inbox/`: un solo nivel, sin `..` ni separadores.
_FOLDER_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.-]{0,63}$")
RESERVED_FOLDERS = {"respuestas", "samples"}  # ya tienen otro uso en `data/inbox/`
# Nombres que Windows no deja usar como carpeta.
_WINDOWS_RESERVED = re.compile(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(\..*)?$", re.IGNORECASE)


def _host(value: str) -> str:
    value = value.strip().rstrip(".").lower()
    if not _HOSTNAME.match(value) and not _is_ip(value):
        raise ValueError(
            "Servidor no válido: escribe solo el nombre, como `imap.gmail.com` (sin `https://`, "
            "puerto ni ruta)."
        )
    return value


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _no_controls(value: str) -> str:
    # También C1 y los separadores de línea Unicode: partirían la línea de `.env`.
    if any(ord(c) < 0x20 or 0x7F <= ord(c) <= 0x9F or c in "\u2028\u2029" for c in value):
        raise ValueError("No puede llevar saltos de línea ni caracteres de control.")
    return value


def _label(value: str) -> str:
    value = " ".join(_no_controls(value).split())
    if not value:
        raise ValueError("Escribe un nombre.")
    return value


Host = Annotated[str, Field(max_length=253), AfterValidator(_host)]
Label = Annotated[str, Field(min_length=1, max_length=80), AfterValidator(_label)]
Folder = Annotated[str, Field(min_length=1, max_length=200), AfterValidator(_no_controls)]
User = Annotated[str, Field(min_length=1, max_length=320), AfterValidator(_no_controls)]


def _secret(value: SecretStr) -> SecretStr:
    _no_controls(value.get_secret_value())
    return value


Password = Annotated[SecretStr, Field(min_length=1, max_length=256), AfterValidator(_secret)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MailSourceInput(_Strict):
    """Alta de un buzón desde la UI. `password` solo entra: nunca se devuelve."""

    label: Label
    kind: MailKind = "imap"
    host: Host | None = None
    port: int = Field(default=993, ge=1, le=65535)
    security: MailSecurity = "ssl"
    user: User | None = None
    password: Password | None = None
    folder: Folder = "INBOX"
    replies_folder: Folder = "INBOX"
    enabled: bool = True
    read_replies: bool = False
    allow_private: bool = False

    @model_validator(mode="after")
    def _by_kind(self) -> Self:
        if self.kind == "imap":
            if not self.host or not self.user:
                raise ValueError("Un buzón IMAP necesita servidor y usuario.")
        else:
            name = self.folder.strip()
            bad = name.endswith((".", " ")) or _WINDOWS_RESERVED.match(name)
            if not _FOLDER_NAME.match(name) or ".." in name or bad:
                raise ValueError(
                    "Carpeta no válida: un nombre corto (letras, dígitos, espacio, `.`, `-` o "
                    "`_`), que se crea dentro de data/inbox/."
                )
            if name.casefold() in RESERVED_FOLDERS:
                raise ValueError(f"«{name}» ya tiene otro uso en data/inbox/: elige otro nombre.")
            self.folder = name
            self.host = self.user = self.password = None
            self.read_replies = False
        return self


class MailSourcePatch(_Strict):
    """Cambios de un buzón. Lo que no venga, no cambia. La contraseña, solo si se escribe."""

    label: Label | None = None
    host: Host | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    security: MailSecurity | None = None
    user: User | None = None
    password: Password | None = None
    folder: Folder | None = None
    replies_folder: Folder | None = None
    enabled: bool | None = None
    read_replies: bool | None = None
    allow_private: bool | None = None


class MailError(BaseModel):
    code: str
    message: str


class MailSourceView(BaseModel):
    """Un buzón tal como se enseña. Nunca la contraseña: solo si está puesta y en qué variable."""

    id: int
    label: str
    kind: MailKind
    host: str | None
    port: int | None
    security: MailSecurity
    user: str | None
    folder: str
    replies_folder: str
    enabled: bool
    read_replies: bool
    allow_private: bool
    from_env: bool = Field(description="La cuenta `CAI_IMAP_*` de `.env`: se cambia ahí.")
    has_password: bool
    secret_ref: str | None = Field(description="Variable de `.env` con la contraseña (su nombre).")
    path: str | None = Field(description="Carpeta de los `.eml` (solo `folder`).")
    last_polled_at: datetime | None
    last_error: MailError | None


class MailSourceList(BaseModel):
    sources: list[MailSourceView]
    demo: bool = Field(description="En una demo no se lee ningún buzón IMAP.")
    can_store_passwords: bool = Field(
        description="Si la app puede escribir las contraseñas en `.env` (en Docker, no)."
    )


class MailTestResult(BaseModel):
    ok: bool
    code: str | None = None  # el de `MailboxError` si falla
    message: str


class MailSaveResult(BaseModel):
    source: MailSourceView
    message: str
    # En Docker la contraseña no se puede guardar: qué línea añadir a `.env` (sin el valor).
    env_line: str | None = None
