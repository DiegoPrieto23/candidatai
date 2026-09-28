"""Previews de plantillas: un CV de muestra sacado del perfil, sin agente.

`preview_content` elige de forma determinista qué mostrar según la `capacity` de la plantilla (los
primeros logros de cada experiencia, las skills F/C+ por categoría…). No sustituye al redactor:
solo sirve para ver cómo queda una plantilla. Las integradas guardan su `preview.pdf` generado con
el perfil FICTICIO de `demo/`. La fase 08.2 añade la imagen PNG.
"""

import shutil
import tempfile
from pathlib import Path

from app.schemas.cv import CvContent, CvLanguage
from app.schemas.profile import CandidateProfile
from app.services import profile as profile_service
from app.services.documents import context, pdf
from app.services.documents.engines.docx import render_docx
from app.services.documents.templates import Template, load_meta


def _shorten(text: str, limit: int) -> str:
    """Recorta en la última frase (o palabra) completa que quepa en `limit` caracteres."""
    text = " ".join(text.split())
    if limit <= 0 or len(text) <= limit:
        return text
    cut = text[:limit]
    end = cut.rfind(". ")
    if end >= limit // 2:
        return cut[: end + 1]
    return cut.rsplit(" ", 1)[0].rstrip(",;:") + "…"


def preview_content(
    profile: CandidateProfile, template: Template, language: CvLanguage = "es"
) -> CvContent:
    capacity = template.meta.capacity
    summary = getattr(profile.summary, language) or profile.summary.es or profile.summary.en or ""

    # Reparte los bullets entre experiencias por turnos: primero el primer logro de cada una.
    budget = max(capacity.experience_bullets, len(profile.experience))
    chosen: dict[str, list[dict[str, object]]] = {e.id: [] for e in profile.experience}
    depth = 0
    while budget > 0 and any(len(e.achievements) > depth for e in profile.experience):
        for exp in profile.experience:
            if budget > 0 and len(exp.achievements) > depth:
                ach = exp.achievements[depth]
                text = ach.text.rstrip(".") + (f" ({ach.metrics})" if ach.metrics else "") + "."
                chosen[exp.id].append({"text": text, "evidence": [f"{exp.id}/{ach.id}"]})
                budget -= 1
        depth += 1
    experience = [
        {"experience_id": e.id, "bullets": chosen[e.id]} for e in profile.experience if chosen[e.id]
    ]

    groups: dict[str, list[str]] = {}
    for skill in profile.skills:
        if skill.level in ("F", "C+"):
            groups.setdefault(skill.category or "Skills", []).append(skill.name)
    skills = [
        {"group": group, "items": items}
        for group, items in list(groups.items())[: max(capacity.skill_groups, 1)]
    ]

    return CvContent.model_validate(
        {
            "language": language,
            "subtitle": profile.headline,
            "summary": _shorten(summary, capacity.summary_chars) or profile.headline,
            "experience": experience,
            "projects": [
                {"project_id": p.id, "bullets": [{"text": p.text, "evidence": [p.id]}]}
                for p in profile.projects
            ],
            "skills": skills,
            "education_ids": [e.id for e in profile.education],
            "certification_ids": [c.id for c in profile.certifications],
            "languages": [
                {"language": lang.language, "level": lang.level}
                for lang in profile.languages
                if not lang.regional
            ],
            "include_regional_language": False,
            "keywords_targeted": [],
        }
    )


def render_preview(template: Template, profile: CandidateProfile, output_pdf: Path) -> Path:
    """Renderiza la plantilla con el contenido de muestra del perfil en `output_pdf`."""
    content = preview_content(profile, template)
    ctx = context.build_context(content, profile, [], accent_color=None)
    accent = template.meta.options.accent_color
    if accent is not None:
        ctx["accent_color"] = accent.default
    workdir = Path(tempfile.mkdtemp(prefix="jh-preview-"))
    try:
        docx_file = render_docx(template, ctx, workdir / "preview.docx", template.meta.page.size)
        pdf.convert(docx_file, workdir / "preview.pdf")
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(workdir / "preview.pdf", output_pdf)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return output_pdf


def write_builtin_preview(template_dir: Path) -> Path:
    """`preview.pdf` de una plantilla integrada, con el perfil FICTICIO de `demo/`."""
    template = Template(meta=load_meta(template_dir), path=template_dir)
    demo = profile_service.load_from_yaml(profile_service.EXAMPLE_PATH)
    return render_preview(template, demo, template_dir / "preview.pdf")
