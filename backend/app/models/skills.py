from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, utcnow


class SkillGapMark(Base):
    """Lo que el usuario dijo de una skill que piden las ofertas y el perfil no cubre (fase 14).

    `gap`: «No la tengo», un hueco real que va al plan de formación. `have`: «La tengo», pendiente
    de que su agente la añada al perfil con `update-profile`. Se identifica por la forma
    canónica plegada de la skill (`skill_key`), la misma con la que compara el matching.
    """

    __tablename__ = "skill_gap_marks"

    id: Mapped[int] = mapped_column(primary_key=True)
    skill_key: Mapped[str] = mapped_column(String(200), unique=True)
    skill_name: Mapped[str] = mapped_column(String(200))  # como la escriben las ofertas
    status: Mapped[str] = mapped_column(String(8))  # gap | have
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
