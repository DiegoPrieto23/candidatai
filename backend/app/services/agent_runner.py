"""Ejecuta las `agent_runs` en cola (fase 19, ADR-032): lanza el agente sin ventana, lee su salida
en streaming y guarda progreso, resultado y errores. Lo llama el worker, en un hilo propio.

- Una sola ejecución a la vez, también entre procesos: reclamar es un `UPDATE` condicionado a que
  no haya otra `running`.
- Sin las variables de `unset_env` (la clave de la API): el agente usa tu suscripción. Con
  `CAI_CLIENT_NAME` = el agente, para que lo que haga por la CLI quede a su nombre (fase 24.4).
- Tiempo máximo (`background_runs.timeout_minutes`), cancelación desde la UI y parada del worker:
  se para el árbol de procesos entero (el agente y el `cai-mcp` que lanza). Pase lo que pase, al
  salir de `execute` el proceso no sigue vivo.
- Del progreso solo se guardan los nombres de las herramientas y el texto del agente principal,
  nunca sus entradas ni el detalle de sus errores (pueden llevar texto de una oferta). El formato
  de cada agente lo lee `agent_output.py`.
"""

import logging
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import IO, Any

from pydantic import BaseModel
from sqlalchemy import exists, select, update
from sqlalchemy.orm import aliased

from app.core.config import REPO_ROOT
from app.core.db import session_scope
from app.core.policies import get_policies
from app.models import AgentRun
from app.models.base import utcnow
from app.services import agent_registry
from app.services.agent_launch import CLIENT_ENV, QUESTION_PREFIX
from app.services.agent_output import PARSERS, short
from app.services.agent_runs import INTERRUPTED, ProgressKind, RunStatus

logger = logging.getLogger(__name__)

FLUSH_SECONDS = 2.0  # cada cuánto se guarda el progreso y se mira si han pedido cancelar
RESULT_GRACE_SECONDS = 10.0  # tras el resultado final, lo que se espera a que el agente salga
MAX_QUESTIONS = 10
QUESTION_RE = re.compile(rf"^[\W_]*{re.escape(QUESTION_PREFIX.rstrip(':'))}\s*:\**\s*(.+)$", re.I)
STOPPED = "Se paró el worker mientras se ejecutaba. No se repite: lánzala otra vez si quieres."

# Procesos en marcha y aviso de parada del worker (`stop_active`).
_active: dict[int, subprocess.Popen[str]] = {}
_lock = threading.Lock()
_shutdown = threading.Event()


class AgentRunOutcome(BaseModel):
    run_id: int
    action: str
    status: RunStatus
    error: str | None = None
    questions: int = 0


def questions_in(text: str) -> list[str]:
    """Las líneas «PREGUNTA: …» de la respuesta final (también con viñeta o en negrita)."""
    found = []
    for line in text.splitlines():
        if match := QUESTION_RE.match(line.strip()):
            question = match.group(1).strip().strip("*").strip()
            if question:
                found.append(short(question, 500))
    return found[:MAX_QUESTIONS]


# --- Proceso -----------------------------------------------------------------------------------


def _popen(command: list[str], unset_env: list[str], agent: str) -> subprocess.Popen[str]:
    exe = shutil.which(command[0])
    if exe is None:
        raise FileNotFoundError(f"No se encuentra el programa del agente ({command[0]}).")
    # Fase 24.4: lo que haga por la CLI queda a nombre del agente (`CAI_CLIENT_NAME`).
    env = {**agent_registry.clean_env(unset_env), CLIENT_ENV: agent}
    kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    return subprocess.Popen(  # noqa: S603 - comando del manifiesto, sin shell
        [exe, *command[1:]],
        cwd=REPO_ROOT,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        **kwargs,
    )


def _kill_pid_tree(pid: int) -> None:
    if sys.platform == "win32":
        subprocess.run(  # noqa: S603
            ["taskkill", "/PID", str(pid), "/T", "/F"],  # noqa: S607
            capture_output=True,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    else:
        os.killpg(pid, signal.SIGKILL)


def _kill_tree(proc: subprocess.Popen[str]) -> None:
    """Para el agente y lo que haya lanzado (el servidor MCP)."""
    if proc.poll() is not None:
        return
    try:
        _kill_pid_tree(proc.pid)
    except OSError:
        logger.warning("No se pudo parar el árbol de procesos %s", proc.pid, exc_info=True)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


_EOF = object()


def _pump(stream: IO[str], sink: "queue.Queue[object]") -> None:
    try:
        for line in stream:
            sink.put(line)
    except (OSError, ValueError):
        pass  # se cerró al parar el proceso
    sink.put(_EOF)


def _tail(stream: IO[str], keep: deque[str]) -> None:
    try:
        for line in stream:
            keep.append(line.rstrip())
    except (OSError, ValueError):
        pass


# --- Ejecución ---------------------------------------------------------------------------------


def claim_next() -> AgentRun | None:
    """Pasa a `running` la más antigua en cola, si no hay otra en curso. Devuelve una copia."""
    other = aliased(AgentRun)
    with session_scope() as session:
        candidate = session.scalars(
            select(AgentRun).where(AgentRun.status == "queued").order_by(AgentRun.id).limit(1)
        ).first()
        if candidate is None:
            return None
        claimed = session.execute(
            update(AgentRun)
            .where(
                AgentRun.id == candidate.id,
                AgentRun.status == "queued",
                ~exists().where(other.status == "running"),
            )
            .values(status="running", started_at=utcnow())
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            return None
        session.refresh(candidate)
        session.expunge(candidate)
        return candidate


def _save(run_id: int, **values: Any) -> bool:
    """Guarda en la fila mientras sigue `running` y devuelve si han pedido cancelar (o si ya no
    está en curso, que para el caso es lo mismo)."""
    with session_scope() as session:
        row = session.get(AgentRun, run_id)
        if row is None or row.status != "running":
            return True
        for key, value in values.items():
            setattr(row, key, value)
        return row.cancel_requested


def _mcp_prefix(agent: str) -> str | None:
    """`tools.mcp_prefix` del agente que ejecutó, si tiene segundo plano (`agent_registry`)."""
    try:
        spec = agent_registry.get(agent)
    except agent_registry.ManifestError:
        return None
    return spec.mcp_prefix if spec is not None and spec.headless is not None else None


def execute(run: AgentRun, timeout: float | None = None, poll: float = 0.5) -> AgentRunOutcome:
    """Ejecuta una `agent_run` ya reclamada hasta que termina, se cancela o supera el tiempo."""
    policy = get_policies().background_runs
    timeout = timeout if timeout is not None else policy.timeout_minutes * 60
    progress: deque[dict[str, Any]] = deque(maxlen=policy.max_progress_lines)

    def note(kind: ProgressKind, text: str) -> None:
        progress.append({"at": utcnow().isoformat(), "kind": kind, "text": text})

    def finish(status: RunStatus, error: str | None = None, **values: Any) -> AgentRunOutcome:
        if error:
            note("error", short(error))
        values = {"progress": list(progress), "finished_at": utcnow(), **values}
        _save(run.id, status=status, error=error, **values)
        questions = len(values.get("questions") or [])
        return AgentRunOutcome(
            run_id=run.id, action=run.action, status=status, error=error, questions=questions
        )

    factory = PARSERS.get(run.output_format)
    if factory is None:
        return finish("failed", f"Formato de salida desconocido: «{run.output_format}».")
    parser = factory(_mcp_prefix(run.agent) or "mcp__candidatai__")
    try:
        proc = _popen(list(run.command), list(run.unset_env), run.agent)
    except OSError as exc:
        return finish("failed", f"No se pudo lanzar el agente: {exc}")

    with _lock:
        _active[run.id] = proc
    stderr: deque[str] = deque(maxlen=30)
    stop: str | None = None
    tail: threading.Thread | None = None
    try:
        lines: queue.Queue[object] = queue.Queue()
        assert proc.stdout is not None and proc.stderr is not None
        threading.Thread(target=_pump, args=(proc.stdout, lines), daemon=True).start()
        tail = threading.Thread(target=_tail, args=(proc.stderr, stderr), daemon=True)
        tail.start()
        _save(run.id, pid=proc.pid)

        deadline = time.monotonic() + timeout
        next_flush = 0.0
        result_at: float | None = None
        seen = 0
        while True:
            try:
                item = lines.get(timeout=poll)
            except queue.Empty:
                item = None
            if item is _EOF:
                break
            state = parser.state
            if isinstance(item, str):
                parser.feed(item)
                for kind, text in state.progress[seen:]:
                    note(kind, text)
                seen = len(state.progress)
                if state.mcp_broken:
                    stop = "mcp"
                    break
            now = time.monotonic()
            if state.finished:
                result_at = result_at or now
                if now - result_at > RESULT_GRACE_SECONDS:
                    stop = "linger"  # ya respondió y no sale: se para, no es un error
                    break
            if _shutdown.is_set():
                stop = "shutdown"
                break
            if now >= next_flush:
                next_flush = now + FLUSH_SECONDS
                if _save(run.id, progress=list(progress), session_id=state.session_id):
                    stop = "cancelled"
                    break
            if now >= deadline:
                stop = "timeout"
                break
        if stop is None:
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                stop = "linger"
    finally:
        _kill_tree(proc)  # no hace nada si ya salió
        with _lock:
            _active.pop(run.id, None)
        if tail is not None:
            tail.join(timeout=2)  # el detalle de stderr, completo
        for stream in (proc.stdout, proc.stderr):
            if stream is not None:
                stream.close()

    state = parser.state
    common: dict[str, Any] = {
        "session_id": state.session_id,
        "usage": state.usage or None,
        "result": state.result,
    }
    if stop == "cancelled":
        note("info", "Cancelada desde la UI.")
        return finish("cancelled", **common)
    if stop == "shutdown":
        return finish("failed", STOPPED, **common)
    if stop == "timeout":
        minutes = round(timeout / 60, 1)
        error = f"Superó el tiempo máximo ({minutes:g} min) y se ha parado."
        return finish("timeout", error, **common)
    if stop == "mcp":
        return finish(
            "failed",
            f"El servidor MCP de la app no se conectó (estado: {state.mcp_status}). "
            "Comprueba que `uv run --directory backend cai-mcp` arranca.",
            **common,
        )
    if not state.finished:
        detail = " ".join(list(stderr)[-5:])
        return finish(
            "failed",
            f"El agente terminó sin resultado (código {proc.returncode}). {detail}".strip(),
            **common,
        )
    if state.is_error:
        kind = f" ({state.subtype})" if state.subtype and state.subtype != "success" else ""
        reason = short(state.result or "sin detalle")
        return finish("failed", f"El agente terminó con error{kind}: {reason}", **common)
    questions = questions_in(state.result or "")
    note("info", "Terminada.")
    return finish("needs_user" if questions else "done", questions=questions, **common)


def run_next(timeout: float | None = None, poll: float = 0.5) -> AgentRunOutcome | None:
    if _shutdown.is_set():
        return None
    run = claim_next()
    if run is None:
        return None
    try:
        return execute(run, timeout=timeout, poll=poll)
    except Exception as exc:  # que una ejecución rota no quede `running` para siempre
        logger.exception("Fallo al ejecutar la ejecución en segundo plano %s", run.id)
        error = f"{type(exc).__name__}: {exc}"
        _save(run.id, status="failed", error=error, finished_at=utcnow())
        return AgentRunOutcome(run_id=run.id, action=run.action, status="failed", error=error)


def run_pending(timeout: float | None = None, poll: float = 0.5) -> list[AgentRunOutcome]:
    """Ejecuta, de una en una, las que hay en cola."""
    outcomes = []
    while (outcome := run_next(timeout=timeout, poll=poll)) is not None:
        outcomes.append(outcome)
    return outcomes


def stop_active() -> int:
    """Al parar el worker: no empieza ninguna más y para las que estén en marcha (quedan
    `failed`, sin repetirse). Devuelve cuántas había."""
    _shutdown.set()
    with _lock:
        procs = list(_active.values())
    for proc in procs:
        _kill_tree(proc)
    return len(procs)


def _alive_as(pid: int, program: str) -> bool:
    """Si el proceso `pid` sigue vivo y es el programa del agente (no otro que reusa el pid)."""
    if sys.platform != "win32":
        return False  # sin forma fiable de comprobarlo: no se toca
    out = subprocess.run(  # noqa: S603
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    ).stdout
    image = out.split(",", 1)[0].strip().strip('"').lower()
    return bool(image) and Path(image).stem == Path(program).stem.lower()


def recover_interrupted() -> int:
    """Al arrancar el worker: las que quedaron `running` (el worker se cerró de golpe) pasan a
    `failed` y no se repiten; si su agente sigue vivo, se para."""
    with session_scope() as session:
        rows = list(session.scalars(select(AgentRun).where(AgentRun.status == "running")))
        orphans = [(row.pid, row.command[0]) for row in rows if row.pid and row.command]
        for row in rows:
            row.status = "failed"
            row.error = INTERRUPTED
            row.finished_at = utcnow()
    for pid, program in orphans:
        try:
            if _alive_as(pid, program):
                _kill_pid_tree(pid)
        except OSError:
            logger.warning("No se pudo comprobar el proceso %s", pid, exc_info=True)
    return len(rows)


def describe(outcome: AgentRunOutcome) -> str:
    """Una línea legible para el log del worker."""
    base = f"En segundo plano, «{outcome.action}» (ejecución {outcome.run_id})"
    if outcome.status == "done":
        return f"{base}: terminada."
    if outcome.status == "needs_user":
        return f"{base}: necesita tu respuesta ({outcome.questions} preguntas). Mírala en la UI."
    if outcome.status == "cancelled":
        return f"{base}: cancelada."
    return f"{base}: {outcome.status}. {outcome.error or ''}".strip()
