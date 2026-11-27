from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, utcnow


class AgentRun(Base):
    """Una ejecución del agente en segundo plano (fase 19), lanzada desde la UI.

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
    # Fase 24.5: con techo por configuración, cómo se escribe la de la ejecución (formato,
    # variable de entorno, agente y prefijo MCP). `None`: el techo va en `command`.
    run_config: Mapped[dict[str, str] | None] = mapped_column(JSON)
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


class AgentRunEvent(Base):
    """Un paso de la conversación de una ejecución en segundo plano, para verla en el portal.

    `kind`: `system` (arranque), `tool_start`, `tool_result`, `text` (lo que escribe el agente),
    `user`, `question`, `permission`, `result` o `error`. `seq` ordena los de una ejecución. De
    las herramientas solo se guarda el nombre, un detalle corto (el skill, el subagente, el
    fichero) y si fueron bien, nunca su entrada ni su salida: pueden llevar texto de una oferta.
    `text` es contenido del agente, no confiable: la UI lo pinta como texto plano. `sub`: lo hizo
    un subagente.
    """

    __tablename__ = "agent_run_events"
    __table_args__ = (UniqueConstraint("run_id", "seq"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    seq: Mapped[int]
    at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    kind: Mapped[str] = mapped_column(String(16))
    tool: Mapped[str | None] = mapped_column(String(80))
    text: Mapped[str | None] = mapped_column(Text)
    ok: Mapped[bool | None]
    sub: Mapped[bool] = mapped_column(default=False)


class AgentTask(Base):
    """Lo que un botón acaba de lanzar y de lo que hay que avisar (`services/agent_tasks.py`).

    `total`: lo pendiente al pulsar, en las acciones por lotes. `run_id`: la ejecución, si va en
    segundo plano. `outcome`: lo que dijo el agente con `finish_task`. `dismissed_at`: ya cerrado.
    """

    __tablename__ = "agent_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(40))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    milestone_id: Mapped[int | None]
    run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id"))
    total: Mapped[int] = mapped_column(default=0)
    outcome: Mapped[str | None] = mapped_column(String(16))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    dismissed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)


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


class AssistantConversation(Base):
    """Una conversación del «Asistente» (fase 43.3): sus peticiones van en orden y el agente recibe
    las anteriores como contexto. `title`: el principio de la primera pregunta, sin llamar a ningún
    modelo. No caduca: se borra a mano desde el panel."""

    __tablename__ = "assistant_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)


class AssistantRequest(Base):
    """Lo que el usuario escribe en «Asistente», en la ayuda del portal.

    El texto se queda aquí: la orden del agente solo lleva el `id`, y el skill `assistant` lo lee
    con `get_assistant_request`. `run_id`: la ejecución en segundo plano (`mode = background`);
    `request_id`: el encargo para la próxima sesión (`mode = session`). Con `mode = terminal`, el
    agente se abre en una ventana y no hay ninguna de las dos: `cancelled_at` marca que se canceló
    desde el panel. `answer` y `links`: lo que deja el agente con `save_assistant_answer`. Cada
    una va en una conversación (`conversation_id`).
    """

    __tablename__ = "assistant_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("assistant_conversations.id", name="fk_assistant_requests_conversation_id"),
        index=True,
    )
    text: Mapped[str] = mapped_column(Text)
    mode: Mapped[str] = mapped_column(String(16))  # background | session | terminal
    run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id"), index=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("agent_requests.id"))
    answer: Mapped[str | None] = mapped_column(Text)
    links: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    agent_name: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    cancelled_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class AgentPreference(Base):
    """Preferencias de agente y modelo de la persona (fase 24.4). Datos de uso: viven en
    `data/`, nunca en el repositorio ni en la configuración generada.

    `scope`: `default` (`key` vacía: el agente por defecto), `agent` (`key` = agente: su modelo o
    preset) o `action` (`key` = acción: su agente y, si quieres, su modelo o preset). Fase 24.6:
    `tier` (`key` = `<nivel>:<acción>`: el agente y modelo de esa acción en un nivel de gasto) y
    `tier_undo` (`key` = acción: las preferencias por acción de antes de aplicar un nivel). Fase
    25.4: `setting` (`key="assess_min_score"`: el umbral de la valoración en segundo plano, el
    número en `model`), y también `extra_matching` y `browse_max_offers` (las ofertas por
    portal de las plataformas nuevas, de «Buscar ofertas»).
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
