"""CLI de matching (`jh match`, `jh worker`), orden por score y aviso de embeddings en `doctor`."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from app import cli
from app.core import migrations
from app.core.config import get_settings
from app.core.db import session_scope
from app.schemas.llm_io import JobExtraction
from app.services import doctor, extractions, ingest, jobs, profile
from app.services.matching import embeddings
from app.services.matching import service as matching
from tests.matching_support import FakeEmbedder, demo_extraction_data

runner = CliRunner()


@pytest.fixture
def db(isolated_env: Path) -> None:
    migrations.upgrade()


def seed(title: str, company: str, **changes: object) -> int:
    with session_scope() as session:
        job_id = ingest.add_from_text(session, title, company, "Oferta de ejemplo. " * 20).job_id
        data = {**demo_extraction_data("01-data-engineer"), **changes}
        extractions.save_extraction(session, job_id, JobExtraction.model_validate(data))
        return job_id


def import_profile() -> None:
    with session_scope() as session:
        profile.import_profile(session, profile.EXAMPLE_PATH)


def test_worker_once_json(db: None) -> None:
    import_profile()
    job_id = seed("Data Engineer", "Brétema")
    result = runner.invoke(cli.app, ["worker", "--once", "--json"])
    assert result.exit_code == 0, result.output
    out = json.loads(result.stdout)
    assert (out["done"], out["failed"]) == (2, 0)
    assert out["outcomes"][1]["result"]["job_id"] == job_id


def test_worker_once_text(db: None) -> None:
    result = runner.invoke(cli.app, ["worker", "--once"])
    assert result.exit_code == 0
    assert "No hay tareas pendientes." in result.stdout
    import_profile()
    result = runner.invoke(cli.app, ["worker", "--once"])
    assert "[ok]    tarea 1 rescore_all" in result.stdout


def test_worker_once_reports_failures(db: None) -> None:
    from app.services import tasks

    with session_scope() as session:
        tasks.enqueue(session, "score_job", {"job_id": 7})
    result = runner.invoke(cli.app, ["worker", "--once"])
    assert result.exit_code == 1
    assert "[error] tarea 1 score_job: JobNotFoundError: No existe la oferta 7." in result.stdout


def test_worker_needs_migrated_db(isolated_env: Path) -> None:
    result = runner.invoke(cli.app, ["worker", "--once", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["type"] == "database_not_ready"


def test_match_show_text(db: None) -> None:
    import_profile()
    job_id = seed("Data Engineer", "Brétema")
    result = runner.invoke(cli.app, ["match", "show", str(job_id)])
    assert result.exit_code == 0, result.output
    assert f"Oferta {job_id} · score " in result.stdout
    assert "Filtros duros: pasa." in result.stdout
    assert (
        "Obligatorias: cubiertas Python (F), SQL (F), Snowflake (F), dbt (basic)" in result.stdout
    )
    assert "Nota: Similitud semántica desactivada" in result.stdout


def test_match_show_text_with_failures_and_assessment(db: None) -> None:
    from app.schemas.llm_io import FitAssessment

    import_profile()
    job_id = seed("Data Engineer", "Brétema", years_experience_min=9)
    with session_scope() as session:
        from app.services import events

        events.add_user_event(session, job_id, "reopened")
        matching.save_fit_assessment(
            session,
            job_id,
            FitAssessment(
                verdict="weak", rationale="Pide 9 años.", risks=[], questions_for_user=[]
            ),
        )
    result = runner.invoke(cli.app, ["match", "show", str(job_id)])
    assert "Filtros duros: no pasa." in result.stdout
    assert "  - Pide 9 años de experiencia" in result.stdout
    assert "Valoración del agente: weak" in result.stdout


def test_list_jobs_orders_by_score(db: None) -> None:
    import_profile()
    good = seed("Data Engineer", "Uno")
    bad = seed("Data Engineer", "Dos", must_have_skills=["Kafka", "Scala", "Go"])
    unscored = seed("Data Engineer", "Tres")
    with session_scope() as session:
        matching.get_match(session, good)
        matching.get_match(session, bad)
        by_score = jobs.list_jobs(session, order="score_desc")
        recent = jobs.list_jobs(session, order="recent")
        page = jobs.search_jobs(session)
    assert [j.id for j in by_score] == [good, bad, unscored]
    assert by_score[0].score is not None and by_score[1].score is not None
    assert by_score[0].score > by_score[1].score and by_score[2].score is None
    assert [j.id for j in recent] == [unscored, bad, good]
    assert {row.id: row.score for row in page.items}[good] == by_score[0].score


def test_latest_scores(db: None) -> None:
    import_profile()
    job_id = seed("Data Engineer", "Uno")
    with session_scope() as session:
        assert matching.latest_scores(session, []) == {}
        view = matching.get_match(session, job_id)
        assert matching.latest_scores(session, [job_id, 99]) == {job_id: view.score}


def test_match_rescore(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    import_profile()
    job_id = seed("Data Engineer", "Acme")
    other = seed("Data Engineer", "Globex", locations=["Sevilla"], remote_mode="onsite")
    with session_scope() as session:
        before = matching.get_match(session, job_id).match_id
    monkeypatch.setattr(embeddings, "get_embedder", lambda: FakeEmbedder())
    result = runner.invoke(cli.app, ["match", "rescore", "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {"scored": 1, "closed": []}  # la de Sevilla ya cerró
    with session_scope() as session:
        view = matching.get_match(session, job_id)
    assert view.match_id != before and view.breakdown.semantic is not None
    assert other != job_id
    text = runner.invoke(cli.app, ["match", "rescore"])
    assert text.exit_code == 0 and "Ofertas abiertas revisadas: 1." in text.stdout


def test_match_rescore_without_profile(db: None) -> None:
    result = runner.invoke(cli.app, ["match", "rescore", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["type"] == "not_found"


def test_doctor_embeddings_check(monkeypatch: pytest.MonkeyPatch) -> None:
    check = doctor.check_embeddings(get_settings())
    assert check.status == doctor.CheckStatus.WARN
    assert "JH_EMBEDDINGS=off" in check.detail
    monkeypatch.setattr(embeddings, "unavailable_reason", lambda: None)
    check = doctor.check_embeddings(get_settings())
    assert check.status == doctor.CheckStatus.OK
    assert "paraphrase-multilingual-MiniLM-L12-v2" in check.detail
