"""El idioma del portal, también para lo que se lanza sin él (worker, tareas programadas).

La UI lo manda al lanzar algo (`lang`) y cuando se cambia en el portal; se guarda como una
preferencia más (`agent_preferences`, `scope = "setting"`, `key = "ui_lang"`, el idioma en
`model`). Decide el idioma de la orden del agente, del título de su ventana y de la consola de
`cai start`. El del CV y la carta lo sigue decidiendo la oferta.

Prioridad: el `lang` de la petición (que se guarda antes de lanzar) > la preferencia guardada >
`CAI_LANG` > el idioma del sistema.
"""

import locale
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AgentPreference

Lang = Literal["es", "en"]
LANGS: tuple[Lang, ...] = ("es", "en")
SCOPE = "setting"
KEY = "ui_lang"


def _stored(session: Session) -> AgentPreference | None:
    return session.scalars(
        select(AgentPreference).where(AgentPreference.scope == SCOPE, AgentPreference.key == KEY)
    ).first()


def saved(session: Session) -> Lang | None:
    """El idioma guardado, si lo hay y es uno de los conocidos."""
    row = _stored(session)
    value = row.model if row else None
    return value if value in LANGS else None  # type: ignore[return-value]


def save(session: Session, lang: Lang) -> Lang:
    """Guarda el idioma del portal (si no cambia, no escribe)."""
    row = _stored(session)
    if row is None:
        session.add(AgentPreference(scope=SCOPE, key=KEY, model=lang))
    elif row.model != lang:
        row.model = lang
    session.flush()
    return lang


def fallback() -> Lang:
    """Sin preferencia guardada: `CAI_LANG` si está; si no, español con el sistema en español e
    inglés con cualquier otro."""
    chosen = get_settings().lang
    if chosen is not None:
        return chosen
    system = (locale.getlocale()[0] or "").lower()
    return "es" if system.startswith(("es", "spanish")) else "en"


def current(session: Session) -> Lang:
    """El idioma con el que se escribe lo que se lanza ahora."""
    return saved(session) or fallback()
