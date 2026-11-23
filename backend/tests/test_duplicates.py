"""Las ofertas duplicadas de antes: listarlas y borrarlas sin tocar las que tienen algo propio."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import Event, Job, JobSighting
from app.services import duplicates, erase, ingest, known
from app.services.events import record
from app.services.pipeline import Actor, EventType

TEXT = "Buscamos Data Engineer con Python y SQL para el equipo de datos. " * 10
JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


def _old_duplicate(session: Session, original_id: int, title: str, url: str) -> int:
    """Una duplicada como las que se guardaban antes: oferta propia, `duplicate_of` y cerrada."""
    job_id = ingest.add_from_text(session, title, "Acme", TEXT, url=url).job_id
    job = session.get(Job, job_id)
    assert job is not None
    job.duplicate_of = original_id
    payload = {"duplicate_of": original_id}
    record(session, job_id, EventType.DUPLICATE_DETECTED, Actor.SYSTEM, payload)
    session.flush()
    return job_id


@pytest.fixture
def no_backup(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[int]:
    """La copia previa de verdad mira la base de datos de la configuración, no la del test."""
    calls: list[int] = []

    def fake() -> Path:
        calls.append(1)
        return tmp_path / "data" / "backups" / "copia.db"

    monkeypatch.setattr(erase, "backup_database", fake)
    return calls


def _setup(session: Session) -> tuple[int, int, int, int]:
    original = ingest.add_from_text(
        session, "Data Engineer", "Acme", TEXT, url="https://acme.example/jobs/1"
    ).job_id
    plain = _old_duplicate(session, original, "Product Designer", "https://acme.example/jobs/2")
    with_note = _old_duplicate(
        session, original, "Account Executive", "https://acme.example/jobs/3"
    )
    record(session, with_note, EventType.NOTE, Actor.USER, {"text": "Preguntar a Ana"})
    reopened = _old_duplicate(session, original, "Marketing Manager", "https://acme.example/jobs/4")
    record(session, reopened, EventType.REOPENED, Actor.USER)
    session.flush()
    return original, plain, with_note, reopened


def test_list_says_which_can_be_erased_and_why_the_others_stay(session: Session) -> None:
    original, plain, with_note, reopened = _setup(session)
    result = duplicates.list_duplicates(session)
    reasons = {item.job_id: item.keep_reason for item in result.items}
    assert reasons == {plain: None, with_note: "own_work", reopened: "no_longer_duplicate"}
    assert (result.erasable, result.kept) == (1, 2)
    assert {item.original_id for item in result.items} == {original}
    assert result.items[0].original_title == "Data Engineer"


def test_erase_removes_only_the_erasable_and_moves_their_sightings(
    session: Session, no_backup: list[int]
) -> None:
    original, plain, with_note, reopened = _setup(session)
    result = duplicates.erase_duplicates(session, [plain, with_note, reopened, 99999])

    assert (result.deleted_jobs, result.kept, result.moved_sightings) == (1, 2, 1)
    assert no_backup == [1]
    assert session.get(Job, plain) is None
    assert session.scalar(select(func.count(Event.id)).where(Event.job_id == plain)) == 0
    assert session.get(Job, with_note) is not None and session.get(Job, reopened) is not None
    refs = set(session.scalars(select(JobSighting.ref).where(JobSighting.job_id == original)))
    assert "acme.example/jobs/2" in refs
    # La URL de la borrada se sigue reconociendo sin abrirla.
    item = known.KnownItem(url="https://acme.example/jobs/2")
    [checked] = known.check_known(session, [item]).items
    assert (checked.status, checked.job_id) == ("known", original)


def test_erase_with_nothing_erasable_makes_no_backup(
    session: Session, no_backup: list[int]
) -> None:
    _, _, with_note, _ = _setup(session)
    result = duplicates.erase_duplicates(session, [with_note])
    assert (result.deleted_jobs, result.kept, result.backup) == (0, 1, None)
    assert no_backup == []


def test_own_work_covers_cvs_and_any_new_table() -> None:
    """Toda fila con enlace obligatorio a la oferta, salvo lo automático, cuenta como propia."""
    tables = {table.name for table in duplicates._own_work_tables()}
    assert {"documents", "application_attempts", "milestones", "message_drafts"} <= tables
    assert not tables & duplicates.AUTOMATIC_TABLES


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


def test_api_lists_and_erases_only_from_the_ui(client: TestClient) -> None:
    with session_scope() as session:
        original, plain, _, _ = _setup(session)
    listed = client.get("/jobs/duplicates").json()
    assert listed["erasable"] == 1

    body = {"job_ids": [plain]}
    other_site = {"Origin": "https://evil.example", "Content-Type": "application/json"}
    assert client.post("/jobs/duplicates/erase", json=body, headers=other_site).status_code == 403
    response = client.post("/jobs/duplicates/erase", json=body, headers=JSON)
    assert response.status_code == 200, response.text
    assert response.json()["deleted_jobs"] == 1
    assert response.json()["backup"].startswith("backups/")
    assert client.get("/jobs/duplicates").json()["erasable"] == 0
    assert client.get(f"/jobs/{original}").status_code == 200


def test_sightings_already_on_the_original_are_not_moved_twice(
    session: Session, no_backup: list[int]
) -> None:
    original = ingest.add_from_text(
        session, "Data Engineer", "Acme", TEXT, url="https://acme.example/jobs/1"
    ).job_id
    dup = _old_duplicate(session, original, "Product Designer", "https://acme.example/jobs/1")
    result = duplicates.erase_duplicates(session, [dup])
    assert (result.deleted_jobs, result.moved_sightings) == (1, 0)
    refs = list(session.scalars(select(JobSighting.ref).where(JobSighting.job_id == original)))
    assert refs == ["acme.example/jobs/1"]


def test_an_old_duplicate_found_by_fingerprint_leads_to_its_original(session: Session) -> None:
    original, plain, _, _ = _setup(session)
    again = ingest.add_from_text(
        session, "Product Designer", "Acme", TEXT, url="https://acme.example/jobs/9"
    )
    assert (again.created, again.job_id, again.duplicate_of) == (False, original, original)
    item = known.KnownItem(url="https://x.example/9", title="Product Designer", company="Acme")
    [checked] = known.check_known(session, [item]).items
    assert (checked.status, checked.job_id) == ("same_offer", original)
    assert plain != original


def test_a_tie_goes_to_the_live_offer(session: Session) -> None:
    """Empate entre una cerrada más reciente y una viva: gana la viva."""
    live = ingest.add_from_text(session, "Data Engineer Python", "Acme", TEXT).job_id
    closed = ingest.add_from_text(
        session, "Data Engineer Python", "Acme", TEXT, location="Vigo"
    ).job_id
    record(session, closed, EventType.DISCARDED, Actor.USER, {"reason": "other"})
    variant = ingest.add_from_text(session, "Data Engineer - Python", "Acme", TEXT)
    assert (variant.created, variant.job_id) == (False, live)
