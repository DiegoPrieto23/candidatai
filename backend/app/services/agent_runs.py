"""«En segundo plano» (fase 19): el agente sin ventana, desde el worker, para los skills
que no preguntan. Sin coste de API: es el mismo agente de los botones, con tu suscripción.

- Solo las acciones con `background` en `agent_launch.ACTIONS` (procesar ofertas, evaluar encaje y
  generar el CV) y solo con un agente que tenga `launch.headless` en el manifiesto.
- La ejecución tiene solo las herramientas MCP de la acción, sin terminal ni web: van en el comando
  (Claude Code, que deniega lo demás con `dontAsk`) o, en los agentes que las limitan por
  configuración (OpenCode, fase 24.5), en una propia de la ejecución (`run_config`). Las dos cosas
  se guardan en la fila para auditar qué podía hacer.
- `agent_runs` es su propia cola: la lanza la UI y la ejecuta el worker (`agent_runner.py`), de
  una en una y en un hilo aparte, para no parar la ingesta ni la candidatura asistida.
- Si el skill necesita al usuario, termina con líneas «PREGUNTA:» y la ejecución queda
  `needs_user`: la UI enseña las preguntas y «Abrir en terminal» sigue en la misma sesión.
- Como los botones, solo la UI lanza: no hay herramienta MCP ni comando `--json`.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import AgentRun, SkillGapMark
from app.models.base import utcnow
from app.services import agent_launch, assess_threshold
from app.services.agent_launch import ACTIONS, ActionId, LaunchError, LaunchResult
from app.services.agent_usage import normalize_usage
from app.services.matching import service as matching
from app.services.matching import skills

RunStatus = Literal["queued", "running", "done", "needs_user", "failed", "cancelled", "timeout"]
ACTIVE: tuple[RunStatus, ...] = ("queued", "running")
FINISHED: tuple[RunStatus, ...] = ("done", "needs_user", "failed", "cancelled", "timeout")
ProgressKind = Literal["tool", "text", "info", "error"]
INTERRUPTED = "El worker se cerró mientras se ejecutaba. No se repite: lánzala otra vez si quieres."


class ProgressLine(BaseModel):
    at: datetime
    kind: ProgressKind
    text: str


class AgentRunView(BaseModel):
    id: int
    action: ActionId
    label: str
    job_id: int | None
    milestone_id: int | None
    agent: str
    model: str | None  # fase 24.4: el modelo o el preset con que se lanzó (`None`: el del agente)
    status: RunStatus
    prompt: str
    allowed_tools: list[str]  # herramientas MCP de la acción (sin prefijo)
    progress: list[ProgressLine]
    result: str | None
    questions: list[str]
    error: str | None
    usage: dict[str, int | float] | None  # `agent_usage.USAGE_KEYS`; `None` sin uso
    cancel_requested: bool
    can_resume: bool  # «Abrir en terminal» retoma la misma sesión
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class AgentRunList(BaseModel):
    runs: list[AgentRunView]
    active: int  # en cola o en curso


class RunNotFoundError(LookupError):
    pass


def view(row: AgentRun, resumable: frozenset[str] | None = None) -> AgentRunView:
    """`resumable`: los agentes que saben retomar una sesión (si no se da, se mira ahora)."""
    resumable = agent_launch.resumable_agents() if resumable is None else resumable
    spec = ACTIONS[row.action]
    return AgentRunView(
        id=row.id,
        action=row.action,
        label=spec.label,
        job_id=row.job_id,
        milestone_id=row.milestone_id,
        agent=row.agent,
        model=agent_launch.model_label(row.model, row.preset),
        status=row.status,
        prompt=row.prompt,
        allowed_tools=list(spec.background),
        progress=[ProgressLine.model_validate(p) for p in row.progress or []],
        result=row.result,
        questions=list(row.questions or []),
        error=row.error,
        usage=normalize_usage(row.usage) or None,  # fase 25.4: claves comunes
        cancel_requested=row.cancel_requested,
        can_resume=bool(row.session_id) and row.status in FINISHED and row.agent in resumable,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )


def _cv_gaps_note(session: Session, job_id: int) -> str:
    """`generate-cv` pregunta por las obligatorias ausentes del perfil. En segundo plano solo se
    lanza si no hay ninguna o si todas están marcadas como «No la tengo» (fase 14): entonces la
    orden lo dice, sin nombrarlas (salen de la oferta)."""
    missing = matching.get_match(session, job_id).breakdown.must_have.missing
    if not missing:
        return ""
    index = skills.alias_index()
    marks = {m.skill_key: m.status for m in session.scalars(select(SkillGapMark))}
    unmarked = [name for name in missing if marks.get(skills.canonical(name, index)) != "gap"]
    if unmarked:
        count = len(unmarked)
        noun = "skill obligatoria" if count == 1 else "skills obligatorias"
        raise LaunchError(
            "invalid_request",
            f"A tu perfil le faltan {count} {noun} de esta oferta y el skill te preguntará si las "
            "tienes: usa «En terminal», o márcalas antes en la página Skills.",
        )
    return agent_launch.GAPS_MARKED_NOTE


def _assess_prompt(session: Session, min_score: int | None = None) -> str:
    """«Evaluar encaje» en segundo plano solo con las ofertas que llegan al umbral; si no queda
    ninguna, no se lanza y dice por qué."""
    plan = assess_threshold.plan(session, min_score)
    if not plan.eligible:
        below = len(plan.skipped)
        detail = (
            f" {below} {'tiene' if below == 1 else 'tienen'} un score por debajo de "
            f"{plan.threshold} y no se valoran en segundo plano (cambia el umbral en la página "
            "«Agente» o valóralas «En terminal»)."
            if below
            else ""
        )
        raise LaunchError("invalid_request", f"No hay ofertas pendientes de valorar.{detail}")
    return assess_threshold.prompt(plan)


def _active(session: Session, action: str, job_id: int | None) -> AgentRun | None:
    return session.scalars(
        select(AgentRun)
        .where(AgentRun.action == action, AgentRun.status.in_(ACTIVE), AgentRun.job_id == job_id)
        .order_by(AgentRun.id)
        .limit(1)
    ).first()


def start(
    session: Session,
    action: ActionId,
    job_id: int | None = None,
    milestone_id: int | None = None,
    *,
    agent: str | None = None,
    model: str | None = None,
    preset: str | None = None,
    min_score: int | None = None,
) -> AgentRunView:
    """Deja en cola una ejecución en segundo plano. Si ya hay una igual en cola o en curso,
    devuelve esa en vez de duplicarla. `agent`, `model` y `preset`: la elección puntual (si no, las
    preferencias de `agent_prefs`). `min_score`: el umbral de `assess-fit` solo esta vez."""
    spec = ACTIONS[action]
    if not spec.background:
        raise LaunchError(
            "invalid_request",
            f"«{spec.label}» no se puede lanzar en segundo plano (pregunta, usa tu navegador o la "
            "web): usa «En terminal».",
        )
    prompt, job_id, milestone_id = agent_launch.check_target(session, action, job_id, milestone_id)
    picked = agent_launch.pick(
        session, action, prompt, agent=agent, model=model, preset=preset, mode="background"
    )
    if (existing := _active(session, action, job_id)) is not None:
        return view(existing)
    if action == "assess-fit":  # fase 25.4: umbral antes de gastar
        prompt = _assess_prompt(session, min_score)
    note = _cv_gaps_note(session, job_id) if action == "generate-cv" and job_id else ""
    full_prompt = prompt + note + agent_launch.BACKGROUND_NOTE
    assert picked.headless is not None  # lo garantiza `pick_headless`
    row = AgentRun(
        action=action,
        job_id=job_id,
        milestone_id=milestone_id,
        agent=picked.agent,
        model=picked.model,
        preset=picked.preset,
        status="queued",
        prompt=full_prompt,
        command=agent_launch.headless_command(picked, full_prompt, action),
        unset_env=list(picked.unset_env),
        output_format=picked.headless.output,
        run_config=agent_launch.run_config(picked),
        progress=[],
        questions=[],
        cancel_requested=False,
    )
    session.add(row)
    session.flush()
    return view(row)


def _row(session: Session, run_id: int) -> AgentRun:
    row = session.get(AgentRun, run_id)
    if row is None:
        raise RunNotFoundError(f"No existe la ejecución {run_id}.")
    return row


def get_run(session: Session, run_id: int) -> AgentRunView:
    return view(_row(session, run_id))


def list_runs(session: Session, limit: int = 20, job_id: int | None = None) -> AgentRunList:
    query = select(AgentRun).order_by(AgentRun.id.desc()).limit(limit)
    if job_id is not None:
        query = query.where(AgentRun.job_id == job_id)
    rows = session.scalars(query).all()
    active = len(session.scalars(select(AgentRun.id).where(AgentRun.status.in_(ACTIVE))).all())
    resumable = agent_launch.resumable_agents()
    return AgentRunList(runs=[view(r, resumable) for r in rows], active=active)


def cancel(session: Session, run_id: int) -> AgentRunView:
    """En cola: se cancela ya. En curso: lo pide y el worker para el proceso en unos segundos.
    Con `UPDATE` condicionados: si el worker la reclama a la vez, queda pedida, no pisada."""
    _row(session, run_id)
    queued = session.execute(
        update(AgentRun)
        .where(AgentRun.id == run_id, AgentRun.status == "queued")
        .values(status="cancelled", finished_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    if queued.rowcount != 1:
        running = session.execute(
            update(AgentRun)
            .where(AgentRun.id == run_id, AgentRun.status == "running")
            .values(cancel_requested=True)
            .execution_options(synchronize_session=False)
        )
        if running.rowcount != 1:
            raise LaunchError("invalid_request", "Esa ejecución ya ha terminado.")
    session.expire_all()
    return view(_row(session, run_id))


def open_in_terminal(session: Session, run_id: int) -> LaunchResult:
    """«Abrir en terminal» de una ejecución terminada: sigue su sesión (para contestar las
    preguntas) o, si el agente no sabe retomarla, abre la orden de siempre."""
    row = _row(session, run_id)
    if row.status in ACTIVE:
        raise LaunchError("invalid_request", "Espera a que termine o cancélala antes.")
    action: ActionId = row.action  # validado al crearla
    prompt = agent_launch.prompt_for(action, row.job_id, row.milestone_id)
    return agent_launch.resume_in_terminal(
        session, action, prompt, row.agent, row.session_id, row.model, row.preset
    )
