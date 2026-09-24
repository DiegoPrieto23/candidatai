"""`CandidateProfile`: estructura de `data/profile.yaml` (referencia: `demo/profile.example.yaml`).

Validación estricta: una clave mal escrita es un error, no un campo que se pierde en silencio. Las
comprobaciones entre secciones (ids únicos, skills declaradas, evidencias que existen) se hacen al
final y se lanzan juntas como `ProfileConsistencyError`, cada una con la ruta de su campo.
"""

import re
from collections.abc import Iterator
from typing import Annotated, Any, Literal, Self

from pydantic import AfterValidator, BaseModel, BeforeValidator, ConfigDict, Field, model_validator

PROFILE_SCHEMA_VERSION = 1

SkillLevel = Literal["F", "C+", "C", "B"]
Seniority = Literal["intern", "junior", "mid", "senior", "lead"]
RemoteMode = Literal["onsite", "hybrid", "remote"]

_YEAR_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_ID = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
_LANG = re.compile(r"^[a-z]{2}$")
_COUNTRY = re.compile(r"^[A-Z]{2}$")
PRESENT = "present"


def _year_month(value: Any) -> Any:
    # YAML convierte `2024-03-01` en una fecha: se rechaza con el mismo mensaje que un texto mal
    # formado, en vez de un «Debe ser texto» que despista.
    if not isinstance(value, str) or not _YEAR_MONTH.match(value):
        raise ValueError("Debe ser una fecha con formato AAAA-MM (p. ej. 2024-03).")
    return value


def _year_month_or_present(value: Any) -> Any:
    return value if value == PRESENT else _year_month(value)


def _id(value: str) -> str:
    if not _ID.match(value):
        raise ValueError(
            "Id no válido: minúsculas, dígitos, `-` o `_` (p. ej. `exp-acme`, `a1`), sin `/`."
        )
    return value


def _pattern(regex: re.Pattern[str], example: str) -> AfterValidator:
    def check(value: str) -> str:
        if not regex.match(value):
            raise ValueError(f"Formato no válido (p. ej. {example}).")
        return value

    return AfterValidator(check)


YearMonth = Annotated[str, BeforeValidator(_year_month)]
YearMonthOrPresent = Annotated[str, BeforeValidator(_year_month_or_present)]
Id = Annotated[str, Field(min_length=1), AfterValidator(_id)]
Text = Annotated[str, Field(min_length=1)]
LanguageCode = Annotated[str, _pattern(_LANG, "es, en")]
CountryCode = Annotated[str, _pattern(_COUNTRY, "ES, GB")]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Personal(_Strict):
    name: Text
    email: str | None = None  # nunca sale por `get_profile`
    phone: str | None = None  # nunca sale por `get_profile`; solo en el CV entregado
    linkedin: str | None = None
    github: str | None = None
    city: str | None = None
    profile_location: str | None = None
    availability: str | None = None
    mobility: str | None = None


class Summary(_Strict):
    es: str | None = None
    en: str | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> Self:
        if not (self.es or self.en):
            raise ValueError("Hace falta el resumen en al menos un idioma (`es` o `en`).")
        return self


class Achievement(_Strict):
    id: Id
    text: Text
    metrics: str | None = None
    skills: list[str] = []
    nda: bool = False


class Experience(_Strict):
    id: Id
    company: Text
    city: str | None = None
    role: Text
    start: YearMonth
    end: YearMonthOrPresent
    context: str | None = None
    achievements: list[Achievement] = []

    @model_validator(mode="after")
    def _end_not_before_start(self) -> Self:
        if self.end != PRESENT and self.end < self.start:
            raise ValueError("`end` no puede ser anterior a `start`.")
        return self


class Project(_Strict):
    id: Id
    name: Text
    date: YearMonth | None = None
    text: Text
    skills: list[str] = []
    nda: bool = False


class Education(_Strict):
    id: Id
    title: Text
    center: Text
    start: YearMonth | None = None
    end: YearMonthOrPresent | None = None

    @model_validator(mode="after")
    def _end_not_before_start(self) -> Self:
        if self.start and self.end and self.end != PRESENT and self.end < self.start:
            raise ValueError("`end` no puede ser anterior a `start`.")
        return self


class Certification(_Strict):
    id: Id
    name: Text
    issuer: str | None = None
    date: YearMonth | None = None


class Language(_Strict):
    language: Text
    level: Text  # libre: «Nativo», «B2», «C1 (Cambridge)»…
    regional: str | None = None  # comunidad donde tiene sentido ponerlo en el CV


class Skill(_Strict):
    name: Text
    level: SkillLevel
    category: str | None = None


class Story(_Strict):
    """Historia STAR. `evidence` cita logros (`exp-x/a1`) u otros elementos del perfil por id."""

    id: Id
    title: Text
    situation: Text
    task: Text
    action: Text
    result: Text
    evidence: list[str] = Field(min_length=1)


class Locations(_Strict):
    preferred: list[str] = []
    allowed: list[str] = []  # solo si es híbrido o remoto
    excluded: list[str] = []


class PhotoPolicy(_Strict):
    default: bool
    by_country: dict[CountryCode, bool] = {}


class CvPreferences(_Strict):
    max_pages: int = Field(default=1, ge=1, le=3)
    photo_policy: PhotoPolicy


class Preferences(_Strict):
    roles: list[str] = Field(min_length=1)
    seniority_target: list[Seniority] = Field(min_length=1)
    max_years_required: int | None = Field(default=None, ge=0, le=40)
    remote_modes: list[RemoteMode] = Field(min_length=1)
    locations: Locations = Locations()
    languages_for_work: list[LanguageCode] = Field(min_length=1)
    cv: CvPreferences


class ConsistencyIssue(BaseModel):
    """Un problema de coherencia del perfil, con la ruta de su campo."""

    loc: tuple[str | int, ...]
    reason: str
    received: str | None = None


class ProfileConsistencyError(ValueError):
    """Errores entre secciones. Pydantic la envuelve en su `ValidationError` (en `ctx.error`)."""

    def __init__(self, issues: list[ConsistencyIssue]) -> None:
        self.issues = issues
        super().__init__("; ".join(f"{issue.loc}: {issue.reason}" for issue in issues))


class CandidateProfile(_Strict):
    """Perfil del candidato (schema_version 1): la única fuente de verdad para CVs y respuestas."""

    schema_version: Literal[1]
    personal: Personal
    headline: Text
    summary: Summary
    experience: list[Experience] = []
    projects: list[Project] = []
    education: list[Education] = []
    certifications: list[Certification] = []
    languages: list[Language] = []
    skills: list[Skill] = []
    basic_skills: list[str] = []  # solo si la oferta lo pide, como «conocimientos de X»
    stories: list[Story] = []
    preferences: Preferences
    private: dict[str, Any] = {}  # nunca sale por la MCP ni en ningún documento

    def evidence_refs(self) -> dict[str, str]:
        """Referencias citables como evidencia y su texto: `exp-x`, `exp-x/a1`, `prj-x`…"""
        refs: dict[str, str] = {}
        for exp in self.experience:
            refs[exp.id] = f"{exp.role} en {exp.company} ({exp.start} – {exp.end})"
            for ach in exp.achievements:
                text = ach.text + (f" (métrica: {ach.metrics})" if ach.metrics else "")
                refs[f"{exp.id}/{ach.id}"] = text + (" [NDA]" if ach.nda else "")
        for prj in self.projects:
            refs[prj.id] = f"{prj.name}: {prj.text}" + (" [NDA]" if prj.nda else "")
        for edu in self.education:
            refs[edu.id] = f"{edu.title}, {edu.center}"
        for cert in self.certifications:
            details = ", ".join(part for part in (cert.issuer, cert.date) if part)
            refs[cert.id] = cert.name + (f" ({details})" if details else "")
        return refs

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        issues = [*self._duplicate_ids(), *self._undeclared_skills(), *self._broken_evidence()]
        if issues:
            raise ProfileConsistencyError(issues)
        return self

    def _duplicate_ids(self) -> Iterator[ConsistencyIssue]:
        # Los ids de primer nivel son únicos en todo el perfil (las evidencias los citan sin
        # sección); los de logro, dentro de su experiencia (`exp-x/a1`).
        seen: set[str] = set()
        sections: tuple[tuple[str, list[Any]], ...] = (
            ("experience", self.experience),
            ("projects", self.projects),
            ("education", self.education),
            ("certifications", self.certifications),
            ("stories", self.stories),
        )
        for section, items in sections:
            for i, item in enumerate(items):
                if item.id in seen:
                    loc = (section, i, "id")
                    yield ConsistencyIssue(loc=loc, reason="Id repetido.", received=item.id)
                seen.add(item.id)
        for i, exp in enumerate(self.experience):
            seen_ach: set[str] = set()
            for j, ach in enumerate(exp.achievements):
                if ach.id in seen_ach:
                    yield ConsistencyIssue(
                        loc=("experience", i, "achievements", j, "id"),
                        reason=f"Id de logro repetido dentro de `{exp.id}`.",
                        received=ach.id,
                    )
                seen_ach.add(ach.id)
        seen_skills: set[str] = set()
        for i, skill in enumerate(self.skills):
            if skill.name.casefold() in seen_skills:
                yield ConsistencyIssue(
                    loc=("skills", i, "name"), reason="Skill repetida.", received=skill.name
                )
            seen_skills.add(skill.name.casefold())
        for i, name in enumerate(self.basic_skills):
            if name.casefold() in seen_skills:
                yield ConsistencyIssue(
                    loc=("basic_skills", i),
                    reason="Ya está en `skills` o repetida: cada skill va en un solo sitio.",
                    received=name,
                )
            seen_skills.add(name.casefold())

    def _undeclared_skills(self) -> Iterator[ConsistencyIssue]:
        declared = {s.name.casefold() for s in self.skills} | {
            name.casefold() for name in self.basic_skills
        }
        reason = "Skill no declarada: añádela a `skills` (con su nivel) o a `basic_skills`."
        for i, exp in enumerate(self.experience):
            for j, ach in enumerate(exp.achievements):
                for k, name in enumerate(ach.skills):
                    if name.casefold() not in declared:
                        loc = ("experience", i, "achievements", j, "skills", k)
                        yield ConsistencyIssue(loc=loc, reason=reason, received=name)
        for i, prj in enumerate(self.projects):
            for k, name in enumerate(prj.skills):
                if name.casefold() not in declared:
                    loc = ("projects", i, "skills", k)
                    yield ConsistencyIssue(loc=loc, reason=reason, received=name)

    def _broken_evidence(self) -> Iterator[ConsistencyIssue]:
        refs = self.evidence_refs()
        for i, story in enumerate(self.stories):
            for k, ref in enumerate(story.evidence):
                if ref not in refs:
                    yield ConsistencyIssue(
                        loc=("stories", i, "evidence", k),
                        reason="La evidencia no existe: usa `exp-x/a1` o el id de un proyecto, "
                        "formación o certificación.",
                        received=ref,
                    )
