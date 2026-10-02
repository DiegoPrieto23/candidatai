"""Filtro previo de título y ubicación (`ingestion/prefilter.py`) con las preferencias demo:
roles Data Engineer, Analytics Engineer y Data Analyst; remoto o híbrido; preferidas A Coruña,
Santiago de Compostela y Vigo; permitida Madrid."""

import pytest

from app.core.policies import get_policies
from app.services.ingestion.prefilter import Prefilter, title_seniority
from tests.matching_support import demo_profile


def _prefilter(extra: list[str] | None = None, **preferences: object) -> Prefilter:
    return Prefilter(demo_profile(**preferences).preferences, extra or [])


@pytest.mark.parametrize(
    "title",
    [
        "Data Engineer",
        "Senior Data Engineer (m/f/d)",
        "Data Engineering Lead",
        "Ingeniero/a de datos (Data Engineer)",
        "Analytics Engineer - Growth",
    ],
)
def test_titles_that_pass(title: str) -> None:
    assert _prefilter().check(title, "Vigo", None).passed


@pytest.mark.parametrize("title", ["Account Executive", "Sales Engineer", "Office Manager"])
def test_titles_that_fail(title: str) -> None:
    verdict = _prefilter().check(title, "Vigo", None)
    assert not verdict.passed
    assert "preferences.roles" in (verdict.reason or "")


def test_extra_keywords_of_the_source_let_a_title_through() -> None:
    assert _prefilter(["ingeniero de datos"]).check("Ingeniero de Datos Sr.", "Vigo", None).passed


def test_discard_keywords_win(monkeypatch: pytest.MonkeyPatch) -> None:
    policy = get_policies().hard_filters
    monkeypatch.setattr(policy, "discard_title_keywords", ["prácticas"])
    verdict = _prefilter().check("Data Engineer en prácticas", "Vigo", None)
    assert not verdict.passed and "prácticas" in (verdict.reason or "")


@pytest.mark.parametrize(
    ("location", "remote", "passed"),
    [
        ("Vigo, Spain", None, True),
        ("Madrid", None, True),  # permitida (la modalidad aún no se sabe)
        ("Berlin, Germany", None, False),
        ("Berlin, Germany", True, True),  # remota y el candidato acepta remoto
        ("Remote - Spain", None, True),
        ("Remoto", None, True),
        (None, None, True),  # sin ubicación: pasa
        ("", None, True),
    ],
)
def test_locations(location: str | None, remote: bool | None, passed: bool) -> None:
    assert _prefilter().check("Data Engineer", location, remote).passed is passed


def test_excluded_location_and_no_remote_preference() -> None:
    prefilter = _prefilter(
        remote_modes=["onsite", "hybrid"],
        locations={"preferred": [], "allowed": [], "excluded": ["Barcelona"]},
    )
    verdict = prefilter.check("Data Engineer", "Barcelona", None)
    assert not verdict.passed and "descartada" in (verdict.reason or "")
    assert not prefilter.check("Data Engineer", "Remote - Barcelona", True).passed
    assert prefilter.check("Data Engineer", "Berlin", None).passed  # sin zonas: cualquiera


def test_without_profile_everything_passes() -> None:
    prefilter = Prefilter(None, [])
    assert not prefilter.active
    assert prefilter.check("Account Executive", "Berlin", None).passed


@pytest.mark.parametrize(
    ("title", "level"),
    [
        ("Senior Data Engineer", "senior"),
        ("Data Engineer Sr.", "senior"),
        ("Jr. Data Analyst", "junior"),
        ("Becario/a Data (Prácticas)", "intern"),
        ("Lead Data Engineer", "lead"),
        ("Head of Data", "lead"),
        ("Data Engineer", None),
        ("Leading data platform engineer", None),
    ],
)
def test_title_seniority(title: str, level: str | None) -> None:
    assert title_seniority(title) == level


def test_summary_check_adds_title_seniority() -> None:
    # Perfil demo: acepta junior y mid.
    prefilter = _prefilter()
    assert prefilter.check_summary("Junior Data Engineer", "Vigo").passed
    assert prefilter.check_summary("Data Engineer", "Vigo").passed
    verdict = prefilter.check_summary("Senior Data Engineer", "Vigo")
    assert not verdict.passed
    assert "seniority senior" in (verdict.reason or "")
    assert not prefilter.check_summary("Office Manager", "Vigo").passed


def test_summary_check_without_profile_passes() -> None:
    assert Prefilter(None, []).check_summary("Senior Office Manager", "Marte").passed
