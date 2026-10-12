"""Modo demo (fase 12.1): `jh demo seed` y la marca de demo."""

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from app import cli
from app.core.config import DEMO_MARKER, get_settings
from app.core.db import session_scope
from app.models import Event, Job, Match, Source, Task
from app.services import analytics, demo, events, network, status
from app.services.documents import pdf
from app.services.documents import service as cv_service
from app.services.pipeline import Stage
from tests.cv_support import fake_converter

runner = CliRunner()
NOW = datetime(2026, 10, 5, 9, 30, tzinfo=UTC)


@pytest.fixture
def fake_pdf(monkeypatch: pytest.MonkeyPatch) -> None:
    """PDF sin LibreOffice: los CVs de la demo se renderizan con el conversor falso."""
    monkeypatch.setattr(pdf, "converter_name", lambda: "Conversor de prueba")
    monkeypatch.setattr(pdf, "get_converter", lambda: fake_converter())


def _snapshot(target: Path) -> list[tuple[object, ...]]:
    """Lo que debe repetirse entre ejecuciones: oferta, fuente, etapa, score y eventos (con el
    motivo de descarte y el canal, que usa la analítica)."""
    with demo.use_data_dir(target), session_scope() as session:
        rows: list[tuple[object, ...]] = []
        for job in session.scalars(select(Job).order_by(Job.id)):
            source = session.get(Source, job.source_id)
            history = [
                (e.type, e.payload.get("reason"), e.payload.get("channel"))
                for e in session.scalars(
                    select(Event).where(Event.job_id == job.id).order_by(Event.id)
                )
            ]
            score = session.scalars(
                select(Match.score).where(Match.job_id == job.id).order_by(Match.id.desc())
            ).first()
            stage = events.current_stage(session, job.id)
            rows.append(
                (job.title, job.location_raw, source and source.kind, str(stage), score, history)
            )
        return rows


@pytest.mark.usefixtures("fake_pdf")
def test_seed_fills_a_demo_folder(tmp_path: Path, isolated_env: Path) -> None:
    target = tmp_path / "data-demo"
    summary = demo.seed(target, now=NOW)

    assert summary.jobs == 60
    assert summary.cvs == 2
    assert summary.warnings == []
    assert (target / DEMO_MARKER).is_file()
    assert (target / "profile.yaml").is_file()
    assert summary.by_stage[Stage.CV_READY] == 2
    assert summary.by_stage[Stage.PENDING_EXTRACTION] == 3
    assert summary.by_stage[Stage.CLOSED] > 0
    # Nada fuera de la carpeta: la configuración vuelve a la de antes.
    assert get_settings().data_dir == isolated_env.resolve()
    assert not (isolated_env / "jobhunter.db").exists()

    with demo.use_data_dir(target), session_scope() as session:
        assert get_settings().demo_mode
        assert status.get_status(session).demo_mode
        # Historial dentro de las 8 semanas; solo los CVs (hechos al sembrar) llevan la hora real.
        oldest = NOW - timedelta(weeks=demo.WEEKS)
        story = session.scalars(select(Event.occurred_at).where(Event.type.not_like("cv_%"))).all()
        assert oldest <= min(story)
        assert max(story) <= NOW

        stats = analytics.get_funnel_stats(session)
        counts = {step.step: step.count for step in stats.steps}
        for step in ("found", "triaged", "approved", "applied", "replied", "interview", "offer"):
            assert counts[step] > 0, step
        assert len([w for w in stats.by_week if w.found]) >= demo.WEEKS
        assert {r.reason for r in stats.discard_reasons} >= {"skills", "other"}
        assert stats.hard_filter_failures

        # Red de LinkedIn ficticia (fase 18): importada y cruzada con alguna oferta de la demo.
        all_jobs = session.scalars(select(Job.id)).all()
        assert sum(network.known_counts(session, list(all_jobs)).values()) > 0

        # Las fuentes de ATS quedan en pausa (el worker no descarga tableros inventados) y la cola
        # de score, vacía (ya está calculado).
        ats = session.scalars(select(Source).where(Source.kind.in_(["greenhouse", "lever"])))
        assert [s.active for s in ats] == [False, False]
        assert not session.scalars(select(Task).where(Task.status == "queued")).all()

        ready = session.scalars(select(Job).where(Job.title.in_(["Data Engineer"]))).all()
        with_cv = [j for j in ready if cv_service.latest_document(session, j.id) is not None]
        assert len(with_cv) == 1
        assert events.current_stage(session, with_cv[0].id) == Stage.CV_READY

        # La oferta con la instrucción oculta llega marcada.
        assert [j.title for j in session.scalars(select(Job)) if j.risk_flags] == [
            "Analytics Engineer"
        ]

    # Misma semilla, mismo contenido.
    first = _snapshot(target)
    demo.seed(target, force=True, now=NOW)
    assert _snapshot(target) == first


def test_status_is_not_demo_by_default(session) -> None:  # noqa: ANN001
    assert not get_settings().demo_mode
    assert status.get_status(session).demo_mode is False


def test_seed_refuses_a_folder_that_is_not_a_demo(tmp_path: Path) -> None:
    target = tmp_path / "mis-datos"
    target.mkdir()
    (target / "jobhunter.db").write_text("no tocar", encoding="utf-8")
    with pytest.raises(demo.DemoSeedError, match="no es una demo"):
        demo.seed(target)
    assert (target / "jobhunter.db").read_text(encoding="utf-8") == "no tocar"


@pytest.mark.parametrize("where", ["data", "data/demo", ".", ".."])
def test_seed_refuses_the_real_data_folder_and_its_parents(where: str) -> None:
    with pytest.raises(demo.DemoSeedError, match="data/"):
        demo.prepare_dir(demo.REPO_ROOT / where, force=True)


def test_use_data_dir_restores_the_environment_after_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, isolated_env: Path
) -> None:
    monkeypatch.delenv("JH_DB_URL", raising=False)
    with pytest.raises(RuntimeError), demo.use_data_dir(tmp_path / "demo", embeddings=False):
        assert get_settings().data_dir == (tmp_path / "demo").resolve()
        assert get_settings().embeddings == "off"
        raise RuntimeError("falla dentro")
    assert "JH_DB_URL" not in os.environ
    assert os.environ["JH_DATA_DIR"] == str(isolated_env)
    assert get_settings().data_dir == isolated_env.resolve()


def test_seed_needs_force_to_replace_a_demo(tmp_path: Path) -> None:
    target = tmp_path / "data-demo"
    target.mkdir()
    (target / DEMO_MARKER).write_text("", encoding="utf-8")
    (target / "jobhunter.db").write_text("", encoding="utf-8")
    with pytest.raises(demo.DemoSeedError, match="--force"):
        demo.prepare_dir(target, force=False)
    demo.prepare_dir(target, force=True)
    assert sorted(p.name for p in target.iterdir()) == [DEMO_MARKER]


def test_seed_without_pdf_engine_skips_the_cvs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(demo, "_pdf_engine", lambda: (None, None))
    summary = demo.seed(tmp_path / "data-demo", now=NOW)
    assert summary.cvs == 0
    assert summary.by_stage[Stage.APPROVED] == 5  # las dos del CV se quedan aprobadas
    assert len(summary.warnings) == 2
    assert "LibreOffice" in summary.warnings[0]


def test_cli_demo_seed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(demo, "_pdf_engine", lambda: (None, None))
    target = tmp_path / "data-demo"
    result = runner.invoke(cli.app, ["demo", "seed", "--dir", str(target)])
    assert result.exit_code == 0, result.output
    assert "60 ofertas" in result.stdout
    assert "JH_DATA_DIR" in result.stdout

    again = runner.invoke(cli.app, ["demo", "seed", "--dir", str(target), "--json"])
    assert again.exit_code == 1
    error = json.loads(again.stdout)["error"]
    assert error["type"] == "validation_error"
    assert "--force" in error["message"]
