"""Reglas genéricas de `config/`: `policies.yaml` e `injection_patterns.yaml`.

Solo se modelan las secciones que usa el código; el resto del YAML se ignora hasta que haga falta.
"""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import REPO_ROOT

CONFIG_DIR = REPO_ROOT / "config"


class DedupPolicy(BaseModel):
    fuzzy_title_threshold: int = Field(ge=0, le=100)
    fuzzy_window_days: int = Field(gt=0)


class Policies(BaseModel):
    model_config = ConfigDict(extra="ignore")

    dedup: DedupPolicy


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
