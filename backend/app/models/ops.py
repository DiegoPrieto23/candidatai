from datetime import datetime
from typing import Any

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, utcnow


class Task(Base):
    """Cola de trabajo del worker (sin Redis)."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(default=0)
    run_after: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_error: Mapped[str | None] = mapped_column(Text)


class McpCall(Base):
    """Auditoría de la interfaz para agentes. Nunca guarda texto crudo ni datos del perfil."""

    __tablename__ = "mcp_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel: Mapped[str] = mapped_column(String(8))
    client_name: Mapped[str | None] = mapped_column(String(64))
    tool: Mapped[str] = mapped_column(String(64))
    args_summary: Mapped[str | None] = mapped_column(Text)
    job_id: Mapped[int | None] = mapped_column(index=True)
    ok: Mapped[bool]
    error: Mapped[str | None] = mapped_column(Text)
    called_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
