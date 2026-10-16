"""Qué agente y qué modelo usa cada acción (fase 24.4, ADR-037).

Las preferencias de la persona viven en la base de datos (`agent_preferences`, en `data/`), nunca
en el repositorio: agente por defecto, modelo o preset de cada agente y agente (y modelo) de cada
acción. Este módulo es el único sitio con el orden de precedencia:

    elección puntual (el botón) > preferencia de la acción > agente por defecto > `CAI_AGENT` >
    el primero habilitado e instalado

y con las comprobaciones que impiden lanzar una acción con un agente que no sirve para ella:

- **capacidades** (`REQUIRES`, con el registro como fuente): `false` la bloquea; `null` (sin
  comprobar) la deja lanzar con un aviso;
- **contenido no confiable** (`UNTRUSTED`) con un agente de nivel C: en terminal, con un aviso; en
  segundo plano, nunca;
- **instalado**: si el agente elegido no está, se dice por qué; no se cambia a otro sin avisar.

El modelo es texto libre validado sin red: caracteres seguros, sin `-` delante (no puede colarse
una bandera) y con `models.pattern` del agente si lo tiene. Nada específico de un agente vive aquí
(regla dura 2): se lee del manifiesto con `agent_registry`.
"""

import re
from collections.abc import Callable, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import AgentPreference
from app.services import agent_registry
from app.services.agent_actions import ACTIONS, ActionId

Capability = Literal["browser", "web", "vision"]
ReasonCode = Literal["explicit", "action", "default", "env", "first_installed", "none"]
BlockedCode = Literal[
    "no_agent", "not_launchable", "not_installed", "no_headless", "capability", "untrusted", "model"
]
Mode = Literal["terminal", "background"]

# Lo que necesita cada acción del agente. `import-cv-template` aún no tiene botón (la página
# Plantillas enseña la orden): queda escrito para cuando lo tenga.
REQUIRES: dict[str, tuple[Capability, ...]] = {
    "search-jobs": ("browser",),
    "research-company": ("web",),
    "training-plan": ("web",),
    "import-cv-template": ("vision",),
}
# Acciones que leen contenido no confiable (ofertas, correos, webs): con un agente de nivel C, el
# mismo agente que lee ese texto tiene todas las herramientas (docs/AGENTS_COMPAT.md). `assess-fit`
# y `generate-cv` no están: no leen el texto de la oferta (no tienen `get_job`), sino la extracción
# ya validada por su esquema.
UNTRUSTED: frozenset[str] = frozenset({"process-jobs", "review-replies", "search-jobs"})

CAPABILITY_NAMES: dict[Capability, str] = {
    "browser": "navegador",
    "web": "búsqueda web",
    "vision": "visión (leer PDF o imágenes)",
}
REASON_TEXTS: dict[ReasonCode, str] = {
    "explicit": "elegido para esta ejecución",
    "action": "elegido para esta acción",
    "default": "tu agente por defecto",
    "env": "por CAI_AGENT",
    "first_installed": "el primero instalado",
    "none": "ninguno disponible",
}
# Nombre de un modelo: empieza por letra o número (nunca `-`, que sería una bandera) y solo lleva
# caracteres que no hay que escapar en ningún sistema.
PREF_SCOPES = ("default", "agent", "action")
MODEL_RE = re.compile(r"[A-Za-z0-9][\w.:/@-]{0,99}", re.ASCII)


class PreferenceError(ValueError):
    def __init__(self, field: str, message: str):
        super().__init__(message)
        self.field = field


class ModelPref(BaseModel):
    """El modelo (por su nombre) o el preset de un agente. Los dos vacíos: el que use el agente."""

    model_config = ConfigDict(extra="forbid")

    model: str | None = None
    preset: str | None = None

    @model_validator(mode="after")
    def _one_of(self) -> "ModelPref":
        self.model = (self.model or "").strip() or None
        self.preset = (self.preset or "").strip() or None
        if self.model and self.preset:
            raise ValueError("elige un modelo o un preset, no los dos")
        return self


class ActionPref(ModelPref):
    agent: str


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_agent: str | None = None
    agents: dict[str, ModelPref] = {}  # agente → su modelo o preset
    actions: dict[ActionId, ActionPref] = {}  # acción → su agente (y modelo)


class Resolution(BaseModel):
    """El agente que usaría una acción, con qué modelo, por qué y si se puede lanzar con él."""

    agent: str | None
    display_name: str | None = None
    model: str | None = None
    preset: str | None = None
    reason: ReasonCode
    reason_text: str
    blocked: str | None = None  # por qué no se puede lanzar con él
    blocked_code: BlockedCode | None = None
    warning: str | None = None  # se puede, pero conviene saberlo

    @property
    def usable(self) -> bool:
        return self.agent is not None and self.blocked is None


# --- Guardar y leer ----------------------------------------------------------------------------


def get_preferences(session: Session) -> Preferences:
    prefs = Preferences()
    for row in session.scalars(select(AgentPreference).order_by(AgentPreference.id)):
        if row.scope == "default":
            prefs.default_agent = row.agent
        elif row.scope == "agent":
            prefs.agents[row.key] = ModelPref(model=row.model, preset=row.preset)
        elif row.scope == "action" and row.key in ACTIONS and row.agent:
            prefs.actions[row.key] = ActionPref(  # type: ignore[index]
                agent=row.agent, model=row.model, preset=row.preset
            )
    return prefs


def _spec(name: str) -> agent_registry.AgentSpec | None:
    try:
        return agent_registry.get(name)
    except agent_registry.ManifestError:
        return None


def _display(name: str) -> str:
    spec = _spec(name)
    return spec.info.display_name if spec else name


def model_problem(
    spec: agent_registry.AgentSpec, model: str | None, preset: str | None
) -> str | None:
    """Por qué ese modelo o preset no vale para el agente (sin consultar la red), o `None`."""
    name = spec.info.display_name
    if model and preset:
        return "Elige un modelo o un preset, no los dos."
    if preset and preset not in spec.models.presets:
        return f"{name} no tiene el preset «{preset[:40]}»."
    if model:
        if not spec.models.flag:
            return f"{name} no sabe elegir el modelo al lanzarlo: déjalo vacío."
        example = f" (p. ej. {spec.models.example})" if spec.models.example else ""
        if not MODEL_RE.fullmatch(model):
            return (
                f"El modelo «{model[:40]}» no es válido: empieza por una letra o un número, sin "
                f"espacios, y usa solo letras, números y . : / @ - _{example}."
            )
        if spec.models.pattern and not re.fullmatch(spec.models.pattern, model):
            return f"El modelo «{model[:40]}» no tiene el formato de {name}{example}."
    return None


def _check_agent(name: str, field: str, launchable: Sequence[str]) -> agent_registry.AgentSpec:
    spec = _spec(name)
    if spec is None:
        raise PreferenceError(field, f"No hay ningún agente «{name[:40]}» en el manifiesto.")
    if name not in launchable:
        raise PreferenceError(
            field, f"{spec.info.display_name} no se puede abrir desde la app (sin `launch`)."
        )
    return spec


def _check_model(spec: agent_registry.AgentSpec, pref: ModelPref, field: str) -> None:
    if (problem := model_problem(spec, pref.model, pref.preset)) is not None:
        raise PreferenceError(field, problem)


def validate(prefs: Preferences, launchable: Sequence[str]) -> None:
    """Comprueba agentes, modelos y presets. Lanza `PreferenceError` con el campo que falla."""
    if prefs.default_agent:
        _check_agent(prefs.default_agent, "default_agent", launchable)
    for name, pref in prefs.agents.items():
        spec = _check_agent(name, f"agents.{name}", launchable)
        _check_model(spec, pref, f"agents.{name}")
    for action, pref in prefs.actions.items():
        spec = _check_agent(pref.agent, f"actions.{action}.agent", launchable)
        _check_model(spec, pref, f"actions.{action}")


def save_preferences(
    session: Session, prefs: Preferences, launchable: Sequence[str]
) -> Preferences:
    """Sustituye todas las preferencias. Los agentes sin modelo ni preset no se guardan."""
    validate(prefs, launchable)
    # Solo las suyas y la copia para deshacer un nivel de gasto (fase 24.6), que tras un cambio a
    # mano ya no vale: los niveles viven en la misma tabla con otros `scope`.
    session.execute(
        delete(AgentPreference).where(AgentPreference.scope.in_((*PREF_SCOPES, "tier_undo")))
    )
    if prefs.default_agent:
        session.add(AgentPreference(scope="default", key="", agent=prefs.default_agent))
    for name, pref in prefs.agents.items():
        if pref.model or pref.preset:
            session.add(
                AgentPreference(scope="agent", key=name, model=pref.model, preset=pref.preset)
            )
    for action, action_pref in prefs.actions.items():
        session.add(
            AgentPreference(
                scope="action",
                key=action,
                agent=action_pref.agent,
                model=action_pref.model,
                preset=action_pref.preset,
            )
        )
    session.flush()
    return get_preferences(session)


# --- Resolver ----------------------------------------------------------------------------------


def check_explicit(
    agent: str | None, model: str | None, preset: str | None, launchable: Sequence[str]
) -> None:
    """Valida una elección puntual (la del botón) antes de resolver: `PreferenceError` si no vale.
    Un modelo sin agente se valida al resolver, con el agente que salga de las preferencias."""
    if not agent:
        return
    spec = _check_agent(agent, "agent", launchable)
    if (problem := model_problem(spec, model, preset)) is not None:
        raise PreferenceError("model", problem)


def _blocked(res: Resolution, code: BlockedCode, message: str) -> Resolution:
    return res.model_copy(update={"blocked": message, "blocked_code": code})


def _checks(res: Resolution, action: str | None, mode: Mode) -> Resolution:
    """Capacidades, nivel de aislamiento y modelo del agente ya elegido."""
    assert res.agent is not None
    spec = _spec(res.agent)
    if spec is None:
        return res
    name = spec.info.display_name
    problem = model_problem(spec, res.model, res.preset)
    if problem is not None:
        return _blocked(res, "model", problem)
    warnings: list[str] = []
    for capability in REQUIRES.get(action or "", ()):
        has = getattr(spec.capabilities, capability)
        label = CAPABILITY_NAMES[capability]
        if has is False:
            return _blocked(
                res, "capability", f"{name} no tiene {label}, y esta acción lo necesita."
            )
        if has is None:
            warnings.append(f"Sin comprobar si {name} tiene {label}, que esta acción necesita.")
    if action in UNTRUSTED and spec.capabilities.isolation_level == "C":
        if mode == "background":
            return _blocked(
                res,
                "untrusted",
                f"{name} es de nivel C: esta acción lee contenido no confiable y en segundo plano "
                "nadie vería lo que hace. Usa «En terminal».",
            )
        warnings.append(
            f"{name} es de nivel C: esta acción lee contenido no confiable. Ejecútala en una "
            "sesión dedicada solo a ella (ver docs/AGENTS_COMPAT.md)."
        )
    return res.model_copy(update={"warning": " ".join(warnings) or None})


def resolve(
    prefs: Preferences,
    action: str | None,
    *,
    candidates: Sequence[str],
    installed: Callable[[str], bool],
    env_agent: str | None = None,
    agent: str | None = None,
    model: str | None = None,
    preset: str | None = None,
    mode: Mode = "terminal",
) -> Resolution:
    """El agente y el modelo de `action` (o el general, sin acción), con su motivo.

    `candidates`: los agentes que se pueden abrir (habilitados y con `launch`), en el orden del
    manifiesto. `installed(nombre)`: si su programa está. `agent`, `model` y `preset`: la elección
    puntual del botón.
    """
    action_pref = prefs.actions.get(action) if action else None  # type: ignore[call-overload]
    chosen: str | None
    level: ModelPref | None
    if agent:
        chosen, reason, level = agent, "explicit", None
    elif action_pref is not None:
        chosen, reason, level = action_pref.agent, "action", action_pref
    elif prefs.default_agent:
        chosen, reason, level = prefs.default_agent, "default", None
    elif env_agent:
        chosen, reason, level = env_agent, "env", None
        if env_agent not in candidates:
            return Resolution(
                agent=None,
                reason="env",
                reason_text=REASON_TEXTS["env"],
                blocked=f"CAI_AGENT={env_agent}, pero ese agente no tiene `launch` en el "
                "manifiesto.",
                blocked_code="not_launchable",
            )
    else:
        chosen = next((name for name in candidates if installed(name)), None)
        reason, level = "first_installed", None
        if chosen is None:
            return Resolution(
                agent=None,
                reason="none",
                reason_text=REASON_TEXTS["none"],
                blocked="No se encuentra el programa de ningún agente en el PATH."
                if candidates
                else "Ningún agente tiene `launch` en .agents/manifest.yaml.",
                blocked_code="no_agent",
            )

    # El modelo: el de la elección puntual; si no, el del nivel que eligió el agente; si no, el
    # guardado para ese agente.
    if model or preset:
        picked_model, picked_preset = model, preset
    elif level is not None and (level.model or level.preset):
        picked_model, picked_preset = level.model, level.preset
    else:
        saved = prefs.agents.get(chosen) or ModelPref()
        picked_model, picked_preset = saved.model, saved.preset

    res = Resolution(
        agent=chosen,
        display_name=_display(chosen),
        model=picked_model,
        preset=picked_preset,
        reason=reason,  # type: ignore[arg-type]
        reason_text=REASON_TEXTS[reason],  # type: ignore[index]
    )
    if chosen not in candidates:
        return _blocked(
            res,
            "not_launchable",
            f"{res.display_name} no se puede abrir desde la app (sin `launch`).",
        )
    if not installed(chosen):
        spec = _spec(chosen)
        how = (
            spec.info.install.model_dump().get(agent_registry.current_platform()) if spec else None
        )
        hint = f" Instálalo con: {how}" if how else ""
        return _blocked(res, "not_installed", f"{res.display_name} no está instalado.{hint}")
    return _checks(res, action, mode)
