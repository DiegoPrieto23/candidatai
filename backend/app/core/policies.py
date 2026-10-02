"""Reglas genéricas de `config/`: `policies.yaml`, `injection_patterns.yaml`, `skill_aliases.yaml`
y `countries.yaml`.

Solo se modelan las secciones que usa el código; el resto del YAML se ignora hasta que haga falta.
"""

from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.config import REPO_ROOT

CONFIG_DIR = REPO_ROOT / "config"


class DedupPolicy(BaseModel):
    fuzzy_title_threshold: int = Field(ge=0, le=100)
    fuzzy_window_days: int = Field(gt=0)


class HardFilterPolicy(BaseModel):
    years_tolerance: int = Field(ge=0)
    unknown_remote_mode_passes: bool
    discard_title_keywords: list[str] = []


class ScoringWeights(BaseModel):
    must_have_coverage: float = Field(ge=0)
    semantic_similarity: float = Field(ge=0)
    preferences_fit: float = Field(ge=0)
    nice_to_have_coverage: float = Field(ge=0)

    @model_validator(mode="after")
    def _some_weight(self) -> "ScoringWeights":
        if sum(self.model_dump().values()) <= 0:
            raise ValueError("Al menos un peso de `scoring.weights` debe ser mayor que 0.")
        return self


class LevelWeights(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    F: float = Field(ge=0, le=1)
    C_plus: float = Field(ge=0, le=1, alias="C+")
    C: float = Field(ge=0, le=1)
    B: float = Field(ge=0, le=1)

    def for_level(self, level: str) -> float:
        return {"F": self.F, "C+": self.C_plus, "C": self.C, "B": self.B}[level]


class SemanticPolicy(BaseModel):
    model: str = Field(min_length=1)
    similarity_floor: float = Field(ge=-1, le=1)
    similarity_ceiling: float = Field(ge=-1, le=1)

    @model_validator(mode="after")
    def _floor_below_ceiling(self) -> "SemanticPolicy":
        if self.similarity_floor >= self.similarity_ceiling:
            raise ValueError("`similarity_floor` debe ser menor que `similarity_ceiling`.")
        return self


class PreferencesPolicy(BaseModel):
    role_min_similarity: int = Field(ge=0, le=100)


class ScoringPolicy(BaseModel):
    weights: ScoringWeights
    level_weights: LevelWeights
    triage_threshold: int = Field(ge=0, le=100)
    semantic: SemanticPolicy
    preferences: PreferencesPolicy


class CvPolicy(BaseModel):
    fallback_template: str
    # ATS -> dominios de sus URLs (se compara el dominio de la oferta y sus subdominios).
    ats_platforms: dict[str, list[str]]
    pdf_timeout_seconds: int = Field(gt=0)


class ConnectorsPolicy(BaseModel):
    """Conectores de ATS y portales (fase 09)."""

    daily_at: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")  # HH:MM, hora local de `timezone`
    timezone: str = Field(min_length=1)
    timeout_seconds: float = Field(gt=0)
    max_jobs_per_source: int = Field(gt=0)

    @model_validator(mode="after")
    def _known_timezone(self) -> "ConnectorsPolicy":
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Zona horaria desconocida: «{self.timezone}».") from exc
        return self


class EmailAlertsPolicy(BaseModel):
    """Alertas de empleo por correo (fase 09b)."""

    poll_minutes: int = Field(gt=0)
    summary_expire_days: int = Field(gt=0)
    # Plataforma -> dominios del remitente (se compara el dominio y sus subdominios).
    platforms: dict[str, list[str]]


class Policies(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dedup: DedupPolicy
    hard_filters: HardFilterPolicy
    scoring: ScoringPolicy
    cv: CvPolicy
    connectors: ConnectorsPolicy
    email_alerts: EmailAlertsPolicy


class InjectionPatterns(BaseModel):
    phrases: list[str]
    hidden_text_min_chars: int = Field(ge=0)


def _read_yaml(path: Path) -> object:
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@lru_cache
def get_policies() -> Policies:
    return Policies.model_validate(_read_yaml(CONFIG_DIR / "policies.yaml"))


@lru_cache
def get_injection_patterns() -> InjectionPatterns:
    return InjectionPatterns.model_validate(_read_yaml(CONFIG_DIR / "injection_patterns.yaml"))


@lru_cache
def get_skill_aliases() -> dict[str, list[str]]:
    """Nombre canónico -> sinónimos. Un canónico sin sinónimos puede venir como `[]` o `null`."""
    data = _read_yaml(CONFIG_DIR / "skill_aliases.yaml") or {}
    if not isinstance(data, dict):
        raise ValueError("config/skill_aliases.yaml debe ser un diccionario nombre -> sinónimos.")
    return {str(name): [str(alias) for alias in (aliases or [])] for name, aliases in data.items()}


@lru_cache
def get_countries() -> dict[str, list[str]]:
    """Código ISO 3166-1 -> nombres de país, regiones y ciudades que lo identifican."""
    data = _read_yaml(CONFIG_DIR / "countries.yaml") or {}
    if not isinstance(data, dict):
        raise ValueError("config/countries.yaml debe ser un diccionario código -> nombres.")
    return {str(code): [str(name) for name in (names or [])] for code, names in data.items()}
