"""Niveles de gasto (fase 24.6): «Económico», «Equilibrado» y «Máximo».

Cada nivel es un conjunto de preferencias por acción (agente y modelo, las de la 24.4) para las
acciones de `TIER_ACTIONS`. La persona lo rellena una vez y lo aplica con un clic; aplicar guarda
antes las preferencias por acción que había, y «Deshacer» las devuelve (un nivel de deshacer).

Sin nombres de modelos en el código: la propuesta por defecto sale del manifiesto y de lo que está
instalado (`proposal`):

- **Económico**: las acciones cerradas (`CLOSED_ACTIONS`) con el primer agente instalado que admite
  modelos locales (con su preset `local`, si lo tiene; si no, eliges tú el modelo), y el CV con el
  agente más capaz que tengas (el primero instalado en el orden del manifiesto, con su modelo).
- **Equilibrado**: las cerradas con el agente más capaz y su modelo rápido (`models.fast`), y el CV
  con el más capaz.
- **Máximo**: todo con el agente más capaz y su modelo.

Se guardan en `agent_preferences` (`scope` `tier` y `tier_undo`); un nivel sin filas es la
propuesta.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import AgentPreference
from app.services import agent_launch, agent_prefs, agent_registry
from app.services.agent_actions import ACTIONS, ActionId
from app.services.agent_prefs import ActionPref, PreferenceError

Tier = Literal["economy", "balanced", "max"]
TIERS: tuple[Tier, ...] = ("economy", "balanced", "max")
TIER_LABELS: dict[Tier, str] = {
    "economy": "Económico",
    "balanced": "Equilibrado",
    "max": "Máximo",
}
# Las que leen y guardan algo cerrado (una extracción, una valoración, una propuesta): un modelo
# local o pequeño puede con ellas, y el esquema estricto lo comprueba.
CLOSED_ACTIONS: tuple[ActionId, ...] = ("process-jobs", "assess-fit", "review-replies")
WRITING_ACTIONS: tuple[ActionId, ...] = ("generate-cv",)  # la carta, cuando tenga botón
TIER_ACTIONS: tuple[ActionId, ...] = CLOSED_ACTIONS + WRITING_ACTIONS
UNDO_MARK = "@"  # fila de `tier_undo` que dice que hay algo que deshacer

TierNote = Literal["no_local_agent", "needs_local_model", "no_agent"]


class TierView(BaseModel):
    id: Tier
    label: str
    actions: dict[ActionId, ActionPref]
    custom: bool  # la persona lo editó (si no, es la propuesta)
    active: bool  # las preferencias por acción de ahora son las de este nivel
    notes: list[TierNote] = []


class TiersView(BaseModel):
    actions: list[ActionId]
    tiers: list[TierView]
    can_undo: bool


class TierActions(BaseModel):
    """Lo que se guarda de un nivel: el agente (y modelo) de cada acción."""

    model_config = ConfigDict(extra="forbid")

    actions: dict[ActionId, ActionPref]


# --- Propuesta ---------------------------------------------------------------------------------


def _capable(ctx: agent_launch.Context) -> str | None:
    """El agente más capaz que tengas: el primero instalado, en el orden del manifiesto."""
    return next((name for name in ctx.by_name if ctx.installed(name)), None) or next(
        iter(ctx.by_name), None
    )


def _local(ctx: agent_launch.Context) -> str | None:
    """El primer agente instalado que admite modelos locales y no es de nivel C (las cerradas
    leen contenido no confiable). Mejor si tiene segundo plano."""
    found: list[tuple[bool, str]] = []
    for name in ctx.by_name:
        spec = agent_registry.get(name)
        if spec is None or not ctx.installed(name):
            continue
        caps = spec.capabilities
        if caps.local_models and caps.isolation_level != "C":
            found.append((not caps.headless, name))
    return min(found)[1] if found else None


def _local_pref(name: str) -> tuple[ActionPref, bool]:
    """El agente local con su preset `local` si lo tiene; si no, sin modelo (hay que elegirlo)."""
    spec = agent_registry.get(name)
    if spec is not None and "local" in spec.models.presets:
        return ActionPref(agent=name, preset="local"), False
    return ActionPref(agent=name), True


def _with_fast(name: str) -> ActionPref:
    spec = agent_registry.get(name)
    fast = spec.models.fast if spec is not None and spec.models.flag else None
    return ActionPref(agent=name, model=fast)


def proposal(
    tier: Tier, ctx: agent_launch.Context
) -> tuple[dict[ActionId, ActionPref], list[TierNote]]:
    capable = _capable(ctx)
    if capable is None:
        return {}, ["no_agent"]
    notes: list[TierNote] = []
    best = ActionPref(agent=capable)
    closed: ActionPref
    if tier == "max":
        closed = best
    elif tier == "balanced":
        closed = _with_fast(capable)
    else:
        local = _local(ctx)
        if local is None:
            closed, notes = _with_fast(capable), ["no_local_agent"]
        else:
            closed, needs_model = _local_pref(local)
            if needs_model:
                notes.append("needs_local_model")
    actions = {action: closed for action in CLOSED_ACTIONS}
    actions.update({action: best for action in WRITING_ACTIONS})
    return actions, notes


# --- Leer, editar, aplicar y deshacer ---------------------------------------------------------


def _key(tier: Tier, action: str) -> str:
    return f"{tier}:{action}"


def _stored(session: Session) -> dict[Tier, dict[ActionId, ActionPref]]:
    found: dict[Tier, dict[ActionId, ActionPref]] = {}
    for row in session.scalars(select(AgentPreference).where(AgentPreference.scope == "tier")):
        tier, _, action = row.key.partition(":")
        if tier in TIERS and action in TIER_ACTIONS and row.agent:
            found.setdefault(tier, {})[action] = ActionPref(  # type: ignore[index]
                agent=row.agent, model=row.model, preset=row.preset
            )
    return found


def _same(a: ActionPref | None, b: ActionPref | None) -> bool:
    return a is not None and b is not None and a.model_dump() == b.model_dump()


def tiers(session: Session, ctx: agent_launch.Context | None = None) -> TiersView:
    ctx = ctx or agent_launch.Context(session)
    stored = _stored(session)
    current = ctx.prefs.actions
    views = []
    for tier in TIERS:
        proposed, notes = proposal(tier, ctx)
        custom = tier in stored
        actions = {**proposed, **stored.get(tier, {})} if custom else proposed
        if custom:
            notes = [n for n in notes if n == "no_agent"]
        views.append(
            TierView(
                id=tier,
                label=TIER_LABELS[tier],
                actions=actions,
                custom=custom,
                active=bool(actions) and all(_same(current.get(a), p) for a, p in actions.items()),
                notes=notes,
            )
        )
    can_undo = (
        session.scalars(
            select(AgentPreference.id).where(
                AgentPreference.scope == "tier_undo", AgentPreference.key == UNDO_MARK
            )
        ).first()
        is not None
    )
    return TiersView(actions=list(TIER_ACTIONS), tiers=views, can_undo=can_undo)


def _launchable(ctx: agent_launch.Context) -> list[str]:
    return list(ctx.by_name)


def save_tier(session: Session, tier: Tier, body: TierActions) -> TiersView:
    """Sustituye lo guardado de un nivel. Las acciones que no van en el cuerpo quedan con la
    propuesta. `PreferenceError` si un agente o modelo no vale."""
    ctx = agent_launch.Context(session)
    unknown = [a for a in body.actions if a not in TIER_ACTIONS]
    if unknown:
        raise PreferenceError(
            f"actions.{unknown[0]}", f"«{unknown[0]}» no forma parte de los niveles de gasto."
        )
    agent_prefs.validate(agent_prefs.Preferences(actions=body.actions), _launchable(ctx))
    session.execute(
        delete(AgentPreference).where(
            AgentPreference.scope == "tier", AgentPreference.key.like(f"{tier}:%")
        )
    )
    for action, pref in body.actions.items():
        session.add(
            AgentPreference(
                scope="tier",
                key=_key(tier, action),
                agent=pref.agent,
                model=pref.model,
                preset=pref.preset,
            )
        )
    session.flush()
    return tiers(session)


def reset_tier(session: Session, tier: Tier) -> TiersView:
    """Vuelve a la propuesta."""
    session.execute(
        delete(AgentPreference).where(
            AgentPreference.scope == "tier", AgentPreference.key.like(f"{tier}:%")
        )
    )
    session.flush()
    return tiers(session)


def _action_rows(session: Session, scope: str) -> list[AgentPreference]:
    return list(
        session.scalars(
            select(AgentPreference).where(
                AgentPreference.scope == scope, AgentPreference.key != UNDO_MARK
            )
        )
    )


def apply(session: Session, tier: Tier) -> TiersView:
    """Pone las preferencias por acción del nivel (las demás acciones no se tocan) y guarda las de
    antes para deshacer. `PreferenceError` si alguna ya no vale (p. ej. un agente desinstalado
    del manifiesto) o si el nivel aún necesita que elijas el modelo local."""
    ctx = agent_launch.Context(session)
    view = next(t for t in tiers(session, ctx).tiers if t.id == tier)
    if not view.actions:
        raise PreferenceError("tier", "No hay ningún agente que se pueda abrir desde la app.")
    if "needs_local_model" in view.notes:
        # Sin modelo, el agente usaría el suyo, que puede ser de pago o en la nube.
        raise PreferenceError(
            "tier",
            "Elige antes el modelo local de este nivel («Editar»): sin él, el agente usaría "
            "el que tenga configurado.",
        )
    prefs = ctx.prefs.model_copy(deep=True)
    prefs.actions.update(view.actions)
    before = [
        (row.key, row.agent, row.model, row.preset) for row in _action_rows(session, "action")
    ]
    # `save_preferences` borra la copia para deshacer (un cambio a mano la deja obsoleta): se
    # escribe después.
    agent_prefs.save_preferences(session, prefs, _launchable(ctx))
    session.add(AgentPreference(scope="tier_undo", key=UNDO_MARK, agent=tier))
    for key, agent, model, preset in before:
        session.add(
            AgentPreference(scope="tier_undo", key=key, agent=agent, model=model, preset=preset)
        )
    session.flush()
    return tiers(session)


def undo(session: Session) -> TiersView:
    """Devuelve las preferencias por acción de antes de aplicar el último nivel."""
    marks = session.scalars(
        select(AgentPreference.id).where(
            AgentPreference.scope == "tier_undo", AgentPreference.key == UNDO_MARK
        )
    ).first()
    if marks is None:
        raise PreferenceError("tier", "No hay nada que deshacer.")
    saved = _action_rows(session, "tier_undo")
    session.execute(delete(AgentPreference).where(AgentPreference.scope == "action"))
    for row in saved:
        if row.key in ACTIONS:
            session.add(
                AgentPreference(
                    scope="action", key=row.key, agent=row.agent, model=row.model, preset=row.preset
                )
            )
    session.execute(delete(AgentPreference).where(AgentPreference.scope == "tier_undo"))
    session.flush()
    return tiers(session)
