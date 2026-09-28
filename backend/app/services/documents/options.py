"""Resolución de las opciones de render (`docs/CV_TEMPLATES.md` §Opciones de render por oferta).

Lo que queda en `null` o `auto` se decide aquí, sin IA:

1. plantilla: la opción explícita > la primera regla de `preferences.cv.template_rules` que encaje
   con la oferta > `preferences.cv.default_template` > `cv.fallback_template` de las políticas;
2. foto (`auto`): si la plantilla la admite, hay foto y `photo_policy` la permite en el país;
3. lo demás, lo que diga la plantilla.

Las reglas miran el ATS (por el dominio de la URL), el país (por la ubicación, con
`config/countries.yaml`), el `domain` de la extracción y el idioma del CV. Una oferta puede estar
en varios países: una regla de país encaja si alguno está en su lista, y la foto solo va si la
política la permite en todos.
"""

import re
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel

from app.core.policies import get_countries, get_policies
from app.schemas.cv import CvLanguage, CvRenderOptions, PageSize, SectionName
from app.schemas.llm_io import JobExtraction
from app.schemas.profile import CandidateProfile, TemplateRuleWhen
from app.services.documents import templates
from app.services.normalize import fold


class RenderWarning(BaseModel):
    code: str
    message: str


class OfferContext(BaseModel):
    """Lo que las reglas saben de la oferta."""

    ats: str | None
    countries: list[str]
    domain: str | None
    language: CvLanguage


TemplateSource = Literal["option", "rule", "default_template", "fallback"]


class ResolvedOptions(BaseModel):
    template_id: str
    template_source: TemplateSource
    rule_index: int | None = None  # posición en `template_rules` si la eligió una regla
    photo: bool
    accent_color: str | None
    max_pages: int
    hidden_sections: list[SectionName]
    page_size: PageSize
    offer: OfferContext
    warnings: list[RenderWarning] = []


class InvalidRenderOptionsError(ValueError):
    pass


# --- Datos de la oferta ---------------------------------------------------------------------


def detect_ats(url: str | None, platforms: dict[str, list[str]] | None = None) -> str | None:
    """ATS por el dominio de la URL o un subdominio (`x.wd3.myworkdayjobs.com` -> workday)."""
    if not url:
        return None
    host = (urlsplit(url if "//" in url else f"//{url}").hostname or "").lower().rstrip(".")
    if not host:
        return None
    platforms = get_policies().cv.ats_platforms if platforms is None else platforms
    for ats, domains in platforms.items():
        for domain in domains:
            domain = domain.lower()
            if host == domain or host.endswith(f".{domain}"):
                return ats
    return None


@lru_cache
def _country_patterns() -> tuple[tuple[re.Pattern[str], str], ...]:
    names = [(fold(name), code) for code, items in get_countries().items() for name in items]
    names = [(name, code) for name, code in names if name]
    names.sort(key=lambda item: len(item[0]), reverse=True)  # «nueva york» antes que «york»
    return tuple((re.compile(rf"(?<!\w){re.escape(name)}(?!\w)"), code) for name, code in names)


def detect_countries(locations: list[str]) -> list[str]:
    """Códigos de país de las ubicaciones, en orden de aparición y sin repetir."""
    found: list[str] = []
    for location in locations:
        text = fold(location)
        hits: list[tuple[int, str]] = []
        for pattern, code in _country_patterns():
            match = pattern.search(text)
            if match:
                hits.append((match.start(), code))
                text = text[: match.start()] + " " * len(match.group()) + text[match.end() :]
        for _pos, code in sorted(hits):
            if code not in found:
                found.append(code)
    return found


def offer_context(
    url: str | None,
    location_raw: str | None,
    extraction: JobExtraction | None,
    language: CvLanguage,
) -> OfferContext:
    locations = list(extraction.locations) if extraction else []
    if location_raw:
        locations.append(location_raw)
    return OfferContext(
        ats=detect_ats(url),
        countries=detect_countries(locations),
        domain=extraction.domain if extraction else None,
        language=language,
    )


# --- Reglas ---------------------------------------------------------------------------------


def _contains_words(text: str, term: str) -> bool:
    term = fold(term)
    return bool(term) and re.search(rf"(?<!\w){re.escape(term)}(?!\w)", fold(text)) is not None


def rule_matches(when: TemplateRuleWhen, offer: OfferContext) -> bool:
    """Encaja si la oferta cumple todas las condiciones informadas de la regla."""
    if when.ats and (offer.ats is None or fold(offer.ats) not in {fold(a) for a in when.ats}):
        return False
    if when.country and not set(when.country) & set(offer.countries):
        return False
    if when.domain and (
        offer.domain is None or not any(_contains_words(offer.domain, d) for d in when.domain)
    ):
        return False
    return not (when.language and offer.language not in when.language)


def photo_allowed_by_policy(profile: CandidateProfile, countries: list[str]) -> bool:
    policy = profile.preferences.cv.photo_policy
    if not countries:
        return policy.default
    return all(policy.by_country.get(code, policy.default) for code in countries)


def _choose_template(
    profile: CandidateProfile,
    options: CvRenderOptions,
    offer: OfferContext,
    warnings: list[RenderWarning],
) -> tuple[templates.Template, TemplateSource, int | None]:
    if options.template_id is not None:
        return templates.get(options.template_id), "option", None

    def lookup(template_id: str, origin: str) -> templates.Template | None:
        try:
            return templates.get(template_id)
        except templates.TemplateNotFoundError:
            warnings.append(
                RenderWarning(
                    code="template_not_found",
                    message=f"{origin} pide la plantilla «{template_id}», que no existe o no es "
                    "válida; se usa la siguiente opción.",
                )
            )
            return None

    prefs = profile.preferences.cv
    for index, rule in enumerate(prefs.template_rules):
        if rule_matches(rule.when, offer):
            found = lookup(rule.use, f"La regla {index + 1} de `template_rules`")
            if found is not None:
                return found, "rule", index
            break  # la primera regla que encaja decide; si su plantilla falta, se sigue abajo
    if prefs.default_template:
        found = lookup(prefs.default_template, "`default_template`")
        if found is not None:
            return found, "default_template", None
    return templates.get(get_policies().cv.fallback_template), "fallback", None


def resolve(
    profile: CandidateProfile,
    options: CvRenderOptions,
    offer: OfferContext,
    photo_available: bool,
) -> ResolvedOptions:
    """Opciones definitivas de un render. Lanza `InvalidRenderOptionsError` si no son válidas."""
    warnings: list[RenderWarning] = []
    template, source, rule_index = _choose_template(profile, options, offer, warnings)
    meta = template.meta

    accent_option = meta.options.accent_color
    if options.accent_color is not None:
        if accent_option is None:
            raise InvalidRenderOptionsError(
                f"La plantilla «{meta.id}» no admite color de acento (`accent_color`)."
            )
        if options.accent_color not in accent_option.choices:
            raise InvalidRenderOptionsError(
                f"La plantilla «{meta.id}» admite estos colores: "
                f"{', '.join(accent_option.choices)}."
            )
    accent = options.accent_color or (accent_option.default if accent_option else None)

    photo = False
    if options.photo == "include":
        if not meta.photo.supported:
            warnings.append(
                RenderWarning(
                    code="photo_excluded",
                    message=f"Pediste foto, pero la plantilla «{meta.id}» no la admite.",
                )
            )
        elif not photo_available:
            warnings.append(
                RenderWarning(
                    code="photo_excluded", message="Pediste foto, pero no hay foto disponible."
                )
            )
        else:
            photo = True
    elif options.photo == "auto":
        photo = (
            meta.photo.supported
            and photo_available
            and photo_allowed_by_policy(profile, offer.countries)
        )

    return ResolvedOptions(
        template_id=meta.id,
        template_source=source,
        rule_index=rule_index,
        photo=photo,
        accent_color=accent,
        max_pages=options.max_pages or meta.page.max_pages,
        hidden_sections=sorted(set(options.hidden_sections), key=options.hidden_sections.index),
        page_size=options.page_size or meta.page.size,
        offer=offer,
        warnings=warnings,
    )
