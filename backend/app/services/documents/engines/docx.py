"""Motor docx: contexto del contrato → docxtpl → DOCX (ADR-004, ADR-014).

docxtpl usa Jinja2. El texto del contexto viene del perfil y del agente: docxtpl lo escapa para XML
(`autoescape`), así que un `<` o un `&` en un logro no rompen el documento.
"""

from pathlib import Path
from typing import Any

from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage
from jinja2.sandbox import SandboxedEnvironment

from app.schemas.cv import PageSize
from app.services.documents.templates import Template

# Tamaños en mm (ancho, alto).
PAGE_SIZES_MM: dict[PageSize, tuple[float, float]] = {"A4": (210, 297), "Letter": (215.9, 279.4)}


def _set_page_size(doc: DocxTemplate, page_size: PageSize) -> None:
    width, height = PAGE_SIZES_MM[page_size]
    for section in doc.docx.sections:  # type: ignore[union-attr]
        if abs(section.page_width.mm - width) > 1 or abs(section.page_height.mm - height) > 1:
            section.page_width = Mm(width)
            section.page_height = Mm(height)


def render_docx(
    template: Template,
    context: dict[str, Any],
    output: Path,
    page_size: PageSize,
    photo_path: Path | None = None,
    file: Path | None = None,
) -> Path:
    """Renderiza la plantilla (o `file`, p. ej. su carta) y escribe el DOCX en `output`."""
    doc = DocxTemplate(file or template.engine_file)
    values = dict(context)
    if photo_path is not None:
        values["photo"] = InlineImage(doc, str(photo_path), width=Mm(template.meta.photo.size_mm))
    else:
        values["photo"] = ""
    # Sandbox: una plantilla del usuario (importada desde un CV que puede no ser suyo) no puede
    # llegar a atributos internos de Python (`''.__class__…`) desde un marcador.
    doc.render(values, jinja_env=SandboxedEnvironment(autoescape=True), autoescape=True)
    _set_page_size(doc, page_size)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)
    return output
