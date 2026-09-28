"""Cobertura de skills, similitud semántica y score con el perfil y las ofertas de `demo/`."""

import pytest

from app.core.policies import get_policies, get_skill_aliases
from app.services.matching import embeddings, scorer, skills
from tests.matching_support import BrokenEmbedder, FakeEmbedder, demo_extraction, demo_profile

LEVELS = get_policies().scoring.level_weights
SCORING = get_policies().scoring
TITLE = "Data Engineer (m/f/d)"


def by_name(coverage: skills.SkillCoverage) -> dict[str, str]:
    return {c.skill: c.level for c in coverage.covered}


# --- Skills --------------------------------------------------------------------------------------


def test_levels_are_weighted() -> None:
    cov = skills.coverage(["Python", "Power BI", "DAX", "dbt", "Kafka"], demo_profile(), LEVELS)
    assert by_name(cov) == {"Python": "F", "Power BI": "C+", "DAX": "C", "dbt": "basic"}
    assert [c.weight for c in cov.covered] == [1.0, 0.8, 0.5, 0.2]
    assert cov.missing == ["Kafka"]
    assert cov.ratio == pytest.approx((1.0 + 0.8 + 0.5 + 0.2) / 5)


@pytest.mark.parametrize(
    ("job_skill", "profile_skill"),
    [
        ("python3", "Python"),
        ("T-SQL", "SQL"),
        ("tsql", "SQL"),
        ("PowerBI", "Power BI"),
        ("microsoft power bi", "Power BI"),
        ("Airflow", "Apache Airflow"),  # básico en el perfil de demo
        ("amazon web services", "AWS"),
        ("GenAI", "LLMs"),
        ("ELT", "ETL"),
        ("SNOWFLAKE", "Snowflake"),
        ("Modelado Dimensional", "Modelado dimensional"),
    ],
)
def test_aliases_and_case(job_skill: str, profile_skill: str) -> None:
    cov = skills.coverage([job_skill], demo_profile(), LEVELS)
    assert [c.profile_skill for c in cov.covered] == [profile_skill]


def test_alias_on_the_profile_side() -> None:
    data = demo_profile().model_dump()
    data["skills"].append({"name": "PySpark", "level": "C", "category": "Datos"})
    profile = type(demo_profile()).model_validate(data)
    cov = skills.coverage(["Apache Spark"], profile, LEVELS)
    assert [(c.profile_skill, c.level) for c in cov.covered] == [("PySpark", "C")]


def test_custom_aliases() -> None:
    aliases = {"SQL Server": ["ms sql", "mssql"], "Python": []}
    cov = skills.coverage(["MS SQL", "Python"], demo_profile(), LEVELS, aliases)
    assert cov.missing == ["MS SQL"]  # el perfil de demo no tiene SQL Server
    assert by_name(cov) == {"Python": "F"}


def test_repeated_skills_count_once() -> None:
    cov = skills.coverage(
        ["Python", "python", "Python 3", "Kafka", "kafka"], demo_profile(), LEVELS
    )
    assert by_name(cov) == {"Python": "F"}
    assert cov.missing == ["Kafka"]
    assert cov.ratio == pytest.approx(0.5)


def test_no_skills_means_no_ratio() -> None:
    assert skills.coverage([], demo_profile(), LEVELS).ratio is None


def test_symbols_are_kept() -> None:
    aliases = {"C++": [], "C#": []}
    data = demo_profile().model_dump()
    data["skills"].append({"name": "C#", "level": "B"})
    profile = type(demo_profile()).model_validate(data)
    cov = skills.coverage(["C++", "c#"], profile, LEVELS, aliases)
    assert by_name(cov) == {"c#": "B"}
    assert cov.missing == ["C++"]


def test_aliases_file_loads() -> None:
    aliases = get_skill_aliases()
    assert "pyspark" in aliases["Apache Spark"]
    assert aliases["Databricks"] == []


# --- Similitud semántica -------------------------------------------------------------------------


def test_texts_use_posting_language() -> None:
    profile = demo_profile()
    assert "Data Engineer with three years" in embeddings.profile_text(profile, "en")
    assert "Data Engineer con tres años" in embeddings.profile_text(profile, "es")
    assert "Migré 40 procesos ETL" in embeddings.profile_text(profile, "es")
    text = embeddings.job_text(demo_extraction())
    assert "Orquestar cargas diarias" in text and "Snowflake" in text and "retail" in text


@pytest.mark.parametrize(("raw", "scaled"), [(0.15, 0.0), (0.0, 0.0), (0.45, 0.5), (0.9, 1.0)])
def test_rescale(raw: float, scaled: float) -> None:
    assert embeddings.rescale(raw, SCORING.semantic) == pytest.approx(scaled)


def test_cosine() -> None:
    assert embeddings.cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert embeddings.cosine([1.0, 0.0], [0.0, 2.0]) == pytest.approx(0.0)
    assert embeddings.cosine([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_embedder_off_by_env() -> None:
    assert embeddings.get_embedder() is None  # los tests fijan JH_EMBEDDINGS=off
    assert embeddings.unavailable_reason() == (
        "Similitud semántica desactivada (JH_EMBEDDINGS=off)."
    )


def test_embedder_not_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("JH_EMBEDDINGS", "auto")
    get_settings.cache_clear()
    monkeypatch.setattr(embeddings, "is_installed", lambda: False)
    assert embeddings.get_embedder() is None
    assert "uv sync --extra matching" in (embeddings.unavailable_reason() or "")


def test_sentence_transformer_embedder_caches(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    calls: list[list[str]] = []

    class Model:
        def encode(self, texts, **_kwargs):
            calls.append(list(texts))
            return [[float(len(t)), 1.0] for t in texts]

    embedder = embeddings.SentenceTransformerEmbedder("x", tmp_path)
    monkeypatch.setattr(embedder, "_load", lambda: Model())
    assert embedder.encode(["ab", "abc"]) == [[2.0, 1.0], [3.0, 1.0]]
    assert embedder.encode(["abc", "abcd", "abc"]) == [[3.0, 1.0], [4.0, 1.0], [3.0, 1.0]]
    assert calls == [["ab", "abc"], ["abcd"]]  # lo ya codificado no se repite


# --- Score ---------------------------------------------------------------------------------------


def test_demo_job_01_breakdown_without_embeddings() -> None:
    result = scorer.score(TITLE, demo_extraction(), demo_profile(), SCORING, None)
    b = result.breakdown
    # Obligatorias: Python, SQL, Snowflake (F) y dbt (básico) -> (3 + 0.2) / 4.
    assert b.must_have.ratio == pytest.approx(0.8)
    # Deseables: Power BI (C+) y Docker (básico) -> (0.8 + 0.2) / 2.
    assert b.nice_to_have.ratio == pytest.approx(0.5)
    # Puesto: primero de la lista; híbrido: segundo de `remote_modes`; Santiago: preferida.
    assert (b.preferences.role, b.preferences.remote_mode, b.preferences.location) == (
        1.0,
        0.85,
        1.0,
    )
    assert b.preferences.role_match == "Data Engineer"
    assert b.semantic is None
    assert b.notes == ["Similitud semántica desactivada (JH_EMBEDDINGS=off)."]
    semantic = next(c for c in b.components if c.name == "semantic_similarity")
    assert (semantic.value, semantic.effective_weight, semantic.points) == (None, 0.0, 0.0)
    # Sin semántica, sus 0.30 se reparten: los demás pesos se dividen entre 0.70.
    expected = 100 * (0.45 * 0.8 + 0.15 * 0.95 + 0.10 * 0.5) / 0.70
    assert result.score == round(expected)
    assert sum(c.points for c in b.components) == pytest.approx(expected, abs=0.05)
    assert sum(c.effective_weight for c in b.components) == pytest.approx(1.0, abs=1e-3)


def test_demo_job_01_with_embeddings() -> None:
    embedder = FakeEmbedder()
    result = scorer.score(TITLE, demo_extraction(), demo_profile(), SCORING, embedder)
    semantic = result.breakdown.semantic
    assert semantic is not None and semantic.model == "fake-bow"
    assert 0.0 <= semantic.value <= 1.0
    assert result.breakdown.notes == []
    weights = {c.name: c.effective_weight for c in result.breakdown.components}
    assert weights == {
        "must_have_coverage": 0.45,
        "semantic_similarity": 0.3,
        "preferences_fit": 0.15,
        "nice_to_have_coverage": 0.1,
    }
    expected = 100 * (0.45 * 0.8 + 0.3 * semantic.value + 0.15 * 0.95 + 0.10 * 0.5)
    assert result.score == round(expected)


def test_embedder_failure_degrades_gracefully() -> None:
    result = scorer.score(TITLE, demo_extraction(), demo_profile(), SCORING, BrokenEmbedder())
    assert result.breakdown.semantic is None
    assert result.breakdown.notes == [
        "No se pudo calcular la similitud semántica (OSError: sin red para descargar el modelo)."
    ]


def test_demo_job_02_scores_lower_than_01() -> None:
    profile = demo_profile()
    one = scorer.score(TITLE, demo_extraction(), profile, SCORING, None)
    two = scorer.score(
        "Analytics Engineer", demo_extraction("02-analytics-engineer"), profile, SCORING, None
    )
    assert two.breakdown.preferences.role_match == "Analytics Engineer"
    assert two.breakdown.preferences.role == pytest.approx(0.85)  # segundo de la lista
    assert [s for s in two.breakdown.nice_to_have.missing] == ["BigQuery", "Estadística"]
    assert two.score < one.score


def test_job_without_skills_redistributes_weights() -> None:
    ext = demo_extraction(must_have_skills=[], nice_to_have_skills=[])
    result = scorer.score(TITLE, ext, demo_profile(), SCORING, None)
    assert result.score == round(100 * 0.95)  # solo cuentan las preferencias
    assert len(result.breakdown.notes) == 3


def test_unrelated_job_scores_low() -> None:
    ext = demo_extraction(
        title_normalized="Frontend Developer",
        remote_mode="onsite",
        locations=["Sevilla"],
        must_have_skills=["React", "TypeScript", "CSS"],
        nice_to_have_skills=["Figma"],
    )
    result = scorer.score("Frontend Developer", ext, demo_profile(), SCORING, None)
    assert result.score == 0
    assert result.breakdown.preferences.role_match is None


@pytest.mark.parametrize(
    ("mode", "locations", "remote_fit", "location_fit"),
    [
        ("remote", ["Sevilla"], 1.0, 1.0),
        ("hybrid", ["Madrid"], 0.85, 0.6),  # permitida
        ("onsite", ["Madrid"], 0.0, 0.0),  # permitida solo en híbrido o remoto
        ("unknown", [], 0.5, 0.5),
        ("hybrid", ["Sevilla"], 0.85, 0.0),
    ],
)
def test_preferences_fit(
    mode: str, locations: list[str], remote_fit: float, location_fit: float
) -> None:
    ext = demo_extraction(remote_mode=mode, locations=locations)
    fit = scorer.preferences_fit(TITLE, ext, demo_profile(), 60)
    assert (fit.remote_mode, fit.location) == (pytest.approx(remote_fit), location_fit)


def test_preferences_without_zone_constraints() -> None:
    zones = {"preferred": [], "allowed": [], "excluded": ["Sevilla"]}
    profile = demo_profile(locations=zones)
    ext = demo_extraction(remote_mode="onsite", locations=["Bilbao"])
    assert scorer.preferences_fit(TITLE, ext, profile, 60).location == 1.0
    ext = demo_extraction(remote_mode="onsite", locations=["Sevilla"])
    assert scorer.preferences_fit(TITLE, ext, profile, 60).location == 0.0


def test_role_priority_floor() -> None:
    others = ["Backend Developer", "QA Tester", "Product Manager", "UX Designer", "Sales Manager"]
    profile = demo_profile(roles=[*others, "Data Engineer"])
    fit = scorer.preferences_fit(TITLE, demo_extraction(), profile, 60)
    assert fit.role == pytest.approx(0.4)  # sexto de la lista: el mínimo


@pytest.mark.parametrize(
    ("title", "title_normalized", "role_match", "role"),
    [
        # Contiene «data» y «engineer», pero el puesto es otro: no cuenta como Data Engineer.
        ("Sales Engineer (Data Platform)", "Sales Engineer", None, 0.0),
        ("Ingeniero/a de datos (Data Engineer)", "Ingeniero de datos", "Data Engineer", 1.0),
        ("Senior Data Engineer", "Senior Data Engineer", "Data Engineer", 1.0),
        ("Data Engineer (GenAI)", "Data Engineer (GenAI)", "Data Engineer", 1.0),
        ("Data Engineering Lead", "Data Engineering Lead", "Data Engineer", pytest.approx(0.8966)),
        ("Analytics Engineer", "Analytics Engineer", "Analytics Engineer", pytest.approx(0.85)),
        ("Senior Data Scientist", "Senior Data Scientist", None, 0.0),
    ],
)
def test_role_needs_every_word_of_the_wanted_role(
    title: str, title_normalized: str, role_match: str | None, role: float
) -> None:
    ext = demo_extraction(title_normalized=title_normalized)
    fit = scorer.preferences_fit(title, ext, demo_profile(), 60)
    assert (fit.role_match, fit.role) == (role_match, role)


def test_gender_tags_do_not_match_roles() -> None:
    profile = demo_profile(roles=["D", "Data Engineer"])
    fit = scorer.preferences_fit("Data Engineer (m/f/d)", demo_extraction(), profile, 60)
    assert fit.role_match == "Data Engineer"
