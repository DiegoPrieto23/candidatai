from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, utcnow


class Document(Base):
    """Contenido de un CV, carta o respuestas para una oferta (lo que escribe el agente).

    La presentación (plantilla, opciones y ficheros) va en `DocumentRender`.
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    profile_version_id: Mapped[int] = mapped_column(ForeignKey("profile_versions.id"))
    kind: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(8))
    content: Mapped[dict[str, Any]] = mapped_column(JSON)
    verification: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class DocumentRender(Base):
    """Una combinación ya generada de contenido + plantilla + opciones. Rutas relativas a data/."""

    __tablename__ = "document_renders"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    template_id: Mapped[str] = mapped_column(String(64))
    template_hash: Mapped[str] = mapped_column(String(64))
    options: Mapped[dict[str, Any]] = mapped_column(JSON)
    docx_path: Mapped[str | None] = mapped_column(String(500))
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    pages: Mapped[int]
    keyword_coverage: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    selected: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
