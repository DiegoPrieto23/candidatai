"""Indicaciones del usuario para el CV de una oferta («destaca el proyecto de Airflow», «en
inglés»…). Las escribe en la ficha, junto a «Generar CV», y `generate-cv` las lee con
`get_cv_brief` cada vez que redacta o rehace ese CV. Como las de la carta: sustituyen a las
anteriores, vacías las borran y no son un hecho del candidato (lo que diga el CV sigue saliendo
del perfil)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.models import CvBrief
from app.models.base import utcnow
from app.schemas.cover_letter import MAX_INSTRUCTIONS
from app.services.documents import service


class CvBriefInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instructions: str = Field(default="", max_length=MAX_INSTRUCTIONS)


class CvBriefView(BaseModel):
    job_id: int
    instructions: str  # vacío: sin indicaciones
    updated_at: datetime | None


def get_brief(session: Session, job_id: int) -> CvBriefView:
    service._job(session, job_id)
    row = session.get(CvBrief, job_id)
    if row is None:
        return CvBriefView(job_id=job_id, instructions="", updated_at=None)
    return CvBriefView(job_id=job_id, instructions=row.instructions, updated_at=row.updated_at)


def save_brief(session: Session, job_id: int, brief: CvBriefInput) -> CvBriefView:
    """Guarda (o sustituye) las indicaciones del CV de la oferta. Sin evento: no cambia su etapa."""
    service._job(session, job_id)
    row = session.get(CvBrief, job_id)
    if row is None:
        row = CvBrief(job_id=job_id)
        session.add(row)
    row.instructions = brief.instructions.strip()
    row.updated_at = utcnow()
    session.flush()
    return get_brief(session, job_id)
