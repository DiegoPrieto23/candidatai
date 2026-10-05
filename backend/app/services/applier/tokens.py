"""Confirmación de envío de un solo uso (POLICIES §5.1: una confirmación, una candidatura).

- `issue` la emite `service.confirm_submission`, que solo llama la API de la UI tras comprobar el
  nombre de la empresa que escribes. En la BD queda su hash; el valor viaja una vez al worker.
- `consume` la valida (intento listo, hash correcto, sin usar y sin caducar) y la marca usada en
  la misma transacción. Solo ella crea una `SubmitConfirmation`, que es lo que exige
  `submit.click_submit`.
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import ApplicationAttempt
from app.models.base import utcnow

_ISSUER = object()  # solo `consume` crea confirmaciones


class TokenError(ValueError):
    """La confirmación no vale: no existe, no coincide, ya se usó o caducó."""


@dataclass(frozen=True)
class SubmitConfirmation:
    """Prueba de que confirmaste el envío de este intento. Se consume al crearse."""

    attempt_id: int
    consents: tuple[str, ...]  # marcadores de las casillas de consentimiento que aceptaste
    _issuer: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._issuer is not _ISSUER:
            raise TokenError("Una confirmación de envío solo la crea `tokens.consume`.")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue(attempt: ApplicationAttempt, ttl_seconds: int, now: datetime | None = None) -> str:
    """Emite una confirmación nueva para el intento (anula la anterior, si la hubiera)."""
    token = secrets.token_urlsafe(32)
    attempt.token_hash = _hash(token)
    attempt.token_expires_at = (now or utcnow()) + timedelta(seconds=ttl_seconds)
    attempt.token_used_at = None
    return token


def consume(
    session: Session,
    attempt_id: int,
    token: str,
    consents: tuple[str, ...] = (),
    now: datetime | None = None,
) -> SubmitConfirmation:
    """Valida la confirmación y la marca usada. Lanza `TokenError` si no vale."""
    now = now or utcnow()
    attempt = session.get(ApplicationAttempt, attempt_id)
    if attempt is None or attempt.token_hash is None:
        raise TokenError("No hay ninguna confirmación de envío para este intento.")
    if not hmac.compare_digest(attempt.token_hash, _hash(token)):
        raise TokenError("La confirmación de envío no coincide.")
    if attempt.token_used_at is not None:
        raise TokenError("Esta confirmación de envío ya se usó: confirma de nuevo en la UI.")
    if attempt.token_expires_at is None or attempt.token_expires_at < now:
        raise TokenError("La confirmación de envío ha caducado: confirma de nuevo en la UI.")
    if attempt.status != "ready":
        raise TokenError(f"El intento no está listo para enviar (estado «{attempt.status}»).")
    attempt.token_used_at = now
    attempt.status = "submitting"
    attempt.updated_at = now
    session.flush()
    return SubmitConfirmation(attempt_id=attempt_id, consents=consents, _issuer=_ISSUER)
