"""Mide el backend sobre la base sintética: mediana y p95 de cada endpoint, y consultas SQL.

No es un test (los tiempos dependen de la máquina): se ejecuta a mano desde `backend/`:

    uv run python -m tests.perf.profile_backend               # 5000 ofertas, 20 llamadas
    uv run python -m tests.perf.profile_backend --explain     # y el plan de las consultas lentas

Crea la base en un directorio temporal, nunca en `data/`. Con `--data-dir`, en esa carpeta: si
ya tiene la base, la reutiliza (útil para comparar antes y después de un cambio). Ojo: las
migraciones nuevas se le aplican al arrancar.
"""

import argparse
import os
import statistics
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

STAGES = (
    None,
    "pending_detail",
    "pending_extraction",
    "pending_triage",
    "approved",
    "cv_ready",
    "applied",
    "in_process",
    "closed",
)
SORTS = ("date", "score", "salary", "closed")


@dataclass
class _Statement:
    sql: str
    params: Any
    seconds: float


@dataclass
class _Counter:
    """Cuenta y cronometra las sentencias SQL de cada llamada."""

    statements: list[_Statement] = field(default_factory=list)
    _started: float = 0.0

    def before(self, _conn: Any, _cursor: Any, sql: str, params: Any, *_args: Any) -> None:
        self._started = time.perf_counter()

    def after(self, _conn: Any, _cursor: Any, sql: str, params: Any, *_args: Any) -> None:
        self.statements.append(_Statement(sql, params, time.perf_counter() - self._started))


@dataclass
class Result:
    name: str
    median_ms: float
    p95_ms: float
    queries: int
    slowest: _Statement | None


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(0.95 * (len(ordered) - 1)))]


def measure(name: str, call: Callable[[], Any], counter: _Counter, runs: int) -> Result:
    call()  # calentamiento: la primera llamada carga módulos y la caché de SQLite
    times, queries = [], []
    slowest: _Statement | None = None
    for _ in range(runs):
        counter.statements.clear()
        started = time.perf_counter()
        call()
        times.append((time.perf_counter() - started) * 1000)
        queries.append(len(counter.statements))
        for statement in counter.statements:
            if slowest is None or statement.seconds > slowest.seconds:
                slowest = statement
    return Result(name, statistics.median(times), _p95(times), max(queries), slowest)


def _setup(data_dir: Path) -> None:
    os.environ.update(
        {
            "CAI_DATA_DIR": str(data_dir),
            "CAI_EMBEDDINGS": "off",
            "CAI_OLLAMA_URL": "http://127.0.0.1:9",
            "CAI_IMAP_HOST": "",
            "CAI_IMAP_USER": "",
            "CAI_IMAP_PASSWORD": "",
            "CAI_ENV_FILE": str(data_dir / ".env"),
        }
    )
    os.environ.pop("CAI_DB_URL", None)


def run(jobs: int, runs: int, explain: bool, only: str | None) -> list[Result]:
    from fastapi.testclient import TestClient
    from sqlalchemy import event, func, select

    from app.agent_interface.output import dump_json
    from app.agent_interface.registry import CallContext
    from app.agent_interface.runner import call_tool
    from app.agent_interface.tools import TOOLS_BY_NAME
    from app.api.main import create_app
    from app.core import migrations
    from app.core.db import get_engine, session_scope
    from app.models import Application
    from tests.perf.synthetic import populate

    migrations.upgrade()
    with session_scope() as session:
        empty = not session.scalar(select(func.count()).select_from(Application))
    if empty:
        started = time.perf_counter()
        with session_scope() as session:
            summary = populate(session, jobs=jobs, now=datetime.now(UTC))
        print(f"Base sintética: {summary} en {time.perf_counter() - started:.1f} s\n")
    with session_scope() as session:
        detail_ids = list(
            session.scalars(
                select(Application.job_id).where(Application.stage == "in_process").limit(runs)
            )
        )
    print("| Endpoint | Mediana (ms) | p95 (ms) | Consultas |\n|---|---|---|---|")
    counter = _Counter()
    engine = get_engine()
    event.listen(engine, "before_cursor_execute", counter.before)
    event.listen(engine, "after_cursor_execute", counter.after)

    since_90 = {"since": (date.today() - timedelta(days=90)).isoformat()}
    month = date.today().replace(day=1)
    calendar = {"start": month.isoformat(), "end": (month + timedelta(days=41)).isoformat()}
    page_5 = {"limit": 25, "offset": 100}
    rotating = iter(range(10**9))

    def tool(name: str, arguments: dict[str, Any] | None = None) -> str:
        """Lo que hace el servidor MCP con una llamada, sin el transporte (stdio en la realidad)."""
        context = CallContext(channel="mcp", client_name="perf")
        result = call_tool(TOOLS_BY_NAME[name], arguments or {}, context)
        return dump_json(result.model_dump(mode="json"))

    def detail(path: str) -> Callable[[], Any]:
        return lambda: client.get(path.format(detail_ids[next(rotating) % len(detail_ids)]))

    calls: list[tuple[str, Callable[[], Any]]] = [("GET /status", lambda: client.get("/status"))]
    for stage in STAGES:
        for sort in SORTS:
            for direction in ("desc", "asc"):
                params = {"limit": 25, "sort": sort, "dir": direction}
                if stage:
                    params["stage"] = stage
                calls.append(
                    (
                        f"Bandeja {stage or 'todas'} · {sort} {direction}",
                        lambda p=params: client.get("/jobs", params=p),
                    )
                )
    calls += [
        ("Bandeja todas · página 5", lambda: client.get("/jobs", params=page_5)),
        ("Búsqueda «data»", lambda: client.get("/jobs", params={"q": "data", "limit": 25})),
        ("Búsqueda «nova»", lambda: client.get("/jobs", params={"q": "nova", "limit": 25})),
        ("Búsqueda sin resultados", lambda: client.get("/jobs", params={"q": "zzz", "limit": 25})),
        ("GET /jobs/{id}", detail("/jobs/{}")),
        ("GET /jobs/{id}/match", detail("/jobs/{}/match")),
        ("GET /jobs/{id}/process", detail("/jobs/{}/process")),
        ("GET /jobs/{id}/costs", detail("/jobs/{}/costs")),
        ("Embudo", lambda: client.get("/stats/funnel")),
        ("Embudo · 90 días", lambda: client.get("/stats/funnel", params=since_90)),
        ("Calibración", lambda: client.get("/stats/calibration")),
        ("Calibración · 90 días", lambda: client.get("/stats/calibration", params=since_90)),
        ("Historia de la búsqueda", lambda: client.get("/stats/story")),
        ("Kanban", lambda: client.get("/board")),
        ("Próximos hitos", lambda: client.get("/upcoming")),
        ("Seguimientos", lambda: client.get("/followups")),
        ("Calendario (mes)", lambda: client.get("/calendar", params=calendar)),
        ("Respuestas", lambda: client.get("/replies")),
        ("Por revisar", lambda: client.get("/triage")),
        ("Alertas", lambda: client.get("/alerts")),
        ("Ejecuciones del agente", lambda: client.get("/agent/runs", params={"limit": 20})),
        ("MCP get_status", lambda: tool("get_status")),
        ("MCP list_jobs", lambda: tool("list_jobs")),
        ("MCP list_jobs · por revisar", lambda: tool("list_jobs", {"stage": "pending_triage"})),
    ]
    results = []
    with TestClient(create_app()) as client:
        for name, call in calls:
            if only and only.lower() not in name.lower():
                continue
            response = call()
            status = getattr(response, "status_code", 200)
            if status != 200:
                raise RuntimeError(f"{name}: {status} {response.text[:300]}")
            results.append(measure(name, call, counter, runs))
            print(_line(results[-1]), flush=True)
    if explain:
        _explain(results, engine)
    return results


def _line(result: Result) -> str:
    return f"| {result.name} | {result.median_ms:.0f} | {result.p95_ms:.0f} | {result.queries} |"


def _explain(results: list[Result], engine: Any) -> None:
    print("\n## Planes de las consultas más lentas (p95 ≥ 50 ms)\n")
    with engine.connect() as conn:
        for result in sorted(results, key=lambda r: -r.p95_ms):
            if result.p95_ms < 50 or result.slowest is None:
                continue
            slowest = result.slowest
            print(f"### {result.name} · {slowest.seconds * 1000:.0f} ms\n")
            print(slowest.sql.strip()[:1500], "\n")
            plan = conn.exec_driver_sql(f"EXPLAIN QUERY PLAN {slowest.sql}", slowest.params)
            for row in plan:
                print("   ", row[-1])
            print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jobs", type=int, default=5000)
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--explain", action="store_true", help="plan de las consultas lentas")
    parser.add_argument("--only", help="solo los endpoints cuyo nombre contenga este texto")
    parser.add_argument(
        "--data-dir",
        type=Path,
        help="carpeta donde dejar (o reutilizar) la base sintética; por defecto, una temporal",
    )
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]  # la consola de Windows
    with tempfile.TemporaryDirectory(prefix="cai-perf-") as tmp:
        data_dir = args.data_dir or Path(tmp)
        data_dir.mkdir(parents=True, exist_ok=True)
        _setup(data_dir)
        try:
            run(args.jobs, args.runs, args.explain, args.only)
        finally:
            from app.core.db import get_engine

            get_engine().dispose()  # Windows no borra el directorio con la base abierta


if __name__ == "__main__":
    main()
