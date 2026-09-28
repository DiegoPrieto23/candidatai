"""Perfil y ofertas de `demo/` para los tests de matching, y un embedder falso sin red."""

import hashlib
import json
import math
from collections.abc import Sequence
from functools import cache
from typing import Any

from app.core.config import REPO_ROOT
from app.schemas.llm_io import JobExtraction
from app.schemas.profile import CandidateProfile
from app.services.profile import EXAMPLE_PATH, load_from_yaml

DEMO_JOBS = REPO_ROOT / "demo" / "jobs"
DEMO_TITLES = {
    "01-data-engineer": ("Data Engineer (m/f/d)", "Brétema Analytics", "Santiago de Compostela"),
    "02-analytics-engineer": ("Analytics Engineer", "Lonxa Retail Tech", "Remoto, España"),
}


@cache
def _demo_profile_data() -> dict[str, Any]:
    return load_from_yaml(EXAMPLE_PATH).model_dump(mode="json")


def demo_profile(**preferences: Any) -> CandidateProfile:
    """El perfil de `demo/`, con las preferencias cambiadas que se indiquen."""
    data = json.loads(json.dumps(_demo_profile_data()))
    data["preferences"].update(preferences)
    return CandidateProfile.model_validate(data)


def demo_extraction_data(name: str) -> dict[str, Any]:
    return json.loads((DEMO_JOBS / f"{name}.extraction.json").read_text(encoding="utf-8"))


def demo_extraction(name: str = "01-data-engineer", **changes: Any) -> JobExtraction:
    data = demo_extraction_data(name)
    data.update(changes)
    return JobExtraction.model_validate(data)


class FakeEmbedder:
    """Bolsa de palabras con hash: textos con palabras en común se parecen. Determinista."""

    model_name = "fake-bow"

    def __init__(self) -> None:
        self.calls = 0

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls += 1
        vectors = []
        for text in texts:
            vector = [0.0] * 64
            for word in text.lower().split():
                slot = int(hashlib.md5(word.encode()).hexdigest(), 16) % 64
                vector[slot] += 1.0
            norm = math.sqrt(sum(x * x for x in vector)) or 1.0
            vectors.append([x / norm for x in vector])
        return vectors


class BrokenEmbedder:
    model_name = "broken"

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        raise OSError("sin red para descargar el modelo")
