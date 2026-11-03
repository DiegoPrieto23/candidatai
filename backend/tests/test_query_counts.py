"""Número de consultas SQL de las vistas de lista: no crece con el número de ofertas (sin N+1).

Se cuentan las sentencias de cada llamada sobre la base sintética con 10 y con 100 ofertas; tienen
que ser las mismas. Sin tiempos: dependen de la máquina (las cifras van con
`tests/perf/profile_backend.py`).
"""

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.api.main import create_app
from app.core import migrations
from app.core.config import get_settings
from app.core.db import get_engine, session_scope
from app.models import Application
from tests.agent_support import mcp_call
from tests.perf.synthetic import populate

# Lo que pide cada página de lista, la ficha y las herramientas MCP más usadas.
CALLS: dict[str, Callable[[TestClient, int], Any]] = {
    "status": lambda c, _: c.get("/status"),
    "bandeja": lambda c, _: c.get("/jobs", params={"limit": 25}),
    "bandeja_score": lambda c, _: c.get("/jobs", params={"limit": 25, "sort": "score"}),
    "bandeja_salario": lambda c, _: c.get("/jobs", params={"limit": 25, "sort": "salary"}),
    "bandeja_cerradas": lambda c, _: c.get(
        "/jobs", params={"limit": 25, "stage": "closed", "sort": "closed"}
    ),
    "busqueda": lambda c, _: c.get("/jobs", params={"limit": 25, "q": "data"}),
    "ficha": lambda c, job_id: c.get(f"/jobs/{job_id}"),
    "ficha_match": lambda c, job_id: c.get(f"/jobs/{job_id}/match"),
    "ficha_proceso": lambda c, job_id: c.get(f"/jobs/{job_id}/process"),
    "embudo": lambda c, _: c.get("/stats/funnel"),
    "calibracion": lambda c, _: c.get("/stats/calibration"),
    "historia": lambda c, _: c.get("/stats/story"),
    "kanban": lambda c, _: c.get("/board"),
    "proximos": lambda c, _: c.get("/upcoming", params={"days": 30}),
    "seguimientos": lambda c, _: c.get("/followups"),
    "respuestas": lambda c, _: c.get("/replies"),
    "por_revisar": lambda c, _: c.get("/triage"),
    "alertas": lambda c, _: c.get("/alerts"),
}
MCP_CALLS: dict[str, dict[str, Any]] = {
    "get_status": {},
    "list_jobs": {},
}


def _counts(data_dir: Path, monkeypatch: pytest.MonkeyPatch, jobs: int) -> dict[str, int]:
    monkeypatch.setenv("CAI_DATA_DIR", str(data_dir))
    get_settings.cache_clear()
    get_engine.cache_clear()
    migrations.upgrade()
    with session_scope() as session:
        populate(session, jobs=jobs)
    with session_scope() as session:
        job_id = session.scalar(
            select(Application.job_id).where(Application.stage == "in_process").limit(1)
        )
    assert job_id is not None
    statements: list[str] = []

    def count(_conn: Any, _cursor: Any, sql: str, *_args: Any) -> None:
        statements.append(sql)

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", count)
    counts = {}
    try:
        with TestClient(create_app()) as client:
            for name, call in CALLS.items():
                call(client, job_id)  # la primera llamada puede preparar algo (caché, perfil)
                statements.clear()
                response = call(client, job_id)
                assert response.status_code == 200, (name, response.text)
                counts[name] = len(statements)
        for name, arguments in MCP_CALLS.items():
            mcp_call(name, arguments)
            statements.clear()
            is_error, payload = mcp_call(name, arguments)
            assert not is_error, payload
            # Sin la auditoría de la llamada (`mcp_calls`): una inserción fija por llamada.
            counts[f"mcp_{name}"] = len(statements)
    finally:
        event.remove(engine, "before_cursor_execute", count)
        engine.dispose()
    return counts


@pytest.fixture(scope="module")
def query_counts(tmp_path_factory: pytest.TempPathFactory) -> Iterator[dict[int, dict[str, int]]]:
    """Consultas de cada llamada con 10 y con 100 ofertas (una sola vez para todo el módulo)."""
    root = tmp_path_factory.mktemp("query-counts")
    with pytest.MonkeyPatch.context() as monkeypatch:
        for name in ("CAI_IMAP_HOST", "CAI_IMAP_USER", "CAI_IMAP_PASSWORD"):
            monkeypatch.setenv(name, "")
        monkeypatch.setenv("CAI_EMBEDDINGS", "off")
        monkeypatch.setenv("CAI_OLLAMA_URL", "http://127.0.0.1:9")
        monkeypatch.setenv("CAI_ENV_FILE", str(root / ".env"))
        monkeypatch.delenv("CAI_DB_URL", raising=False)
        yield {n: _counts(root / str(n), monkeypatch, n) for n in (10, 100)}
    get_settings.cache_clear()
    get_engine.cache_clear()


@pytest.mark.parametrize("name", [*CALLS, *(f"mcp_{n}" for n in MCP_CALLS)])
def test_queries_do_not_grow_with_jobs(query_counts: dict[int, dict[str, int]], name: str) -> None:
    small, large = query_counts[10][name], query_counts[100][name]
    assert small == large, f"{name}: {small} consultas con 10 ofertas y {large} con 100"
