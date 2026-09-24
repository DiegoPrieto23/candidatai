"""Esquemas que rellena el agente. Ver `docs/AGENT_INTERFACE.md` §Esquemas que rellena el agente.

Validación estricta: campos desconocidos se rechazan, para que un error del agente se note en vez de
perderse en silencio.
"""

from datetime import date
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

JOB_EXTRACTION_SCHEMA_VERSION = 1

MAX_RESPONSIBILITIES = 6
MAX_INJECTION_EXCERPT = 200


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


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

    @model_validator(mode="after")
    def _excerpt_only_if_suspected(self) -> Self:
        if self.injection_excerpt and not self.injection_suspected:
            raise ValueError("`injection_excerpt` solo va si `injection_suspected` es true.")
        return self
