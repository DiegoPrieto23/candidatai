"""Cobertura de skills de la oferta con las del perfil, ponderada por nivel.

Los nombres se comparan en forma canónica: sin tildes ni mayúsculas y pasando los sinónimos de
`config/skill_aliases.yaml` a su nombre canónico («PySpark» → «Apache Spark»). Cada skill cubierta
suma el peso de su nivel en el perfil (`scoring.level_weights`: F=1.0, C+=0.8, C=0.5, B=0.2); las de
`basic_skills` cuentan como B. Funciones puras: sin BD ni red.
"""

from collections.abc import Iterable, Mapping
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel

from app.core.policies import LevelWeights, get_skill_aliases
from app.schemas.profile import CandidateProfile
from app.services.normalize import fold

CoveredLevel = Literal["F", "C+", "C", "B", "basic"]
_KEEP = "+#"  # C++, C#


class CoveredSkill(BaseModel):
    skill: str  # como la escribe la oferta
    profile_skill: str  # como la escribe el perfil
    level: CoveredLevel
    weight: float


class SkillCoverage(BaseModel):
    """`ratio` es `None` si la oferta no lista skills de este tipo (el componente no cuenta)."""

    ratio: float | None
    covered: list[CoveredSkill]
    missing: list[str]


def _key(name: str) -> str:
    return fold(name, keep=_KEEP)


@lru_cache
def _alias_index(frozen: tuple[tuple[str, tuple[str, ...]], ...]) -> dict[str, str]:
    index: dict[str, str] = {}
    for canonical, aliases in frozen:
        for name in (canonical, *aliases):
            index[_key(name)] = _key(canonical)
    return index


def alias_index(aliases: Mapping[str, Iterable[str]] | None = None) -> dict[str, str]:
    """Forma plegada de cualquier nombre o sinónimo -> forma plegada del canónico."""
    source = get_skill_aliases() if aliases is None else aliases
    return _alias_index(tuple((k, tuple(v)) for k, v in source.items()))


def canonical(name: str, index: Mapping[str, str]) -> str:
    key = _key(name)
    return index.get(key, key)


def _profile_levels(
    profile: CandidateProfile, index: Mapping[str, str]
) -> dict[str, tuple[str, CoveredLevel]]:
    levels: dict[str, tuple[str, CoveredLevel]] = {}
    for name in profile.basic_skills:
        levels[canonical(name, index)] = (name, "basic")
    # Si una skill y un básico casan con el mismo canónico, gana la skill con su nivel.
    for skill in profile.skills:
        levels[canonical(skill.name, index)] = (skill.name, skill.level)
    return levels


def coverage(
    job_skills: list[str],
    profile: CandidateProfile,
    level_weights: LevelWeights,
    aliases: Mapping[str, Iterable[str]] | None = None,
) -> SkillCoverage:
    """Qué skills de la oferta cubre el perfil y con qué peso. Los repetidos cuentan una vez."""
    index = alias_index(aliases)
    levels = _profile_levels(profile, index)
    seen: set[str] = set()
    covered: list[CoveredSkill] = []
    missing: list[str] = []
    for skill in job_skills:
        key = canonical(skill, index)
        if not key or key in seen:
            continue
        seen.add(key)
        match = levels.get(key)
        if match is None:
            missing.append(skill)
            continue
        profile_name, level = match
        weight = level_weights.for_level("B" if level == "basic" else level)
        covered.append(
            CoveredSkill(skill=skill, profile_skill=profile_name, level=level, weight=weight)
        )
    total = len(covered) + len(missing)
    ratio = sum(c.weight for c in covered) / total if total else None
    return SkillCoverage(ratio=ratio, covered=covered, missing=missing)
