from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, utcnow


class Source(Base):
    """Origen de ofertas (alta manual o conector de un ATS o portal)."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(200))
    config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class SourceRun(Base):
    """Una ejecución de una fuente: lo encontrado, lo que pasó el filtro previo y lo nuevo."""

    __tablename__ = "source_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    actor: Mapped[str] = mapped_column(String(16))  # `system` (worker), `user`, `agent`
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    found: Mapped[int] = mapped_column(default=0)
    after_filters: Mapped[int] = mapped_column(default=0)
    created: Mapped[int] = mapped_column(default=0)
    completed: Mapped[int] = mapped_column(default=0)  # resúmenes completados (fase 09b)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
