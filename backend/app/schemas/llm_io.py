"""Esquemas que rellena el agente. Ver `docs/AGENT_INTERFACE.md` §Esquemas que rellena el agente.

Validación estricta: campos desconocidos se rechazan, para que un error del agente se note en vez de
perderse en silencio.
"""

from datetime import date
from typing import Annotated, Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

JOB_EXTRACTION_SCHEMA_VERSION = 1

MAX_RESPONSIBILITIES = 6
MAX_INJECTION_EXCERPT = 200


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _optional(**kwargs: Any) -> Any:
    """Campo opcional que no se vuelca si es `None` (para añadir campos sin cambiar lo guardado)."""
    return Field(default=None, exclude_if=lambda value: value is None, **kwargs)


class LanguageRequirement(_Strict):
    language: str = Field(min_length=1)
    level: str | None = None


class Salary(_Strict):
    min: int | None = Field(default=None, ge=0)
    max: int | None = Field(default=None, ge=0)
    currency: str | None = None
    period: Literal["year", "month", "hour"] | None = None

    @model_validator(mode="after")
    def _min_not_above_max(self) -> Self:
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("`min` no puede ser mayor que `max`.")
        return self


class JobExtraction(_Strict):
    """Datos de una oferta (schema_version 1). Lo que no dice el texto: null o unknown."""

    title_normalized: str = Field(min_length=1)
    seniority: Literal["intern", "junior", "mid", "senior", "lead", "unknown"]
    years_experience_min: int | None = Field(ge=0, le=40)
    employment_type: Literal["full_time", "part_time", "contract", "internship", "unknown"]
    remote_mode: Literal["onsite", "hybrid", "remote", "unknown"]
    locations: list[str]
    languages_required: list[LanguageRequirement]
    salary: Salary | None
    must_have_skills: list[str]
    nice_to_have_skills: list[str]
    responsibilities: list[str] = Field(max_length=MAX_RESPONSIBILITIES)
    domain: str | None
    posting_language: str = Field(min_length=2, max_length=10)
    application_deadline: date | None
    red_flags: list[str]
    injection_suspected: bool
    injection_excerpt: str | None = Field(default=None, max_length=MAX_INJECTION_EXCERPT)
    # Fase 25.3: para las señales de oferta dudosa (`services/doubtful.py`). `None` en las
    # extracciones anteriores (vacíos no se vuelcan: se guardan igual que antes); el rol
    # `extractor` los rellena siempre que el texto lo diga.
    contract_type: Literal["permanent", "fixed_term", "freelance", "unknown"] | None = _optional()
    hiring_entity: str | None = _optional(max_length=200)  # quién contrata, si lo dice
    is_agency: bool | None = _optional()  # la publica una agencia, consultora de selección o ETT
    mentions_ai_screening: bool | None = _optional()  # cribado con IA o test antes de hablar

    @model_validator(mode="after")
    def _excerpt_only_if_suspected(self) -> Self:
        if self.injection_excerpt and not self.injection_suspected:
            raise ValueError("`injection_excerpt` solo va si `injection_suspected` es true.")
        return self


MAX_ASSESSMENT_ITEMS = 8
MAX_ASSESSMENT_ITEM = 300


AssessmentItem = Annotated[str, Field(min_length=1, max_length=MAX_ASSESSMENT_ITEM)]


class FitAssessment(_Strict):
    """Valoración del encaje que escribe el agente (skill `assess-fit`). Ver POLICIES §2."""

    verdict: Literal["strong", "possible", "weak"]
    rationale: str = Field(min_length=1, max_length=1000)  # 2-3 frases con datos del desglose
    risks: list[AssessmentItem] = Field(max_length=MAX_ASSESSMENT_ITEMS)
    questions_for_user: list[AssessmentItem] = Field(max_length=MAX_ASSESSMENT_ITEMS)


MAX_ANSWERS = 50
MAX_QUESTION = 1000
MAX_ANSWER = 5000
MAX_ANSWER_EVIDENCE = 10

# Evidencias de una respuesta que no son ids del perfil: la extracción de la oferta y lo que el
# usuario haya contado (POLICIES §1).
EVIDENCE_EXTRACTION = "extraction"
EVIDENCE_USER = "user"


class ScreeningAnswer(_Strict):
    question: str = Field(min_length=1, max_length=MAX_QUESTION)
    answer: str = Field(max_length=MAX_ANSWER)  # vacía solo con `needs_user_input`
    evidence: list[Annotated[str, Field(min_length=1, max_length=200)]] = Field(
        max_length=MAX_ANSWER_EVIDENCE
    )
    needs_user_input: bool


class ApplicationAnswers(_Strict):
    """Respuestas de screening (skill `prepare-application`). Sin carta: es un documento propio.

    Las reglas que dependen del perfil (evidencias, respuestas vacías) las comprueba
    `services/answers.py`, para dar todos los problemas juntos.
    """

    answers: list[ScreeningAnswer] = Field(min_length=1, max_length=MAX_ANSWERS)
