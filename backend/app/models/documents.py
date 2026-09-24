from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, utcnow


class Document(Base):
    """CV, carta o respuestas generados para una oferta. Rutas relativas a `data/`."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    profile_version_id: Mapped[int] = mapped_column(ForeignKey("profile_versions.id"))
    kind: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(8))
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    docx_path: Mapped[str | None] = mapped_column(String(500))
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    pages: Mapped[int | None]
    verification: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
