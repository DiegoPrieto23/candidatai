from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, utcnow


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    normalized_name: Mapped[str] = mapped_column(String(200), unique=True)
    ats_kind: Mapped[str | None] = mapped_column(String(32))
    ats_slug: Mapped[str | None] = mapped_column(String(200))
    watchlist: Mapped[bool] = mapped_column(default=False)


class CompanyResearch(Base):
    """Dosier de una empresa con fuentes de la web pública (fase 18, skill `research-company`).

    Uno por empresa (lo comparten todas sus ofertas); guardar otro lo sustituye. Lo redacta el
    agente a partir de páginas web, que son contenido no confiable: `risk_flags` marca si el texto
    guardado contiene frases de inyección. El código escribe además una copia en Markdown en
    `data/documentos/empresas/` (`file_name`).
    """

    __tablename__ = "company_research"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), unique=True)
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))  # desde qué oferta se pidió
    content: Mapped[dict[str, Any]] = mapped_column(JSON)  # `CompanyResearchContent`
    risk_flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    file_name: Mapped[str] = mapped_column(String(200))
    agent_name: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
