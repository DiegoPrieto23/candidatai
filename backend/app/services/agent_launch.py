"""Botones «en tu agente» de la UI (ADR-024): abren tu agente en una terminal visible con la orden
de un skill ya escrita. La app no llama a ningún modelo (ADR-001): lanza el agente que ya usas,
con tu suscripción, y tú ves, contestas y apruebas lo que haga.

- Las órdenes son una lista cerrada (`ACTIONS`) que construye la app. Lo único variable es el
  `job_id`, un entero: ningún texto de una oferta ni de una web llega al comando.
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
from app.services import events
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
]


@dataclass(frozen=True)
class Action:
    label: str
    prompt: str  # `{job_id}` si la acción es de una oferta
    needs_job: bool = False


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
}
# Etapas en las que tiene sentido redactar el CV de una oferta (también para rehacerlo).
CV_STAGES = frozenset({Stage.APPROVED, Stage.CV_READY})


class LaunchError(Exception):
    def __init__(self, code: Literal["not_found", "invalid_request", "unavailable"], message: str):
        super().__init__(message)
        self.code = code


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


def prompt_for(action: ActionId, job_id: int | None = None) -> str:
    """La orden que se le da al agente (la misma que copia la UI si no puede lanzarlo)."""
    spec = ACTIONS[action]
    if spec.needs_job and job_id is None:
        raise LaunchError("invalid_request", f"«{spec.label}» necesita una oferta.")
    return spec.prompt.format(job_id=job_id)


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


def launch(session: Session, action: ActionId, job_id: int | None = None) -> LaunchResult:
    """Abre el agente en una terminal con la orden de `action`. No espera a que termine."""
    spec = ACTIONS[action]
    if spec.needs_job:
        if job_id is None:
            raise LaunchError("invalid_request", f"«{spec.label}» necesita una oferta.")
        try:
            stage = events.current_stage(session, job_id)
        except events.JobNotFoundError as exc:
            raise LaunchError("not_found", f"No existe la oferta {job_id}.") from exc
        if stage not in CV_STAGES:
            raise LaunchError("invalid_request", "Solo se genera el CV de una oferta aprobada.")
    prompt = prompt_for(action, job_id if spec.needs_job else None)
    picked = _pick()
    if isinstance(picked, str):
        raise LaunchError("unavailable", picked)
    try:
        _open_terminal(f"Job Hunter · {spec.label}", powershell_command(picked, prompt))
    except OSError as exc:
        raise LaunchError("unavailable", f"No se pudo abrir la terminal: {exc}") from exc
    return LaunchResult(
        agent=picked.agent,
        prompt=prompt,
        message=f"Se ha abierto {picked.agent} en una terminal con la orden escrita.",
    )
