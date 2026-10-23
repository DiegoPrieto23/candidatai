"""Filtros duros: lo que descarta una oferta sin mirar el encaje técnico.

Parámetros en `data/profile.yaml` → `preferences` (niveles aceptados, años, modalidad, ubicaciones,
idiomas, palabras de descarte, contrato, jornada y tipo de empresa), → `private.salary_floor_eur`
(sueldo mínimo) y en `config/policies.yaml` → `hard_filters` (tolerancias y más palabras de
descarte). Lo que la oferta no dice (`unknown`, `null`, listas vacías) no descarta, salvo la
modalidad si la política lo pide. Funciones puras: sin BD ni red.

El sueldo mínimo es privado (ADR-046): su motivo no lleva cifras, porque el agente lo lee en
`get_match`.
"""

import re
from typing import Literal

from pydantic import BaseModel

from app.core.policies import HardFilterPolicy
from app.schemas.llm_io import JobExtraction, Salary
from app.schemas.profile import SALARY_FLOOR_KEY, CandidateProfile
from app.services.normalize import fold

FilterName = Literal[
    "seniority",
    "years",
    "remote_mode",
    "location",
    "language",
    "title_keyword",
    "signal",
    "salary",
    "contract",
    "employer_kind",
]

SENIORITY_ORDER = ("intern", "junior", "mid", "senior", "lead")
SENIORITY_LABEL = {
    "intern": "prácticas",
    "junior": "junior",
    "mid": "intermedio",
    "senior": "senior",
    "lead": "lead",
}
REMOTE_LABEL = {"onsite": "presencial", "hybrid": "híbrido", "remote": "remoto"}
CONTRACT_LABEL = {"permanent": "indefinido", "fixed_term": "temporal", "freelance": "autónomo"}
EMPLOYMENT_LABEL = {
    "full_time": "jornada completa",
    "part_time": "jornada parcial",
    "internship": "prácticas",
}
EMPLOYER_LABEL = {"consultancy": "una consultora", "agency": "una agencia de selección o ETT"}
SALARY_REASON = "El sueldo publicado está por debajo de tu mínimo salarial."
MONTHS_PER_YEAR = 12  # un sueldo mensual se pasa a anual ×12, no ×14 (ADR-046)
SALARY_CURRENCY = "EUR"

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
    asked = ext.years_experience_min
    if asked is None:
        return None
    high, low = profile.preferences.max_years_required, profile.preferences.min_years_required
    if high is not None and asked > high + policy.years_tolerance:
        return (
            f"Pide {asked} años de experiencia; tu máximo es {high} "
            f"(+{policy.years_tolerance} de tolerancia)."
        )
    if low is not None and asked < low - policy.years_tolerance:
        return (
            f"Pide {asked} años de experiencia; tu mínimo es {low} "
            f"(−{policy.years_tolerance} de tolerancia)."
        )
    return None


def published_annual(salary: Salary | None) -> tuple[int | None, int | None]:
    """Mínimo y máximo publicados, en bruto anual (mensual ×12). Por horas o sin periodo: nada."""
    if salary is None or salary.period not in ("year", "month"):
        return None, None
    factor = MONTHS_PER_YEAR if salary.period == "month" else 1
    low = salary.min * factor if salary.min is not None else None
    high = salary.max * factor if salary.max is not None else None
    return low, high


def salary_floor(profile: CandidateProfile) -> int | None:
    """`private.salary_floor_eur`, o `None` si no está (el esquema ya valida que sea > 0)."""
    value = profile.private.get(SALARY_FLOOR_KEY)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def salary_gap(ext: JobExtraction, floor: int | None) -> int | None:
    """Cuánto queda el tope publicado (anual, en EUR) por debajo del mínimo; `None` si no se puede
    comparar o no queda por debajo. Solo para la UI: la cifra nunca sale hacia el agente."""
    salary = ext.salary
    if floor is None or salary is None or (salary.currency or "").upper() != SALARY_CURRENCY:
        return None
    low, high = published_annual(salary)
    top = high if high is not None else low
    if top is None or top >= floor:
        return None
    return floor - top


def _salary(ext: JobExtraction, profile: CandidateProfile) -> str | None:
    return SALARY_REASON if salary_gap(ext, salary_floor(profile)) is not None else None


def accepted_contracts(profile: CandidateProfile) -> list[str]:
    """`contract_types`, sin `fixed_term` si `exclude_signals` lo excluye (es lo mismo). Vacía =
    cualquiera."""
    prefs = profile.preferences
    if "fixed_term" not in prefs.exclude_signals:
        return list(prefs.contract_types)
    return [c for c in (prefs.contract_types or CONTRACT_LABEL) if c != "fixed_term"]


def _contract(ext: JobExtraction, profile: CandidateProfile) -> str | None:
    problems: list[str] = []
    contracts = accepted_contracts(profile)
    kind = ext.contract_type
    if contracts and kind in CONTRACT_LABEL and kind not in contracts:
        accepted = ", ".join(CONTRACT_LABEL[c] for c in CONTRACT_LABEL if c in contracts)
        problems.append(f"contrato {CONTRACT_LABEL[kind]} (aceptas: {accepted})")
    shifts = profile.preferences.employment_types
    work = ext.employment_type  # `contract` no dice la jornada: pasa, como `unknown`
    if shifts and work in EMPLOYMENT_LABEL and work not in shifts:
        accepted = ", ".join(EMPLOYMENT_LABEL[e] for e in EMPLOYMENT_LABEL if e in shifts)
        problems.append(f"{EMPLOYMENT_LABEL[work]} (aceptas: {accepted})")
    if problems:
        return "Tipo de contrato: " + "; ".join(problems) + "."
    return None


def employer_kind(ext: JobExtraction) -> str | None:
    """`employer_kind` de la extracción; `is_agency: true` cuenta como `agency`."""
    if ext.employer_kind not in (None, "unknown"):
        return ext.employer_kind
    return "agency" if ext.is_agency else ext.employer_kind


def _employer_kind(ext: JobExtraction, profile: CandidateProfile) -> str | None:
    kind = employer_kind(ext)
    if kind in EMPLOYER_LABEL and kind in profile.preferences.excluded_employer_kinds:
        return f"La publica {EMPLOYER_LABEL[kind]} y las excluyes."
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


def discard_keywords(profile_keywords: list[str], policy: HardFilterPolicy) -> list[str]:
    """Las palabras de descarte del perfil y las de `policies.yaml`, sin repetir."""
    seen: set[str] = set()
    out: list[str] = []
    for keyword in (*profile_keywords, *policy.discard_title_keywords):
        key = fold(keyword)
        if key and key not in seen:
            seen.add(key)
            out.append(keyword)
    return out


def _title_keywords(
    title: str, ext: JobExtraction, profile: CandidateProfile, policy: HardFilterPolicy
) -> str | None:
    titles = f" {fold(title)} | {fold(ext.title_normalized)} "
    keywords = discard_keywords(profile.preferences.discard_title_keywords, policy)
    hits = [k for k in keywords if f" {fold(k)} " in titles]
    if hits:
        return f"El título contiene palabras de descarte: {', '.join(hits)}."
    return None


def _signals(ext: JobExtraction, company: str | None, profile: CandidateProfile) -> str | None:
    """Señales de oferta dudosa que el usuario pidió como filtro (`preferences.exclude_signals`).
    Sin eso, las señales son solo información (fase 25.3)."""
    from app.services import doubtful  # evita la importación circular

    wanted = profile.preferences.exclude_signals
    hits: list[str] = []
    if "employer_hidden" in wanted and doubtful.employer_hidden(ext, company):
        hits.append("empresa oculta o agencia")
    # `fixed_term` lo evalúa `_contract`: equivale a no aceptar contrato temporal.
    if hits:
        return f"Excluida por tus preferencias (`exclude_signals`): {', '.join(hits)}."
    return None


def evaluate(
    title: str,
    ext: JobExtraction,
    profile: CandidateProfile,
    policy: HardFilterPolicy,
    company: str | None = None,
) -> HardFilterResult:
    """Aplica todos los filtros y devuelve todos los fallos a la vez (no se para en el primero).
    `company` (el nombre de la empresa de la oferta) solo hace falta para `exclude_signals`."""
    checks: list[tuple[FilterName, str | None]] = [
        ("seniority", _seniority(ext, profile)),
        ("years", _years(ext, profile, policy)),
        ("remote_mode", _remote_mode(ext, profile, policy)),
        ("location", _location(ext, profile, policy)),
        ("language", _languages(ext, profile, policy)),
        ("title_keyword", _title_keywords(title, ext, profile, policy)),
        ("signal", _signals(ext, company, profile)),
        ("salary", _salary(ext, profile)),
        ("contract", _contract(ext, profile)),
        ("employer_kind", _employer_kind(ext, profile)),
    ]
    failures = [FilterFailure(filter=name, reason=reason) for name, reason in checks if reason]
    return HardFilterResult(passed=not failures, failures=failures)
