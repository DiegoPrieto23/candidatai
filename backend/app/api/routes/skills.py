"""Página «Skills» (fase 14): huecos agregados, «es lo mismo que…» y marcas.

Añadir un alias escribe `config/skill_aliases.yaml`, así que, como `POST /agent/launch`
(ADR-024), solo lo puede pedir la UI. Las marcas también: son decisiones del usuario.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import SessionDep
from app.api.routes.agent import require_ui
from app.services import skill_aliases, skill_gaps

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("/gaps", operation_id="get_skill_gaps")
def get_skill_gaps(
    session: SessionDep, days: int = Query(default=skill_gaps.DEFAULT_DAYS, ge=1, le=365)
) -> skill_gaps.SkillGapsView:
    """Skills que piden las ofertas abiertas y las aprobadas o enviadas en los últimos `days` días
    y el perfil no cubre, de más a menos ofertas, con su marca y las skills del perfil."""
    return skill_gaps.get_skill_gaps(session, days)


class AliasBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill: str = Field(min_length=1, max_length=200)  # como la escriben las ofertas
    profile_skill: str = Field(min_length=1, max_length=200)


@router.post("/aliases", operation_id="add_skill_alias", dependencies=[Depends(require_ui)])
def add_skill_alias(body: AliasBody, session: SessionDep) -> skill_aliases.AliasResult:
    """«Es lo mismo que…»: la skill pasa a ser sinónimo de una del perfil y se recalculan los
    scores en el worker."""
    return skill_aliases.add_alias(session, body.skill, body.profile_skill)


class MarkBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill: str = Field(min_length=1, max_length=200)
    status: skill_gaps.MarkStatus | None  # `null` quita la marca


@router.post("/marks", operation_id="set_skill_mark", dependencies=[Depends(require_ui)])
def set_skill_mark(body: MarkBody, session: SessionDep) -> skill_gaps.MarkResult:
    """«No la tengo» (`gap`), «La tengo» (`have`) o quitar la marca (`null`)."""
    return skill_gaps.set_mark(session, body.skill, body.status)
