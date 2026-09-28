from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, utcnow


class Event(Base):
    """Fuente de verdad del estado de una oferta. Se escribe solo con `services.events.record()`."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_events_job_id_occurred_at", "job_id", "occurred_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"))
    type: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(16))
    agent_name: Mapped[str | None] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Application(Base):
    """Proyección del estado de candidatura; se recalcula desde `events`."""

    __tablename__ = "applications"

    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), primary_key=True)
    stage: Mapped[str] = mapped_column(String(32), index=True)
    channel: Mapped[str | None] = mapped_column(String(32))
    render_id: Mapped[int | None] = mapped_column(ForeignKey("document_renders.id"))
    applied_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    last_event_at: Mapped[datetime] = mapped_column(UTCDateTime)
