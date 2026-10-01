"""Previews de plantillas: un CV de muestra sacado del perfil, sin agente.

`preview_content` elige de forma determinista qué mostrar según la `capacity` de la plantilla (los
primeros logros de cada experiencia, las skills F/C+ por categoría…). No sustituye al redactor:
solo sirve para ver cómo queda una plantilla. Las integradas guardan su `preview.pdf` generado con
el perfil FICTICIO de `demo/` y su foto (una silueta generada, no una persona): `preview.pdf` y
`preview.png` (la primera página, para las miniaturas de la UI).
"""

import shutil
import tempfile
from pathlib import Path

from app.core.config import REPO_ROOT
from app.schemas.cv import CvContent, CvLanguage
from app.schemas.profile import CandidateProfile
from app.services import profile as profile_service
from app.services.documents import context, pdf, photo
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


DEMO_PHOTO = REPO_ROOT / "demo" / "photo.png"
PREVIEW_WIDTH_PX = 800


def pdf_to_png(pdf_file: Path, png_file: Path, width_px: int = PREVIEW_WIDTH_PX) -> Path:
    """Primera página del PDF como PNG de `width_px` de ancho."""
    import pypdfium2

    document = pypdfium2.PdfDocument(pdf_file)
    try:
        page = document[0]
        image = page.render(scale=width_px / page.get_width()).to_pil()
        page.close()
    finally:
        document.close()
    png_file.parent.mkdir(parents=True, exist_ok=True)
    image.convert("RGB").save(png_file, format="PNG", optimize=True)
    return png_file


def render_preview(
    template: Template,
    profile: CandidateProfile,
    output_pdf: Path,
    photo_source: Path | None = None,
    output_png: Path | None = None,
) -> Path:
    """Renderiza la plantilla con el contenido de muestra del perfil en `output_pdf` (y el PNG)."""
    content = preview_content(profile, template)
    ctx = context.build_context(content, profile, [], accent_color=None)
    accent = template.meta.options.accent_color
    if accent is not None:
        ctx["accent_color"] = accent.default
    workdir = Path(tempfile.mkdtemp(prefix="jh-preview-"))
    try:
        photo_file = None
        if photo_source is not None and template.meta.photo.supported:
            meta = template.meta.photo
            photo_file = photo.prepared_photo(photo_source, meta.shape, meta.size_mm, workdir)
        docx_file = render_docx(
            template, ctx, workdir / "preview.docx", template.meta.page.size, photo_file
        )
        pdf.convert(docx_file, workdir / "preview.pdf")
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(workdir / "preview.pdf", output_pdf)
        if output_png is not None:
            pdf_to_png(output_pdf, output_png)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return output_pdf


def write_builtin_preview(template_dir: Path) -> Path:
    """`preview.pdf` y `preview.png` de una integrada, con el perfil y la foto demo (ficticios)."""
    template = Template(meta=load_meta(template_dir), path=template_dir)
    demo = profile_service.load_from_yaml(profile_service.EXAMPLE_PATH)
    return render_preview(
        template,
        demo,
        template_dir / "preview.pdf",
        photo_source=DEMO_PHOTO,
        output_png=template_dir / "preview.png",
    )
