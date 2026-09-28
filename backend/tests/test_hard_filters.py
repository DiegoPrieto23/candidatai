"""Filtros duros con el perfil y las ofertas de `demo/`."""

import pytest

from app.core.policies import HardFilterPolicy, get_policies
from app.services.matching.hard_filters import evaluate, language_code, language_rank
from tests.matching_support import demo_extraction, demo_profile

TITLE = "Data Engineer (m/f/d)"


def policy(**changes: object) -> HardFilterPolicy:
    return get_policies().hard_filters.model_copy(update=changes)


def failures(ext=None, profile=None, pol=None, title: str = TITLE) -> dict[str, str]:
    result = evaluate(title, ext or demo_extraction(), profile or demo_profile(), pol or policy())
    assert result.passed == (not result.failures)
    return {f.filter: f.reason for f in result.failures}


def test_demo_jobs_pass_with_demo_profile() -> None:
    assert failures() == {}
    assert failures(demo_extraction("02-analytics-engineer"), title="Analytics Engineer") == {}


def test_all_failures_are_reported_together() -> None:
    ext = demo_extraction(
        seniority="lead",
        years_experience_min=10,
        remote_mode="onsite",
        locations=["Sevilla"],
        languages_required=[{"language": "Deutsch", "level": "C1"}],
    )
    got = failures(ext, pol=policy(discard_title_keywords=["sales"]), title="Sales Lead")
    assert set(got) == {
        "seniority",
        "years",
        "remote_mode",
        "location",
        "language",
        "title_keyword",
    }


# --- Seniority -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("seniority", "passes"),
    [
        ("intern", False),
        ("junior", True),
        ("mid", True),
        ("senior", False),
        ("lead", False),
        ("unknown", True),
    ],
)
def test_seniority_only_accepted_levels(seniority: str, passes: bool) -> None:
    got = failures(demo_extraction(seniority=seniority))  # el perfil de demo acepta junior y mid
    assert ("seniority" not in got) is passes


@pytest.mark.parametrize(
    ("accepted", "seniority", "reason"),
    [
        # Busca un puesto intermedio o senior y no quiere junior.
        (["senior", "mid"], "junior", "Pide seniority junior; solo aceptas: intermedio, senior."),
        # Primer empleo: no quiere puestos de más nivel.
        (
            ["intern", "junior"],
            "mid",
            "Pide seniority intermedio; solo aceptas: prácticas, junior.",
        ),
        (["intern", "junior"], "junior", None),
        (["mid", "lead"], "senior", "Pide seniority senior; solo aceptas: intermedio, lead."),
    ],
)
def test_seniority_follows_the_profile_in_both_directions(
    accepted: list[str], seniority: str, reason: str | None
) -> None:
    got = failures(demo_extraction(seniority=seniority), demo_profile(seniority_target=accepted))
    assert got.get("seniority") == reason


# --- Años ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(("years", "passes"), [(None, True), (0, True), (5, True), (6, False)])
def test_years_with_tolerance(years: int | None, passes: bool) -> None:
    got = failures(demo_extraction(years_experience_min=years))  # máximo 4 + 1 de tolerancia
    assert ("years" not in got) is passes


def test_years_without_limit_in_profile() -> None:
    profile = demo_profile(max_years_required=None)
    assert "years" not in failures(demo_extraction(years_experience_min=15), profile)


def test_years_reason() -> None:
    got = failures(demo_extraction(years_experience_min=8))
    assert got["years"] == "Pide 8 años de experiencia; tu máximo es 4 (+1 de tolerancia)."


# --- Modalidad -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "passes"), [("remote", True), ("hybrid", True), ("onsite", False), ("unknown", True)]
)
def test_remote_mode(mode: str, passes: bool) -> None:
    got = failures(demo_extraction(remote_mode=mode))
    assert ("remote_mode" not in got) is passes


def test_unknown_remote_mode_can_be_required() -> None:
    got = failures(
        demo_extraction(remote_mode="unknown"), pol=policy(unknown_remote_mode_passes=False)
    )
    assert got["remote_mode"] == "La oferta no dice la modalidad y la política exige conocerla."


def test_remote_mode_reason_in_spanish() -> None:
    got = failures(demo_extraction(remote_mode="onsite"))
    assert got["remote_mode"] == "Modalidad presencial; aceptas: remoto, híbrido."


# --- Ubicación -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("locations", "mode", "passes"),
    [
        (["Vigo"], "onsite", True),  # preferida: vale presencial (falla la modalidad, no la zona)
        (["Santiago de Compostela, A Coruña"], "hybrid", True),  # por palabras completas
        (["SANTIAGO DE COMPOSTELA"], "hybrid", True),  # sin mayúsculas ni tildes
        (["Madrid"], "hybrid", True),  # permitida en híbrido
        (["Madrid"], "onsite", False),  # permitida, pero no presencial
        (["Madrid"], "unknown", True),  # modalidad desconocida: pasa según la política
        (["Sevilla"], "hybrid", False),  # fuera de zona
        (["Sevilla"], "remote", True),  # remota: la zona no importa
        (["Sevilla", "Vigo"], "hybrid", True),  # basta con una
        ([], "onsite", True),  # sin ubicación: no se descarta
        (["Vigoña"], "hybrid", False),  # «Vigo» no casa dentro de otra palabra
    ],
)
def test_location(locations: list[str], mode: str, passes: bool) -> None:
    got = failures(demo_extraction(locations=locations, remote_mode=mode))
    assert ("location" not in got) is passes


def test_location_reasons() -> None:
    got = failures(demo_extraction(locations=["Madrid"], remote_mode="onsite"))
    assert got["location"] == "Madrid solo te vale en híbrido o remoto, y la oferta es presencial."
    got = failures(demo_extraction(locations=["Sevilla"], remote_mode="hybrid"))
    assert got["location"] == "Fuera de zona: Sevilla."


def test_excluded_location() -> None:
    profile = demo_profile(locations={"preferred": [], "allowed": [], "excluded": ["Barcelona"]})
    got = failures(demo_extraction(locations=["Barcelona"], remote_mode="hybrid"), profile)
    assert got["location"] == "Ubicación descartada: Barcelona."
    assert "location" not in failures(demo_extraction(locations=["Sevilla"]), profile)
    remote = demo_extraction(locations=["Barcelona"], remote_mode="remote")
    assert "location" not in failures(remote, profile)


def test_excluded_wins_over_preferred() -> None:
    zones = {"preferred": ["Galicia"], "allowed": [], "excluded": ["Ourense"]}
    got = failures(demo_extraction(locations=["Ourense, Galicia"]), demo_profile(locations=zones))
    assert "location" in got


# --- Idiomas -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("required", "passes"),
    [
        ([{"language": "Inglés", "level": "B2"}], True),
        ([{"language": "English", "level": "C1"}], False),  # el perfil tiene B2
        ([{"language": "english", "level": "fluent"}], False),  # fluent ~ C1
        ([{"language": "Inglés", "level": "intermedio"}], True),
        ([{"language": "Inglés", "level": None}], True),
        ([{"language": "Español", "level": "nativo"}], True),
        ([{"language": "Gallego", "level": "C2"}], True),  # nativo >= C2
        ([{"language": "Alemán", "level": None}], False),  # no está en el perfil
        ([{"language": "Klingon", "level": "C2"}], True),  # desconocido: no descarta
        ([{"language": "Inglés", "level": "nivel alto"}], False),  # «alto» ~ C1; el perfil, B2
    ],
)
def test_languages(required: list[dict[str, str | None]], passes: bool) -> None:
    got = failures(demo_extraction(languages_required=required))
    assert ("language" not in got) is passes


def test_language_reason() -> None:
    required = [{"language": "English", "level": "C1"}, {"language": "Deutsch", "level": None}]
    got = failures(demo_extraction(languages_required=required))
    assert got["language"] == (
        "Idiomas: pide English C1 y tienes B2; pide Deutsch y no está en tu perfil."
    )


def test_languages_for_work_count_as_known() -> None:
    profile = demo_profile(languages_for_work=["es", "en", "fr"])
    got = failures(
        demo_extraction(languages_required=[{"language": "French", "level": "B2"}]), profile
    )
    assert "language" not in got  # en `languages_for_work` pero sin nivel en `languages`


@pytest.mark.parametrize(
    ("name", "code"),
    [("Inglés", "en"), ("ENGLISH", "en"), ("en", "en"), ("Castellano", "es"), ("Euskera", "eu"),
     ("Galego", "gl"), ("Klingon", None)],
)  # fmt: skip
def test_language_code(name: str, code: str | None) -> None:
    assert language_code(name) == code


@pytest.mark.parametrize(
    ("level", "rank"),
    [("B2", 4), ("c1 (Cambridge)", 5), ("Nativo", 7), ("bilingüe", 7), ("Advanced", 5),
     ("básico", 2), ("", None), (None, None), ("se valorará", None)],
)  # fmt: skip
def test_language_rank(level: str | None, rank: int | None) -> None:
    assert language_rank(level) == rank


# --- Palabras de descarte ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "passes"),
    [
        ("Sales Engineer", False),
        ("Comercial de datos", False),
        ("Becario de Prácticas", False),  # sin tildes ni mayúsculas
        ("Data Engineer", True),
        ("Wholesales Analyst", True),  # palabra completa, no subcadena
    ],
)
def test_title_keywords(title: str, passes: bool) -> None:
    pol = policy(discard_title_keywords=["sales", "comercial", "prácticas"])
    got = failures(demo_extraction(title_normalized="Data Engineer"), pol=pol, title=title)
    assert ("title_keyword" not in got) is passes


def test_title_keywords_also_checked_in_normalized_title() -> None:
    pol = policy(discard_title_keywords=["sales"])
    got = failures(demo_extraction(title_normalized="Sales Engineer"), pol=pol, title="Engineer")
    assert got["title_keyword"] == "El título contiene palabras de descarte: sales."
