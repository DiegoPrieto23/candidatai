"""Filtro previo barato antes de guardar una oferta de un conector, y orden de las ofertas
resumen de las alertas (fase 09b).

Solo mira el título y la ubicación contra `preferences` del perfil vigente, sin descripción ni
agente: su objetivo es no llenar la BD de ofertas que no tienen nada que ver. Ante la duda deja
pasar (ubicación desconocida, sin perfil…): los filtros duros y el score afinan después.
"""

import re
from dataclasses import dataclass

from app.core.policies import get_policies
from app.schemas.profile import Preferences
from app.services.matching.hard_filters import SENIORITY_LABEL, SENIORITY_ORDER, location_matches
from app.services.matching.scorer import role_similarity
from app.services.normalize import fold, normalize_location, normalize_title, title_segments

_SENIORITY_WORDS = frozenset({"intern", "trainee", "junior", "mid", "senior", "lead", "principal"})
# Seniority que se lee en un título sin descripción (sobre el título plegado: sin tildes y en
# minúsculas). Ante varias, la primera que aparece en esta lista.
_TITLE_SENIORITY = (
    ("intern", re.compile(r"\b(?:intern|internship|trainee|becari[oa]s?|practicas)\b")),
    ("junior", re.compile(r"\b(?:junior|jr)\b")),
    ("lead", re.compile(r"\b(?:lead|principal|head of|jefe de equipo)\b")),
    ("senior", re.compile(r"\b(?:senior|sr)\b")),
)


@dataclass(frozen=True)
class Verdict:
    passed: bool
    reason: str | None = None


PASS = Verdict(True)


def _has_words(text: str, phrase: str) -> bool:
    folded = fold(phrase)
    return bool(folded) and f" {folded} " in f" {fold(text)} "


class Prefilter:
    """Se construye una vez por ejecución. Sin preferencias (sin perfil), todo pasa."""

    def __init__(self, preferences: Preferences | None, extra_title_keywords: list[str]) -> None:
        self.preferences = preferences
        self.extra = [k for k in extra_title_keywords if fold(k)]
        self.discard = [k for k in get_policies().hard_filters.discard_title_keywords if fold(k)]

    @property
    def active(self) -> bool:
        return self.preferences is not None

    def check(self, title: str, location: str | None, remote: bool | None) -> Verdict:
        if self.preferences is None:
            return PASS
        verdict = self._title(title)
        return verdict if not verdict.passed else self._location(location, remote)

    def check_summary(self, title: str, location: str | None) -> Verdict:
        """Prefiltro de una oferta resumen: lo de `check` y, además, los filtros duros que se
        pueden evaluar sin descripción (de momento, la seniority que diga el título)."""
        verdict = self.check(title, location, None)
        if not verdict.passed or self.preferences is None:
            return verdict
        level = title_seniority(title)
        accepted = self.preferences.seniority_target
        if level is None or level in accepted:
            return PASS
        labels = ", ".join(SENIORITY_LABEL[s] for s in SENIORITY_ORDER if s in accepted)
        return Verdict(
            False, f"El título indica seniority {SENIORITY_LABEL[level]}; solo aceptas: {labels}."
        )

    def _title(self, title: str) -> Verdict:
        assert self.preferences is not None
        hits = [k for k in self.discard if _has_words(title, k)]
        if hits:
            return Verdict(False, f"El título contiene palabras de descarte: {', '.join(hits)}.")
        if any(_has_words(title, k) for k in self.extra):
            return PASS
        segments = {
            " ".join(w for w in s.split() if w not in _SENIORITY_WORDS)
            for s in title_segments(title)
        } - {""}
        # Todas las palabras de algún puesto buscado deben estar en el título (con margen para
        # variantes como «engineering»); el parecido fino lo calcula el score.
        for role in self.preferences.roles:
            wanted = normalize_title(role)
            if any(role_similarity(segment, wanted) > 0 for segment in segments):
                return PASS
        return Verdict(False, "El título no encaja con tus puestos (`preferences.roles`).")

    def _location(self, location: str | None, remote: bool | None) -> Verdict:
        assert self.preferences is not None
        if not location or not location.strip():
            return PASS
        zones = self.preferences.locations
        is_remote = remote is True or "remote" in normalize_location(location).split()
        if is_remote and "remote" in self.preferences.remote_modes:
            return PASS
        if location_matches(location, zones.excluded):
            return Verdict(False, f"Ubicación descartada: {location}.")
        if not zones.preferred and not zones.allowed:
            return PASS
        if location_matches(location, zones.preferred) or location_matches(location, zones.allowed):
            return PASS
        return Verdict(False, f"Fuera de zona: {location}.")


def title_seniority(title: str) -> str | None:
    """Seniority explícita en el título («Senior», «Jr.», «Becario»…), o `None` si no dice."""
    folded = fold(title)
    for level, pattern in _TITLE_SENIORITY:
        if pattern.search(folded):
            return level
    return None
