"""Propuestas de tu agente para un campo del perfil (fase 41.2): hoy, el resumen en inglés.

El agente **no escribe en el perfil**: deja una propuesta con `save_profile_suggestion` y la UI la
enseña junto al campo para usarla tal cual, editarla o descartarla. Lo que se guarda en el perfil
pasa por «Guardar», como cualquier cambio hecho a mano. Por eso la acción puede ir en segundo plano
sin más herramientas que leer el perfil y dejar la propuesta.

- Una propuesta pendiente por campo: una nueva sustituye a la anterior.
- Se guarda también el texto de origen (el resumen en español que se tradujo): si cambia después,
  la UI avisa de que la propuesta se hizo con otra versión.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ProfileSuggestion
from app.models.base import utcnow
from app.services import profile

MAX_TEXT = 4000

SuggestionField = Literal["summary.en"]
SuggestionText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT)
]


class SuggestionNotFoundError(LookupError):
    pass


class SuggestionClosedError(ValueError):
    pass


class SuggestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: SuggestionField
    text: SuggestionText


class SuggestionView(BaseModel):
    id: int
    field: SuggestionField
    text: str
    source: str | None  # el texto del que sale (el resumen en español), tal como estaba
    agent_name: str | None
    created_at: datetime


class SaveSuggestionResult(BaseModel):
    ok: bool = True
    suggestion_id: int
    message: str


class PendingSuggestions(BaseModel):
    suggestions: list[SuggestionView]


def _source(session: Session, field: SuggestionField) -> str:
    """El texto del que sale la propuesta, del perfil vigente. Sin él no hay nada que proponer."""
    current = profile.current(session).profile
    if field == "summary.en":
        source = (current.summary.es or "").strip()
        if not source:
            raise ValueError(
                "El perfil no tiene resumen en español: hay que escribirlo y guardarlo antes de "
                "pedir la "
                "versión en inglés."
            )
        return source
    raise ValueError(f"Campo no admitido: {field}.")  # pragma: no cover - Literal lo impide


def _view(row: ProfileSuggestion) -> SuggestionView:
    return SuggestionView(
        id=row.id,
        field=row.field,  # type: ignore[arg-type]
        text=row.text,
        source=row.source,
        agent_name=row.agent_name,
        created_at=row.created_at,
    )


def _pending(session: Session, field: str | None = None) -> list[ProfileSuggestion]:
    query = select(ProfileSuggestion).where(ProfileSuggestion.status == "pending")
    if field is not None:
        query = query.where(ProfileSuggestion.field == field)
    return list(session.scalars(query.order_by(ProfileSuggestion.id.desc())))


def save(
    session: Session, data: SuggestionInput, agent_name: str | None = None
) -> SaveSuggestionResult:
    source = _source(session, data.field)
    for old in _pending(session, data.field):
        old.status = "replaced"
        old.resolved_at = utcnow()
    row = ProfileSuggestion(
        field=data.field, text=data.text, source=source, agent_name=agent_name, status="pending"
    )
    session.add(row)
    session.flush()
    return SaveSuggestionResult(
        suggestion_id=row.id,
        message="Propuesta guardada: el usuario la revisa en «Mi perfil» antes de guardarla.",
    )


def pending(session: Session) -> PendingSuggestions:
    """Las propuestas sin resolver, una por campo (la más reciente)."""
    seen: set[str] = set()
    views = []
    for row in _pending(session):
        if row.field not in seen:
            seen.add(row.field)
            views.append(_view(row))
    return PendingSuggestions(suggestions=views)


def resolve(session: Session, suggestion_id: int, outcome: Literal["used", "discarded"]) -> None:
    """La usaste (pasó al formulario, que se guarda aparte) o la descartaste."""
    row = session.get(ProfileSuggestion, suggestion_id)
    if row is None:
        raise SuggestionNotFoundError(f"No existe la propuesta {suggestion_id}.")
    if row.status != "pending":
        raise SuggestionClosedError("Esa propuesta ya no está pendiente.")
    row.status = outcome
    row.resolved_at = utcnow()
