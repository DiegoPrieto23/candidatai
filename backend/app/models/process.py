from datetime import date, datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text
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
    # Entrevistas (fase 17): plan de preparación (`services/interviews.py`) y repaso posterior.
    # `notes` es lo que anota el usuario en el formulario; el repaso va aparte.
    prep_plan: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    # Guía de preparación en PDF (`services/interview_guide.py`).
    prep_guide: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    debrief_notes: Mapped[str | None] = mapped_column(Text)
    next_steps: Mapped[str | None] = mapped_column(Text)
    debriefed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Contact(Base):
    """Persona de contacto en un proceso (recruiter, hiring manager…). Datos solo locales.

    Fase 18: `relation` es su papel en el proceso (`referral`, `recruiter`, `hiring_manager`),
    `referral` marca si se le pidió o dio una referencia (no es un evento: no cambia la etapa) y
    `network_contact_id`, la persona de tu red de LinkedIn de la que sale, si sale de ahí.
    """

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
    relation: Mapped[str | None] = mapped_column(String(16))
    referral: Mapped[str | None] = mapped_column(String(16))  # requested | given
    referral_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    network_contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("network_contacts.id"), index=True
    )


class NetworkContact(Base):
    """Una persona de tu red de LinkedIn, de la exportación oficial `Connections.csv` (fase 18).

    Separada de los contactos de cada proceso: se cruza con las ofertas por la empresa normalizada
    (`company_key`). Sin email: aunque la exportación lo traiga, no se guarda.
    """

    __tablename__ = "network_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(200))
    last_name: Mapped[str] = mapped_column(String(200), default="")
    linkedin_url: Mapped[str | None] = mapped_column(String(500), unique=True)
    company: Mapped[str | None] = mapped_column(String(200))
    company_key: Mapped[str | None] = mapped_column(String(200), index=True)
    position: Mapped[str | None] = mapped_column(String(300))
    connected_on: Mapped[date | None]
    imported_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class ReceivedOffer(Base):
    """La oferta que ha hecho la empresa de un proceso (fase 21). Solo la escribe el usuario.

    Una por oferta de empleo: si la empresa la mejora, se sobrescribe (el cambio queda como nota en
    el historial). Con `amounts_private` (por defecto), fijo y variable no salen nunca por la
    interfaz para agentes; la comparación con `private.salary_floor_eur` solo la ve la UI.
    """

    __tablename__ = "received_offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), unique=True)
    base_salary: Mapped[int | None] = mapped_column()  # fijo bruto
    variable: Mapped[int | None] = mapped_column()  # variable o bonus bruto objetivo, anual
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    period: Mapped[str] = mapped_column(String(8), default="year")  # del fijo: year | month
    benefits: Mapped[str | None] = mapped_column(Text)
    work_mode: Mapped[str | None] = mapped_column(String(16))  # remote | hybrid | onsite
    location: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date | None] = mapped_column()
    respond_by: Mapped[date | None] = mapped_column()
    notes: Mapped[str | None] = mapped_column(Text)
    amounts_private: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
