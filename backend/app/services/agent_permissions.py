"""Permisos desde el portal (fase 48.1b).

Sin ventana, el agente no tiene a quién pedir permiso. Los agentes que saben delegar esa pregunta
en una herramienta (en Claude Code, `--permission-prompt-tool`) llaman a `request_permission`: la
app la enseña en el panel de la ejecución con «Permitir una vez», «Permitir siempre en este
proyecto» y «Denegar», espera la respuesta y la devuelve. Sin respuesta en `TIMEOUT_SECONDS`, se
deniega.

- Lo que el techo de la acción deniega no llega aquí: el agente lo deniega sin preguntar.
- Un permiso del agente nunca sustituye la confirmación de una acción protegida (enviar, aplicar:
  POLICIES §5) ni activa LinkedIn: eso no son herramientas del agente, sino botones de la UI.
- «Siempre» se guarda en la app (`agent_permission_rules`), no en la configuración del agente, y
  se quita desde la página «Agente». Queda registrado quién permitió qué: el aviso (`user_prompts`,
  con la herramienta, lo que pedía, la respuesta y cuándo) y la llamada (`mcp_calls`).

La ejecución sale de `CAI_RUN_ID`, que el runner pone en el entorno del agente (y este, en el del
servidor MCP). Sin ejecución en curso, se deniega: fuera del portal, el agente pregunta en su
ventana.
"""

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.models import AgentPermissionRule, AgentRun, UserPrompt
from app.models.base import utcnow
from app.services import prompts

RUN_ENV = "CAI_RUN_ID"
TIMEOUT_SECONDS = 300
DETAIL_CHARS = 500
_POLL_SECONDS = 1.0
# El campo de la entrada que dice qué quiere hacer, en las herramientas conocidas.
_KEY_FIELDS = ("command", "file_path", "path", "url", "skill", "pattern", "subagent_type", "query")
# Las herramientas que puede tener una ejecución sin ventana (`--tools Skill,Agent,Read`): las
# únicas en las que se ofrece «Permitir siempre». Una petición inventada con otro nombre (el agente
# también puede llamar a `request_permission`) solo se puede permitir una vez.
ALWAYS_TOOLS = frozenset({"Read", "Skill", "Agent"})

Behavior = Literal["allow", "deny"]


class PermissionDecision(BaseModel):
    """Lo que espera el agente: permitir (con la entrada tal cual) o denegar con un motivo."""

    behavior: Behavior
    updatedInput: dict[str, Any] | None = None  # noqa: N815 - el nombre lo fija el agente
    message: str | None = None


class PermissionRuleView(BaseModel):
    id: int
    tool: str
    detail: str
    created_at: datetime


class PermissionRules(BaseModel):
    rules: list[PermissionRuleView]


class RuleNotFoundError(LookupError):
    pass


def _full_detail(tool_input: dict[str, Any]) -> str:
    for key in _KEY_FIELDS:
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return json.dumps(tool_input, ensure_ascii=False, sort_keys=True) if tool_input else ""


def describe(tool_name: str, tool_input: dict[str, Any]) -> str:
    """Qué quiere hacer, en una línea: el comando, el fichero, la URL o el skill; si no, la
    entrada entera, recortada."""
    text = _full_detail(tool_input) or tool_name
    return text if len(text) <= DETAIL_CHARS else text[: DETAIL_CHARS - 1] + "…"


def can_always(tool_name: str, tool_input: dict[str, Any]) -> bool:
    """Si se ofrece «Permitir siempre»: solo en las herramientas que puede tener una ejecución sin
    ventana (`ALWAYS_TOOLS`), cuando la entrada entera es su campo clave y cabe sin recortar. Así
    una regla nunca cubre más de lo que se vio (otro contenido sobre el mismo fichero, otro
    comando con el mismo principio)."""
    if tool_name not in ALWAYS_TOOLS:
        return False
    keys = [key for key in _KEY_FIELDS if isinstance(tool_input.get(key), str)]
    extra = set(tool_input) - set(keys) - {"description"}  # la descripción no cambia lo que hace
    detail = _full_detail(tool_input)
    return len(keys) == 1 and not extra and 0 < len(detail) <= DETAIL_CHARS


def current_run(session: Session) -> AgentRun | None:
    """La ejecución en curso de `CAI_RUN_ID`, o `None`."""
    raw = os.environ.get(RUN_ENV, "")
    if not raw.isdigit():
        return None
    run = session.get(AgentRun, int(raw))
    return run if run is not None and run.status == "running" else None


def current_run_id(session: Session) -> int | None:
    run = current_run(session)
    return run.id if run is not None else None


def _rule(session: Session, tool: str, detail: str) -> AgentPermissionRule | None:
    return session.scalars(
        select(AgentPermissionRule).where(
            AgentPermissionRule.tool == tool, AgentPermissionRule.detail == detail
        )
    ).first()


def _allow(tool_input: dict[str, Any]) -> PermissionDecision:
    return PermissionDecision(behavior="allow", updatedInput=tool_input)


def _deny(message: str) -> PermissionDecision:
    return PermissionDecision(behavior="deny", message=message)


@dataclass(frozen=True)
class _Asked:
    """Lo que pasó al ir a preguntar: ya permitido siempre, sin ejecución a la que preguntar, o el
    aviso que espera respuesta (`prompt_id`)."""

    allowed: bool = False
    prompt_id: int | None = None


def _ask(tool_name: str, tool_input: dict[str, Any], detail: str) -> _Asked:
    """Deja el permiso a la vista en el portal, en su propia transacción para que la UI lo vea
    ya."""
    tool = tool_name[:80]
    with session_scope() as session:
        if can_always(tool_name, tool_input) and _rule(session, tool, detail) is not None:
            return _Asked(allowed=True)
        run = current_run(session)
        if run is None:
            return _Asked()
        now = utcnow()
        options = [
            a
            for a in prompts.PERMISSION_ANSWERS
            if a != "always" or can_always(tool_name, tool_input)
        ]
        prompt = UserPrompt(
            kind="permission",
            message=detail,
            tool=tool,
            run_id=run.id,
            job_id=run.job_id,
            options=options,
            status="pending",
            created_at=now,
            expires_at=now + timedelta(seconds=TIMEOUT_SECONDS),
        )
        session.add(prompt)
        session.flush()
        return _Asked(prompt_id=prompt.id)


def request(
    tool_name: str,
    tool_input: dict[str, Any],
    timeout: float = TIMEOUT_SECONDS,
    poll: float = _POLL_SECONDS,
) -> PermissionDecision:
    """Pregunta en el portal y espera la respuesta (como mucho `timeout`). Si la ejecución deja de
    estar en curso mientras espera (la detienen, falla), el aviso caduca y se deniega."""
    detail = describe(tool_name, tool_input)
    asked = _ask(tool_name, tool_input, detail)
    if asked.allowed:
        return _allow(tool_input)
    if asked.prompt_id is None:
        return _deny("No hay ninguna ejecución sin ventana en curso a la que preguntar.")
    deadline = time.monotonic() + timeout
    while True:
        with session_scope() as session:
            row = session.get(UserPrompt, asked.prompt_id)
            assert row is not None
            run = session.get(AgentRun, row.run_id) if row.run_id else None
            gone = run is None or run.status != "running"
            if row.status == "pending" and (gone or time.monotonic() >= deadline):
                row.status = "expired"
                session.flush()
            view = prompts.get(session, asked.prompt_id)
            if view.status != "pending":
                return _decide(session, view, tool_name, tool_input, detail)
        time.sleep(poll)


def _decide(
    session: Session,
    view: prompts.PromptView,
    tool_name: str,
    tool_input: dict[str, Any],
    detail: str,
) -> PermissionDecision:
    if view.status == "expired":
        return _deny(
            "Nadie ha contestado en el portal a tiempo: denegado. Sigue sin ello o termina "
            "explicando qué necesitabas."
        )
    if view.answer == "always":
        # Solo se guarda donde se ofrecía; si no, vale como «una vez».
        tool = tool_name[:80]
        if can_always(tool_name, tool_input) and _rule(session, tool, detail) is None:
            session.add(AgentPermissionRule(tool=tool, detail=detail))
        return _allow(tool_input)
    if view.answer == "once":
        return _allow(tool_input)
    return _deny("Denegado desde el portal. Sigue sin ello o termina explicando qué necesitabas.")


def list_rules(session: Session) -> PermissionRules:
    rows = session.scalars(select(AgentPermissionRule).order_by(AgentPermissionRule.id)).all()
    return PermissionRules(
        rules=[
            PermissionRuleView(id=r.id, tool=r.tool, detail=r.detail, created_at=r.created_at)
            for r in rows
        ]
    )


def delete_rule(session: Session, rule_id: int) -> PermissionRules:
    row = session.get(AgentPermissionRule, rule_id)
    if row is None:
        raise RuleNotFoundError(f"No existe el permiso {rule_id}.")
    session.delete(row)
    session.flush()
    return list_rules(session)
