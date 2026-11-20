"""Borrar una oferta o todas desde la UI: con confirmación escrita, copia previa y sin dejar nada
colgando en la base de datos. Sobre la demo, que tiene de todo (CVs, hitos, correos, borradores…).
"""

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core.db import session_scope
from app.models import (
    Application,
    Company,
    Document,
    Event,
    Job,
    Milestone,
    NetworkContact,
    ProfileVersion,
    Reply,
    Source,
)
from app.services import demo, erase
from app.services.documents import pdf
from tests.cv_support import fake_converter

NOW = datetime(2026, 10, 5, 9, 30, tzinfo=UTC)
JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


@pytest.fixture
def demo_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_env: Path
) -> Iterator[Path]:
    monkeypatch.setattr(pdf, "converter_name", lambda: "Conversor de prueba")
    monkeypatch.setattr(pdf, "get_converter", lambda: fake_converter())
    target = tmp_path / "data-demo"
    demo.seed(target, now=NOW)
    with demo.use_data_dir(target, embeddings=False):
        yield target


@pytest.fixture
def client(demo_data: Path) -> Iterator[TestClient]:
    with TestClient(create_app()) as client:
        yield client


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


def _dangling(session: Session) -> list[tuple[object, ...]]:
    return list(session.execute(text("PRAGMA foreign_key_check")))


def _busiest_job(session: Session) -> Job:
    """La oferta con más cosas colgando: hitos, CVs y eventos."""
    stmt = (
        select(Job)
        .join(Milestone, Milestone.job_id == Job.id)
        .join(Document, Document.job_id == Job.id)
        .group_by(Job.id)
        .order_by(func.count(Milestone.id).desc())
    )
    job = session.scalars(stmt).first()
    return job or session.scalars(select(Job).join(Milestone, Milestone.job_id == Job.id)).first()


def test_erasing_one_job_takes_everything_of_it_and_nothing_else(client: TestClient) -> None:
    with session_scope() as session:
        job = _busiest_job(session)
        job_id, company = job.id, session.get(Company, job.company_id).name  # type: ignore[union-attr]
        jobs_before = _count(session, Job)
        other_events = session.scalar(
            select(func.count()).select_from(Event).where(Event.job_id != job_id)
        )

    # Sin el nombre de la empresa, nada: ni copia ni borrado.
    wrong = client.post(f"/jobs/{job_id}/erase", json={"confirm": "otra"}, headers=JSON)
    assert wrong.status_code == 422 and company in wrong.json()["error"]["message"]
    assert not erase.backups_dir().exists()
    # Solo desde la UI.
    outside = client.post(
        f"/jobs/{job_id}/erase",
        json={"confirm": company},
        headers={"Origin": "https://evil.example", "Content-Type": "application/json"},
    )
    assert outside.status_code == 403

    response = client.post(f"/jobs/{job_id}/erase", json={"confirm": company.upper()}, headers=JSON)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["deleted_jobs"] == 1 and result["backup"].startswith("backups/")

    with session_scope() as session:
        assert session.get(Job, job_id) is None and session.get(Application, job_id) is None
        assert _count(session, Job) == jobs_before - 1
        assert session.scalar(select(func.count()).select_from(Event)) == other_events
        assert all(
            job_id not in [c["job_id"] for c in reply.candidates]
            for reply in session.scalars(select(Reply))
        )
        assert _dangling(session) == []
    assert client.get(f"/jobs/{job_id}").status_code == 404
    assert client.get("/board").status_code == 200 and client.get("/replies").status_code == 200

    # La copia previa tiene la oferta: es la forma de deshacerlo.
    copy = erase.backups_dir() / Path(result["backup"]).name
    with sqlite3.connect(copy) as db:
        assert db.execute("SELECT count(*) FROM jobs WHERE id = ?", (job_id,)).fetchone() == (1,)
    db.close()


def test_erasing_everything_keeps_profile_sources_and_network(client: TestClient) -> None:
    with session_scope() as session:
        kept = {m: _count(session, m) for m in (ProfileVersion, Source, NetworkContact)}
        total = _count(session, Job)
    assert total > 0

    wrong = client.post("/data/erase", json={"confirm": "borrar"}, headers=JSON)
    assert wrong.status_code == 422
    response = client.post("/data/erase", json={"confirm": "BORRAR"}, headers=JSON)
    assert response.status_code == 200, response.text
    assert response.json()["deleted_jobs"] == total

    with session_scope() as session:
        assert _count(session, Job) == 0 and _count(session, Event) == 0
        assert _count(session, Company) == 0 and _count(session, Reply) == 0
        assert {m: _count(session, m) for m in kept} == kept
        assert _dangling(session) == []
    assert client.get("/board").json()["columns"][0]["cards"] == []
    assert client.get("/status").status_code == 200


def test_only_the_latest_backups_are_kept(demo_data: Path) -> None:
    for second in range(erase.BACKUPS_KEPT + 2):
        erase.backup_database(datetime(2026, 11, 20, 10, 0, second))
    copies = sorted(erase.backups_dir().glob("*.db"))
    assert len(copies) == erase.BACKUPS_KEPT
    assert copies[0].name.endswith("100002-000000.db")
