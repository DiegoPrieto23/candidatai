from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, utcnow


class AgentRun(Base):
    """Una ejecución del agente en segundo plano (fase 19, ADR-032), lanzada desde la UI.

    Es su propia cola: el worker las ejecuta de una en una. `command` es lo que se lanza (para
    auditar qué herramientas tenía); `progress`, líneas cortas con las herramientas que usó, nunca
    sus entradas. `questions`: lo que el skill necesita del usuario para seguir (`needs_user`).
    """

    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(40))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), index=True)
    milestone_id: Mapped[int | None] = mapped_column(ForeignKey("milestones.id"))
    agent: Mapped[str] = mapped_column(String(32))
    # Fase 24.4: el modelo o el preset con que se lanzó (`None`: el que use el agente por defecto).
    model: Mapped[str | None] = mapped_column(String(100))
    preset: Mapped[str | None] = mapped_column(String(40))
    # queued | running | done | needs_user | failed | cancelled | timeout
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    prompt: Mapped[str] = mapped_column(Text)
    command: Mapped[list[str]] = mapped_column(JSON)
    unset_env: Mapped[list[str]] = mapped_column(JSON, default=list)
    output_format: Mapped[str] = mapped_column(String(32))
    session_id: Mapped[str | None] = mapped_column(String(64))
    progress: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    result: Mapped[str | None] = mapped_column(Text)
    questions: Mapped[list[str]] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSON)  # turnos, duración, coste estimado
    cancel_requested: Mapped[bool] = mapped_column(default=False)
    pid: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class AgentRequest(Base):
    """Un encargo que la UI deja para la próxima sesión interactiva del agente (fase 19).

    La orden la compone la app (`agent_launch.ACTIONS`), como en los botones: ningún texto de una
    oferta. El agente los lee con `list_agent_requests` y los cierra con `complete_agent_request`.
    """

    __tablename__ = "agent_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(40))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"), index=True)
    milestone_id: Mapped[int | None] = mapped_column(ForeignKey("milestones.id"))
    prompt: Mapped[str] = mapped_column(Text)
    # pending | done | cancelled
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    summary: Mapped[str | None] = mapped_column(Text)  # lo que dice el agente al cerrarlo
    agent_name: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class AgentPreference(Base):
    """Preferencias de agente y modelo de la persona (fase 24.4, ADR-037). Datos de uso: viven en
    `data/`, nunca en el repositorio ni en la configuración generada.

    `scope`: `default` (`key` vacía: el agente por defecto), `agent` (`key` = agente: su modelo o
    preset) o `action` (`key` = acción: su agente y, si quieres, su modelo o preset).
    """

    __tablename__ = "agent_preferences"
    __table_args__ = (UniqueConstraint("scope", "key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(16))
    key: Mapped[str] = mapped_column(String(40), default="")
    agent: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(100))
    preset: Mapped[str | None] = mapped_column(String(40))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
