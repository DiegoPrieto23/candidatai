"""Avisos al usuario: «completa el captcha en InfoJobs», «inicia sesión en…».

Los pide el agente al buscar ofertas (`request_user_action`) o el worker en una candidatura
asistida. La UI los enseña en un pop-up (y en una notificación del sistema, si la activaste) y tú
contestas «Ya está» o «Saltar». Quien lo pidió espera como mucho hasta `expires_at` (5 minutos por
defecto, `wait_user_action` en tramos cortos) y luego sigue: si no contestaste, ese paso se salta.

Nada aquí resuelve ni esquiva un captcha: solo te avisa para que lo hagas tú (POLICIES §5.3).
"""

import time
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import session_scope
from app.models import ApplicationAttempt, Source, UserPrompt
from app.models.base import utcnow

PromptKind = Literal["captcha", "anti_bot", "login_required"]
PromptStatus = Literal["pending", "done", "skipped", "expired"]
Outcome = Literal["done", "skipped"]

DEFAULT_TIMEOUT_SECONDS = 300
MAX_WAIT_SECONDS = 55  # cada llamada a `wait`: por debajo del timeout de una herramienta MCP
_POLL_SECONDS = 2.0

_TITLES: dict[str, str] = {
    "captcha": "Completa el captcha",
    "anti_bot": "La web pide comprobar que eres una persona",
    "login_required": "Inicia sesión",
}


class PromptNotFoundError(LookupError):
    pass


class PromptView(BaseModel):
    id: int
    kind: PromptKind
    title: str
    message: str
    url: str | None
    source_id: int | None
    source_name: str | None
    attempt_id: int | None
    status: PromptStatus
    created_at: datetime
    expires_at: datetime
    answered_at: datetime | None
    seconds_left: int  # hasta que caduca; 0 si ya no está pendiente


class PendingPrompts(BaseModel):
    prompts: list[PromptView]


def _expire(prompt: UserPrompt, now: datetime) -> None:
    if prompt.status == "pending" and prompt.expires_at <= now:
        prompt.status = "expired"


def _view(session: Session, prompt: UserPrompt, now: datetime | None = None) -> PromptView:
    now = now or utcnow()
    source = session.get(Source, prompt.source_id) if prompt.source_id else None
    pending = prompt.status == "pending"
    return PromptView(
        id=prompt.id,
        kind=prompt.kind,  # type: ignore[arg-type]
        title=_TITLES.get(prompt.kind, "Hace falta que hagas algo en el navegador"),
        message=prompt.message,
        url=prompt.url,
        source_id=prompt.source_id,
        source_name=source.name if source else None,
        attempt_id=prompt.attempt_id,
        status=prompt.status,  # type: ignore[arg-type]
        created_at=prompt.created_at,
        expires_at=prompt.expires_at,
        answered_at=prompt.answered_at,
        seconds_left=max(0, int((prompt.expires_at - now).total_seconds())) if pending else 0,
    )


def _get(session: Session, prompt_id: int) -> UserPrompt:
    prompt = session.get(UserPrompt, prompt_id)
    if prompt is None:
        raise PromptNotFoundError(f"No existe el aviso {prompt_id}.")
    return prompt


def request(
    session: Session,
    kind: PromptKind,
    message: str,
    url: str | None = None,
    source_id: int | None = None,
    attempt_id: int | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> PromptView:
    """Crea un aviso pendiente. Uno anterior para lo mismo (plataforma o intento) se da por
    caducado: solo vale el último."""
    if source_id is not None and session.get(Source, source_id) is None:
        raise PromptNotFoundError(f"No existe la plataforma {source_id}.")
    now = utcnow()
    for old in session.scalars(select(UserPrompt).where(UserPrompt.status == "pending")):
        same = (source_id is not None and old.source_id == source_id) or (
            attempt_id is not None and old.attempt_id == attempt_id
        )
        if same:
            old.status = "expired"
    prompt = UserPrompt(
        kind=kind,
        message=message.strip(),
        url=url,
        source_id=source_id,
        attempt_id=attempt_id,
        status="pending",
        created_at=now,
        expires_at=now + timedelta(seconds=timeout_seconds),
    )
    session.add(prompt)
    session.flush()
    return _view(session, prompt, now)


def get(session: Session, prompt_id: int) -> PromptView:
    prompt = _get(session, prompt_id)
    now = utcnow()
    _expire(prompt, now)
    return _view(session, prompt, now)


def wait(prompt_id: int, max_seconds: int = 50) -> PromptView:
    """Espera a que contestes o caduque, como mucho `max_seconds` (≤ 55). Devuelve el estado:
    si sigue `pending`, vuelve a llamar hasta que deje de estarlo."""
    deadline = time.monotonic() + min(max(max_seconds, 0), MAX_WAIT_SECONDS)
    while True:
        with session_scope() as session:
            view = get(session, prompt_id)
        if view.status != "pending" or time.monotonic() >= deadline:
            return view
        time.sleep(min(_POLL_SECONDS, max(0.0, deadline - time.monotonic())))


def list_pending(session: Session) -> PendingPrompts:
    """Los avisos que esperan tu respuesta (los caducados se marcan al consultarlos)."""
    now = utcnow()
    rows = list(
        session.scalars(
            select(UserPrompt).where(UserPrompt.status == "pending").order_by(UserPrompt.id)
        )
    )
    for row in rows:
        _expire(row, now)
    return PendingPrompts(prompts=[_view(session, r, now) for r in rows if r.status == "pending"])


def answer(session: Session, prompt_id: int, outcome: Outcome) -> PromptView:
    """Tu respuesta en la UI: «Ya está» (`done`) o «Saltar» (`skipped`). En una candidatura
    asistida, «Ya está» vuelve a rellenar la página que tienes delante."""
    prompt = _get(session, prompt_id)
    now = utcnow()
    _expire(prompt, now)
    if prompt.status != "pending":
        raise ValueError(f"Este aviso ya no está pendiente («{prompt.status}»).")
    prompt.status = outcome
    prompt.answered_at = now
    session.flush()
    if outcome == "done" and prompt.attempt_id is not None:
        from app.services.applier import service as applier

        attempt = session.get(ApplicationAttempt, prompt.attempt_id)
        if attempt is not None and applier._fill_page_problem(session, attempt) is None:
            applier.fill_page(session, prompt.attempt_id)
    return _view(session, prompt, now)
