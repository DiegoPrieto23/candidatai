"""Similitud semántica entre el perfil y una oferta con embeddings locales (ADR-006).

sentence-transformers es un extra opcional (`uv sync --extra matching`): trae torch. Sin él, o con
`CAI_EMBEDDINGS=off`, el score se calcula sin este componente y su peso se reparte entre los demás.
El modelo se carga la primera vez que hace falta, en CPU, y se guarda en `data/models/`.
"""

import math
from collections import OrderedDict
from collections.abc import Sequence
from functools import lru_cache
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel

from app.core.config import get_settings
from app.core.policies import SemanticPolicy, get_policies
from app.schemas.llm_io import JobExtraction
from app.schemas.profile import CandidateProfile

EXTRA_HINT = "instala el extra con `uv sync --extra matching` (en backend/)"
_CACHE_SIZE = 512


class Embedder(Protocol):
    model_name: str

    def encode(self, texts: Sequence[str]) -> list[list[float]]: ...


class SentenceTransformerEmbedder:
    """Carga perezosa del modelo y caché en memoria de los textos ya codificados."""

    def __init__(self, model_name: str, cache_dir: Path) -> None:
        self.model_name = model_name
        self._cache_dir = cache_dir
        self._model: Any = None
        self._cache: OrderedDict[str, list[float]] = OrderedDict()

    def _load(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._cache_dir.mkdir(parents=True, exist_ok=True)
            self._model = SentenceTransformer(
                self.model_name, cache_folder=str(self._cache_dir), device="cpu"
            )
        return self._model

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        pending = [t for t in dict.fromkeys(texts) if t not in self._cache]
        found = {t: self._cache[t] for t in texts if t in self._cache}
        if pending:
            vectors = self._load().encode(
                pending, normalize_embeddings=True, show_progress_bar=False
            )
            found.update({t: [float(x) for x in v] for t, v in zip(pending, vectors, strict=True)})
        for text, vector in found.items():  # los recién usados, al final; se expulsan los viejos
            self._cache[text] = vector
            self._cache.move_to_end(text)
        while len(self._cache) > _CACHE_SIZE:
            self._cache.popitem(last=False)
        return [found[t] for t in texts]


def is_installed() -> bool:
    return find_spec("sentence_transformers") is not None


@lru_cache
def _embedder_for(model_name: str, cache_dir: Path) -> SentenceTransformerEmbedder:
    return SentenceTransformerEmbedder(model_name, cache_dir)


def get_embedder() -> Embedder | None:
    """El embedder configurado, o `None` si está desactivado o sin instalar."""
    settings = get_settings()
    if settings.embeddings == "off" or not is_installed():
        return None
    return _embedder_for(get_policies().scoring.semantic.model, settings.models_dir)


def unavailable_reason() -> str | None:
    """Por qué no hay similitud semántica (para el desglose y `cai doctor`), o `None` si la hay."""
    if get_settings().embeddings == "off":
        return "Similitud semántica desactivada (CAI_EMBEDDINGS=off)."
    if not is_installed():
        return f"Similitud semántica no disponible: {EXTRA_HINT}."
    return None


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def profile_text(profile: CandidateProfile, language: str | None = None) -> str:
    """Resumen (en el idioma de la oferta si lo hay) + titular + logros."""
    summary = profile.summary.en if language == "en" and profile.summary.en else None
    summary = summary or profile.summary.es or profile.summary.en or ""
    achievements = [a.text for exp in profile.experience for a in exp.achievements]
    return "\n".join([profile.headline, summary, *achievements])


def job_text(ext: JobExtraction) -> str:
    """Título + responsabilidades + skills + sector de la oferta."""
    skills = ", ".join([*ext.must_have_skills, *ext.nice_to_have_skills])
    parts = [ext.title_normalized, *ext.responsibilities, skills, ext.domain or ""]
    return "\n".join(p for p in parts if p)


class SemanticResult(BaseModel):
    model: str
    cosine: float  # similitud coseno bruta
    value: float  # 0-1, reescalada entre `similarity_floor` y `similarity_ceiling`


def rescale(value: float, policy: SemanticPolicy) -> float:
    span = policy.similarity_ceiling - policy.similarity_floor
    return min(1.0, max(0.0, (value - policy.similarity_floor) / span))


def similarity(
    profile: CandidateProfile, ext: JobExtraction, embedder: Embedder, policy: SemanticPolicy
) -> SemanticResult:
    a, b = embedder.encode([profile_text(profile, ext.posting_language), job_text(ext)])
    raw = cosine(a, b)
    return SemanticResult(
        model=embedder.model_name, cosine=round(raw, 4), value=rescale(raw, policy)
    )
