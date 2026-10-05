from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, utcnow


class ApplicationAttempt(Base):
    """Un intento de candidatura asistida (fase 11): rellenar, revisar y, si confirmas, enviar.

    El estado de la oferta sigue saliendo de los eventos (`application_filled`, `applied`); esta
    tabla guarda lo que necesita la pantalla de revisión y el token de envío (solo su hash).
    """

    __tablename__ = "application_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    # greenhouse | lever | ashby | generic | linkedin | unknown
    platform: Mapped[str] = mapped_column(String(16))
    # `fill`: rellenar y revisar; `open`: solo abrir la URL (LinkedIn y webs desconocidas).
    mode: Mapped[str] = mapped_column(String(8), default="fill")
    url: Mapped[str] = mapped_column(String(2000))
    # queued | filling | ready | needs_user | failed | submitting | submitted | submit_failed |
    # submit_unconfirmed | manual | manual_done | cancelled
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    fields: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    screenshot_path: Mapped[str | None] = mapped_column(String(500))  # relativo a `data/`
    confirmation_path: Mapped[str | None] = mapped_column(String(500))
    token_hash: Mapped[str | None] = mapped_column(String(64))
    token_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    token_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
