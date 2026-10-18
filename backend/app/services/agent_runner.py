"""Ejecuta las `agent_runs` en cola (fase 19, ADR-032): lanza el agente sin ventana, lee su salida
en streaming y guarda progreso, resultado y errores. Lo llama el worker, en un hilo propio.

- Hasta `background_runs.max_parallel` a la vez (fase 25.4, ADR-038; 1 por defecto), también entre
  procesos: reclamar es un único `UPDATE` condicionado a que haya hueco, a que el agente no haya
  llegado a su tope (`per_agent`) y a que ninguna en curso trabaje la misma oferta o, si es de lote
  (sin oferta), la misma acción. Cada ejecución sigue con el techo de herramientas de su acción.
- SQLite con varias escribiendo: las escrituras de la fila se reintentan si la base está bloqueada.
- Sin las variables de `unset_env` (la clave de la API): el agente usa tu suscripción. Con
  `CAI_CLIENT_NAME` = el agente, para que lo que haga por la CLI quede a su nombre (fase 24.4).
- Tiempo máximo (`background_runs.timeout_minutes`), cancelación desde la UI y parada del worker:
  se para el árbol de procesos entero (el agente y el `cai-mcp` que lanza). Pase lo que pase, al
  salir de `execute` el proceso no sigue vivo.
- Del progreso solo se guardan los nombres de las herramientas y el texto del agente principal,
  nunca sus entradas ni el detalle de sus errores (pueden llevar texto de una oferta). El formato
  de cada agente lo lee `agent_output.py`.
- Con techo por configuración (`run_config`, fase 24.5), la configuración de la ejecución se
  escribe antes de lanzar (`agent_run_config`) y se borra al salir de `execute`, termine como
  termine. Si no se puede escribir, no se lanza.
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
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from pathlib import Path
from typing import IO, Any

from pydantic import BaseModel
from sqlalchemy import and_, exists, func, select, update
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import aliased

from app.core.config import REPO_ROOT
from app.core.db import session_scope
from app.core.policies import get_policies
from app.models import AgentRun
from app.models.base import utcnow
from app.services import agent_registry, agent_run_config
from app.services.agent_launch import CLIENT_ENV, QUESTION_PREFIX
from app.services.agent_output import PARSERS, short
from app.services.agent_runs import INTERRUPTED, ProgressKind, RunStatus

logger = logging.getLogger(__name__)

FLUSH_SECONDS = 2.0  # cada cuánto se guarda el progreso y se mira si han pedido cancelar
RESULT_GRACE_SECONDS = 10.0  # tras el resultado final, lo que se espera a que el agente salga
MAX_QUESTIONS = 10
QUESTION_RE = re.compile(rf"^[\W_]*{re.escape(QUESTION_PREFIX.rstrip(':'))}\s*:\**\s*(.+)$", re.I)
ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")  # colores de la consola en stderr (OpenCode)
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


def _popen(
    command: list[str], unset_env: list[str], agent: str, extra_env: dict[str, str] | None = None
) -> subprocess.Popen[str]:
    exe = shutil.which(command[0])
    if exe is None:
        raise FileNotFoundError(f"No se encuentra el programa del agente ({command[0]}).")
    # Fase 24.4: lo que haga por la CLI queda a nombre del agente (`CAI_CLIENT_NAME`). Fase 24.5:
    # `extra_env` lleva la configuración de la ejecución.
    env = {**agent_registry.clean_env(unset_env), **(extra_env or {}), CLIENT_ENV: agent}
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
            keep.append(ANSI_RE.sub("", line).rstrip())
    except (OSError, ValueError):
        pass


# --- Ejecución ---------------------------------------------------------------------------------


LOCK_RETRIES = 5
LOCK_PAUSE = 0.2  # segundos; se dobla en cada intento


def _retry_locked[T](work: Callable[[], T]) -> T:
    """Repite `work` si SQLite dice «database is locked» (varias ejecuciones escribiendo)."""
    pause = LOCK_PAUSE
    for attempt in range(LOCK_RETRIES):
        try:
            return work()
        except OperationalError as exc:
            if "locked" not in str(exc).lower() or attempt == LOCK_RETRIES - 1:
                raise
            logger.info("Base de datos bloqueada; reintento %s", attempt + 1)
            time.sleep(pause)
            pause *= 2
    raise AssertionError("inalcanzable")


def _limits() -> tuple[int, dict[str, int]]:
    policy = get_policies().background_runs
    return policy.max_parallel, dict(policy.per_agent)


def _claim(candidate: AgentRun, max_parallel: int, per_agent: dict[str, int]) -> bool:
    """Un único `UPDATE`: atómico también entre procesos."""
    running = aliased(AgentRun)
    busy = select(func.count()).select_from(running).where(running.status == "running")
    # Choca con otra en curso de la misma oferta o, si es de lote (sin oferta), de la misma acción.
    if candidate.job_id is not None:
        clash = running.job_id == candidate.job_id
    else:
        clash = and_(running.job_id.is_(None), running.action == candidate.action)
    conditions = [
        AgentRun.id == candidate.id,
        AgentRun.status == "queued",
        busy.scalar_subquery() < max_parallel,
        ~exists().where(running.status == "running", clash),
    ]
    if (cap := per_agent.get(candidate.agent)) is not None:
        conditions.append(busy.where(running.agent == candidate.agent).scalar_subquery() < cap)
    with session_scope() as session:
        claimed = session.execute(
            update(AgentRun)
            .where(*conditions)
            .values(status="running", started_at=utcnow())
            .execution_options(synchronize_session=False)
        )
        return claimed.rowcount == 1


def claim_next(
    max_parallel: int | None = None, per_agent: dict[str, int] | None = None
) -> AgentRun | None:
    """Pasa a `running` la más antigua en cola que se pueda empezar ya (hay hueco, su agente no
    está en su tope y no choca con otra en curso). Devuelve una copia, o `None` si no hay."""
    default_parallel, default_agents = _limits()
    max_parallel = max_parallel or default_parallel
    per_agent = default_agents if per_agent is None else per_agent
    with session_scope() as session:
        queued = list(
            session.scalars(
                select(AgentRun).where(AgentRun.status == "queued").order_by(AgentRun.id)
            )
        )
        session.expunge_all()
    for candidate in queued:
        if _retry_locked(lambda c=candidate: _claim(c, max_parallel, per_agent)):
            with session_scope() as session:
                row = session.get(AgentRun, candidate.id)
                assert row is not None
                session.expunge(row)
                return row
    return None


def _save(run_id: int, **values: Any) -> bool:
    """Guarda en la fila mientras sigue `running` y devuelve si han pedido cancelar (o si ya no
    está en curso, que para el caso es lo mismo)."""

    def work() -> bool:
        with session_scope() as session:
            row = session.get(AgentRun, run_id)
            if row is None or row.status != "running":
                return True
            for key, value in values.items():
                setattr(row, key, value)
            return row.cancel_requested

    return _retry_locked(work)


def _mcp_prefix(agent: str) -> str | None:
    """`tools.mcp_prefix` del agente que ejecutó, si tiene segundo plano (`agent_registry`)."""
    try:
        spec = agent_registry.get(agent)
    except agent_registry.ManifestError:
        return None
    return spec.mcp_prefix if spec is not None and spec.headless is not None else None


def _write_config(run: AgentRun) -> tuple[dict[str, str], list[str]]:
    """Escribe la configuración de la ejecución, si la lleva, y devuelve las variables que se la
    pasan al agente y las que hay que quitar (`RunConfigError` si no se puede limitar)."""
    if not run.run_config:
        return {}, []
    data = dict(run.run_config)
    prefix = data.pop("mcp_prefix", "") or ""
    try:
        spec = agent_registry.RunConfigSpec.model_validate(data)
    except ValueError as exc:
        raise agent_run_config.RunConfigError("La configuración guardada no es válida.") from exc
    env = agent_run_config.write(run.id, run.action, spec, prefix)  # type: ignore[arg-type]
    return env, list(spec.clear_env)


def execute(run: AgentRun, timeout: float | None = None, poll: float = 0.5) -> AgentRunOutcome:
    """Ejecuta una `agent_run` ya reclamada hasta que termina, se cancela o supera el tiempo."""
    try:
        return _execute(run, timeout, poll)
    finally:
        agent_run_config.remove(run.id)  # también si se cancela, falla o se para el worker


def _execute(run: AgentRun, timeout: float | None, poll: float) -> AgentRunOutcome:
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
        extra_env, clear_env = _write_config(run)
    except (agent_run_config.RunConfigError, OSError) as exc:
        return finish("failed", f"No se pudo preparar la configuración de la ejecución: {exc}")
    try:
        unset = [*run.unset_env, *clear_env]
        proc = _popen(list(run.command), unset, run.agent, extra_env)
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
                # Fase 26.1: en macOS y Linux, `killpg` cierra la salida al momento y se llega aquí
                # antes de ver la parada del worker.
                if _shutdown.is_set():
                    stop = "shutdown"
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


def _run_claimed(run: AgentRun, timeout: float | None, poll: float) -> AgentRunOutcome:
    try:
        return execute(run, timeout=timeout, poll=poll)
    except Exception as exc:  # que una ejecución rota no quede `running` para siempre
        logger.exception("Fallo al ejecutar la ejecución en segundo plano %s", run.id)
        error = f"{type(exc).__name__}: {exc}"
        _save(run.id, status="failed", error=error, finished_at=utcnow())
        return AgentRunOutcome(run_id=run.id, action=run.action, status="failed", error=error)


def run_next(timeout: float | None = None, poll: float = 0.5) -> AgentRunOutcome | None:
    if _shutdown.is_set():
        return None
    run = claim_next()
    if run is None:
        return None
    return _run_claimed(run, timeout, poll)


def run_pending(
    timeout: float | None = None, poll: float = 0.5, max_parallel: int | None = None
) -> list[AgentRunOutcome]:
    """Ejecuta las que hay en cola: hasta `max_parallel` a la vez (por defecto, el de
    `policies.yaml`), cada una en su hilo. Cuando una termina, se reclama la siguiente."""
    limit, per_agent = _limits()
    limit = max_parallel or limit
    outcomes: list[AgentRunOutcome] = []
    if limit <= 1:  # sin hilos, con el límite pedido también al reclamar
        while not _shutdown.is_set() and (run := claim_next(limit, per_agent)) is not None:
            outcomes.append(_run_claimed(run, timeout, poll))
        return outcomes
    with ThreadPoolExecutor(max_workers=limit, thread_name_prefix="agent-run") as pool:
        pending: set[Future[AgentRunOutcome]] = set()
        while True:
            while len(pending) < limit and not _shutdown.is_set():
                run = claim_next(limit, per_agent)
                if run is None:
                    break
                pending.add(pool.submit(_run_claimed, run, timeout, poll))
            if not pending:
                break
            done, pending = wait(pending, return_when=FIRST_COMPLETED)
            outcomes.extend(future.result() for future in done)
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
        return _alive_as_posix(pid, program)
    out = subprocess.run(  # noqa: S603
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        creationflags=subprocess.CREATE_NO_WINDOW,
    ).stdout
    image = out.split(",", 1)[0].strip().strip('"').lower()
    return bool(image) and Path(image).stem == Path(program).stem.lower()


def _alive_as_posix(pid: int, program: str) -> bool:
    """macOS y Linux (fase 26.1): vivo (`kill -0`), jefe de su grupo (como lo deja `_popen`, así
    `killpg` no toca a nadie más) y con el programa del agente como programa, o como primer
    argumento de un intérprete (`node …/codex.js`). Un `vim claude.md` con el pid reutilizado no
    cuenta."""
    try:
        os.kill(pid, 0)
        if os.getpgid(pid) != pid:
            return False
    except ProcessLookupError:
        return False
    except PermissionError:
        return False  # de otro usuario: no es nuestro
    wanted = Path(program).stem.lower()
    args = [Path(arg).stem.lower() for arg in _args_of(pid)[:2]]
    if not args:
        return False
    return args[0] == wanted or (args[0] in INTERPRETERS and args[1:] == [wanted])


INTERPRETERS = frozenset({"node", "nodejs", "bun", "deno", "python", "python3"})


def _args_of(pid: int) -> list[str]:
    """Los argumentos del proceso: exactos en Linux (`/proc`); en macOS, de `ps`, partidos por
    espacios (una ruta con espacios no casará y el proceso no se toca)."""
    cmdline = Path(f"/proc/{pid}/cmdline")
    try:
        return [arg for arg in cmdline.read_bytes().decode(errors="replace").split("\0") if arg]
    except OSError:
        pass
    out = subprocess.run(  # noqa: S603
        ["ps", "-o", "args=", "-p", str(pid)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return out.split()


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
    # Fase 24.5: ninguna está en curso, así que sobra cualquier configuración que quedara.
    folder = agent_run_config.runs_dir()
    if folder.is_dir():
        for child in folder.iterdir():
            if child.name.isdigit():
                agent_run_config.remove(int(child.name))
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
