"""De los bytes de un correo a sus partes útiles. Nunca se guarda el cuerpo."""

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from email import message_from_bytes, policy
from email.message import EmailMessage
from email.utils import parseaddr, parsedate_to_datetime

_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
MAX_PART_CHARS = 2_000_000  # una alerta normal ronda los 100 KB; lo que pase se recorta


@dataclass(frozen=True)
class AlertMessage:
    message_id: str
    sender: str  # dirección del remitente, en minúsculas
    subject: str
    received_at: datetime | None
    html: str | None
    text: str | None
    sender_name: str = ""  # nombre visible del remitente, sin caracteres de control

    @property
    def sender_domain(self) -> str:
        return self.sender.rpartition("@")[2]


def _part(msg: EmailMessage, subtype: str) -> str | None:
    part = msg.get_body(preferencelist=(subtype,))
    if part is None:
        return None
    try:
        content = part.get_content()
    except (LookupError, ValueError):  # charset desconocido o contenido roto
        payload = part.get_payload(decode=True)
        content = payload.decode("utf-8", "replace") if isinstance(payload, bytes) else None
    return content[:MAX_PART_CHARS] if isinstance(content, str) else None


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def clean_header(value: str, limit: int) -> str:
    """Una cabecera en una línea: sin caracteres de control ni espacios repetidos."""
    return " ".join(_CONTROL.sub(" ", value).split())[:limit]


def message_id_of(raw: bytes, header: str | None) -> str:
    """El `Message-ID` del correo o, si no tiene, uno estable a partir de su contenido."""
    value = (header or "").strip()
    if value:
        return value[:998]
    return f"<sha256:{hashlib.sha256(raw).hexdigest()}>"


def parse_message(raw: bytes) -> AlertMessage:
    msg = message_from_bytes(raw, policy=policy.default)
    assert isinstance(msg, EmailMessage)
    name, address = parseaddr(str(msg.get("From", "")))
    sender = address.strip().lower()
    return AlertMessage(
        sender_name=clean_header(name, 200),
        message_id=message_id_of(raw, msg.get("Message-ID")),
        sender=sender,
        subject=clean_header(str(msg.get("Subject", "")), 300),
        received_at=parse_date(msg.get("Date")),
        html=_part(msg, "html"),
        text=_part(msg, "plain"),
    )
