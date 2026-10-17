"""Botones «en tu agente» de la UI (ADR-024): abren tu agente en una terminal visible con la orden
de un skill ya escrita. La app no llama a ningún modelo (ADR-001): lanza el agente que ya usas,
con tu suscripción, y tú ves, contestas y apruebas lo que haga.

- Las órdenes son una lista cerrada (`ACTIONS`) que construye la app. Lo único variable son el
  `job_id` y el `milestone_id` (fase 17), enteros, y el id de un logro o una historia del perfil
  (fase 25.7b), con el formato de un id y solo si existe: ningún texto de una oferta ni de una
  web llega al comando.
- Qué programa se lanza no está aquí: es `launch` del agente en `.agents/manifest.yaml` (regla
  dura 2), que se lee con `agent_registry`. Con varios, cuál se abre lo decide `agent_prefs`
  (fase 24.4): el botón, la acción, el agente por defecto, `CAI_AGENT` y, si no, el primero
  habilitado e instalado.
- Antes de lanzar se quitan del entorno las variables de `launch.unset_env` (p. ej. la clave de la
  API): así el agente usa tu suscripción y no factura por API.
- Solo Windows de momento (Windows Terminal o, si no está, una ventana de PowerShell). En otro
  sistema, o sin agente instalado, la UI copia la orden para que la pegues tú.
- «En segundo plano» (fase 19, ADR-032): las acciones con `background` también se pueden lanzar
  sin ventana desde el worker (`services/agent_runs.py`), con `launch.headless` del manifiesto y
  solo las herramientas MCP que declara la acción: en la orden (`ceiling: args`) o, desde la fase
  24.5, en una configuración propia de la ejecución (`ceiling: config`, `agent_run_config`).
"""

import base64
import logging
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.models import Milestone
from app.models.base import utcnow
from app.services import (
    agent_prefs,
    agent_registry,
    agent_run_config,
    events,
    interviews,
    process,
)
from app.services import profile as profiles
from app.services.agent_actions import (  # noqa: F401 - se reexportan
    ACTIONS,
    CV_STAGES,
    OUTREACH_STAGES,
    RESEARCH_STAGES,
    SENT_STAGES,
    Action,
    ActionId,
    MilestoneRule,
)
from app.services.agent_prefs import Preferences, Resolution
from app.services.agent_registry import (
    DENIED_PLACEHOLDER,
    MODEL_PLACEHOLDER,
    PROMPT_PLACEHOLDER,
    SESSION_PLACEHOLDER,
    SKILL_PLACEHOLDER,
    TOOLS_PLACEHOLDER,
    RunConfigSpec,
)

logger = logging.getLogger(__name__)


class LaunchError(Exception):
    def __init__(
        self,
        code: Literal["not_found", "invalid_request", "unavailable"],
        message: str,
        prompt: str | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.prompt = prompt  # con `unavailable`: la orden, para que la UI la copie


class AgentInfo(BaseModel):
    """Qué agente abrirían los botones, o por qué no se puede (y entonces se copia la orden)."""

    available: bool
    agent: str | None = None  # nombre del agente en el manifiesto (`claude`, `codex`…)
    reason: str | None = None


class LaunchResult(BaseModel):
    ok: bool = True
    agent: str
    model: str | None = None  # fase 24.4: el modelo o el preset con que se abrió
    prompt: str
    message: str
    warning: str | None = None  # p. ej. un agente de nivel C con contenido no confiable


@dataclass(frozen=True)
class Headless:
    """`launch.headless` del manifiesto: cómo se lanza el agente sin ventana (fase 19)."""

    command: list[str]  # con `{prompt}`; con `ceiling: args`, `{allowed_tools}` y `{denied_tools}`
    allow: list[str]  # herramientas permitidas además del skill y las MCP de la acción
    skill_rule: str  # cómo se permite solo el skill de la acción (con `{skill}`)
    output: str  # formato de la salida (`claude-stream-json`, `opencode-json`)
    mcp_prefix: str  # `tools.mcp_prefix` del agente: nombre MCP → nombre nativo
    # Fase 24.5: `config` = el techo va en una configuración propia de la ejecución (`config`).
    ceiling: Literal["args", "config"] = "args"
    config: RunConfigSpec | None = None


@dataclass(frozen=True)
class _Launcher:
    agent: str
    command: list[str]
    unset_env: list[str]
    resume: list[str] = field(default_factory=list)  # con `{session_id}`
    headless: Headless | None = None
    # Fase 24.4: el modelo o preset elegido; sus argumentos ya van en los comandos de arriba.
    model: str | None = None
    preset: str | None = None
    warning: str | None = None


def prompt_for(
    action: ActionId,
    job_id: int | None = None,
    milestone_id: int | None = None,
    profile_item: str | None = None,
) -> str:
    """La orden que se le da al agente (la misma que copia la UI si no puede lanzarlo)."""
    spec = ACTIONS[action]
    if spec.needs_job and job_id is None:
        raise LaunchError("invalid_request", f"«{spec.label}» necesita una oferta.")
    if spec.milestone and milestone_id is None:
        raise LaunchError("invalid_request", f"«{spec.label}» necesita una entrevista.")
    if spec.profile_item and profile_item is None:
        raise LaunchError("invalid_request", f"«{spec.label}» necesita un logro o una historia.")
    return spec.prompt.format(job_id=job_id, milestone_id=milestone_id, profile_item=profile_item)


# Un logro (`exp-acme/a2`) o una historia (`st-x`): el formato de los ids del perfil.
PROFILE_ITEM = re.compile(r"^[a-z0-9][a-z0-9_-]*(?:/[a-z0-9][a-z0-9_-]*)?$")


def _check_profile_item(session: Session, profile_item: str | None) -> str:
    """El id de un logro o una historia del perfil vigente (fase 25.7b, matiz a la ADR-024: es
    texto, pero solo con el formato de un id y solo si existe)."""
    if profile_item is None:
        raise LaunchError("invalid_request", "Esta acción necesita un logro o una historia.")
    if not PROFILE_ITEM.fullmatch(profile_item):
        raise LaunchError("invalid_request", "Id de perfil no válido.")
    try:
        current = profiles.current(session).profile
    except profiles.ProfileNotFoundError as exc:
        raise LaunchError("not_found", str(exc)) from exc
    known = {f"{exp.id}/{a.id}" for exp in current.experience for a in exp.achievements}
    known |= {story.id for story in current.stories}
    if profile_item not in known:
        raise LaunchError(
            "not_found", f"«{profile_item}» no es un logro ni una historia de tu perfil vigente."
        )
    return profile_item


def _manifest_problem() -> str | None:
    """El error del manifiesto, si no es válido (se avisa en el log una vez por mensaje)."""
    try:
        agent_registry.load()
    except agent_registry.ManifestError as exc:
        message = str(exc)
        if message not in _logged_problems:
            _logged_problems.add(message)
            logger.warning("Manifiesto de agentes inválido: %s", message)
        return message
    return None


_logged_problems: set[str] = set()


def _launchers() -> list[_Launcher]:
    """Los agentes habilitados con `launch`, en el orden del manifiesto (vía `agent_registry`)."""
    if _manifest_problem() is not None:
        return []
    agents = agent_registry.load()
    found = []
    for spec in agents.values():
        if not spec.launchable or spec.launch is None:
            continue
        launch = spec.launch
        resume = list(launch.resume) if SESSION_PLACEHOLDER in launch.resume else []
        found.append(
            _Launcher(spec.name, list(launch.command), spec.unset_env, resume, _headless(spec))
        )
    return found


def _headless(spec: agent_registry.AgentSpec) -> Headless | None:
    """`launch.headless`, si está completo: orden, herramientas y un formato de salida conocido."""
    headless = spec.headless
    if headless is None or spec.mcp_prefix is None:
        return None
    return Headless(
        list(headless.command),
        list(headless.allow),
        headless.skill_rule,
        headless.output,
        spec.mcp_prefix,
        headless.ceiling,
        headless.config,
    )


WINDOWS_ONLY = "Abrir el agente desde la UI solo está disponible en Windows de momento."
# Motivos por los que no hay agente que lanzar: la UI copia la orden para que la pegues tú. Los
# demás (capacidad, nivel, modelo) son una elección que no vale y se dicen sin copiar nada.
_UNAVAILABLE: frozenset[str] = frozenset(
    {"no_agent", "not_launchable", "not_installed", "no_headless"}
)


def _with_model(parts: list[str], args: list[str]) -> list[str]:
    """Los argumentos del modelo (`models.flag` o un preset) van donde diga `{model}` (fase 24.5:
    `opencode run` no los acepta delante de `run`) o, si no lo dice, justo detrás del programa.
    Sin modelo, `{model}` desaparece."""
    if MODEL_PLACEHOLDER in parts:
        return [arg for part in parts for arg in (args if part == MODEL_PLACEHOLDER else [part])]
    return [*parts[:1], *args, *parts[1:]] if args and parts else list(parts)


class Context:
    """Lo que se lee una vez para elegir agente varias veces en la misma petición: los lanzadores,
    las preferencias y qué programas están en el `PATH`."""

    def __init__(self, session: Session | None = None):
        self.launchers = _launchers()
        self.by_name = {launcher.agent: launcher for launcher in self.launchers}
        self.prefs = agent_prefs.get_preferences(session) if session is not None else Preferences()
        self._found: dict[str, bool] = {}

    def installed(self, name: str) -> bool:
        if name not in self._found:
            launcher = self.by_name.get(name)
            self._found[name] = bool(launcher and shutil.which(launcher.command[0]))
        return self._found[name]


def choose(
    session: Session | None,
    action: str | None = None,
    *,
    agent: str | None = None,
    model: str | None = None,
    preset: str | None = None,
    mode: agent_prefs.Mode = "terminal",
    ctx: Context | None = None,
) -> tuple[_Launcher | None, Resolution]:
    """El agente que usaría `action` (con el modelo ya puesto en sus comandos) y por qué. Sin
    lanzador si no se puede usar; el motivo va en `Resolution.blocked`. La precedencia y las
    comprobaciones son de `agent_prefs`."""
    ctx = ctx or Context(session)
    if not ctx.launchers and (problem := _manifest_problem()) is not None:
        return None, Resolution(
            agent=None,
            reason="none",
            reason_text=agent_prefs.REASON_TEXTS["none"],
            blocked=f"El manifiesto de agentes no es válido: {problem}",
            blocked_code="no_agent",
        )
    res = agent_prefs.resolve(
        ctx.prefs,
        action,
        candidates=list(ctx.by_name),
        installed=ctx.installed,
        env_agent=get_settings().agent,
        agent=agent,
        model=model,
        preset=preset,
        mode=mode,
    )
    if not res.usable or res.agent is None:
        return None, res
    launcher = ctx.by_name[res.agent]
    if mode == "background" and (blocked := _no_background(launcher, res, action)) is not None:
        return None, res.model_copy(update={"blocked": blocked, "blocked_code": "no_headless"})
    spec = agent_registry.get(res.agent)
    args = spec.model_args(res.model, res.preset) if spec is not None else []
    headless = launcher.headless
    if headless is not None:
        headless = replace(headless, command=_with_model(headless.command, args))
    picked = replace(
        launcher,
        command=_with_model(launcher.command, args),
        resume=_with_model(launcher.resume, args),
        headless=headless,
        model=res.model,
        preset=res.preset,
        warning=res.warning,
    )
    return picked, res


def _no_background(launcher: _Launcher, res: Resolution, action: str | None) -> str | None:
    """Por qué el agente no puede lanzar `action` en segundo plano, o `None` si puede."""
    if launcher.headless is None:
        return (
            f"Tu agente ({res.display_name}) no tiene `launch.headless` en "
            ".agents/manifest.yaml: usa «En terminal»."
        )
    if launcher.headless.ceiling == "config" and action in ACTIONS:
        return agent_run_config.ceiling_problem(action)  # type: ignore[arg-type]
    return None


def pick(
    session: Session | None,
    action: str | None,
    prompt: str,
    *,
    agent: str | None = None,
    model: str | None = None,
    preset: str | None = None,
    mode: agent_prefs.Mode = "terminal",
) -> _Launcher:
    """Como `choose`, pero lanza `LaunchError` si no se puede: `unavailable` (con la orden, para
    copiarla) si no hay agente; `invalid_request` si la elección no vale para la acción."""
    if mode == "terminal" and sys.platform != "win32":
        raise LaunchError("unavailable", WINDOWS_ONLY, prompt)
    ctx = Context(session)
    try:
        agent_prefs.check_explicit(agent, model, preset, list(ctx.by_name))
    except agent_prefs.PreferenceError as exc:
        raise LaunchError("invalid_request", str(exc)) from exc
    launcher, res = choose(
        session, action, agent=agent, model=model, preset=preset, mode=mode, ctx=ctx
    )
    if launcher is None:
        code = "unavailable" if res.blocked_code in _UNAVAILABLE else "invalid_request"
        raise LaunchError(code, res.blocked or "No se puede lanzar el agente.", prompt)
    return launcher


def _pick(session: Session | None = None) -> _Launcher | str:
    """El agente que se lanzaría (sin acción), o el motivo por el que no hay ninguno."""
    if sys.platform != "win32":
        return WINDOWS_ONLY
    return _pick_any(session)


def _pick_any(session: Session | None = None) -> _Launcher | str:
    """Como `_pick`, sin exigir Windows: el segundo plano no abre ninguna ventana."""
    launcher, res = choose(session)
    return launcher if launcher is not None else (res.blocked or "")


def info(session: Session | None = None) -> AgentInfo:
    picked = _pick(session)
    if isinstance(picked, str):
        return AgentInfo(available=False, reason=picked)
    return AgentInfo(available=True, agent=picked.agent)


def selection(session: Session | None = None) -> AgentInfo:
    """Como `info`, sin exigir Windows: el agente que se usaría hoy (`cai agents doctor`)."""
    picked = _pick_any(session)
    if isinstance(picked, str):
        return AgentInfo(available=False, reason=picked)
    return AgentInfo(available=True, agent=picked.agent)


def _quote(value: str) -> str:
    """Literal de PowerShell entre comillas simples."""
    return "'" + value.replace("'", "''") + "'"


# Fase 24.4: el agente lanzado se identifica con esta variable, para que los eventos que haga por
# la CLI queden a su nombre (por MCP lo dice el propio cliente).
CLIENT_ENV = "CAI_CLIENT_NAME"


def powershell_command(
    launcher: _Launcher, value: str, command: Sequence[str] | None = None
) -> str:
    """Lo que ejecuta la ventana: quitar las variables de `unset_env`, poner `CAI_CLIENT_NAME` y
    abrir el agente. `value` va donde esté `{prompt}` (o `{session_id}`, si `command` es
    `launch.resume`)."""
    markers = (PROMPT_PLACEHOLDER, SESSION_PLACEHOLDER)
    parts = [value if p in markers else p for p in command or launcher.command]
    unset = [f"Remove-Item Env:{name} -ErrorAction SilentlyContinue" for name in launcher.unset_env]
    client = f"$env:{CLIENT_ENV} = {_quote(launcher.agent)}"
    return "; ".join([*unset, client, "& " + " ".join(_quote(p) for p in parts)])


def shell_args(command: str) -> list[str]:
    """PowerShell con la orden codificada (`-EncodedCommand`: base64 de UTF-16LE). Así no lleva
    `;`, comillas ni espacios que reinterprete quien lo lanza: `wt` parte su línea por cada `;`."""
    encoded = base64.b64encode(command.encode("utf-16-le")).decode("ascii")
    return ["powershell", "-NoLogo", "-NoExit", "-EncodedCommand", encoded]


def _open_terminal(title: str, command: str) -> None:
    shell = shell_args(command)
    wt = shutil.which("wt")
    if wt:
        args = [wt, "-w", "0", "new-tab", "--title", title, "-d", str(REPO_ROOT), *shell]
        subprocess.Popen(args, cwd=REPO_ROOT)  # noqa: S603 - argumentos fijos, sin shell
        return
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen(shell, cwd=REPO_ROOT, creationflags=flags)  # noqa: S603


def _check_milestone(
    session: Session, rule: MilestoneRule, milestone_id: int | None, job_id: int | None
) -> int:
    """Comprueba el hito de una acción de entrevista y devuelve el id de su oferta."""
    if milestone_id is None:
        raise LaunchError("invalid_request", "Esta acción necesita una entrevista.")
    row = session.get(Milestone, milestone_id)
    if row is None:
        raise LaunchError("not_found", f"No existe el hito {milestone_id}.")
    if job_id is not None and job_id != row.job_id:
        raise LaunchError("invalid_request", "El hito no es de esa oferta.")
    # Las mismas comprobaciones que las herramientas, para que botón y herramienta no diverjan.
    try:
        if rule == "upcoming":
            interviews.check_can_prepare(session, row, utcnow())
        else:
            interviews.check_can_debrief(row, utcnow())
    except interviews.InterviewNotAllowedError as exc:
        raise LaunchError("invalid_request", str(exc)) from exc
    return row.job_id


def check_target(
    session: Session,
    action: ActionId,
    job_id: int | None = None,
    milestone_id: int | None = None,
    profile_item: str | None = None,
) -> tuple[str, int | None, int | None]:
    """Comprueba que la acción se puede lanzar para esa oferta o hito y devuelve su orden, con la
    oferta y el hito que le corresponden (`None` si la acción no los usa)."""
    spec = ACTIONS[action]
    item = _check_profile_item(session, profile_item) if spec.profile_item else None
    if spec.milestone:
        job_id = _check_milestone(session, spec.milestone, milestone_id, job_id)
    elif spec.needs_job:
        if job_id is None:
            raise LaunchError("invalid_request", f"«{spec.label}» necesita una oferta.")
        try:
            stage = events.current_stage(session, job_id)
        except events.JobNotFoundError as exc:
            raise LaunchError("not_found", f"No existe la oferta {job_id}.") from exc
        if stage not in spec.stages:
            raise LaunchError("invalid_request", spec.wrong_stage)
        if spec.needs_offer and not process.offer_received(session, job_id):
            raise LaunchError("invalid_request", "Esta oferta no tiene una propuesta recibida.")
    job_id = job_id if spec.needs_job else None
    milestone_id = milestone_id if spec.milestone else None
    return prompt_for(action, job_id, milestone_id, item), job_id, milestone_id


def launch(
    session: Session,
    action: ActionId,
    job_id: int | None = None,
    milestone_id: int | None = None,
    *,
    agent: str | None = None,
    model: str | None = None,
    preset: str | None = None,
    profile_item: str | None = None,
) -> LaunchResult:
    """Abre el agente en una terminal con la orden de `action`. No espera a que termine. `agent`,
    `model` y `preset`: la elección puntual del botón (si no, las preferencias)."""
    spec = ACTIONS[action]
    prompt, _, _ = check_target(session, action, job_id, milestone_id, profile_item)
    picked = pick(session, action, prompt, agent=agent, model=model, preset=preset)
    return _open(spec.label, prompt, picked, picked.command, prompt)


def model_label(model: str | None, preset: str | None) -> str | None:
    """El modelo o el preset, para enseñarlo (`None`: el que use el agente por defecto)."""
    return f"preset {preset}" if preset else model


def _open(
    label: str, prompt: str, picked: _Launcher, command: list[str], value: str
) -> LaunchResult:
    """Abre la terminal con `command` de `picked`, sustituyendo el marcador por `value`."""
    try:
        _open_terminal(f"CandidatAI · {label}", powershell_command(picked, value, command))
    except OSError as exc:
        raise LaunchError("unavailable", f"No se pudo abrir la terminal: {exc}", prompt) from exc
    model = model_label(picked.model, picked.preset)
    with_model = f" ({model})" if model else ""
    return LaunchResult(
        agent=picked.agent,
        model=model,
        prompt=prompt,
        message=f"Se ha abierto {picked.agent}{with_model} en una terminal con la orden escrita.",
        warning=picked.warning,
    )


def resumable_agents() -> frozenset[str]:
    """Los agentes que «Abrir en terminal» puede retomar: los que se pueden abrir, están
    instalados y tienen `resume` (la sesión se retoma con el agente que la ejecutó)."""
    if sys.platform != "win32":
        return frozenset()
    return frozenset(
        launcher.agent
        for launcher in _launchers()
        if launcher.resume and shutil.which(launcher.command[0])
    )


def resume_in_terminal(
    session: Session,
    action: ActionId,
    prompt: str,
    run_agent: str,
    session_id: str | None,
    model: str | None = None,
    preset: str | None = None,
) -> LaunchResult:
    """«Abrir en terminal» de una ejecución en segundo plano (fase 19): retoma su sesión con el
    agente y el modelo que la ejecutaron si ese agente sabe (`launch.resume`); si no, abre la
    orden de nuevo con el agente que toque."""
    label = ACTIONS[action].label
    if sys.platform != "win32":
        raise LaunchError("unavailable", WINDOWS_ONLY, prompt)
    same, _ = choose(session, action, agent=run_agent, model=model, preset=preset)
    if same is not None and session_id and same.resume and SESSION_ID_RE.fullmatch(session_id):
        result = _open(label, prompt, same, same.resume, session_id)
        result.message = f"Se ha abierto {same.agent} en una terminal con la misma sesión."
        return result
    if same is not None:
        return _open(label, prompt, same, same.command, prompt)
    # El agente que la ejecutó ya no se puede usar: se abre el que toque hoy, y se dice.
    picked = pick(session, action, prompt)
    result = _open(label, prompt, picked, picked.command, prompt)
    changed = (
        f"No se puede abrir {run_agent}, que la ejecutó: se ha abierto {picked.agent} desde cero."
    )
    result.warning = " ".join(filter(None, [changed, result.warning]))
    return result


# --- En segundo plano (fase 19) ----------------------------------------------------------------

# Lo que se añade a la orden en segundo plano: nadie puede contestar. Las preguntas se recogen de
# la respuesta final (`agent_runs`) y se enseñan en la UI.
BACKGROUND_NOTE = (
    " Estás en segundo plano y nadie puede contestarte: no preguntes ni esperes confirmación. Si "
    "necesitas algo del usuario para seguir, para ahí y termina tu respuesta con una línea por "
    "pregunta que empiece por «PREGUNTA:»."
)
# Fase 14: con todas las obligatorias ausentes marcadas como «No la tengo», `generate-cv` no tiene
# nada que preguntar. Los nombres de las skills salen de las ofertas: no van en la orden.
GAPS_MARKED_NOTE = (
    " Las skills obligatorias ausentes de esa oferta ya las he marcado como «No la tengo» en la "
    "página Skills: no preguntes por ellas ni las pongas en el CV."
)
QUESTION_PREFIX = "PREGUNTA:"
# Identificador de sesión que devuelve el agente: solo se pasa al comando si tiene esta forma.
SESSION_ID_RE = re.compile(r"[A-Za-z0-9_-]{8,64}")  # OpenCode: `ses_…`


class BackgroundInfo(BaseModel):
    """Si los botones pueden lanzar en segundo plano, con qué agente o por qué no."""

    available: bool
    agent: str | None = None
    reason: str | None = None
    # Fase 24.5: si no se puede, otro agente que sí lanza esta acción en segundo plano.
    suggested: str | None = None
    suggested_name: str | None = None


def suggest_background(
    session: Session | None, action: str, ctx: Context, skip: str | None = None
) -> Resolution | None:
    """El primer agente (en el orden del manifiesto) que puede lanzar `action` en segundo plano,
    sin contar `skip`."""
    for name in ctx.by_name:
        if name == skip:
            continue
        launcher, res = choose(session, action, agent=name, mode="background", ctx=ctx)
        if launcher is not None:
            return res
    return None


def pick_headless(session: Session | None = None, action: str | None = None) -> _Launcher | str:
    """El agente con el que se lanzaría en segundo plano, o el motivo por el que no se puede."""
    launcher, res = choose(session, action, mode="background")
    return launcher if launcher is not None else (res.blocked or "")


def background_info(session: Session | None = None, action: str | None = None) -> BackgroundInfo:
    picked = pick_headless(session, action)
    if isinstance(picked, str):
        return BackgroundInfo(available=False, reason=picked)
    return BackgroundInfo(available=True, agent=picked.agent)


def all_mcp_tools() -> list[str]:
    """Todas las herramientas de la interfaz para agentes (las que se deniegan si no son de la
    acción). Se importa aquí: el registro importa servicios que importan este módulo."""
    from app.agent_interface.tools import TOOLS_BY_NAME

    return sorted(TOOLS_BY_NAME)


def headless_command(launcher: _Launcher, prompt: str, action: ActionId) -> list[str]:
    """El comando sin ventana. Con `ceiling: args`, una herramienta por argumento: en
    `{allowed_tools}`, las de `allow`, el skill de la acción y sus herramientas MCP; en
    `{denied_tools}`, todas las demás MCP (un deny gana a cualquier allow de la configuración del
    agente y vale para sus subagentes). Con `ceiling: config`, solo la orden: el techo lo pone la
    configuración de la ejecución (`run_config`)."""
    spec = ACTIONS[action]
    if launcher.headless is None or not spec.background:
        raise LaunchError("unavailable", "Esta acción no se puede lanzar en segundo plano.")
    headless = launcher.headless
    if headless.ceiling == "config":
        if (problem := agent_run_config.ceiling_problem(action)) is not None:
            raise LaunchError("unavailable", problem)
        parts = _with_model(headless.command, [])  # sin modelo elegido, `{model}` sobra
        return [prompt if part == PROMPT_PLACEHOLDER else part for part in parts]
    prefix = headless.mcp_prefix
    allowed = [
        *headless.allow,
        headless.skill_rule.replace(SKILL_PLACEHOLDER, spec.skill or action),
        *(prefix + tool for tool in spec.background),
    ]
    denied = [prefix + tool for tool in all_mcp_tools() if tool not in spec.background]
    command: list[str] = []
    for part in _with_model(headless.command, []):
        if part == PROMPT_PLACEHOLDER:
            command.append(prompt)
        elif part == TOOLS_PLACEHOLDER:
            command.extend(allowed)
        elif part == DENIED_PLACEHOLDER:
            command.extend(denied)
        else:
            command.append(part)
    return command


def run_config(launcher: _Launcher) -> dict[str, str] | None:
    """Lo que se guarda en la fila para que el runner escriba la configuración de la ejecución
    (`ceiling: config`), o `None` si el techo va en la orden."""
    headless = launcher.headless
    if headless is None or headless.ceiling != "config" or headless.config is None:
        return None
    return {**headless.config.model_dump(), "mcp_prefix": headless.mcp_prefix}


# --- Elegir agente desde la UI (fase 24.4) -----------------------------------------------------


class EffectiveAction(BaseModel):
    """Con qué agente y modelo iría una acción, por qué y si se puede (en terminal y, si la
    acción lo admite, en segundo plano)."""

    action: ActionId
    label: str
    terminal: Resolution
    background: Resolution | None = None


class AgentsOverview(agent_registry.AgentList):
    """`GET /agent/agents` y `cai agents list --json`: los agentes del manifiesto, tus preferencias
    y el agente efectivo de cada acción."""

    launchable: list[str]  # los que se pueden abrir desde la app (habilitados y con `launch`)
    preferences: Preferences
    effective: list[EffectiveAction]


def effective_actions(session: Session | None, ctx: Context | None = None) -> list[EffectiveAction]:
    ctx = ctx or Context(session)
    return [
        EffectiveAction(
            action=action_id,
            label=spec.label,
            terminal=choose(session, action_id, ctx=ctx)[1],
            background=choose(session, action_id, mode="background", ctx=ctx)[1]
            if spec.background
            else None,
        )
        for action_id, spec in ACTIONS.items()
    ]


def overview(session: Session | None, refresh: bool = False) -> AgentsOverview:
    """Lanza `agent_registry.ManifestError` si el manifiesto no es válido."""
    listed = agent_registry.list_agents(refresh=refresh)
    ctx = Context(session)
    return AgentsOverview(
        agents=listed.agents,
        launchable=list(ctx.by_name),
        preferences=ctx.prefs,
        effective=effective_actions(session, ctx),
    )


def save_preferences(session: Session, prefs: Preferences) -> Preferences:
    """Guarda las preferencias (`agent_prefs.PreferenceError` si alguna no vale)."""
    return agent_prefs.save_preferences(
        session, prefs, [launcher.agent for launcher in _launchers()]
    )
