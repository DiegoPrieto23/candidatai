"""Score de encaje 0-100: combinación ponderada según `config/policies.yaml` → `scoring`.

Componentes: cobertura de `must_have_skills`, similitud semántica, preferencias (puesto, modalidad y
zona) y cobertura de `nice_to_have_skills`. Un componente que no se puede calcular (la oferta no
lista skills de ese tipo, o no hay modelo de embeddings) no cuenta: su peso se reparte entre los
demás en proporción, y el desglose lo dice. Los filtros duros no cambian el score. Sin BD.
"""

import logging
from collections.abc import Iterable, Mapping
from typing import Literal

from pydantic import BaseModel
from rapidfuzz import fuzz

from app.core.policies import ScoringPolicy
from app.schemas.llm_io import JobExtraction
from app.schemas.profile import CandidateProfile
from app.services.matching import embeddings, skills
from app.services.matching.embeddings import Embedder, SemanticResult
from app.services.matching.hard_filters import location_matches
from app.services.normalize import normalize_title, title_segments

logger = logging.getLogger(__name__)

ComponentName = Literal[
    "must_have_coverage", "semantic_similarity", "preferences_fit", "nice_to_have_coverage"
]
# Cuánto baja cada preferencia por posición en su lista (la primera vale 1).
PRIORITY_STEP = 0.15
PRIORITY_MIN = 0.4
UNKNOWN_FIT = 0.5  # la oferta no lo dice
ALLOWED_LOCATION_FIT = 0.6  # zona permitida (solo en híbrido o remoto), por debajo de la preferida
WORD_MIN_SIMILARITY = 80  # fuzz.ratio para dar por presente una palabra del puesto buscado
SENIORITY_WORDS = frozenset({"intern", "trainee", "junior", "mid", "senior", "lead", "principal"})
# Súbela cuando cambie cómo se calcula el score: los matches con otra versión quedan desfasados.
SCORER_VERSION = 2


class ScoreComponent(BaseModel):
    name: ComponentName
    value: float | None  # 0-1; None si no se ha podido calcular (no cuenta)
    weight: float  # el de la política
    effective_weight: float  # tras repartir el peso de los que no cuentan
    points: float  # aportación al score (0-100)


class PreferencesFit(BaseModel):
    value: float
    role: float
    role_match: str | None  # el puesto de `preferences.roles` que más se parece al de la oferta
    remote_mode: float
    location: float


class ScoreBreakdown(BaseModel):
    components: list[ScoreComponent]
    must_have: skills.SkillCoverage
    nice_to_have: skills.SkillCoverage
    semantic: SemanticResult | None
    preferences: PreferencesFit
    notes: list[str]  # p. ej. por qué falta un componente


class ScoreResult(BaseModel):
    score: int
    breakdown: ScoreBreakdown


def _priority(index: int) -> float:
    return max(PRIORITY_MIN, 1 - PRIORITY_STEP * index)


def _without_seniority(segment: str) -> str:
    return " ".join(w for w in segment.split() if w not in SENIORITY_WORDS)


def role_similarity(segment: str, wanted: str) -> float:
    """0-100. Todas las palabras del puesto buscado deben estar en el segmento del título (con
    margen para variantes como «engineering»); si no, 0. Así «Sales Engineer» no pasa por «Data
    Engineer» solo por compartir «engineer», ni «Sales Engineer (Data Platform)» por contener
    «data» fuera del puesto."""
    words = segment.split()
    wanted_words = wanted.split()
    if not wanted_words or not all(
        any(fuzz.ratio(w, t) >= WORD_MIN_SIMILARITY for t in words) for w in wanted_words
    ):
        return 0.0
    return fuzz.token_sort_ratio(segment, wanted)


def preferences_fit(
    title: str, ext: JobExtraction, profile: CandidateProfile, role_min_similarity: int
) -> PreferencesFit:
    prefs = profile.preferences
    # Por segmentos (fuera y dentro de paréntesis…) y sin seniority, que ya miran los filtros duros.
    # `title_segments` quita «(m/f/d)» y similares: sus letras sueltas casarían con cualquier cosa.
    raw = [*title_segments(title), *title_segments(ext.title_normalized)]
    segments = {_without_seniority(s) for s in raw} - {""}
    role, role_match = 0.0, None
    for i, wanted in enumerate(prefs.roles):
        target = normalize_title(wanted)
        ratio = max((role_similarity(s, target) for s in segments), default=0.0)
        if ratio >= role_min_similarity and (value := _priority(i) * ratio / 100) > role:
            role, role_match = value, wanted

    if ext.remote_mode == "unknown":
        remote = UNKNOWN_FIT
    elif ext.remote_mode in prefs.remote_modes:
        remote = _priority(prefs.remote_modes.index(ext.remote_mode))
    else:
        remote = 0.0

    zones = prefs.locations
    places = [loc for loc in ext.locations if not location_matches(loc, zones.excluded)]
    if ext.remote_mode == "remote":
        location = 1.0
    elif not ext.locations:
        location = UNKNOWN_FIT
    elif not places:
        location = 0.0
    elif not (zones.preferred or zones.allowed) or any(
        location_matches(loc, zones.preferred) for loc in places
    ):
        location = 1.0
    elif ext.remote_mode != "onsite" and any(location_matches(p, zones.allowed) for p in places):
        location = ALLOWED_LOCATION_FIT
    else:
        location = 0.0

    return PreferencesFit(
        value=round((role + remote + location) / 3, 4),
        role=round(role, 4),
        role_match=role_match,
        remote_mode=remote,
        location=location,
    )


def _semantic(
    profile: CandidateProfile,
    ext: JobExtraction,
    embedder: Embedder | None,
    policy: ScoringPolicy,
    notes: list[str],
) -> SemanticResult | None:
    if embedder is None:
        notes.append(embeddings.unavailable_reason() or "Similitud semántica no disponible.")
        return None
    try:
        return embeddings.similarity(profile, ext, embedder, policy.semantic)
    except Exception as exc:  # p. ej. sin red la primera vez que se descarga el modelo
        logger.warning("No se pudo calcular la similitud semántica", exc_info=True)
        notes.append(f"No se pudo calcular la similitud semántica ({type(exc).__name__}: {exc}).")
        return None


def score(
    title: str,
    ext: JobExtraction,
    profile: CandidateProfile,
    policy: ScoringPolicy,
    embedder: Embedder | None,
    aliases: Mapping[str, Iterable[str]] | None = None,
) -> ScoreResult:
    notes: list[str] = []
    must = skills.coverage(ext.must_have_skills, profile, policy.level_weights, aliases)
    nice = skills.coverage(ext.nice_to_have_skills, profile, policy.level_weights, aliases)
    if must.ratio is None:
        notes.append("La oferta no lista skills obligatorias: la cobertura obligatoria no cuenta.")
    if nice.ratio is None:
        notes.append("La oferta no lista skills deseables: la cobertura deseable no cuenta.")
    semantic = _semantic(profile, ext, embedder, policy, notes)
    prefs = preferences_fit(title, ext, profile, policy.preferences.role_min_similarity)

    values: dict[ComponentName, float | None] = {
        "must_have_coverage": must.ratio,
        "semantic_similarity": semantic.value if semantic else None,
        "preferences_fit": prefs.value,
        "nice_to_have_coverage": nice.ratio,
    }
    weights = policy.weights.model_dump()
    active = sum(weights[name] for name, value in values.items() if value is not None)
    components: list[ScoreComponent] = []
    for name, value in values.items():
        effective = weights[name] / active if value is not None and active else 0.0
        components.append(
            ScoreComponent(
                name=name,
                value=None if value is None else round(value, 4),
                weight=weights[name],
                effective_weight=round(effective, 4),
                points=round(100 * effective * (value or 0.0), 2),
            )
        )
    total = sum(
        100 * (weights[name] / active) * value
        for name, value in values.items()
        if value is not None and active
    )
    return ScoreResult(
        score=max(0, min(100, round(total))),
        breakdown=ScoreBreakdown(
            components=components,
            must_have=must,
            nice_to_have=nice,
            semantic=semantic,
            preferences=prefs,
            notes=notes,
        ),
    )
