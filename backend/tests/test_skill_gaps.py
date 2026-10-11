"""Huecos de skills (fase 14): agregación, marcas y «es lo mismo que…» con recálculo del score."""

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from sqlalchemy import delete, select, update

from app.core import migrations, policies
from app.core.db import session_scope
from app.models import Event, Task
from app.models.base import utcnow
from app.services import events, profile, skill_aliases, skill_gaps, worker
from app.services.matching import service as matching
from app.services.pipeline import Actor, EventType
from tests.skills_support import add_job, import_demo_profile, use_aliases_copy


@pytest.fixture(autouse=True)
def db(isolated_env: Path) -> Iterator[None]:
    migrations.upgrade()
    yield


@pytest.fixture(autouse=True)
def aliases_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return use_aliases_copy(tmp_path, monkeypatch)


def record(job_id: int, type: EventType, **payload: Any) -> None:
    with session_scope() as session:
        events.record(session, job_id, type, Actor.USER, payload=payload or None)


def gaps(**kwargs: Any) -> dict[str, skill_gaps.SkillGap]:
    with session_scope() as session:
        view = skill_gaps.get_skill_gaps(session, **kwargs)
    return {g.key: g for g in view.gaps}


# --- Agregación ----------------------------------------------------------------------------------


def test_aggregates_missing_skills_by_kind_with_frequency_and_examples() -> None:
    import_demo_profile()
    a = add_job(["Python", "Kafka", "Data Warehousing"], ["Terraform"])
    b = add_job(["kafka"], ["Data warehousing", "Kafka"])  # repetida en las dos: obligatoria
    add_job(["SQL"], ["Terraform", "Python"])

    result = gaps()
    assert set(result) == {"kafka", "data warehousing", "terraform"}  # Python y SQL, cubiertas
    kafka = result["kafka"]
    assert (kafka.must_have_count, kafka.nice_to_have_count, kafka.jobs_count) == (2, 0, 2)
    assert kafka.skill in {"Kafka", "kafka"}
    assert {e.job_id for e in kafka.examples} == {a, b}
    dwh = result["data warehousing"]
    assert (dwh.must_have_count, dwh.nice_to_have_count) == (1, 1)
    terraform = result["terraform"]
    assert (terraform.must_have_count, terraform.nice_to_have_count) == (0, 2)
    # Sin score todavía cuentan como 50: obligatoria 1,0 × 0,5; deseable 0,5 × 0,5.
    assert kafka.weight == pytest.approx(1.0)
    assert dwh.weight == pytest.approx(0.75)
    assert terraform.weight == pytest.approx(0.5)
    # De más a menos ofertas y, a igualdad, por peso.
    with session_scope() as session:
        keys = [g.key for g in skill_gaps.get_skill_gaps(session).gaps]
    assert keys == ["kafka", "data warehousing", "terraform"]


def test_weight_uses_the_job_score() -> None:
    import_demo_profile()
    strong = add_job(["Python", "SQL", "Snowflake", "Kafka"])
    weak = add_job(["Kafka", "Rust", "Go", "Scala"])
    worker.run_pending()
    with session_scope() as session:
        scores = matching.latest_scores(session, [strong, weak])
    kafka = gaps()["kafka"]
    assert kafka.weight == pytest.approx((scores[strong] + scores[weak]) / 100, abs=0.01)
    assert [e.job_id for e in kafka.examples] == sorted([strong, weak], key=lambda j: -scores[j])


def test_aliases_and_profile_levels_hide_vocabulary() -> None:
    import_demo_profile()
    add_job(["PySpark", "T-SQL", "Airflow", "Docker"])  # Spark no está en el perfil de demo
    result = gaps()
    assert set(result) == {"apache spark"}  # T-SQL → SQL; Airflow y Docker, básicos
    assert result["apache spark"].skill == "PySpark"


def test_job_window_open_and_recent_approved_or_applied() -> None:
    import_demo_profile()
    open_job = add_job(["Kafka"])
    discarded = add_job(["Rust"])
    record(discarded, EventType.DISCARDED, reason="skills")
    recent = add_job(["Go"])
    record(recent, EventType.APPROVED)
    record(recent, EventType.REJECTED)
    old = add_job(["Scala"])
    record(old, EventType.APPROVED)
    record(old, EventType.REJECTED)
    with session_scope() as session:
        session.execute(
            update(Event)
            .where(Event.job_id == old, Event.type == EventType.APPROVED.value)
            .values(occurred_at=utcnow() - timedelta(days=100))
        )

    assert set(gaps()) == {"kafka", "go"}
    assert set(gaps(days=120)) == {"kafka", "go", "scala"}
    with session_scope() as session:
        assert skill_gaps.get_skill_gaps(session).jobs_considered == 2
    assert open_job


def test_without_profile_raises() -> None:
    add_job(["Kafka"])
    with session_scope() as session, pytest.raises(profile.ProfileNotFoundError):
        skill_gaps.get_skill_gaps(session)


# --- Marcas --------------------------------------------------------------------------------------


def test_marks_filter_and_persist() -> None:
    import_demo_profile()
    add_job(["Kafka", "Rust", "Go"])
    with session_scope() as session:
        skill_gaps.set_mark(session, "kafka", "gap")
        skill_gaps.set_mark(session, "Rust", "have")
        skill_gaps.set_mark(session, "Rust", "gap")
        skill_gaps.set_mark(session, "Rust", "have")
        skill_gaps.set_mark(session, "Terraform", "gap")  # ya no la pide nadie: sale igual
        skill_gaps.set_mark(session, "Python", "gap")  # el perfil la cubre: no sale

    all_gaps = gaps()
    assert all_gaps["kafka"].mark == "gap"
    assert all_gaps["rust"].mark == "have"
    assert all_gaps["go"].mark is None
    assert all_gaps["terraform"].jobs_count == 0
    assert "python" not in all_gaps
    assert set(gaps(status="gap")) == {"kafka", "terraform"}
    assert set(gaps(status="have")) == {"rust"}
    assert set(gaps(status="unmarked")) == {"go"}

    with session_scope() as session:
        skill_gaps.set_mark(session, "Kafka", None)
    assert gaps()["kafka"].mark is None


def test_marks_survive_when_their_jobs_leave_the_window() -> None:
    """«La tengo» sigue visible para el agente aunque sus ofertas salgan del periodo."""
    import_demo_profile()
    old = add_job(["Kafka", "Rust", "Go"])
    record(old, EventType.DISCARDED, reason="skills")
    with session_scope() as session:
        skill_gaps.set_mark(session, "Kafka", "have")
        skill_gaps.set_mark(session, "Rust", "gap")
    result = gaps(days=1)
    assert {k: (g.mark, g.jobs_count) for k, g in result.items()} == {
        "kafka": ("have", 0),
        "rust": ("gap", 0),
    }
    assert set(gaps(status="have")) == {"kafka"}


def test_mark_is_stored_by_canonical_form() -> None:
    import_demo_profile()
    add_job(["PySpark"])
    with session_scope() as session:
        result = skill_gaps.set_mark(session, "spark", "gap")
    assert result.key == "apache spark"
    assert gaps()["apache spark"].mark == "gap"


# --- «Es lo mismo que…» --------------------------------------------------------------------------


def test_add_alias_keeps_comments_and_order(aliases_file: Path) -> None:
    import_demo_profile()
    before_bytes = aliases_file.read_bytes()
    with session_scope() as session:
        added = skill_aliases.add_alias(session, "Data Warehousing", "Snowflake")
        created = skill_aliases.add_alias(session, "Modelado semántico", "Modelado dimensional")
    assert (added.canonical, added.added, added.rescore_queued) == ("Snowflake", True, True)
    assert created.canonical == "Modelado de datos"  # «Modelado dimensional» ya era sinónimo

    after = aliases_file.read_bytes().decode("utf-8")
    before = before_bytes.decode("utf-8")
    old_lines = before.splitlines()
    new_lines = after.splitlines()
    assert len(new_lines) == len(old_lines)  # nada se reparte ni se reordena
    changed = [(o, n) for o, n in zip(old_lines, new_lines, strict=True) if o != n]
    assert [o.split(":")[0] for o, _ in changed] == ["Snowflake", "Modelado de datos"]
    assert new_lines[0].startswith("# Sinónimos")  # el comentario sigue
    assert "Snowflake: [snowflake db, Data Warehousing]" in after
    assert after.count("\r\n") == before.count("\r\n")
    # Las demás líneas, idénticas (comillas incluidas).
    assert 'Python: [python3, "python 3"]' in after

    data = yaml.safe_load(after)
    assert list(data) == list(yaml.safe_load(before))
    assert policies.get_skill_aliases()["Snowflake"] == ["snowflake db", "Data Warehousing"]


def test_add_alias_creates_entry_for_profile_skill(aliases_file: Path) -> None:
    import_demo_profile()
    with session_scope() as session:
        result = skill_aliases.add_alias(session, "Time series", "series temporales")
    assert (result.canonical, result.profile_skill) == ("Series temporales", "Series temporales")
    last = aliases_file.read_text(encoding="utf-8").splitlines()[-1]
    assert last == "Series temporales: [Time series]"


def test_add_alias_round_trip_without_changes_is_identical(aliases_file: Path) -> None:
    """Cargar y volcar con ruamel deja el fichero byte a byte igual."""
    before = aliases_file.read_bytes()
    yaml_rt = skill_aliases._round_trip_yaml()
    data, newline = skill_aliases._load(aliases_file, yaml_rt)
    skill_aliases._write(aliases_file, data, yaml_rt, newline)
    assert aliases_file.read_bytes() == before


def test_add_alias_already_same_does_nothing(aliases_file: Path) -> None:
    import_demo_profile()
    with session_scope() as session:
        session.execute(delete(Task))  # el `rescore_all` de importar el perfil
    before = aliases_file.read_bytes()
    with session_scope() as session:
        result = skill_aliases.add_alias(session, "pl/sql", "SQL")
        queued = session.scalars(select(Task).where(Task.kind == "rescore_all")).all()
    assert (result.added, result.rescore_queued) == (False, False)
    assert aliases_file.read_bytes() == before
    assert queued == []


@pytest.mark.parametrize(
    ("alias", "target", "message"),
    [
        ("Spark", "Python", "ya es sinónimo de «Apache Spark»"),
        ("Databricks", "Python", "ya es sinónimo de «Databricks»"),
        ("DAX", "Power BI", "ya la cubre tu perfil como «DAX»"),
        ("Kafka", "Kubernetes", "no está entre las skills de tu perfil"),
        ("  ", "Python", "no puede quedar vacía"),
    ],
)
def test_add_alias_rejects_conflicts(
    aliases_file: Path, alias: str, target: str, message: str
) -> None:
    import_demo_profile()
    before = aliases_file.read_bytes()
    with session_scope() as session, pytest.raises(ValueError, match=message):
        skill_aliases.add_alias(session, alias, target)
    assert aliases_file.read_bytes() == before


def test_add_alias_rescores_and_changes_the_score() -> None:
    """Criterio de aceptación: el alias cambia el `scoring_key`, el worker recalcula y el score
    de las ofertas afectadas sube; el hueco desaparece al momento."""
    import_demo_profile()
    affected = add_job(["Python", "SQL", "Data Warehousing"])
    other = add_job(["Python", "SQL", "Kafka"])
    worker.run_pending()
    with session_scope() as session:
        before = matching.latest_scores(session, [affected, other])
        key_before = matching.scoring_key()
    assert "data warehousing" in gaps()

    with session_scope() as session:
        skill_aliases.add_alias(session, "Data Warehousing", "Snowflake")
    assert "data warehousing" not in gaps()
    assert matching.scoring_key() != key_before
    run = worker.run_pending()
    assert "rescore_all" in [o.kind for o in run.outcomes]

    with session_scope() as session:
        after = matching.latest_scores(session, [affected, other])
        view = matching.get_match(session, affected)
    assert after[affected] > before[affected]
    assert after[other] == before[other]
    assert view.breakdown.must_have.missing == []
    covered = {c.skill: c.profile_skill for c in view.breakdown.must_have.covered}
    assert covered["Data Warehousing"] == "Snowflake"
