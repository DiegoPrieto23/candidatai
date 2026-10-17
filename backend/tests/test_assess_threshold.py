"""Umbral antes de gastar (fase 25.4): «Evaluar encaje» en segundo plano solo con las ofertas que
llegan al score; las demás no entran en la orden y la UI sabe por qué."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.core.policies import get_policies
from app.services import agent_runs, assess_threshold, triage
from app.services.agent_launch import LaunchError
from app.services.assess_threshold import AssessThresholdInput
from app.services.matching import service as matching
from tests.test_matching_service import add_job, extract, import_demo_profile

UI = {"Origin": "http://127.0.0.1:5173"}


@pytest.fixture(autouse=True)
def db(isolated_env: Path) -> Iterator[None]:
    migrations.upgrade()
    yield


def _jobs() -> tuple[int, int, int, int]:
    """Una oferta que encaja (score alto) y otra que no (score bajo), con sus scores."""
    import_demo_profile()
    good, bad = add_job(), add_job("Kafka Developer", "Otra Empresa")
    extract(good)
    extract(bad, must_have_skills=["Kafka", "Scala", "Rust", "Go"], nice_to_have_skills=[])
    with session_scope() as session:
        high = matching.get_match(session, good).score
        low = matching.get_match(session, bad).score
    assert high > low
    return good, bad, high, low


def test_default_is_the_triage_threshold_minus_ten() -> None:
    with session_scope() as session:
        view = assess_threshold.get_threshold(session)
    triage_threshold = get_policies().scoring.triage_threshold
    assert view.source == "default" and view.value == triage_threshold - 10
    assert view.default == view.value and view.triage_threshold == triage_threshold


def test_policies_then_ui_override(monkeypatch: pytest.MonkeyPatch) -> None:
    policies = get_policies()
    runs = policies.background_runs.model_copy(update={"assess_min_score": 70})
    patched = policies.model_copy(update={"background_runs": runs})
    monkeypatch.setattr(assess_threshold, "get_policies", lambda: patched)
    with session_scope() as session:
        assert assess_threshold.get_threshold(session).source == "policies"
        saved = assess_threshold.set_threshold(session, AssessThresholdInput(value=30))
        assert (saved.value, saved.source, saved.default) == (30, "ui", 70)
        back = assess_threshold.set_threshold(session, AssessThresholdInput(value=None))
        assert (back.value, back.source) == (70, "policies")


def test_below_the_threshold_is_not_in_the_background_prompt() -> None:
    good, bad, high, low = _jobs()
    with session_scope() as session:
        assess_threshold.set_threshold(session, AssessThresholdInput(value=low + 1))
        plan = assess_threshold.plan(session)
        assert plan.eligible == [good] and plan.skipped == {bad: low}
        prompt = assess_threshold.prompt(plan)
    assert f"ofertas {good}." in prompt and str(bad) not in prompt.split("ofertas")[1][:10]
    assert f"por debajo de {low + 1}" in prompt

    with session_scope() as session:
        queue = triage.triage_queue(session)
        assert queue.assess_min_score == low + 1  # la UI dice por qué se queda sin valorar
        scores = {item.job.id: item.match.score for item in queue.items if item.match}
        assert scores[bad] < queue.assess_min_score <= scores[good]


def test_nothing_above_the_threshold_does_not_launch() -> None:
    _good, _bad, high, _low = _jobs()
    with session_scope() as session:
        assess_threshold.set_threshold(session, AssessThresholdInput(value=high + 1))
        with pytest.raises(LaunchError, match=rf"2 tienen un score por debajo de {high + 1}"):
            agent_runs._assess_prompt(session)
        # La matriz de `cai eval compat` las valora todas.
        assert len(assess_threshold.plan(session, threshold=0).eligible) == 2


def test_already_assessed_jobs_are_left_out() -> None:
    good, bad, _high, low = _jobs()
    with session_scope() as session:
        assess_threshold.set_threshold(session, AssessThresholdInput(value=0))
        matching.save_fit_assessment(
            session,
            good,
            matching.FitAssessment(
                verdict="strong", rationale="r", risks=[], questions_for_user=[]
            ),
        )
        assert assess_threshold.plan(session).eligible == [bad]
    assert low >= 0


def test_api_threshold_needs_the_ui() -> None:
    client = TestClient(create_app())
    assert client.get("/agent/assess-threshold").json()["source"] == "default"
    other = {"Origin": "https://evil.example.com"}
    assert (
        client.put("/agent/assess-threshold", json={"value": 50}, headers=other).status_code == 403
    )
    saved = client.put("/agent/assess-threshold", json={"value": 50}, headers=UI)
    assert saved.status_code == 200 and saved.json()["value"] == 50
    assert client.put("/agent/assess-threshold", json={"value": 101}, headers=UI).status_code == 422
