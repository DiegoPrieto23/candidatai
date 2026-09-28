"""Filtros duros: lo que descarta una oferta sin mirar el encaje técnico.

Parámetros en `data/profile.yaml` → `preferences` (niveles aceptados, años, modalidad, ubicaciones e
idiomas) y en `config/policies.yaml` → `hard_filters` (tolerancias y palabras de descarte). Lo que
la oferta no dice (`unknown`, `null`, listas vacías) no descarta, salvo la modalidad si la política
lo pide. Funciones puras: sin BD ni red.
"""

import re
from typing import Literal

from pydantic import BaseModel

from app.core.policies import HardFilterPolicy
from app.schemas.llm_io import JobExtraction
from app.schemas.profile import CandidateProfile
from app.services.normalize import fold

FilterName = Literal["seniority", "years", "remote_mode", "location", "language", "title_keyword"]

SENIORITY_ORDER = ("intern", "junior", "mid", "senior", "lead")
SENIORITY_LABEL = {
    "intern": "prácticas",
    "junior": "junior",
    "mid": "intermedio",
    "senior": "senior",
    "lead": "lead",
}
REMOTE_LABEL = {"onsite": "presencial", "hybrid": "híbrido", "remote": "remoto"}

# Nombres de idioma (ya plegados: sin tildes, en minúsculas) -> código ISO 639-1.
LANGUAGE_NAMES: dict[str, tuple[str, ...]] = {
    "es": ("espanol", "castellano", "spanish"),
    "en": ("ingles", "english"),
    "fr": ("frances", "french", "francais"),
    "de": ("aleman", "german", "deutsch"),
    "pt": ("portugues", "portuguese"),
    "it": ("italiano", "italian"),
    "gl": ("gallego", "galego", "galician"),
    "ca": ("catalan", "catala", "valenciano"),
    "eu": ("euskera", "euskara", "basque", "vasco"),
    "nl": ("neerlandes", "holandes", "dutch"),
}
_CODE_BY_NAME = {name: code for code, names in LANGUAGE_NAMES.items() for name in (code, *names)}

_CEFR = {"a1": 1, "a2": 2, "b1": 3, "b2": 4, "c1": 5, "c2": 6}
NATIVE = 7
_LEVEL_WORDS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"\b(nativo|nativa|native|bilingue|bilingual|lengua materna|mother tongue)\b"), 7),
    (re.compile(r"\b(avanzado|alto|advanced|fluent|fluido|proficient)\b"), 5),
    (re.compile(r"\b(intermedio|medio|intermediate)\b"), 3),
    (re.compile(r"\b(basico|basic|elemental|elementary)\b"), 2),
)
_LEVEL_NAME = {**{rank: code.upper() for code, rank in _CEFR.items()}, NATIVE: "nativo"}


class FilterFailure(BaseModel):
    filter: FilterName
    reason: str  # en español, para la UI y el agente


class HardFilterResult(BaseModel):
    passed: bool
    failures: list[FilterFailure]


def language_code(name: str) -> str | None:
    """«Inglés», «English», «en» -> «en». `None` si no se reconoce."""
    return _CODE_BY_NAME.get(fold(name))


def language_rank(level: str | None) -> int | None:
    """«B2» -> 4, «C1 (Cambridge)» -> 5, «Nativo» -> 7. `None` si no se entiende."""
    if not level:
        return None
    folded = fold(level)
    for token in folded.split():
        if token in _CEFR:
            return _CEFR[token]
    for pattern, rank in _LEVEL_WORDS:
        if pattern.search(folded):
            return rank
    return None


def location_matches(location: str, places: list[str]) -> bool:
    """Coincidencia por palabras completas, sin tildes: «Santiago de Compostela, A Coruña»
    encaja con «A Coruña» y con «Santiago de Compostela»."""
    haystack = f" {fold(location)} "
    return any(f" {fold(place)} " in haystack for place in places if fold(place))


def _seniority(ext: JobExtraction, profile: CandidateProfile) -> str | None:
    """Pasan solo los niveles que el candidato acepta (`seniority_target`), en las dos direcciones:
    quien busca un puesto intermedio puede no querer junior, y quien empieza, no querer senior."""
    accepted = profile.preferences.seniority_target
    if ext.seniority == "unknown" or ext.seniority in accepted:
        return None
    labels = ", ".join(SENIORITY_LABEL[s] for s in SENIORITY_ORDER if s in accepted)
    return f"Pide seniority {SENIORITY_LABEL[ext.seniority]}; solo aceptas: {labels}."


def _years(ext: JobExtraction, profile: CandidateProfile, policy: HardFilterPolicy) -> str | None:
    limit = profile.preferences.max_years_required
    if ext.years_experience_min is None or limit is None:
        return None
    if ext.years_experience_min > limit + policy.years_tolerance:
        return (
            f"Pide {ext.years_experience_min} años de experiencia; tu máximo es {limit} "
            f"(+{policy.years_tolerance} de tolerancia)."
        )
    return None


def _remote_mode(
    ext: JobExtraction, profile: CandidateProfile, policy: HardFilterPolicy
) -> str | None:
    wanted = profile.preferences.remote_modes
    if ext.remote_mode == "unknown":
        if policy.unknown_remote_mode_passes:
            return None
        return "La oferta no dice la modalidad y la política exige conocerla."
    if ext.remote_mode not in wanted:
        accepted = ", ".join(REMOTE_LABEL[m] for m in wanted)
        return f"Modalidad {REMOTE_LABEL[ext.remote_mode]}; aceptas: {accepted}."
    return None


def _location(
    ext: JobExtraction, profile: CandidateProfile, policy: HardFilterPolicy
) -> str | None:
    if ext.remote_mode == "remote" or not ext.locations:
        return None
    zones = profile.preferences.locations
    unrestricted = not zones.preferred and not zones.allowed
    # En una ubicación «permitida» hace falta que no sea presencial.
    flexible = ext.remote_mode == "hybrid" or (
        ext.remote_mode == "unknown" and policy.unknown_remote_mode_passes
    )
    for location in ext.locations:
        if location_matches(location, zones.excluded):
            continue
        if unrestricted or location_matches(location, zones.preferred):
            return None
        if flexible and location_matches(location, zones.allowed):
            return None
    shown = ", ".join(ext.locations)
    if any(location_matches(loc, zones.excluded) for loc in ext.locations):
        return f"Ubicación descartada: {shown}."
    if any(location_matches(loc, zones.allowed) for loc in ext.locations):
        return f"{shown} solo te vale en híbrido o remoto, y la oferta es presencial."
    return f"Fuera de zona: {shown}."


def _languages(
    ext: JobExtraction, profile: CandidateProfile, _policy: HardFilterPolicy
) -> str | None:
    known: dict[str, int | None] = {}
    for lang in profile.languages:
        code = language_code(lang.language)
        if code is not None:
            known[code] = language_rank(lang.level)
    for code in profile.preferences.languages_for_work:
        known.setdefault(code, None)
    problems: list[str] = []
    for req in ext.languages_required:
        code = language_code(req.language)
        if code is None:
            continue  # idioma que no sabemos interpretar: no descarta
        if code not in known:
            problems.append(f"pide {req.language} y no está en tu perfil")
            continue
        wanted, have = language_rank(req.level), known[code]
        if wanted is not None and have is not None and have < wanted:
            level, own = _LEVEL_NAME[wanted], _LEVEL_NAME[have]
            problems.append(f"pide {req.language} {level} y tienes {own}")
    if problems:
        return "Idiomas: " + "; ".join(problems) + "."
    return None


def _title_keywords(title: str, ext: JobExtraction, policy: HardFilterPolicy) -> str | None:
    titles = f" {fold(title)} | {fold(ext.title_normalized)} "
    hits = [k for k in policy.discard_title_keywords if fold(k) and f" {fold(k)} " in titles]
    if hits:
        return f"El título contiene palabras de descarte: {', '.join(hits)}."
    return None


def evaluate(
    title: str, ext: JobExtraction, profile: CandidateProfile, policy: HardFilterPolicy
) -> HardFilterResult:
    """Aplica todos los filtros y devuelve todos los fallos a la vez (no se para en el primero)."""
    checks: list[tuple[FilterName, str | None]] = [
        ("seniority", _seniority(ext, profile)),
        ("years", _years(ext, profile, policy)),
        ("remote_mode", _remote_mode(ext, profile, policy)),
        ("location", _location(ext, profile, policy)),
        ("language", _languages(ext, profile, policy)),
        ("title_keyword", _title_keywords(title, ext, policy)),
    ]
    failures = [FilterFailure(filter=name, reason=reason) for name, reason in checks if reason]
    return HardFilterResult(passed=not failures, failures=failures)
