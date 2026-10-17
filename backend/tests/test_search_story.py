"""Fase 25.6: la búsqueda entera en números agregados (`cai stats story`), sin nombres."""

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from app import cli
from app.core.db import session_scope
from app.models import Company, Job, Source
from app.services import analytics, demo
from tests.test_analytics import History, _t

runner = CliRunner()
NOW = datetime(2026, 10, 5, 9, 30, tzinfo=UTC)


def test_story_without_jobs(session: Session) -> None:
    story = analytics.get_search_story(session)
    assert story.found == story.applied == 0
    assert story.started_on is None and story.weeks is None
    assert story.reply_rate is None
    assert story.markdown["es"].startswith("**Mi búsqueda con CandidatAI**: 0 ofertas evaluadas")


def test_story_counts_the_whole_search(session: Session) -> None:
    h = History(session)
    h.job(h.ats, _t(1), "Data Engineer", ("extracted", _t(1, 11)), ("approved", _t(2)))
    h.job(
        h.ats,
        _t(3),
        "Data Engineer",
        ("extracted", _t(3, 11)),
        ("approved", _t(4)),
        ("applied_manually", _t(5)),
        ("reply_received", _t(9)),
        ("interview_scheduled", _t(10)),
        ("offer_received", _t(20)),
    )
    h.job(h.alerts, _t(6), "Analista", ("extracted", _t(6, 11)), ("hard_filter_failed", _t(6, 12)))
    h.job(h.alerts, _t(7), None)  # sin extraer: vista, no evaluada
    duplicate = h.job(h.alerts, _t(8), "Data Engineer", ("duplicate_detected", _t(8, 11)))
    session.commit()

    story = analytics.get_search_story(session)
    assert duplicate.id  # la duplicada no cuenta
    assert (story.found, story.evaluated, story.approved, story.applied) == (4, 3, 2, 1)
    assert (story.replied, story.interviews, story.offers, story.accepted) == (1, 1, 1, 0)
    assert story.started_on == date(2026, 9, 1)
    assert story.first_applied_on == date(2026, 9, 5)
    assert story.last_activity_on == date(2026, 9, 20)
    assert story.weeks == 3
    assert story.reply_rate == story.interview_rate == 1.0
    assert story.median_days_to_reply == 4.0
    assert story.markdown["es"] == (
        "**Mi búsqueda con CandidatAI** (1 sep 2026 → 20 sep 2026, 3 semanas): 3 ofertas "
        "evaluadas, 2 aprobadas, 1 candidatura, 1 respuesta, 1 entrevista y 1 oferta."
    )
    assert story.markdown["en"].startswith(
        "**My search with CandidatAI** (1 Sep 2026 → 20 Sep 2026, 3 weeks): 3 postings evaluated"
    )


@pytest.fixture
def demo_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_env: Path) -> Path:
    monkeypatch.setattr(demo, "_pdf_engine", lambda: (None, None))
    target = tmp_path / "data-demo"
    demo.seed(target, now=NOW)
    return target


def test_cli_story_on_the_demo_has_no_names(demo_dir: Path) -> None:
    with demo.use_data_dir(demo_dir):
        result = runner.invoke(cli.app, ["stats", "story", "--json"])
        assert result.exit_code == 0, result.output
        story = json.loads(result.stdout)
        with session_scope() as session:
            funnel = {s.step: s.count for s in analytics.get_funnel_stats(session).steps}
            names = set(session.scalars(select(Company.name)))
            names |= set(session.scalars(select(Source.name)))
            names |= set(session.scalars(select(Job.title)))
            names |= set(
                session.scalars(select(Job.location_raw).where(Job.location_raw.is_not(None)))
            )
        text = runner.invoke(cli.app, ["stats", "story"])
        assert text.exit_code == 0, text.output

    # Los mismos números que el embudo, desde el principio.
    assert story["found"] == funnel["found"] > 0
    assert story["applied"] == funnel["applied"] > 0
    assert story["interviews"] == funnel["interview"] > 0
    assert story["offers"] == funnel["offer"] > 0
    assert story["approved"] >= story["applied"]
    # Solo números y fechas: ningún nombre de empresa, puesto, fuente ni lugar.
    assert set(story) == set(analytics.SearchStory.model_fields)
    dumped = json.dumps(story, ensure_ascii=False) + text.stdout
    leaked = [n for n in names if n and n in dumped]
    assert leaked == []
    assert "Para el README" in text.stdout
