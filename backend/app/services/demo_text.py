"""Texto de una oferta FICTICIA a partir de su `JobExtraction` (demo y casos de evals).

Todo lo que dice la extracción sale en el texto, en el idioma de la oferta, para que un agente
que la extraiga pueda llegar a la misma extracción.
"""

from app.schemas.llm_io import JobExtraction

_MODES = {
    "es": {"remote": "en remoto", "hybrid": "con modelo híbrido", "onsite": "presencial"},
    "en": {"remote": "fully remote", "hybrid": "hybrid", "onsite": "on-site"},
}
_LEVELS = {
    "es": {"intern": "en prácticas", "junior": "junior", "mid": "de nivel intermedio",
           "senior": "senior", "lead": "lead"},
    "en": {"intern": "intern", "junior": "junior", "mid": "mid-level", "senior": "senior",
           "lead": "lead"},
}  # fmt: skip
_TEXT = {
    "es": {
        "intro": "{company} (empresa ficticia) trabaja en el sector {sector}. Buscamos "
        "{title}{level} en {city}, {mode}.",
        "level": " ({level})",
        "resp": "Responsabilidades",
        "req": "Requisitos",
        "years": "- Al menos {years} años de experiencia.",
        "skill": "- Experiencia con {skill}.",
        "nice": "Se valorará",
        "salary": "Ofrecemos {low}-{high} € brutos al año.",
    },
    "en": {
        "intro": "{company} (fictitious company) works in {sector}. We are hiring a{level} {title} "
        "in {city}, {mode}.",
        "level": " {level}",
        "resp": "Responsibilities",
        "req": "Requirements",
        "years": "- At least {years} years of experience.",
        "skill": "- Experience with {skill}.",
        "nice": "Nice to have",
        "salary": "We offer EUR {low}-{high} gross per year.",
    },
}


def _money(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def posting_text(title: str, company: str, sector: str, city: str, ext: JobExtraction) -> str:
    lang = "en" if ext.posting_language.startswith("en") else "es"
    t = _TEXT[lang]
    level = _LEVELS[lang].get(ext.seniority)
    mode = _MODES[lang].get(ext.remote_mode, "")
    lines = [
        f"{title} – {company}",
        "",
        t["intro"].format(
            company=company,
            sector=sector,
            title=title,
            level=t["level"].format(level=level) if level else "",
            city=city,
            mode=mode,
        ),
        "",
        t["resp"],
        *(f"- {r}." for r in ext.responsibilities),
        "",
        t["req"],
    ]
    if ext.years_experience_min:
        lines.append(t["years"].format(years=ext.years_experience_min))
    lines += [t["skill"].format(skill=s) for s in ext.must_have_skills]
    lines += [f"- {lang_req.language} {lang_req.level}." for lang_req in ext.languages_required]
    if ext.nice_to_have_skills:
        lines += ["", t["nice"], *(f"- {s}." for s in ext.nice_to_have_skills)]
    if ext.salary and ext.salary.min and ext.salary.max:
        lines += ["", t["salary"].format(low=_money(ext.salary.min), high=_money(ext.salary.max))]
    return "\n".join(lines) + "\n"
