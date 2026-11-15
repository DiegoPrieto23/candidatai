"""Contraseñas guardadas en claro y su paso al llavero (fase 41.5). Solo la UI, con confirmación;
nunca devuelve un valor."""

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep, require_ui, require_ui_read
from app.schemas.secrets import MoveSecretsInput, MoveSecretsResult, PlaintextSecrets
from app.services import secret_storage

router = APIRouter(prefix="/secrets", tags=["secrets"])


@router.get(
    "/plaintext",
    operation_id="list_plaintext_secrets",
    dependencies=[Depends(require_ui_read)],
)
def list_plaintext_secrets(session: SessionDep) -> PlaintextSecrets:
    """Las contraseñas y claves que siguen guardadas en un fichero (sus nombres, no sus valores)."""
    return secret_storage.list_plaintext(session)


@router.post(
    "/move-to-keyring", operation_id="move_secrets_to_keyring", dependencies=[Depends(require_ui)]
)
def move_secrets_to_keyring(session: SessionDep, body: MoveSecretsInput) -> MoveSecretsResult:
    """Mueve esas contraseñas al llavero del sistema y las quita del fichero."""
    return secret_storage.move_to_keyring(session, body.names)
