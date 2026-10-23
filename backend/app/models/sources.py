from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, event, select
from sqlalchemy.orm import Mapped, Session, mapped_column

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


class PriorityConflictError(ValueError):
    """Dos plataformas con el mismo puesto en el orden de recorrido (fase 27.3)."""


@event.listens_for(Session, "before_flush")
def _unique_platform_priority(session: Session, _context: object, _instances: object) -> None:
    """Red de seguridad (fase 27.3): ningún flush deja dos plataformas `agent_browse` con la misma
    prioridad. El orden se mantiene en `browse.place`; esto solo para un camino que escriba
    `config` por fuera de él. Es una restricción que SQLite no puede expresar sobre un JSON."""
    touched = [
        obj
        for obj in (*session.new, *session.dirty)
        if isinstance(obj, Source) and obj.kind == "agent_browse"
    ]
    if not touched:
        return
    with session.no_autoflush:
        stored = session.scalars(select(Source).where(Source.kind == "agent_browse")).all()
    # Primero las que no cambian: el error nombra a la que ya tenía el puesto.
    ordered = [s for s in stored if s not in touched and s not in session.deleted] + touched
    holders: dict[int, Source] = {}
    for source in ordered:
        priority = (source.config or {}).get("priority")
        if not isinstance(priority, int) or isinstance(priority, bool):
            continue
        if (holder := holders.get(priority)) is not None and holder is not source:
            raise PriorityConflictError(
                f"El puesto {priority} ya lo tiene «{holder.name}»: «{source.name}» no puede "
                "tener la misma prioridad."
            )
        holders[priority] = source


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


class EmailMessage(Base):
    """Correo de alertas ya procesado. Solo su `Message-ID`, nunca el cuerpo."""

    __tablename__ = "email_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(String(998), unique=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    received_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    jobs_found: Mapped[int] = mapped_column(default=0)
    processed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
