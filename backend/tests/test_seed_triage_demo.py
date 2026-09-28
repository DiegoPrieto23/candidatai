"""`scripts/seed_triage_demo.py`: da de alta la semilla sin romperse con duplicados."""

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest

from app.core import migrations
from app.core.config import REPO_ROOT
from app.core.db import session_scope
from app.services import ingest, jobs, profile

SCRIPT = REPO_ROOT / "scripts" / "seed_triage_demo.py"


def load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("seed_triage_demo", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def db(isolated_env: Path) -> None:
    migrations.upgrade()
    with session_scope() as session:
        profile.import_profile(session, profile.EXAMPLE_PATH)


def all_jobs() -> list[jobs.JobSummary]:
    with session_scope() as session:
        return jobs.list_jobs(session, limit=100, order="recent")


def test_seeds_twenty_jobs_and_is_idempotent(db: None, capsys: pytest.CaptureFixture[str]) -> None:
    script = load_script()
    assert script.main() == 0
    assert "20 ofertas creadas, 0 ya existían" in capsys.readouterr().out
    assert len(all_jobs()) == 20
    assert script.main() == 0
    assert "0 ofertas creadas, 20 ya existían" in capsys.readouterr().out
    assert len(all_jobs()) == 20


def test_survives_demo_jobs_and_duplicates(db: None, capsys: pytest.CaptureFixture[str]) -> None:
    script = load_script()
    with session_scope() as session:
        # Las ofertas de demo/jobs/ que el usuario ya dio de alta en la fase 06.
        ingest.add_from_text(session, "Data Engineer (m/f/d)", "Brétema Analytics", "x " * 50)
        ingest.add_from_text(session, "Analytics Engineer", "Lonxa Retail Tech", "x " * 50)
        # Y una que sí choca con la primera de la semilla (misma empresa, mismo puesto).
        ingest.add_from_text(
            session, "Data Engineer", script.COMPANIES[0], "otro texto " * 30, location="Madrid"
        )
    assert script.main() == 0
    out = capsys.readouterr().out
    assert "19 ofertas creadas, 0 ya existían, 1 cerradas como duplicado" in out
    assert "(duplicado de la oferta 3: sin extracción)" in out
    assert len(all_jobs()) == 23


def test_companies_do_not_clash_with_demo_jobs() -> None:
    companies = load_script().COMPANIES
    assert len(set(companies)) == 20
    assert not {"Brétema Analytics", "Lonxa Retail Tech"} & set(companies)
