"""Matches en la BD: filtros al extraer, score en el worker, valoración y recálculo por perfil."""

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from sqlalchemy import func, select

from app.core import migrations
from app.core.db import session_scope
from app.models import Event, Match, Task
from app.models.base import utcnow
from app.schemas.llm_io import FitAssessment, JobExtraction
from app.services import events, extractions, ingest, profile, tasks, worker
from app.services.events import JobNotFoundError
from app.services.extractions import ExtractionNotFoundError
from app.services.matching import embeddings
from app.services.matching import service as matching
from app.services.pipeline import Stage
from tests.matching_support import BrokenEmbedder, FakeEmbedder, demo_extraction_data

ASSESSMENT = FitAssessment(
    verdict="strong",
    rationale="Cubre Python, SQL y Snowflake con nivel F; dbt solo como básico.",
    risks=["dbt a nivel básico"],
    questions_for_user=["¿Has usado dbt en algún proyecto?"],
)


@pytest.fixture(autouse=True)
def db(isolated_env: Path) -> Iterator[None]:
    migrations.upgrade()
    yield


def import_demo_profile(tmp_path: Path | None = None, **preferences: Any) -> int:
    path = profile.EXAMPLE_PATH
    if preferences:
        assert tmp_path is not None
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["preferences"].update(preferences)
        path = tmp_path / "profile.yaml"
        path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    with session_scope() as session:
        return profile.import_profile(session, path).profile_version_id


def add_job(title: str = "Data Engineer (m/f/d)", company: str = "Brétema Analytics") -> int:
    with session_scope() as session:
        return ingest.add_from_text(session, title, company, "Texto de la oferta. " * 20).job_id


def extract(job_id: int, name: str = "01-data-engineer", **changes: Any) -> Any:
    data = demo_extraction_data(name)
    data.update(changes)
    with session_scope() as session:
        return extractions.save_extraction(session, job_id, JobExtraction.model_validate(data))


def event_types(job_id: int) -> list[str]:
    with session_scope() as session:
        return [e.type for e in events.get_timeline(session, job_id).events]


def queued() -> list[tuple[str, dict[str, Any]]]:
    with session_scope() as session:
        rows = session.scalars(select(Task).where(Task.status == "queued").order_by(Task.id))
        return [(t.kind, t.payload) for t in rows]


def clear_queue() -> None:
    with session_scope() as session:
        for task in session.scalars(select(Task)):
            session.delete(task)


def stage(job_id: int) -> Stage:
    with session_scope() as session:
        return events.current_stage(session, job_id)


# --- Al guardar una extracción -------------------------------------------------------------------


def test_extraction_without_profile_skips_filters_and_score() -> None:
    job_id = add_job()
    result = extract(job_id)
    assert result.hard_filters is None
    assert result.stage == Stage.PENDING_TRIAGE
    assert queued() == []


def test_extraction_passing_filters_enqueues_score() -> None:
    import_demo_profile()
    clear_queue()
    job_id = add_job()
    result = extract(job_id)
    assert result.hard_filters is not None and result.hard_filters.passed
    assert result.stage == Stage.PENDING_TRIAGE
    assert queued() == [("score_job", {"job_id": job_id})]
    assert event_types(job_id) == ["found", "extracted"]


def test_extraction_failing_filters_closes_job() -> None:
    import_demo_profile()
    job_id = add_job()
    result = extract(job_id, seniority="lead", remote_mode="onsite", locations=["Madrid"])
    assert result.hard_filters is not None and not result.hard_filters.passed
    assert result.stage == Stage.CLOSED
    assert event_types(job_id) == ["found", "extracted", "hard_filter_failed"]
    with session_scope() as session:
        failed = events.get_timeline(session, job_id).events[-1]
        assert failed.actor == "system"
        assert [f["filter"] for f in failed.payload["failures"]] == [
            "seniority",
            "remote_mode",
            "location",
        ]


def test_reopened_job_is_not_closed_again_by_filters() -> None:
    import_demo_profile()
    job_id = add_job()
    extract(job_id, seniority="lead")
    with session_scope() as session:
        events.add_user_event(session, job_id, "reopened")
    assert stage(job_id) == Stage.PENDING_TRIAGE
    extract(job_id, seniority="lead")  # el agente vuelve a extraer: no se cierra de nuevo
    assert stage(job_id) == Stage.PENDING_TRIAGE
    with session_scope() as session:
        assert matching.user_overrode_filters(session, job_id)


# --- get_match -----------------------------------------------------------------------------------


def test_get_match_computes_and_reuses() -> None:
    version = import_demo_profile()
    job_id = add_job()
    extract(job_id)
    with session_scope() as session:
        view = matching.get_match(session, job_id)
        again = matching.get_match(session, job_id)
    assert again.match_id == view.match_id
    assert view.profile_version_id == version
    assert view.hard_filters.passed
    assert view.triage_threshold == 55
    assert view.below_threshold is (view.score < 55)
    assert view.assessment is None and not view.assessment_stale
    assert view.assessment_score is None
    assert [c.name for c in view.breakdown.components][0] == "must_have_coverage"
    assert view.breakdown.must_have.ratio == pytest.approx(0.8)
    assert event_types(job_id) == ["found", "extracted", "scored"]
    with session_scope() as session:
        scored = events.get_timeline(session, job_id).events[-1]
        assert scored.payload == {"match_id": view.match_id, "score": view.score, "passed": True}


def test_get_match_brings_doubtful_signals_without_changing_the_score(tmp_path: Path) -> None:
    # Fase 25.3: `assess-fit` las ve en `get_match` y las cita en los riesgos. Sin los filtros de
    # contrato y tipo de empresa de la 27.5, que el perfil demo trae.
    import_demo_profile(tmp_path, contract_types=[], excluded_employer_kinds=[])
    plain, flagged = add_job(), add_job(company="Hays")
    extract(plain)
    extract(flagged, contract_type="fixed_term")
    with session_scope() as session:
        clean = matching.get_match(session, plain)
        noted = matching.get_match(session, flagged)
    assert clean.signals == []
    assert [s.code for s in noted.signals] == ["employer_hidden", "fixed_term"]
    assert noted.score == clean.score and noted.hard_filters.passed


def test_exclude_signals_in_the_profile_closes_the_job(tmp_path: Path) -> None:
    import_demo_profile(tmp_path, exclude_signals=["fixed_term"])
    job_id = add_job()
    result = extract(job_id, contract_type="fixed_term")
    assert not result.hard_filters.passed
    assert [f.filter for f in result.hard_filters.failures] == ["contract"]
    assert "hard_filter_failed" in event_types(job_id)


def test_get_match_recomputes_after_new_extraction() -> None:
    import_demo_profile()
    job_id = add_job()
    extract(job_id)
    with session_scope() as session:
        first = matching.get_match(session, job_id)
    extract(job_id, must_have_skills=["Kafka", "Scala"])
    with session_scope() as session:
        second = matching.get_match(session, job_id)
    assert second.match_id != first.match_id
    assert second.score < first.score
    assert second.breakdown.must_have.missing == ["Kafka", "Scala"]


def test_get_match_recomputes_when_scoring_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    import_demo_profile()
    job_id = add_job()
    extract(job_id)
    with session_scope() as session:
        first = matching.get_match(session, job_id)
        matching.save_fit_assessment(session, job_id, ASSESSMENT)
    assert first.breakdown.semantic is None
    # Instalar el extra `matching` cambia la huella: el match se recalcula con similitud.
    monkeypatch.setattr(embeddings, "get_embedder", lambda: FakeEmbedder())
    with session_scope() as session:
        second = matching.get_match(session, job_id)
        again = matching.get_match(session, job_id)
    assert second.match_id != first.match_id and again.match_id == second.match_id
    assert second.breakdown.semantic is not None
    assert second.assessment == ASSESSMENT and second.assessment_stale
    assert second.assessment_score == first.score
    # También una versión nueva del scorer.
    monkeypatch.setattr(matching.scorer, "SCORER_VERSION", matching.scorer.SCORER_VERSION + 1)
    with session_scope() as session:
        assert matching.get_match(session, job_id).match_id != second.match_id


def test_scoring_key_ignores_triage_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    key = matching.scoring_key()
    policies = matching.get_policies()
    scoring = policies.scoring.model_copy(update={"triage_threshold": 70})
    changed = policies.model_copy(update={"scoring": scoring})
    monkeypatch.setattr(matching, "get_policies", lambda: changed)
    assert matching.scoring_key() == key
    weights = scoring.weights.model_copy(update={"preferences_fit": 0.2})
    rescoring = scoring.model_copy(update={"weights": weights})
    reweighted = policies.model_copy(update={"scoring": rescoring})
    monkeypatch.setattr(matching, "get_policies", lambda: reweighted)
    assert matching.scoring_key() != key


def test_get_match_on_closed_job_does_not_record_event() -> None:
    import_demo_profile()
    job_id = add_job()
    extract(job_id, seniority="lead")
    with session_scope() as session:
        view = matching.get_match(session, job_id)
    assert not view.hard_filters.passed
    assert event_types(job_id)[-1] == "hard_filter_failed"  # sin `scored` en una oferta cerrada


def test_get_match_errors() -> None:
    with session_scope() as session, pytest.raises(JobNotFoundError):
        matching.get_match(session, 99)
    job_id = add_job()
    with session_scope() as session, pytest.raises(ExtractionNotFoundError):
        matching.get_match(session, job_id)
    extract(job_id)
    with session_scope() as session, pytest.raises(profile.ProfileNotFoundError):
        matching.get_match(session, job_id)


def test_get_match_uses_embedder(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeEmbedder()
    monkeypatch.setattr(embeddings, "get_embedder", lambda: fake)
    import_demo_profile()
    job_id = add_job()
    extract(job_id)
    with session_scope() as session:
        view = matching.get_match(session, job_id)
    assert view.breakdown.semantic is not None and view.breakdown.semantic.model == "fake-bow"
    assert fake.calls == 1


# --- save_fit_assessment -------------------------------------------------------------------------


def test_save_assessment() -> None:
    import_demo_profile()
    job_id = add_job()
    extract(job_id)
    with session_scope() as session:
        result = matching.save_fit_assessment(session, job_id, ASSESSMENT, agent_name="codex")
        view = matching.get_match(session, job_id)
    assert result.ok and result.match_id == view.match_id
    assert view.assessment == ASSESSMENT and not view.assessment_stale
    with session_scope() as session:
        assessed = events.get_timeline(session, job_id).events[-1]
    assert (assessed.type, assessed.actor, assessed.agent_name) == (
        "fit_assessed",
        "agent",
        "codex",
    )
    assert assessed.payload == {"match_id": view.match_id, "verdict": "strong"}


def test_assessment_becomes_stale_after_new_profile(tmp_path: Path) -> None:
    import_demo_profile()
    job_id = add_job()
    extract(job_id)
    with session_scope() as session:
        matching.save_fit_assessment(session, job_id, ASSESSMENT)
    import_demo_profile(tmp_path, max_years_required=6)
    with session_scope() as session:
        view = matching.get_match(session, job_id)
    assert view.assessment == ASSESSMENT
    assert view.assessment_stale


def test_assessment_on_closed_job_is_rejected() -> None:
    import_demo_profile()
    job_id = add_job()
    extract(job_id, seniority="lead")
    with session_scope() as session, pytest.raises(ValueError, match="no es válido"):
        matching.save_fit_assessment(session, job_id, ASSESSMENT)


def test_assessment_schema_is_strict() -> None:
    with pytest.raises(ValueError):
        FitAssessment.model_validate({"verdict": "great", "rationale": "", "risks": []})


# --- Recalcular tras un perfil nuevo -------------------------------------------------------------


def test_new_profile_enqueues_rescore_once(tmp_path: Path) -> None:
    import_demo_profile()
    assert queued() == [("rescore_all", {})]
    import_demo_profile()  # mismo contenido: no crea versión ni encola
    import_demo_profile(tmp_path, max_years_required=6)
    assert queued() == [("rescore_all", {})]  # la que ya estaba en cola no se duplica


def test_rescore_closes_jobs_that_no_longer_pass(tmp_path: Path) -> None:
    import_demo_profile()
    triage_a, triage_b, reopened, approved, no_extraction = (add_job(f"Job {i}") for i in range(5))
    for job_id in (triage_a, triage_b, reopened, approved):
        extract(job_id)
    extract(reopened, seniority="lead")  # cerrada por filtros y reabierta a mano
    with session_scope() as session:
        events.add_user_event(session, reopened, "reopened")
        events.add_user_event(session, approved, "approved")

    # Si solo acepta prácticas, las ofertas «mid» ya no pasan.
    import_demo_profile(tmp_path, seniority_target=["intern"])
    with session_scope() as session:
        result = matching.rescore_open_jobs(session)
    assert result.scored == 4  # la que no tiene extracción no cuenta
    assert result.closed == [triage_a, triage_b]
    assert stage(reopened) == Stage.PENDING_TRIAGE  # el usuario decidió reabrirla
    assert stage(approved) == Stage.APPROVED  # los filtros solo cierran en triaje
    assert stage(no_extraction) == Stage.PENDING_EXTRACTION


def test_match_views_without_profile_is_empty() -> None:
    job_id = add_job()
    extract(job_id)
    with session_scope() as session:
        assert matching.match_views(session, [job_id]) == {}


def test_match_views_skips_jobs_without_extraction() -> None:
    import_demo_profile()
    with_extraction, without = add_job("A"), add_job("B")
    extract(with_extraction)
    with session_scope() as session:
        views = matching.match_views(session, [with_extraction, without])
    assert list(views) == [with_extraction]


# --- Cola y worker -------------------------------------------------------------------------------


def test_worker_scores_queued_jobs() -> None:
    import_demo_profile()
    job_id = add_job()
    extract(job_id)
    run = worker.run_pending()
    assert (run.done, run.failed) == (2, 0)
    assert [o.kind for o in run.outcomes] == ["rescore_all", "score_job"]
    assert run.outcomes[1].result is not None and run.outcomes[1].result["job_id"] == job_id
    assert queued() == []
    with session_scope() as session:
        assert session.scalar(select(func.count()).select_from(Match)) == 1  # sin duplicar
    assert worker.run_pending().outcomes == []


def test_worker_retries_then_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    with session_scope() as session:
        task_id = tasks.enqueue(session, "score_job", {"job_id": 404}).id
    first = worker.run_pending()
    assert first.failed == 1 and "No existe la oferta 404" in (first.outcomes[0].error or "")
    assert worker.run_pending().outcomes == []  # espera antes de reintentar
    for _ in range(tasks.MAX_ATTEMPTS - 1):
        with session_scope() as session:
            task = session.get(Task, task_id)
            assert task is not None
            task.run_after = utcnow() - timedelta(seconds=1)
        worker.run_pending()
    with session_scope() as session:
        task = session.get(Task, task_id)
        assert task is not None
        assert (task.status, task.attempts) == ("failed", tasks.MAX_ATTEMPTS)
        assert "No existe la oferta 404" in (task.last_error or "")


def test_worker_unknown_kind() -> None:
    with session_scope() as session:
        session.add(Task(kind="nope", payload={}, status="queued", attempts=0, run_after=utcnow()))
    run = worker.run_pending()
    assert run.outcomes[0].error == "ValueError: Tipo de tarea desconocido: «nope»."


def test_worker_limit_and_forever() -> None:
    with session_scope() as session:
        for job_id in (1, 2, 3):
            tasks.enqueue(session, "score_job", {"job_id": job_id})
    assert len(worker.run_pending(limit=2).outcomes) == 2

    runs: list[worker.WorkerRun] = []

    class Stop(Exception):
        pass

    def sleep(_seconds: float) -> None:
        raise Stop

    with pytest.raises(Stop):
        worker.run_forever(0.1, runs.append, sleep=sleep)
    assert len(runs) == 1 and len(runs[0].outcomes) == 1


def test_enqueue_deduplicates_by_payload() -> None:
    with session_scope() as session:
        a = tasks.enqueue(session, "score_job", {"job_id": 1})
        b = tasks.enqueue(session, "score_job", {"job_id": 1})
        c = tasks.enqueue(session, "score_job", {"job_id": 2})
        assert a.id == b.id != c.id
        assert tasks.claim_next(session) is a
        assert tasks.enqueue(session, "score_job", {"job_id": 1}).id != a.id  # ya no está en cola


def test_status_counts_queued_tasks() -> None:
    import_demo_profile()
    from app.services import status

    with session_scope() as session:
        assert status.get_status(session).pending_tasks == 1
        assert session.scalar(select(func.count()).select_from(Event)) == 0


def test_rescore_retries_failed_semantic(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un match con la similitud fallida (sin red, o a mitad de instalarla) se rehace al recalcular
    en el worker en cuanto funciona; leerlo no lo rehace en cada visita."""
    broken: Any = BrokenEmbedder()
    broken.model_name = "fake-bow"  # misma huella que el bueno: solo cambia que ahora funciona
    monkeypatch.setattr(embeddings, "get_embedder", lambda: broken)
    import_demo_profile()
    job_id = add_job()
    extract(job_id)
    with session_scope() as session:
        first = matching.current_match(session, job_id)
        assert matching.semantic_failed(first.breakdown)
        assert matching.has_semantic_failures(session)
        assert matching.current_match(session, job_id).id == first.id
    monkeypatch.setattr(embeddings, "get_embedder", lambda: FakeEmbedder())
    with session_scope() as session:
        assert matching.current_match(session, job_id).id == first.id
        matching.rescore_open_jobs(session)
        again = matching.current_match(session, job_id)
        assert again.id != first.id and not matching.semantic_failed(again.breakdown)
        assert not matching.has_semantic_failures(session)
