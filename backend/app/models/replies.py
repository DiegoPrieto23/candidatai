from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, utcnow


class Reply(Base):
    """Correo de una empresa de uno de tus procesos (fase 15). Contenido no confiable.

    Solo se guardan los correos que casan con una candidatura enviada (`candidates`). El agente
    guarda una propuesta (`proposal`) y nada cambia de etapa hasta que el usuario la acepta en la
    UI: entonces `event_id` apunta al evento registrado.
    """

    __tablename__ = "replies"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(String(998), unique=True)
    origin: Mapped[str] = mapped_column(String(8))  # imap | local
    sender: Mapped[str] = mapped_column(String(320))  # dirección, en minúsculas
    sender_name: Mapped[str] = mapped_column(String(200), default="")
    subject: Mapped[str] = mapped_column(String(300), default="")
    received_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    body_text: Mapped[str] = mapped_column(Text, default="")
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    risk_excerpt: Mapped[str | None] = mapped_column(String(300))
    # [{job_id, reason}] de la coincidencia más fiable a la menos.
    candidates: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(12), default="new", index=True)
    proposal: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    proposed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    proposed_by: Mapped[str | None] = mapped_column(String(64))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), index=True)
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class MessageDraft(Base):
    """Borrador de un mensaje para el usuario. La app nunca lo envía: el usuario lo copia y, si es
    un seguimiento, marca que lo envió (`followup_sent`).

    Fase 15: seguimiento o agradecimiento. Fase 18: mensaje de LinkedIn (≤ 300 caracteres, sin
    asunto) o correo de candidatura (con adjuntos) a un recruiter, al responsable o a un compañero.
    """

    __tablename__ = "message_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # followup | thank_you | linkedin | email
    milestone_id: Mapped[int | None] = mapped_column(ForeignKey("milestones.id"))
    subject: Mapped[str | None] = mapped_column(String(300))  # sin asunto en LinkedIn
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="draft")  # draft | sent | discarded
    event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"))
    agent_name: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    # Fase 18: a quién va (papel y, si existe, el contacto del proceso o la persona de la red) y
    # qué adjuntos menciona un correo de candidatura (solo nombres: la app no adjunta nada).
    recipient_role: Mapped[str | None] = mapped_column(String(16))  # recruiter|hiring_manager|peer
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"))
    network_contact_id: Mapped[int | None] = mapped_column(ForeignKey("network_contacts.id"))
    # El nombre al guardarlo: sigue aunque la persona salga de la red al reimportar.
    recipient_name: Mapped[str | None] = mapped_column(String(200))
    attachments: Mapped[list[str] | None] = mapped_column(JSON)
