"""Cuántas ofertas abre el agente en cada portal (`max_offers` de las plataformas `agent_browse`).

Cada plataforma guarda el suyo. Desde el panel de «Buscar ofertas» se cambia el de varias a la vez,
y ese número pasa a ser el de las plataformas nuevas: se guarda en `agent_preferences`
(`scope="setting"`, `key="browse_max_offers"`, el número en `model`), como el umbral de la
valoración. Sin él, manda `agent_browse.default_max_offers` de `config/policies.yaml`.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.models import AgentPreference

SCOPE, KEY = "setting", "browse_max_offers"
MIN, MAX = 1, 100


def _stored(session: Session) -> AgentPreference | None:
    return session.scalars(
        select(AgentPreference).where(AgentPreference.scope == SCOPE, AgentPreference.key == KEY)
    ).first()


def default_max_offers(session: Session) -> int:
    """El de las plataformas nuevas: el último que elegiste para todas o el de las políticas."""
    row = _stored(session)
    try:
        value = int(row.model) if row is not None and row.model is not None else None
    except ValueError:
        value = None  # un valor estropeado no impide dar de alta plataformas
    if value is not None and MIN <= value <= MAX:
        return value
    return get_policies().agent_browse.default_max_offers


def remember(session: Session, value: int) -> None:
    """Guarda `value` como el de las plataformas nuevas."""
    if not MIN <= value <= MAX:
        raise ValueError(f"El número de ofertas tiene que estar entre {MIN} y {MAX}.")
    row = _stored(session)
    if row is None:
        session.add(AgentPreference(scope=SCOPE, key=KEY, model=str(value)))
    else:
        row.model = str(value)
    session.flush()
