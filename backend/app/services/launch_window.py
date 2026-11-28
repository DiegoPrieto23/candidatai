"""Dónde va lo que lanza el botón principal de una acción: en el portal, sin ventana (por defecto,
si la acción y el agente pueden ir en segundo plano) o en una ventana del agente, para quien la
prefiera. Se guarda en `agent_preferences` (`scope="setting"`, `key="open_in_window"`, `"1"` en
`model`), como el umbral de la valoración: sobrevive a las actualizaciones.

Elegir «En terminal» o «En segundo plano» en el menú del botón sigue valiendo para esa vez.

Fase 48.1d: cómo se abre esa ventana en Windows (`key="window_style"`): minimizada en la barra de
tareas (por defecto), a la vista detrás del navegador o en Windows Terminal. Sin elegir,
`CAI_TERMINAL=wt` sigue dando Windows Terminal. En macOS y Linux manda `CAI_TERMINAL`
(`services/terminals.py`).
"""

import shutil
import sys
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AgentPreference

SCOPE, KEY, STYLE_KEY = "setting", "open_in_window", "window_style"
# `terminal`: macOS y Linux, la terminal que toque; no se elige aquí.
WindowStyle = Literal["minimized", "behind", "wt"]
OpenedStyle = Literal["minimized", "behind", "wt", "terminal"]
WINDOWS_TERMINAL = ("wt", "windows-terminal", "windowsterminal")


class WindowPreference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    open_in_window: bool
    # Sin valor al guardar: se deja la que hubiera.
    window_style: WindowStyle | None = None


def _stored(session: Session, key: str = KEY) -> AgentPreference | None:
    return session.scalars(
        select(AgentPreference).where(AgentPreference.scope == SCOPE, AgentPreference.key == key)
    ).first()


def has_windows_terminal() -> bool:
    return sys.platform == "win32" and shutil.which("wt") is not None


def styles() -> list[WindowStyle]:
    """Las que se pueden elegir en este equipo (ninguna fuera de Windows)."""
    if sys.platform != "win32":
        return []
    found: list[WindowStyle] = ["minimized", "behind"]
    if has_windows_terminal():
        found.append("wt")
    return found


def style(session: Session) -> OpenedStyle:
    """Cómo se abrirá la próxima ventana."""
    if sys.platform != "win32":
        return "terminal"
    row = _stored(session, STYLE_KEY)
    chosen = row.model if row is not None else None
    if chosen not in get_args(WindowStyle):
        terminal = (get_settings().terminal or "").strip().lower()
        chosen = "wt" if terminal in WINDOWS_TERMINAL else "minimized"
    if chosen == "wt" and not has_windows_terminal():
        return "minimized"
    return chosen  # type: ignore[return-value]


def get(session: Session) -> WindowPreference:
    row = _stored(session)
    opened = style(session)
    return WindowPreference(
        open_in_window=row is not None and row.model == "1",
        window_style=None if opened == "terminal" else opened,
    )


def _put(session: Session, key: str, value: str) -> None:
    row = _stored(session, key)
    if row is None:
        session.add(AgentPreference(scope=SCOPE, key=key, model=value))
    else:
        row.model = value


def save(session: Session, value: WindowPreference) -> WindowPreference:
    _put(session, KEY, "1" if value.open_in_window else "0")
    if value.window_style is not None:
        _put(session, STYLE_KEY, value.window_style)
    session.flush()
    return get(session)
