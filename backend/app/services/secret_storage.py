"""Contraseñas y claves guardadas en claro en `.env` y su paso al llavero (fase 41.5).

Hasta esta fase la app guardaba las contraseñas de los buzones en `.env`. Al arrancar, la UI
pregunta si se mueven al llavero del sistema; solo se mueven con esa confirmación. Si no, se quedan
como estaban y la UI las marca como guardadas en un fichero.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import secrets
from app.models import MailSource
from app.schemas.secrets import MoveSecretsResult, PlaintextSecret, PlaintextSecrets, SecretKind

_SETTINGS_KINDS: dict[str, SecretKind] = {
    secrets.ADZUNA_APP_KEY: "adzuna",
    secrets.INFOJOBS_CLIENT_SECRET: "infojobs",
}


def _known(session: Session) -> dict[str, PlaintextSecret]:
    """Los secretos que usa la app, por nombre: los de los buzones y los de los portales."""
    known: dict[str, PlaintextSecret] = {}
    for row in session.scalars(select(MailSource).where(MailSource.secret_ref.is_not(None))):
        assert row.secret_ref
        known[row.secret_ref] = PlaintextSecret(
            name=row.secret_ref, kind="mailbox", label=row.label
        )
    # La cuenta de instalación, aunque aún no se haya creado su buzón «Principal».
    known.setdefault(
        secrets.IMAP_PASSWORD, PlaintextSecret(name=secrets.IMAP_PASSWORD, kind="mailbox")
    )
    for name, kind in _SETTINGS_KINDS.items():
        known[name] = PlaintextSecret(name=name, kind=kind)
    return known


def list_plaintext(session: Session) -> PlaintextSecrets:
    """Los secretos que siguen en `.env`, en claro."""
    known = _known(session)
    return PlaintextSecrets(
        secrets=[known[name] for name in secrets.in_file(list(known))],
        keyring=secrets.keyring_available(),
    )


def move_to_keyring(session: Session, names: list[str]) -> MoveSecretsResult:
    """Mueve al llavero los secretos pedidos (solo los que conoce la app) y quita sus líneas."""
    known = _known(session)
    wanted = [name for name in dict.fromkeys(names) if name in known]
    if not secrets.keyring_available():
        return MoveSecretsResult(
            moved=[],
            failed=wanted,
            message="Este equipo no tiene un llavero del sistema disponible: se quedan como están.",
        )
    moved = [name for name in wanted if secrets.move_to_keyring(name)]
    failed = [name for name in wanted if name not in moved]
    if failed:
        message = f"Movidas al llavero: {len(moved)}. No se pudieron mover: {len(failed)}."
    else:
        message = "Guardadas en el llavero del sistema."
    return MoveSecretsResult(moved=moved, failed=failed, message=message)
