from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, utcnow


class Milestone(Base):
    """Hito con fecha de un proceso: entrevista, prueba, plazo u otro (fase 10).

    Crear una entrevista o una prueba registra su evento (`interview_scheduled`,
    `test_assigned`) con `payload.milestone_id`; `event_id` apunta a ese evento.
    """

    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # interview | test | deadline | other
    title: Mapped[str] = mapped_column(String(200))
    starts_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Todo el día: `starts_at` es las 00:00 de ese día en Europe/Madrid.
    all_day: Mapped[bool] = mapped_column(default=False)
    location: Mapped[str | None] = mapped_column(String(500))  # dirección o enlace
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="scheduled")  # scheduled|done|cancelled
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    # SEQUENCE del iCalendar: sube en cada cambio para que el calendario lo actualice.
    sequence: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Contact(Base):
    """Persona de contacto en un proceso (recruiter, hiring manager…). Datos solo locales."""

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(50))
    linkedin: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
