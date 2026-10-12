"""Botones «en tu agente» de la UI (ADR-024): abren tu agente en una terminal visible con la orden
de un skill ya escrita. La app no llama a ningún modelo (ADR-001): lanza el agente que ya usas,
con tu suscripción, y tú ves, contestas y apruebas lo que haga.

- Las órdenes son una lista cerrada (`ACTIONS`) que construye la app. Lo único variable son el
  `job_id` y el `milestone_id` (fase 17), enteros: ningún texto de una oferta ni de una web llega
  al comando.
- Qué programa se lanza no está aquí: es `launch` del agente en `.agents/manifest.yaml` (regla
  dura 2). Con varios, elige `CAI_AGENT`; si no, el primero que lo tenga y esté instalado.
- Antes de lanzar se quitan del entorno las variables de `launch.unset_env` (p. ej. la clave de la
  API): así el agente usa tu suscripción y no factura por API.
- Solo Windows de momento (Windows Terminal o, si no está, una ventana de PowerShell). En otro
  sistema, o sin agente instalado, la UI copia la orden para que la pegues tú.
- «En segundo plano» (fase 19, ADR-032): las acciones con `background` también se pueden lanzar
  sin ventana desde el worker (`services/agent_runs.py`), con `launch.headless` del manifiesto y
  solo las herramientas MCP que declara la acción.
"""

import base64
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Literal

import yaml
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.models import Milestone
from app.models.base import utcnow
from app.services import events, interviews, process
from app.services.pipeline import Stage

MANIFEST = REPO_ROOT / ".agents" / "manifest.yaml"
PROMPT_PLACEHOLDER = "{prompt}"
TOOLS_PLACEHOLDER = "{allowed_tools}"
DENIED_PLACEHOLDER = "{denied_tools}"
SKILL_PLACEHOLDER = "{skill}"
SESSION_PLACEHOLDER = "{session_id}"
HEADLESS_OUTPUTS = frozenset({"claude-stream-json"})

ActionId = Literal[
    "buscar-ofertas",
    "procesar-ofertas",
    "evaluar-encaje",
    "generar-cv",
    "anadir-skills",
    "plan-formacion",
    "revisar-respuestas",
    "redactar-seguimientos",
    "redactar-seguimiento",
    "ampliar-busqueda",
    "preparar-entrevista",
    "simular-entrevista",
    "repasar-entrevista",
    "dudas-oferta",
    "preparar-negociacion",
    "redactar-mensaje",
    "investigar-empresa",
    "atender-encargos",
    "revisar-busqueda",
]

# Hitos de entrevista (fase 17): `upcoming`, programada y por empezar; `past`, ya empezada y no
# cancelada.
MilestoneRule = Literal["upcoming", "past"]


# Etapas en las que tiene sentido redactar el CV de una oferta (también para rehacerlo).
CV_STAGES = frozenset({Stage.APPROVED, Stage.CV_READY})
# Candidaturas enviadas y abiertas: a las que se escribe un seguimiento o un agradecimiento.
SENT_STAGES = frozenset({Stage.APPLIED, Stage.IN_PROCESS})
# Mensajes a personas de la empresa (fase 18): desde que apruebas la oferta.
OUTREACH_STAGES = frozenset({Stage.APPROVED, Stage.CV_READY, Stage.APPLIED, Stage.IN_PROCESS})
# Investigar la empresa: cualquier oferta abierta ya extraída (también para triarla).
RESEARCH_STAGES = OUTREACH_STAGES | {Stage.PENDING_TRIAGE}


@dataclass(frozen=True)
class Action:
    label: str
    prompt: str  # `{job_id}` si la acción es de una oferta; `{milestone_id}`, de un hito
    needs_job: bool = False
    stages: frozenset[Stage] = frozenset()  # con oferta: etapas en las que se puede lanzar
    wrong_stage: str = ""  # el motivo si la oferta no está en ellas
    milestone: MilestoneRule | None = None  # acción de un hito de entrevista (y de su oferta)
    needs_offer: bool = False  # solo si la oferta tiene un `offer_received`
    # Fase 19: herramientas MCP (sin prefijo) con las que se puede lanzar en segundo plano. Vacío:
    # la acción solo se abre en una terminal (pregunta, usa tu navegador o la web).
    background: tuple[str, ...] = ()
    skill: str | None = None  # el skill que usa la orden, si no se llama como la acción


ACTIONS: dict[ActionId, Action] = {
    "buscar-ofertas": Action(
        "Buscar ofertas",
        "Usa el skill buscar-ofertas de CandidatAI para buscar ofertas en las plataformas activas.",
    ),
    # Las tres que admiten segundo plano (fase 19). Cada lista es lo mínimo que usan el skill y
    # sus roles: con un comodín, una oferta con una inyección podría llamar a herramientas que
    # escriben (`add_event`, `save_source`…).
    "procesar-ofertas": Action(
        "Procesar ofertas",
        "Usa el skill procesar-ofertas de CandidatAI con las ofertas pendientes de extraer.",
        background=("get_status", "list_jobs", "get_job", "save_extraction"),
    ),
    "evaluar-encaje": Action(
        "Evaluar encaje",
        "Usa el skill evaluar-encaje de CandidatAI con las ofertas pendientes de revisar.",
        background=(
            "list_jobs",
            "get_profile",
            "get_context",
            "get_match",
            "get_extraction",
            "save_fit_assessment",
        ),
    ),
    "generar-cv": Action(
        "Generar CV",
        "Usa el skill generar-cv de CandidatAI para la oferta {job_id}.",
        needs_job=True,
        stages=CV_STAGES,
        wrong_stage="Solo se genera el CV de una oferta aprobada.",
        # Las obligatorias ausentes sin marcar se preguntan: `agent_runs` lo comprueba antes.
        background=(
            "list_jobs",
            "check_job_open",
            "get_match",
            "get_extraction",
            "get_profile",
            "get_context",
            "list_cv_templates",
            "save_cv_content",
            "get_cv_content",
            "save_cv_verification",
        ),
    ),
    # Página «Skills» (fase 14). Los nombres de las skills salen de las ofertas, así que no van en
    # la orden: el agente los lee de las marcas con `get_skill_gaps`.
    "anadir-skills": Action(
        "Añadir al perfil las que tengo",
        "Usa el skill actualizar-perfil de CandidatAI para añadir a mi perfil las skills que he "
        "marcado como «La tengo» en la página Skills (get_skill_gaps con status have).",
    ),
    "plan-formacion": Action(
        "Plan de formación",
        "Usa el skill plan-formacion de CandidatAI con los huecos de skills que he marcado como "
        "«No la tengo».",
    ),
    # Inicio y «Respuestas» (fase 15): el agente propone; el usuario acepta en la UI.
    "revisar-respuestas": Action(
        "Revisar respuestas",
        "Usa el skill revisar-respuestas de CandidatAI con los correos de empresas sin clasificar.",
    ),
    # Procesos y ficha (fase 15): el agente redacta; el usuario copia y envía desde su correo.
    "redactar-seguimientos": Action(
        "Redactar seguimientos",
        "Usa el skill redactar-seguimiento de CandidatAI con los seguimientos y agradecimientos "
        "pendientes.",
    ),
    # Plataformas (fase 16): títulos cercanos a los que apruebas. El agente propone; tú decides.
    "ampliar-busqueda": Action(
        "Ampliar búsqueda",
        "Usa el skill ampliar-busqueda de CandidatAI para proponerme títulos de puesto cercanos a "
        "los que apruebo.",
    ),
    # Embudo (fase 20): retrospectiva. Solo propone: los pesos y filtros los cambia el usuario.
    "revisar-busqueda": Action(
        "Revisar mi búsqueda",
        "Usa el skill revisar-busqueda de CandidatAI para hacer la retrospectiva de mi búsqueda: "
        "qué funciona y qué cambiar.",
    ),
    "redactar-seguimiento": Action(
        "Redactar seguimiento",
        "Usa el skill redactar-seguimiento de CandidatAI para la oferta {job_id}.",
        needs_job=True,
        stages=SENT_STAGES,
        wrong_stage="Solo se escribe a la empresa de una candidatura enviada y abierta.",
    ),
    # Ficha, hitos de entrevista (fase 17). El agente prepara, simula o repasa; lo que proponga
    # para el perfil pasa por `actualizar-perfil` y la confirmación del usuario.
    "preparar-entrevista": Action(
        "Preparar",
        "Usa el skill preparar-entrevista de CandidatAI para la entrevista {milestone_id} de la "
        "oferta {job_id}.",
        needs_job=True,
        milestone="upcoming",
    ),
    "simular-entrevista": Action(
        "Simulacro",
        "Usa el skill simular-entrevista de CandidatAI para la entrevista {milestone_id} de la "
        "oferta {job_id}.",
        needs_job=True,
        milestone="upcoming",
    ),
    "repasar-entrevista": Action(
        "Repasar",
        "Usa el skill repasar-entrevista de CandidatAI para repasar la entrevista {milestone_id} "
        "de la oferta {job_id}.",
        needs_job=True,
        milestone="past",
    ),
    # Ficha (fase 18): mensaje a una persona de la empresa y dosier de la empresa. El agente
    # redacta o investiga; la app no envía nada.
    "redactar-mensaje": Action(
        "Redactar mensaje",
        "Usa el skill redactar-mensaje de CandidatAI para la oferta {job_id}.",
        needs_job=True,
        stages=OUTREACH_STAGES,
        wrong_stage="Solo se escribe a la empresa de una oferta aprobada y abierta.",
    ),
    "investigar-empresa": Action(
        "Investigar empresa",
        "Usa el skill investigar-empresa de CandidatAI para la empresa de la oferta {job_id}.",
        needs_job=True,
        stages=RESEARCH_STAGES,
        wrong_stage="Solo para una oferta ya extraída y sin cerrar.",
    ),
    # Panel «Agente» (fase 19): la cola de encargos que dejaste para tu próxima sesión.
    "atender-encargos": Action(
        "Atender encargos",
        "Usa el skill atender-encargos de CandidatAI con los encargos pendientes.",
    ),
    "dudas-oferta": Action(
        "Dudas antes de aceptar",
        "Usa el skill repasar-entrevista de CandidatAI para revisar las dudas antes de aceptar la "
        "oferta {job_id}.",
        needs_job=True,
        stages=frozenset({Stage.IN_PROCESS}),
        wrong_stage="Solo con un proceso abierto.",
        needs_offer=True,
    ),
    # Fase 21: pregunta y admite pegar el contrato, así que solo en terminal.
    "preparar-negociacion": Action(
        "Preparar negociación",
        "Usa el skill preparar-negociacion de CandidatAI para la oferta {job_id}.",
        needs_job=True,
        stages=frozenset({Stage.IN_PROCESS}),
        wrong_stage="Solo con un proceso abierto.",
        needs_offer=True,
    ),
}


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
    prompt: str
    message: str


@dataclass(frozen=True)
class Headless:
    """`launch.headless` del manifiesto: cómo se lanza el agente sin ventana (fase 19)."""

    command: list[str]  # con `{prompt}`, `{allowed_tools}` y `{denied_tools}`
    allow: list[str]  # herramientas permitidas además del skill y las MCP de la acción
    skill_rule: str  # cómo se permite solo el skill de la acción (con `{skill}`)
    output: str  # formato de la salida (`claude-stream-json`)
    mcp_prefix: str  # `tools.mcp_prefix` del agente: nombre MCP → nombre nativo


@dataclass(frozen=True)
class _Launcher:
    agent: str
    command: list[str]
    unset_env: list[str]
    resume: list[str] = field(default_factory=list)  # con `{session_id}`
    headless: Headless | None = None


def prompt_for(action: ActionId, job_id: int | None = None, milestone_id: int | None = None) -> str:
    """La orden que se le da al agente (la misma que copia la UI si no puede lanzarlo)."""
    spec = ACTIONS[action]
    if spec.needs_job and job_id is None:
        raise LaunchError("invalid_request", f"«{spec.label}» necesita una oferta.")
    if spec.milestone and milestone_id is None:
        raise LaunchError("invalid_request", f"«{spec.label}» necesita una entrevista.")
    return spec.prompt.format(job_id=job_id, milestone_id=milestone_id)


def _launchers() -> list[_Launcher]:
    try:
        manifest = yaml.safe_load(MANIFEST.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    found = []
    for name, cfg in (manifest.get("targets") or {}).items():
        launch = (cfg or {}).get("launch") or {}
        command = [str(part) for part in launch.get("command") or []]
        if cfg.get("enabled") and command and PROMPT_PLACEHOLDER in command:
            unset = [str(v) for v in launch.get("unset_env") or []]
            resume = [str(part) for part in launch.get("resume") or []]
            if SESSION_PLACEHOLDER not in resume:
                resume = []
            headless = _headless(launch.get("headless"), (cfg.get("tools") or {}).get("mcp_prefix"))
            found.append(_Launcher(str(name), command, unset, resume, headless))
    return found


def _headless(cfg: object, prefix: object) -> Headless | None:
    """`launch.headless`, si está completo: orden, herramientas y un formato de salida conocido."""
    if not isinstance(cfg, dict) or not isinstance(prefix, str) or not prefix:
        return None
    command = [str(part) for part in cfg.get("command") or []]
    output = str(cfg.get("output") or "")
    skill_rule = str(cfg.get("skill_rule") or "")
    placeholders = (PROMPT_PLACEHOLDER, TOOLS_PLACEHOLDER, DENIED_PLACEHOLDER)
    if any(p not in command for p in placeholders) or SKILL_PLACEHOLDER not in skill_rule:
        return None  # sin la lista de denegadas no hay garantía: mejor sin segundo plano
    if output not in HEADLESS_OUTPUTS:
        return None
    allow = [str(t) for t in cfg.get("allow") or []]
    return Headless(command, allow, skill_rule, output, prefix)


def _pick() -> _Launcher | str:
    """El agente que se lanzaría, o el motivo por el que no hay ninguno."""
    if sys.platform != "win32":
        return "Abrir el agente desde la UI solo está disponible en Windows de momento."
    return _pick_any()


def _pick_any() -> _Launcher | str:
    """Como `_pick`, sin exigir Windows: el segundo plano no abre ninguna ventana."""
    launchers = _launchers()
    if not launchers:
        return "Ningún agente tiene `launch` en .agents/manifest.yaml."
    wanted = get_settings().agent
    if wanted:
        launchers = [launcher for launcher in launchers if launcher.agent == wanted]
        if not launchers:
            return f"CAI_AGENT={wanted}, pero ese agente no tiene `launch` en el manifiesto."
    for launcher in launchers:
        if shutil.which(launcher.command[0]):
            return launcher
    names = ", ".join(launcher.command[0] for launcher in launchers)
    return f"No se encuentra el programa del agente ({names}) en el PATH."


def info() -> AgentInfo:
    picked = _pick()
    if isinstance(picked, str):
        return AgentInfo(available=False, reason=picked)
    return AgentInfo(available=True, agent=picked.agent)


def _quote(value: str) -> str:
    """Literal de PowerShell entre comillas simples."""
    return "'" + value.replace("'", "''") + "'"


def powershell_command(
    launcher: _Launcher, value: str, command: Sequence[str] | None = None
) -> str:
    """Lo que ejecuta la ventana: quitar las variables de `unset_env` y abrir el agente. `value`
    va donde esté `{prompt}` (o `{session_id}`, si `command` es `launch.resume`)."""
    markers = (PROMPT_PLACEHOLDER, SESSION_PLACEHOLDER)
    parts = [value if p in markers else p for p in command or launcher.command]
    unset = [f"Remove-Item Env:{name} -ErrorAction SilentlyContinue" for name in launcher.unset_env]
    return "; ".join([*unset, "& " + " ".join(_quote(p) for p in parts)])


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
) -> tuple[str, int | None, int | None]:
    """Comprueba que la acción se puede lanzar para esa oferta o hito y devuelve su orden, con la
    oferta y el hito que le corresponden (`None` si la acción no los usa)."""
    spec = ACTIONS[action]
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
    return prompt_for(action, job_id, milestone_id), job_id, milestone_id


def launch(
    session: Session,
    action: ActionId,
    job_id: int | None = None,
    milestone_id: int | None = None,
) -> LaunchResult:
    """Abre el agente en una terminal con la orden de `action`. No espera a que termine."""
    spec = ACTIONS[action]
    prompt, _, _ = check_target(session, action, job_id, milestone_id)
    return _open(spec.label, prompt, lambda picked: picked.command, prompt)


def _open(
    label: str, prompt: str, command_of: Callable[[_Launcher], list[str]], value: str
) -> LaunchResult:
    """Abre la terminal con `command_of(agente)`, sustituyendo el marcador por `value`."""
    picked = _pick()
    if isinstance(picked, str):
        raise LaunchError("unavailable", picked, prompt)
    command = command_of(picked)
    try:
        _open_terminal(f"CandidatAI · {label}", powershell_command(picked, value, command))
    except OSError as exc:
        raise LaunchError("unavailable", f"No se pudo abrir la terminal: {exc}", prompt) from exc
    return LaunchResult(
        agent=picked.agent,
        prompt=prompt,
        message=f"Se ha abierto {picked.agent} en una terminal con la orden escrita.",
    )


def resumable_agents() -> frozenset[str]:
    """Los agentes que «Abrir en terminal» puede retomar: el que se abriría, si tiene `resume`."""
    picked = _pick()
    if isinstance(picked, str) or not picked.resume:
        return frozenset()
    return frozenset({picked.agent})


def resume_in_terminal(label: str, prompt: str, agent: str, session_id: str | None) -> LaunchResult:
    """«Abrir en terminal» de una ejecución en segundo plano (fase 19): retoma su sesión si el
    agente sabe (`launch.resume`) y es el mismo que la ejecutó; si no, abre la orden de nuevo."""
    picked = _pick()
    if (
        not isinstance(picked, str)
        and session_id
        and picked.agent == agent
        and picked.resume
        and SESSION_ID_RE.fullmatch(session_id)
    ):
        result = _open(label, prompt, lambda launcher: launcher.resume, session_id)
        result.message = f"Se ha abierto {picked.agent} en una terminal con la misma sesión."
        return result
    return _open(label, prompt, lambda launcher: launcher.command, prompt)


# --- En segundo plano (fase 19) ----------------------------------------------------------------

# Lo que se añade a la orden en segundo plano: nadie puede contestar. Las preguntas se recogen de
# la respuesta final (`agent_runs`) y se enseñan en la UI.
BACKGROUND_NOTE = (
    " Estás en segundo plano y nadie puede contestarte: no preguntes ni esperes confirmación. Si "
    "necesitas algo del usuario para seguir, para ahí y termina tu respuesta con una línea por "
    "pregunta que empiece por «PREGUNTA:»."
)
# Fase 14: con todas las obligatorias ausentes marcadas como «No la tengo», `generar-cv` no tiene
# nada que preguntar. Los nombres de las skills salen de las ofertas: no van en la orden.
GAPS_MARKED_NOTE = (
    " Las skills obligatorias ausentes de esa oferta ya las he marcado como «No la tengo» en la "
    "página Skills: no preguntes por ellas ni las pongas en el CV."
)
QUESTION_PREFIX = "PREGUNTA:"
# Identificador de sesión que devuelve el agente: solo se pasa al comando si tiene esta forma.
SESSION_ID_RE = re.compile(r"[A-Za-z0-9-]{8,64}")


class BackgroundInfo(BaseModel):
    """Si los botones pueden lanzar en segundo plano, con qué agente o por qué no."""

    available: bool
    agent: str | None = None
    reason: str | None = None


def pick_headless() -> _Launcher | str:
    """El agente con el que se lanzaría en segundo plano, o el motivo por el que no se puede."""
    picked = _pick_any()
    if isinstance(picked, str):
        return picked
    if picked.headless is None:
        return (
            f"Tu agente ({picked.agent}) no tiene `launch.headless` en .agents/manifest.yaml: "
            "usa «En terminal»."
        )
    return picked


def background_info() -> BackgroundInfo:
    picked = pick_headless()
    if isinstance(picked, str):
        return BackgroundInfo(available=False, reason=picked)
    return BackgroundInfo(available=True, agent=picked.agent)


def all_mcp_tools() -> list[str]:
    """Todas las herramientas de la interfaz para agentes (las que se deniegan si no son de la
    acción). Se importa aquí: el registro importa servicios que importan este módulo."""
    from app.agent_interface.tools import TOOLS_BY_NAME

    return sorted(TOOLS_BY_NAME)


def headless_command(launcher: _Launcher, prompt: str, action: ActionId) -> list[str]:
    """El comando sin ventana. Una herramienta por argumento: en `{allowed_tools}`, las de `allow`,
    el skill de la acción y sus herramientas MCP; en `{denied_tools}`, todas las demás MCP (un
    deny gana a cualquier allow de la configuración del agente y vale para sus subagentes)."""
    spec = ACTIONS[action]
    if launcher.headless is None or not spec.background:
        raise LaunchError("unavailable", "Esta acción no se puede lanzar en segundo plano.")
    headless = launcher.headless
    prefix = headless.mcp_prefix
    allowed = [
        *headless.allow,
        headless.skill_rule.replace(SKILL_PLACEHOLDER, spec.skill or action),
        *(prefix + tool for tool in spec.background),
    ]
    denied = [prefix + tool for tool in all_mcp_tools() if tool not in spec.background]
    command: list[str] = []
    for part in headless.command:
        if part == PROMPT_PLACEHOLDER:
            command.append(prompt)
        elif part == TOOLS_PLACEHOLDER:
            command.extend(allowed)
        elif part == DENIED_PLACEHOLDER:
            command.extend(denied)
        else:
            command.append(part)
    return command
