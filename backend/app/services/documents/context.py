"""Contexto de render: `CvContent` + perfil → variables del contrato (docs/CV_TEMPLATES.md).

Es el mismo para los dos motores. Las fechas y los títulos de sección (`labels`) salen ya en el
idioma del CV. El contacto (email, teléfono, ciudad, LinkedIn, GitHub) lo pone el código desde el
perfil: el agente nunca lo ve (POLICIES §4).
"""

from dataclasses import dataclass
from typing import Any

from app.schemas.cv import SECTIONS, CvContent, CvLanguage, SectionName
from app.schemas.profile import PRESENT, CandidateProfile, ExtraSection
from app.services.normalize import fold

_MONTHS: dict[CvLanguage, tuple[str, ...]] = {
    "es": (
        "ene.",
        "feb.",
        "mar.",
        "abr.",
        "may.",
        "jun.",
        "jul.",
        "ago.",
        "sept.",
        "oct.",
        "nov.",
        "dic.",
    ),
    "en": ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),
}

LABELS: dict[CvLanguage, dict[str, str]] = {
    "es": {
        "summary": "Perfil",
        "experience": "Experiencia",
        "projects": "Proyectos",
        "education": "Formación",
        "certifications": "Certificaciones",
        "skills": "Habilidades",
        "languages": "Idiomas",
        "contact": "Contacto",
        "present": "actualidad",
    },
    "en": {
        "summary": "Profile",
        "experience": "Experience",
        "projects": "Projects",
        "education": "Education",
        "certifications": "Certifications",
        "skills": "Skills",
        "languages": "Languages",
        "contact": "Contact",
        "present": "Present",
    },
}


@dataclass(frozen=True)
class SkillGroup:
    """Un grupo de skills. No es un dict: en Jinja, `s.items` de un dict sería el método `items`."""

    group: str
    items: list[str]


def format_month(value: str | None, language: CvLanguage) -> str:
    """`2024-03` → «mar. 2024» / «Mar 2024»; `present` → «actualidad» / «Present»."""
    if not value:
        return ""
    if value == PRESENT:
        return LABELS[language]["present"]
    year, month = value.split("-")
    return f"{_MONTHS[language][int(month) - 1]} {year}"


def _regional_languages(profile: CandidateProfile) -> set[str]:
    return {fold(lang.language) for lang in profile.languages if lang.regional}


@dataclass(frozen=True)
class ExtraSectionContext:
    """Una sección extra. Objeto y no dict por lo mismo que `SkillGroup` (`x.items`)."""

    title: str
    items: list[dict[str, str]]


def _extra_section(
    section: ExtraSection, item_ids: list[str], lang: CvLanguage
) -> ExtraSectionContext:
    """Una sección extra con el título en el idioma del CV (o en el otro si solo hay ese)."""
    items = {i.id: i for i in section.items}
    title = getattr(section.title, lang) or section.title.es or section.title.en or ""
    return ExtraSectionContext(
        title=title,
        items=[
            {"text": items[i].text, "date": format_month(items[i].date, lang)} for i in item_ids
        ],
    )


def build_context(
    content: CvContent,
    profile: CandidateProfile,
    hidden_sections: list[SectionName],
    accent_color: str | None = None,
) -> dict[str, Any]:
    """Variables del contrato, salvo `photo`, que añade cada motor a su manera."""
    lang = content.language
    personal = profile.personal
    experiences = {e.id: e for e in profile.experience}
    projects = {p.id: p for p in profile.projects}
    education = {e.id: e for e in profile.education}
    certifications = {c.id: c for c in profile.certifications}
    extra_sections = {s.id: s for s in profile.extra_sections}

    experience = []
    for item in content.experience:
        exp = experiences[item.experience_id]
        experience.append(
            {
                "role": exp.role,
                "company": exp.company,
                "city": exp.city or "",
                "start": format_month(exp.start, lang),
                "end": format_month(exp.end, lang),
                "bullets": [b.text for b in item.bullets],
            }
        )

    # Idioma regional (gallego, catalán…) solo si el redactor lo decidió para esta oferta.
    regional = set() if content.include_regional_language else _regional_languages(profile)
    languages = [
        {"language": item.language, "level": item.level}
        for item in content.languages
        if fold(item.language) not in regional
    ]

    context: dict[str, Any] = {
        "name": personal.name,
        "subtitle": content.subtitle,
        "summary": content.summary,
        "contact": {
            "email": personal.email or "",
            "phone": personal.phone or "",
            "city": personal.city or "",
            "linkedin": personal.linkedin or "",
            "github": personal.github or "",
        },
        "photo": "",
        "experience": experience,
        "projects": [
            {
                "name": projects[p.project_id].name,
                "date": format_month(projects[p.project_id].date, lang),
                "bullets": [b.text for b in p.bullets],
            }
            for p in content.projects
        ],
        "education": [
            {
                "title": education[i].title,
                "center": education[i].center,
                "start": format_month(education[i].start, lang),
                "end": format_month(education[i].end, lang),
                "detail": "",  # el perfil no tiene este campo
            }
            for i in content.education_ids
        ],
        "certifications": [
            {
                "name": certifications[i].name,
                "issuer": certifications[i].issuer or "",
                "date": format_month(certifications[i].date, lang),
            }
            for i in content.certification_ids
        ],
        "extra_sections": [
            _extra_section(extra_sections[s.section_id], s.item_ids, lang)
            for s in content.extra_sections
        ],
        "skills": [SkillGroup(group=g.group, items=list(g.items)) for g in content.skills],
        "languages": languages,
        "labels": dict(LABELS[lang]),
        "accent_color": accent_color or "",
    }
    # Una sección se muestra si no está oculta y tiene algo que mostrar (sin títulos huérfanos).
    context["show"] = {
        section: section not in hidden_sections and bool(context[section]) for section in SECTIONS
    }
    return context
