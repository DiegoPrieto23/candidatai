"""Secretos guardados en claro y su paso al llavero del sistema (fase 41.5). Nunca los valores."""

from typing import Literal

from pydantic import BaseModel, Field

SecretKind = Literal["mailbox", "adzuna", "infojobs"]


class PlaintextSecret(BaseModel):
    name: str = Field(description="Nombre del secreto (la referencia, nunca el valor).")
    kind: SecretKind
    label: str | None = Field(default=None, description="El nombre del buzón, si es de uno.")


class PlaintextSecrets(BaseModel):
    secrets: list[PlaintextSecret] = Field(description="Los que están guardados en un fichero.")
    keyring: bool = Field(description="Si hay llavero del sistema adonde moverlos.")


class MoveSecretsInput(BaseModel):
    names: list[str] = Field(min_length=1, max_length=50)


class MoveSecretsResult(BaseModel):
    moved: list[str]
    failed: list[str]
    message: str
