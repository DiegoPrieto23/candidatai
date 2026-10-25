from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, utcnow


class Job(Base):
    """Oferta de empleo. `raw_text` es contenido no confiable."""

    __tablename__ = "jobs"
    # Los conectores reconocen una oferta ya vista por su id en la fuente; alertas, captura y
    # búsqueda con navegador, por su id en la plataforma (fase 09b).
    __table_args__ = (
        Index("ix_jobs_source_external", "source_id", "external_id"),
        Index(
            "uq_jobs_platform_external",
            "platform",
            "external_id",
            unique=True,
            sqlite_where=text("platform IS NOT NULL AND external_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    external_id: Mapped[str | None] = mapped_column(String(200))
    # Portal donde se publica (`linkedin`, `infojobs`…), si se reconoce por la URL.
    platform: Mapped[str | None] = mapped_column(String(32))
    # `summary`: solo título, empresa, ubicación y enlace (alertas por correo); `full`: con texto.
    detail_level: Mapped[str] = mapped_column(String(16), default="full", server_default="full")
    url: Mapped[str] = mapped_column(String(2000))
    title: Mapped[str] = mapped_column(String(500))
    location_raw: Mapped[str | None] = mapped_column(String(500))
    raw_text: Mapped[str] = mapped_column(Text)
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    duplicate_of: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    posted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    # Observaciones del código que no son riesgo de inyección (fase 16):
    # `possibly_closed`, `liveness`, `open_confirmed` y `reposted`. Ver `services/liveness.py`.
    signals: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default=text("'{}'"))


class JobSighting(Base):
    """Cada vez que se ve una publicación de una oferta (fase 16): la primera, al darla de alta, y
    las siguientes si reaparece con otro id o URL en el mismo canal. Sirve para `reposted`."""

    __tablename__ = "job_sightings"
    __table_args__ = (UniqueConstraint("job_id", "channel", "ref"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    # Plataforma (`infojobs`…) o dominio de la URL (`boards.greenhouse.io`).
    channel: Mapped[str] = mapped_column(String(200))
    # Id en la plataforma o URL sin parámetros: qué publicación concreta se vio.
    ref: Mapped[str] = mapped_column(String(2000))
    seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class JobExtraction(Base):
    """Una fila por extracción; la vigente es la más reciente."""

    __tablename__ = "job_extractions"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)
    schema_version: Mapped[int]
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
