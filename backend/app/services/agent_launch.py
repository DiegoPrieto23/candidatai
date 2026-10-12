"""Botones «en tu agente» de la UI (ADR-024): abren tu agente en una terminal visible con la orden
de un skill ya escrita. La app no llama a ningún modelo (ADR-001): lanza el agente que ya usas,
con tu suscripción, y tú ves, contestas y apruebas lo que haga.

- Las órdenes son una lista cerrada (`ACTIONS`) que construye la app. Lo único variable son el
  `job_id` y el `milestone_id` (fase 17), enteros: ningún texto de una oferta ni de una web llega
  al comando.
- Qué programa se lanza no está aquí: es `launch` del agente en `.agents/manifest.yaml` (regla
  dura 2). Con varios, elige `JH_AGENT`; si no, el primero que lo tenga y esté instalado.
- Antes de lanzar se quitan del entorno las variables de `launch.unset_env` (p. ej. la clave de la
  API): así el agente usa tu suscripción y no factura por API.
- Solo Windows de momento (Windows Terminal o, si no está, una ventana de PowerShell). En otro
  sistema, o sin agente instalado, la UI copia la orden para que la pegues tú.
"""

import base64
import shutil
import subprocess
import sys
from dataclasses import dataclass
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
]

# Hitos de entrevista (fase 17): `upcoming`, programada y por empezar; `past`, ya empezada y no
# cancelada.
MilestoneRule = Literal["upcoming", "past"]


# Etapas en las que tiene sentido redactar el CV de una oferta (también para rehacerlo).
CV_STAGES = frozenset({Stage.APPROVED, Stage.CV_READY})
# Candidaturas enviadas y abiertas: a las que se escribe un seguimiento o un agradecimiento.
SENT_STAGES = frozenset({Stage.APPLIED, Stage.IN_PROCESS})


@dataclass(frozen=True)
class Action:
    label: str
    prompt: str  # `{job_id}` si la acción es de una oferta; `{milestone_id}`, de un hito
    needs_job: bool = False
    stages: frozenset[Stage] = frozenset()  # con oferta: etapas en las que se puede lanzar
    wrong_stage: str = ""  # el motivo si la oferta no está en ellas
    milestone: MilestoneRule | None = None  # acción de un hito de entrevista (y de su oferta)
    needs_offer: bool = False  # solo si la oferta tiene un `offer_received`


ACTIONS: dict[ActionId, Action] = {
    "buscar-ofertas": Action(
        "Buscar ofertas",
        "Usa el skill buscar-ofertas de Job Hunter para buscar ofertas en las plataformas activas.",
    ),
    "procesar-ofertas": Action(
        "Procesar ofertas",
        "Usa el skill procesar-ofertas de Job Hunter con las ofertas pendientes de extraer.",
    ),
    "evaluar-encaje": Action(
        "Evaluar encaje",
        "Usa el skill evaluar-encaje de Job Hunter con las ofertas pendientes de revisar.",
    ),
    "generar-cv": Action(
        "Generar CV",
        "Usa el skill generar-cv de Job Hunter para la oferta {job_id}.",
        needs_job=True,
        stages=CV_STAGES,
        wrong_stage="Solo se genera el CV de una oferta aprobada.",
    ),
    # Página «Skills» (fase 14). Los nombres de las skills salen de las ofertas, así que no van en
    # la orden: el agente los lee de las marcas con `get_skill_gaps`.
    "anadir-skills": Action(
        "Añadir al perfil las que tengo",
        "Usa el skill actualizar-perfil de Job Hunter para añadir a mi perfil las skills que he "
        "marcado como «La tengo» en la página Skills (get_skill_gaps con status have).",
    ),
    "plan-formacion": Action(
        "Plan de formación",
        "Usa el skill plan-formacion de Job Hunter con los huecos de skills que he marcado como "
        "«No la tengo».",
    ),
    # Inicio y «Respuestas» (fase 15): el agente propone; el usuario acepta en la UI.
    "revisar-respuestas": Action(
        "Revisar respuestas",
        "Usa el skill revisar-respuestas de Job Hunter con los correos de empresas sin clasificar.",
    ),
    # Procesos y ficha (fase 15): el agente redacta; el usuario copia y envía desde su correo.
    "redactar-seguimientos": Action(
        "Redactar seguimientos",
        "Usa el skill redactar-seguimiento de Job Hunter con los seguimientos y agradecimientos "
        "pendientes.",
    ),
    # Plataformas (fase 16): títulos cercanos a los que apruebas. El agente propone; tú decides.
    "ampliar-busqueda": Action(
        "Ampliar búsqueda",
        "Usa el skill ampliar-busqueda de Job Hunter para proponerme títulos de puesto cercanos a "
        "los que apruebo.",
    ),
    "redactar-seguimiento": Action(
        "Redactar seguimiento",
        "Usa el skill redactar-seguimiento de Job Hunter para la oferta {job_id}.",
        needs_job=True,
        stages=SENT_STAGES,
        wrong_stage="Solo se escribe a la empresa de una candidatura enviada y abierta.",
    ),
    # Ficha, hitos de entrevista (fase 17). El agente prepara, simula o repasa; lo que proponga
    # para el perfil pasa por `actualizar-perfil` y la confirmación del usuario.
    "preparar-entrevista": Action(
        "Preparar",
        "Usa el skill preparar-entrevista de Job Hunter para la entrevista {milestone_id} de la "
        "oferta {job_id}.",
        needs_job=True,
        milestone="upcoming",
    ),
    "simular-entrevista": Action(
        "Simulacro",
        "Usa el skill simular-entrevista de Job Hunter para la entrevista {milestone_id} de la "
        "oferta {job_id}.",
        needs_job=True,
        milestone="upcoming",
    ),
    "repasar-entrevista": Action(
        "Repasar",
        "Usa el skill repasar-entrevista de Job Hunter para repasar la entrevista {milestone_id} "
        "de la oferta {job_id}.",
        needs_job=True,
        milestone="past",
    ),
    "dudas-oferta": Action(
        "Dudas antes de aceptar",
        "Usa el skill repasar-entrevista de Job Hunter para revisar las dudas antes de aceptar la "
        "oferta {job_id}.",
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
class _Launcher:
    agent: str
    command: list[str]
    unset_env: list[str]


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
            found.append(_Launcher(str(name), command, unset))
    return found


def _pick() -> _Launcher | str:
    """El agente que se lanzaría, o el motivo por el que no hay ninguno."""
    if sys.platform != "win32":
        return "Abrir el agente desde la UI solo está disponible en Windows de momento."
    launchers = _launchers()
    if not launchers:
        return "Ningún agente tiene `launch` en .agents/manifest.yaml."
    wanted = get_settings().agent
    if wanted:
        launchers = [launcher for launcher in launchers if launcher.agent == wanted]
        if not launchers:
            return f"JH_AGENT={wanted}, pero ese agente no tiene `launch` en el manifiesto."
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


def powershell_command(launcher: _Launcher, prompt: str) -> str:
    """Lo que ejecuta la ventana: quitar las variables de `unset_env` y abrir el agente."""
    parts = [prompt if p == PROMPT_PLACEHOLDER else p for p in launcher.command]
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


def launch(
    session: Session,
    action: ActionId,
    job_id: int | None = None,
    milestone_id: int | None = None,
) -> LaunchResult:
    """Abre el agente en una terminal con la orden de `action`. No espera a que termine."""
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
    prompt = prompt_for(
        action, job_id if spec.needs_job else None, milestone_id if spec.milestone else None
    )
    picked = _pick()
    if isinstance(picked, str):
        raise LaunchError("unavailable", picked, prompt)
    try:
        _open_terminal(f"Job Hunter · {spec.label}", powershell_command(picked, prompt))
    except OSError as exc:
        raise LaunchError("unavailable", f"No se pudo abrir la terminal: {exc}", prompt) from exc
    return LaunchResult(
        agent=picked.agent,
        prompt=prompt,
        message=f"Se ha abierto {picked.agent} en una terminal con la orden escrita.",
    )
