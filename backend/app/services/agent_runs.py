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
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models import AgentRun, AgentRunEvent, AssistantRequest, SkillGapMark, UserPrompt
from app.models.base import utcnow
from app.services import agent_launch, agent_tasks, assess_threshold, prompts, ui_language
from app.services.agent_launch import ACTIONS, ActionId, LaunchError, LaunchResult
from app.services.agent_usage import normalize_usage
from app.services.matching import service as matching
from app.services.matching import skills
from app.services.prompts import PromptView

RunStatus = Literal["queued", "running", "done", "needs_user", "failed", "cancelled", "timeout"]
ACTIVE: tuple[RunStatus, ...] = ("queued", "running")
FINISHED: tuple[RunStatus, ...] = ("done", "needs_user", "failed", "cancelled", "timeout")
ProgressKind = Literal["tool", "text", "info", "error"]
# La conversación de una ejecución (`agent_run_events`), para seguirla en el portal.
# Fase 48.1c: escribirle al agente. `live`: está trabajando y lo recibe con su siguiente
# herramienta; `resume`: terminó y se retoma la misma sesión sin ventana; `window`: terminó y solo
# se puede seguir en una ventana; `none`: no se puede.
ReplyMode = Literal["live", "resume", "window", "none"]
MAX_MESSAGE = 2000
EventKind = Literal[
    "system",
    "tool_start",
    "tool_result",
    "text",
    "user",
    "question",
    "permission",
    "result",
    "error",
]
INTERRUPTED = "El worker se cerró mientras se ejecutaba. No se repite: se puede lanzar otra vez."


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
    asks_permissions: bool = False  # fase 48.1b: su agente pide los permisos al portal
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class AgentRunList(BaseModel):
    runs: list[AgentRunView]
    active: int  # en cola o en curso


class AgentRunEventView(BaseModel):
    seq: int
    at: datetime
    kind: EventKind
    tool: str | None  # sin prefijo MCP
    text: str | None  # del agente: contenido no confiable, se pinta como texto plano
    ok: bool | None
    sub: bool


class AgentRunEvents(BaseModel):
    """La conversación de una ejecución desde `after` (el `seq` del último que ya se tiene)."""

    run_id: int
    status: RunStatus
    events: list[AgentRunEventView]
    last_seq: int  # para la próxima consulta; el de `after` si no hay nada nuevo
    # Fase 48.1b: sus preguntas y permisos, contestados o no (siempre todos: cambian de estado).
    prompts: list[PromptView] = []
    # Fase 48.1c: qué pasa si se le escribe ahora (`reply_mode`).
    reply: ReplyMode = "none"


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
        asks_permissions=agent_tasks.asks_permissions(row.agent),
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
            f"Al perfil le faltan {count} {noun} de esta oferta y el skill preguntará si se "
            "tienen: hay que usar «En terminal», o marcarlas antes en la página «Habilidades por "
            "desarrollar».",
        )
    return agent_launch.gaps_marked_note(ui_language.current(session))


def _assess_prompt(session: Session, min_score: int | None = None) -> str:
    """«Valorar las que están por revisar» en segundo plano solo con las ofertas que llegan al
    umbral; si no queda ninguna, no se lanza y dice por qué."""
    plan = assess_threshold.plan(session, min_score)
    if not plan.eligible:
        below = len(plan.skipped)
        detail = (
            f" {below} {'tiene' if below == 1 else 'tienen'} un score por debajo de "
            f"{plan.threshold} y no se valoran en segundo plano (el umbral se cambia en la página "
            "«Agente», o se valoran «En terminal»)."
            if below
            else ""
        )
        raise LaunchError("invalid_request", f"No hay ofertas pendientes de valorar.{detail}")
    return assess_threshold.prompt(plan, ui_language.current(session))


def _threshold_note(session: Session, min_score: int | None = None) -> str:
    """«Valorar las ofertas nuevas» en segundo plano: la valoración (fase 2) solo con las ofertas
    que llegan al umbral, como «Valorar las que están por revisar». Las leídas pero por debajo
    quedan sin valorar, con el motivo en «Por revisar»."""
    threshold = (
        min_score if min_score is not None else assess_threshold.get_threshold(session).value
    )
    if ui_language.current(session) == "en":
        return (
            f" When assessing (step 2), only the jobs with a score of {threshold} or more: the "
            "others are not assessed in the background."
        )
    return (
        f" Al valorar (fase 2), solo las ofertas con un score de {threshold} o más: las demás "
        "no se valoran en segundo plano."
    )


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
    assistant_id: int | None = None,
) -> AgentRunView:
    """Deja en cola una ejecución en segundo plano. Si ya hay una igual en cola o en curso,
    devuelve esa en vez de duplicarla. `agent`, `model` y `preset`: la elección puntual (si no, las
    preferencias de `agent_prefs`). `min_score`: el umbral de `assess-fit` solo esta vez.
    `assistant_id`: la petición de «Asistente»; cada una es una ejecución distinta."""
    spec = ACTIONS[action]
    if not spec.background:
        raise LaunchError(
            "invalid_request",
            f"«{spec.label}» no se puede lanzar en segundo plano (pregunta, usa el navegador o la "
            "web): hay que usar «En terminal».",
        )
    prompt, job_id, milestone_id = agent_launch.check_target(
        session, action, job_id, milestone_id, assistant_id=assistant_id
    )
    picked = agent_launch.pick(
        session, action, prompt, agent=agent, model=model, preset=preset, mode="background"
    )
    if not spec.assistant and (existing := _active(session, action, job_id)) is not None:
        return view(existing)
    if action == "assess-fit":  # fase 25.4: umbral antes de gastar
        prompt = _assess_prompt(session, min_score)
    elif action == "process-jobs":  # su fase 2 valora, con el mismo umbral
        prompt += _threshold_note(session, min_score)
    note = _cv_gaps_note(session, job_id) if action == "generate-cv" and job_id else ""
    lang = ui_language.current(session)
    closing = (
        agent_launch.assistant_note(lang)
        if spec.assistant
        else agent_launch.background_note(lang, can_ask="ask_user" in spec.background)
    )
    full_prompt = prompt + note + closing
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
    agent_tasks.start(session, action, job_id, milestone_id, run_id=row.id)
    return view(row)


def _row(session: Session, run_id: int) -> AgentRun:
    row = session.get(AgentRun, run_id)
    if row is None:
        raise RunNotFoundError(f"No existe la ejecución {run_id}.")
    return row


def get_run(session: Session, run_id: int) -> AgentRunView:
    return view(_row(session, run_id))


EVENTS_PAGE = 500


def run_events(session: Session, run_id: int, after: int = 0) -> AgentRunEvents:
    """Lo nuevo de la conversación desde `after`, en orden. El portal la consulta cada poco."""
    row = _row(session, run_id)
    rows = session.scalars(
        select(AgentRunEvent)
        .where(AgentRunEvent.run_id == run_id, AgentRunEvent.seq > after)
        .order_by(AgentRunEvent.seq)
        .limit(EVENTS_PAGE)
    ).all()
    events = [
        AgentRunEventView(
            seq=e.seq,
            at=e.at,
            kind=e.kind,  # type: ignore[arg-type]
            tool=e.tool,
            text=e.text,
            ok=e.ok,
            sub=e.sub,
        )
        for e in rows
    ]
    asked = session.scalars(
        select(UserPrompt).where(UserPrompt.run_id == run_id).order_by(UserPrompt.id)
    ).all()
    return AgentRunEvents(
        run_id=run_id,
        status=row.status,  # type: ignore[arg-type]
        events=events,
        last_seq=events[-1].seq if events else after,
        prompts=[prompts.get(session, p.id) for p in asked],
        reply=reply_mode(row),
    )


# --- Escribirle al agente (fase 48.1c) ---------------------------------------------------------


def _launcher_of(agent: str) -> agent_launch._Launcher | None:
    return next((x for x in agent_launch._launchers() if x.agent == agent), None)


def reply_mode(row: AgentRun) -> ReplyMode:
    if row.status in ACTIVE:
        return "live"
    launcher = _launcher_of(row.agent)
    if launcher is None or not row.session_id:
        return "none"
    if launcher.headless is not None and launcher.headless.resume_after is not None:
        return "resume"
    return "window" if launcher.resume else "none"


def _last_seq(session: Session, run_id: int) -> int:
    last = session.scalar(select(func.max(AgentRunEvent.seq)).where(AgentRunEvent.run_id == run_id))
    return last or 0


def _next_seq(session: Session, run_id: int) -> int:
    return _last_seq(session, run_id) + 1


def _clean_message(text: str) -> str:
    clean = text.strip()
    if not clean:
        raise LaunchError("invalid_request", "Falta escribir el mensaje.")
    if len(clean) > MAX_MESSAGE:
        raise LaunchError(
            "invalid_request", f"El mensaje no puede pasar de {MAX_MESSAGE} caracteres."
        )
    return clean


def send_message(session: Session, run_id: int, text: str) -> AgentRunEvents:
    """Lo que el usuario le escribe al agente desde el panel. Mientras trabaja, se guarda y se le
    pasa con la respuesta de su siguiente herramienta (`take_user_messages`). Si ya terminó y su
    agente sabe retomar sin ventana, la misma ejecución vuelve a la cola con la sesión de antes y
    el mensaje como orden: la conversación, los pasos y el coste siguen en el mismo sitio."""
    message = _clean_message(text)
    _row(session, run_id)
    # Con la base reservada para escribir (savepoint → `BEGIN IMMEDIATE`, `core.db`): el estado
    # leído aquí es el que se cambia (el worker no puede reclamarla ni terminarla entre medias) y el
    # `seq` no choca con el del runner.
    with session.begin_nested():
        row = _row(session, run_id)
        session.refresh(row)
        mode = reply_mode(row)
        if mode in ("window", "none"):
            raise LaunchError(
                "invalid_request",
                "Esta ejecución no se puede retomar sin ventana: hay que abrirla en una ventana.",
            )
        now = utcnow()
        session.add(
            AgentRunEvent(
                run_id=run_id,
                seq=_next_seq(session, run_id),
                at=now,
                kind="user",
                text=message,
                sub=False,
                delivered_at=None,  # al retomar, `_resume` la pasa en la orden
            )
        )
        session.flush()
        if mode == "resume":
            _resume(session, row)
    session.flush()
    return run_events(session, run_id)


# Delante de lo que escribe el usuario: la orden nunca empieza por su texto (no puede colarse una
# bandera como `--algo`), y el agente sabe que es una petición del usuario.
RESUME_HEADER = {
    "es": "Mensajes del usuario en el portal, sobre lo que acabas de hacer:",
    "en": "Messages from the user in the portal, about what you have just done:",
}


def _resume(session: Session, row: AgentRun) -> None:
    """Vuelve a poner en cola la misma ejecución, retomando su sesión. Mismo agente, modelo y
    techo; el aviso de la acción se reabre. La orden lleva todo lo que el usuario escribió y aún no
    le había llegado (también lo escrito a mitad, si ya no llamó a ninguna herramienta), y lo que
    quedara por contestar en el portal de esa ejecución se cierra."""
    action: ActionId = row.action  # type: ignore[assignment]
    lang = ui_language.current(session)
    pending = list(
        session.scalars(
            select(AgentRunEvent)
            .where(
                AgentRunEvent.run_id == row.id,
                AgentRunEvent.kind == "user",
                AgentRunEvent.delivered_at.is_(None),
            )
            .order_by(AgentRunEvent.seq)
        )
    )
    now = utcnow()
    for event in pending:
        event.delivered_at = event.delivered_at or now
    lines = "\n".join(f"- {event.text}" for event in pending)
    prompt = f"{RESUME_HEADER[lang]}\n{lines}" + agent_launch.background_note(
        lang, can_ask="ask_user" in ACTIONS[action].background
    )
    for asked in session.scalars(
        select(UserPrompt).where(UserPrompt.run_id == row.id, UserPrompt.status == "pending")
    ):
        asked.status = "expired"
    picked = agent_launch.pick(
        session,
        action,
        prompt,
        agent=row.agent,
        model=row.model,
        preset=row.preset,
        mode="background",
    )
    assert row.session_id is not None  # lo garantiza `reply_mode`
    row.command = agent_launch.headless_resume_command(picked, prompt, action, row.session_id)
    row.run_config = agent_launch.run_config(picked)
    # `prompt` se queda con la orden original (la que se ve en el historial); la nueva va en
    # `command` y lo escrito, en la conversación.
    row.status = "queued"
    row.result = None
    row.error = None
    row.questions = []
    row.cancel_requested = False
    row.pid = None
    row.started_at = None
    row.finished_at = None
    agent_tasks.reopen(session, row.id)


def take_user_messages(session: Session, run_id: int) -> list[str]:
    """Los mensajes escritos mientras trabaja que aún no se le han pasado, marcados como pasados.
    Los usa el servidor MCP al devolver la respuesta de una herramienta de esta ejecución."""
    rows = session.scalars(
        select(AgentRunEvent)
        .where(
            AgentRunEvent.run_id == run_id,
            AgentRunEvent.kind == "user",
            AgentRunEvent.delivered_at.is_(None),
        )
        .order_by(AgentRunEvent.seq)
    ).all()
    now = utcnow()
    for row in rows:
        row.delivered_at = now
    return [row.text or "" for row in rows]


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
        raise LaunchError("invalid_request", "Antes hay que esperar a que termine o cancelarla.")
    action: ActionId = row.action  # validado al crearla
    asked = session.scalar(select(AssistantRequest.id).where(AssistantRequest.run_id == row.id))
    prompt = agent_launch.prompt_for(
        action,
        row.job_id,
        row.milestone_id,
        assistant_id=asked,
        lang=ui_language.current(session),
    )
    return agent_launch.resume_in_terminal(
        session, action, prompt, row.agent, row.session_id, row.model, row.preset
    )
