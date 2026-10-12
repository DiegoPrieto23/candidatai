"""Fase 10.2: `GET /stats/funnel` responde en menos de 1 s con 1 000 ofertas sintéticas
(`scripts/seed_funnel_demo.py`)."""

import importlib.util
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.main import create_app
from app.core import migrations
from app.core.config import REPO_ROOT
from app.core.db import session_scope
from app.models import Document, DocumentRender, Event, Job, Match, ProfileVersion

SCRIPT = REPO_ROOT / "scripts" / "seed_funnel_demo.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_funnel_demo", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_funnel_responds_in_under_a_second_with_1000_jobs(isolated_env: Path) -> None:
    migrations.upgrade()
    with session_scope() as session:
        load_script().seed(session, 1000, datetime.now(UTC))

    with TestClient(create_app()) as client:
        client.get("/status")  # calentamiento: políticas, engine y app, no la consulta
        timings = []
        for _ in range(3):
            start = time.perf_counter()
            response = client.get("/stats/funnel")
            timings.append(time.perf_counter() - start)
        elapsed = min(timings)

    assert response.status_code == 200
    data = response.json()
    assert data["steps"][0]["count"] + data["duplicates_excluded"] == 1000
    assert len(data["by_source"]) == 5 and data["by_week"]
    assert elapsed < 1.0, f"/stats/funnel tardó {elapsed:.2f} s"


def test_seed_script_refuses_a_database_with_jobs(
    isolated_env: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    script = load_script()
    assert script.main(["--jobs", "3", "--data-dir", str(isolated_env)]) == 0
    assert script.main(["--jobs", "3", "--data-dir", str(isolated_env)]) == 1
    assert "ya tiene ofertas" in capsys.readouterr().out


def test_api_since_and_validation(isolated_env: Path) -> None:
    migrations.upgrade()
    with session_scope() as session:
        load_script().seed(session, 20, datetime.now(UTC))
    with TestClient(create_app()) as client:
        future = client.get("/stats/funnel", params={"since": "2999-01-01"})
        assert future.status_code == 200
        assert future.json()["since"] == "2999-01-01"
        assert future.json()["steps"][0]["count"] == 0
        assert client.get("/stats/funnel", params={"since": "ayer"}).status_code == 422


def test_calibration_responds_in_under_a_second_with_1000_jobs(isolated_env: Path) -> None:
    """Fase 20: la calibración repite el CTE del embudo en cada desglose; sigue bajo 1 s, con
    match, veredicto, carta y CV en cada oferta para que sus subconsultas trabajen de verdad."""
    migrations.upgrade()
    with session_scope() as session:
        load_script().seed(session, 1000, datetime.now(UTC))
        add_calibration_data(session)

    with TestClient(create_app()) as client:
        client.get("/status")
        timings = []
        for _ in range(3):
            start = time.perf_counter()
            response = client.get("/stats/calibration")
            timings.append(time.perf_counter() - start)
        elapsed = min(timings)
        assert client.get("/stats/calibration", params={"min_cases": 0}).status_code == 422
        future = client.get("/stats/calibration", params={"since": "2999-01-01"}).json()

    assert response.status_code == 200
    data = response.json()
    assert data["total"]["applied"] > 0
    assert sum(g["applied"] for g in data["by_score"]) == data["total"]["applied"]
    assert sum(g["applied"] for g in data["by_source"]) == data["total"]["applied"]
    assert future["total"]["applied"] == 0
    assert elapsed < 1.0, f"/stats/calibration tardó {elapsed:.2f} s"


def add_calibration_data(session: Session) -> None:
    """Dos matches, un `fit_assessed`, una carta y un CV con render por oferta (filas directas: es
    volumen para medir, no un histórico coherente)."""
    profile = ProfileVersion(data={}, content_hash="rendimiento")
    session.add(profile)
    session.flush()
    verdicts = ("strong", "possible", "weak")
    for job in session.scalars(select(Job)):
        seen = job.first_seen_at
        for n, score in enumerate((40 + job.id % 60, 50 + job.id % 50)):
            session.add(
                Match(
                    job_id=job.id,
                    profile_version_id=profile.id,
                    hard_filters={"passed": True, "failures": []},
                    score=score,
                    breakdown={},
                    created_at=seen + timedelta(hours=n + 1),
                )
            )
        session.add(
            Event(
                job_id=job.id,
                type="fit_assessed",
                actor="agent",
                payload={"verdict": verdicts[job.id % 3]},
                occurred_at=seen + timedelta(hours=2),
            )
        )
        for kind in ("cover_letter", "cv"):
            doc = Document(
                job_id=job.id,
                profile_version_id=profile.id,
                kind=kind,
                language="es",
                content={},
                created_at=seen + timedelta(hours=3),
            )
            session.add(doc)
            session.flush()
            if kind == "cv":
                session.add(
                    DocumentRender(
                        document_id=doc.id,
                        template_id="clasica",
                        template_hash="h",
                        options={},
                        pages=1,
                    )
                )
    session.flush()
