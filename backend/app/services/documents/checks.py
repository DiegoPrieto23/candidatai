"""Comprobaciones del CV: el contenido antes de guardarlo y el PDF después de renderizarlo.

- `validate_content`: lo que el código puede comprobar de `POLICIES.md` §1 sin IA (ids y evidencias
  que existen en el perfil, skills del perfil, skills básicas solo si la oferta las pide). Lo demás
  (que un bullet diga lo mismo que su evidencia) lo revisa el rol `verifier`.
- `render_warnings` y `keyword_coverage`: los avisos de `CV_TEMPLATES.md` §Avisos y qué keywords
  de la oferta aparecen de verdad en el PDF.
"""

import re
from collections.abc import Iterable

from pydantic import BaseModel

from app.core.policies import get_skill_aliases
from app.core.validation import quoted, similar
from app.schemas.cv import CvContent
from app.schemas.llm_io import JobExtraction
from app.schemas.profile import CandidateProfile
from app.services.documents.options import RenderWarning, ResolvedOptions
from app.services.documents.templates import Template
from app.services.matching.skills import alias_index, canonical
from app.services.normalize import fold

_KEEP = "+#"  # C++, C#

# Cómo presenta el redactor una skill básica (POLICIES §1): «conocimientos de dbt».
_BASIC_PREFIXES = (
    "conocimientos basicos de",
    "conocimientos de",
    "nociones de",
    "basic knowledge of",
    "working knowledge of",
    "knowledge of",
    "familiarity with",
)


class ContentIssue(BaseModel):
    field: str  # relativo al contenido; la interfaz para agentes le pone delante `root` y puntos
    received: str | None
    reason: str
    expected: str | None = None
    hint: str | None = None


def similar_hint(value: str, valid: Iterable[str], what: str) -> str | None:
    """«<what> del perfil más parecidos: `a`, `b`…» (los 5 más cercanos), o None si no hay."""
    close = similar(value, sorted(valid), n=5)
    return f"{what} del perfil más parecidos: {quoted(close)}." if close else None


def skill_hint(value: str, profile: CandidateProfile) -> str:
    """Una skill que no está en el perfil, a menudo traducida: el nombre tal cual del perfil."""
    names = [s.name for s in profile.skills] + list(profile.basic_skills)
    close = similar(value, names, n=3, cutoff=0.5)
    base = "Usa el nombre tal como aparece en el perfil, sin traducirlo aunque el CV sea en otro "
    if close:
        return base + f"idioma: {quoted(close)}."
    return base + "idioma (`get_profile` con `skills`). Si no la tienes, quítala."


class CvContentError(ValueError):
    """El contenido incumple las reglas; `issues` dice dónde y por qué, para corregir."""

    root = "content"  # el campo de la entrada que lo lleva (`save_cv_content`)

    def __init__(self, issues: list[ContentIssue]) -> None:
        self.issues = issues
        count = len(issues)
        noun = "problema" if count == 1 else "problemas"
        super().__init__(
            f"El contenido del CV no es válido ({count} {noun}): "
            + ", ".join(i.field for i in issues)
            + "."
        )


def _strip_basic_prefix(item: str) -> str:
    words = item.split()
    for prefix in _BASIC_PREFIXES:
        n = len(prefix.split())
        if len(words) > n and fold(" ".join(words[:n])) == prefix:
            return " ".join(words[n:])
    return item


def skill_key(name: str, index: dict[str, str]) -> str:
    return canonical(_strip_basic_prefix(name), index)


def citable_refs(profile: CandidateProfile) -> dict[str, str]:
    """Lo que una carta o una respuesta puede citar: lo del CV y, además, las historias STAR."""
    refs = profile.evidence_refs()
    for story in profile.stories:
        refs[story.id] = f"Historia «{story.title}»: {story.result}"
    return refs


def requested_skills(extraction: JobExtraction | None) -> list[str]:
    if extraction is None:
        return []
    return [*extraction.must_have_skills, *extraction.nice_to_have_skills]


def validate_content(
    content: CvContent, profile: CandidateProfile, extraction: JobExtraction | None
) -> None:
    """Lanza `CvContentError` con todos los problemas juntos, o no hace nada si está bien."""
    issues: list[ContentIssue] = []
    refs = profile.evidence_refs()
    experiences = {e.id for e in profile.experience}
    projects = {p.id for p in profile.projects}

    def check_ids(field: str, ids: Iterable[str], valid: set[str], what: str) -> None:
        for i, value in enumerate(ids):
            if value not in valid:
                issues.append(
                    ContentIssue(
                        field=f"{field}[{i}]",
                        received=value,
                        reason=f"No existe {what} con ese id en el perfil.",
                        hint=similar_hint(value, valid, "Ids"),
                    )
                )

    def check_bullets(field: str, bullets: Iterable[object]) -> None:
        for b, bullet in enumerate(bullets):
            for e, ref in enumerate(bullet.evidence):  # type: ignore[attr-defined]
                if ref not in refs:
                    issues.append(
                        ContentIssue(
                            field=f"{field}.bullets[{b}].evidence[{e}]",
                            received=ref,
                            reason="La evidencia no existe en el perfil (p. ej. `exp-acme/a2`).",
                            hint=similar_hint(ref, refs, "Evidencias"),
                        )
                    )

    for i, item in enumerate(content.experience):
        field = f"experience[{i}]"
        if item.experience_id not in experiences:
            issues.append(
                ContentIssue(
                    field=f"{field}.experience_id",
                    received=item.experience_id,
                    reason="No existe una experiencia con ese id en el perfil.",
                    hint=similar_hint(item.experience_id, experiences, "Experiencias"),
                )
            )
        check_bullets(field, item.bullets)
    for i, item in enumerate(content.projects):
        field = f"projects[{i}]"
        if item.project_id not in projects:
            issues.append(
                ContentIssue(
                    field=f"{field}.project_id",
                    received=item.project_id,
                    reason="No existe un proyecto con ese id en el perfil.",
                    hint=similar_hint(item.project_id, projects, "Proyectos"),
                )
            )
        check_bullets(field, item.bullets)
    check_ids(
        "education_ids", content.education_ids, {e.id for e in profile.education}, "una formación"
    )
    check_ids(
        "certification_ids",
        content.certification_ids,
        {c.id for c in profile.certifications},
        "una certificación",
    )
    extra_sections = {s.id: {i.id for i in s.items} for s in profile.extra_sections}
    for i, section in enumerate(content.extra_sections):
        field = f"extra_sections[{i}]"
        if section.section_id not in extra_sections:
            issues.append(
                ContentIssue(
                    field=f"{field}.section_id",
                    received=section.section_id,
                    reason="No existe una sección extra con ese id en el perfil.",
                    hint=similar_hint(section.section_id, extra_sections, "Secciones"),
                )
            )
            continue
        check_ids(
            f"{field}.item_ids",
            section.item_ids,
            extra_sections[section.section_id],
            f"un item de `{section.section_id}`",
        )

    index = alias_index()
    levels = {canonical(s.name, index): s.level for s in profile.skills}
    basics = {canonical(name, index) for name in profile.basic_skills}
    requested = {canonical(s, index) for s in requested_skills(extraction)}

    def is_basic(key: str) -> bool:
        return (key in basics and key not in levels) or levels.get(key) == "B"

    for g, group in enumerate(content.skills):
        for s, item in enumerate(group.items):
            key = skill_key(item, index)
            field = f"skills[{g}].items[{s}]"
            if key not in levels and key not in basics:
                issues.append(
                    ContentIssue(
                        field=field,
                        received=item,
                        reason="Esta skill no está en el perfil (`skills` ni `basic_skills`). Si "
                        "la tienes, añádela primero con el skill `update-profile`.",
                        hint=skill_hint(item, profile),
                    )
                )
            elif is_basic(key) and key not in requested:
                issues.append(
                    ContentIssue(
                        field=field,
                        received=item,
                        reason="Es una skill básica (nivel B o `basic_skills`) y la oferta no la "
                        "pide: quítala del CV.",
                    )
                )

    if issues:
        raise CvContentError(issues)


# --- Tras el render -------------------------------------------------------------------------


class KeywordCoverage(BaseModel):
    """Keywords de la oferta (skills obligatorias y deseables) en el texto del PDF."""

    present: list[str]
    missing: list[str]


def _names_for(keyword: str, index: dict[str, str]) -> set[str]:
    key = canonical(keyword, index)
    names = {fold(keyword, keep=_KEEP)}
    for name, aliases in get_skill_aliases().items():
        if canonical(name, index) == key:
            names |= {fold(n, keep=_KEEP) for n in (name, *aliases)}
    return {n for n in names if n}


def skill_mentioned(folded_text: str, skill: str, index: dict[str, str]) -> bool:
    """¿Aparece la skill (o uno de sus alias) en el texto ya normalizado con `fold_text`?"""
    return any(
        re.search(rf"(?<![\w+#]){re.escape(name)}(?![\w+#])", folded_text)
        for name in _names_for(skill, index)
    )


def fold_text(text: str) -> str:
    return fold(text, keep=_KEEP)


def keyword_coverage(text: str, extraction: JobExtraction | None) -> KeywordCoverage:
    index = alias_index()
    haystack = fold(text, keep=_KEEP)
    present: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()
    for keyword in requested_skills(extraction):
        key = canonical(keyword, index)
        if not key or key in seen:
            continue
        seen.add(key)
        found = skill_mentioned(haystack, keyword, index)
        (present if found else missing).append(keyword)
    return KeywordCoverage(present=present, missing=missing)


def render_warnings(
    content: CvContent,
    template: Template,
    resolved: ResolvedOptions,
    pages: int,
    substituted_fonts: list[str],
) -> list[RenderWarning]:
    """Avisos del render (`CV_TEMPLATES.md` §Avisos), además de los de la resolución de opciones."""
    warnings = list(resolved.warnings)
    meta = template.meta
    if pages > resolved.max_pages:
        warnings.append(
            RenderWarning(
                code="too_long",
                message=f"El CV ocupa {pages} páginas y el máximo es {resolved.max_pages}. "
                "Recorta contenido (nunca márgenes ni fuente).",
            )
        )
    if resolved.offer.ats and not meta.ats_friendly:
        warnings.append(
            RenderWarning(
                code="not_ats_friendly",
                message=f"La oferta usa {resolved.offer.ats} y la plantilla «{meta.id}» no es apta "
                "para ATS: considera `ats-simple`.",
            )
        )
    present = {
        "summary": bool(content.summary),
        "experience": bool(content.experience),
        "projects": bool(content.projects),
        "education": bool(content.education_ids),
        "certifications": bool(content.certification_ids),
        "extra_sections": bool(content.extra_sections),
        "skills": bool(content.skills),
        "languages": bool(content.languages),
    }
    unsupported = [
        s
        for s, has in present.items()
        if has and s not in meta.sections and s not in resolved.hidden_sections
    ]
    if unsupported:
        warnings.append(
            RenderWarning(
                code="section_not_supported",
                message=f"La plantilla «{meta.id}» no muestra: {', '.join(unsupported)}.",
            )
        )
    if meta.engine == "html":
        warnings.append(
            RenderWarning(
                code="pdf_only",
                message=f"La plantilla «{meta.id}» es html: solo hay PDF. Si el portal pide Word, "
                "renderiza con una plantilla docx (p. ej. `ats-simple`).",
            )
        )
    if substituted_fonts:
        warnings.append(
            RenderWarning(
                code="font_substituted",
                message="Falta la fuente "
                + ", ".join(substituted_fonts)
                + " y el PDF usa otra: instálala para que se vea como la plantilla.",
            )
        )
    return warnings
