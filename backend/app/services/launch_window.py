"""Dónde va lo que lanza el botón principal de una acción: en el portal, sin ventana (por defecto,
si la acción y el agente pueden ir en segundo plano) o en una ventana del agente, para quien la
prefiera. Se guarda en `agent_preferences` (`scope="setting"`, `key="open_in_window"`, `"1"` en
`model`), como el umbral de la valoración: sobrevive a las actualizaciones.

Elegir «En terminal» o «En segundo plano» en el menú del botón sigue valiendo para esa vez.
"""

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AgentPreference

SCOPE, KEY = "setting", "open_in_window"


class WindowPreference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    open_in_window: bool


def _stored(session: Session) -> AgentPreference | None:
    return session.scalars(
        select(AgentPreference).where(AgentPreference.scope == SCOPE, AgentPreference.key == KEY)
    ).first()


def get(session: Session) -> WindowPreference:
    row = _stored(session)
    return WindowPreference(open_in_window=row is not None and row.model == "1")


def save(session: Session, value: WindowPreference) -> WindowPreference:
    row = _stored(session)
    stored = "1" if value.open_in_window else "0"
    if row is None:
        session.add(AgentPreference(scope=SCOPE, key=KEY, model=stored))
    else:
        row.model = stored
    session.flush()
    return get(session)
