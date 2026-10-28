from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, false
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
    # Editado por el usuario en la UI (respuestas, cartas): sin verificación del agente.
    edited_by_user: Mapped[bool] = mapped_column(default=False, server_default=false())
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


class CvBrief(Base):
    """Indicaciones del usuario para el CV de una oferta («destaca el proyecto X», «en inglés»…),
    que escribe en la ficha. Las usa `generate-cv` cada vez que redacta o rehace ese CV."""

    __tablename__ = "cv_briefs"

    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    instructions: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class CoverLetterBrief(Base):
    """Indicaciones de la carta para una oferta (fase 08c). Sin historial: el documento copia las
    que usó al guardarse."""

    __tablename__ = "cover_letter_briefs"

    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    instructions: Mapped[str] = mapped_column(Text, default="")
    max_words: Mapped[int | None]
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
