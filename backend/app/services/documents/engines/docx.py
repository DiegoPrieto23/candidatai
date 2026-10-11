"""Motor docx: contexto del contrato → docxtpl → DOCX (ADR-004, ADR-014).

docxtpl usa Jinja2. El texto del contexto viene del perfil y del agente: docxtpl lo escapa para XML
(`autoescape`), así que un `<` o un `&` en un logro no rompen el documento.

Después del render, los enlaces del perfil (`context.links`) pasan a ser hipervínculos (ADR-023).
"""

import copy
from pathlib import Path
from typing import Any

from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm
from docxtpl import DocxTemplate, InlineImage
from jinja2.sandbox import SandboxedEnvironment

from app.schemas.cv import PageSize
from app.services.documents.context import links, split_links
from app.services.documents.templates import Template

# Tamaños en mm (ancho, alto).
PAGE_SIZES_MM: dict[PageSize, tuple[float, float]] = {"A4": (210, 297), "Letter": (215.9, 279.4)}


def _set_page_size(doc: DocxTemplate, page_size: PageSize) -> None:
    width, height = PAGE_SIZES_MM[page_size]
    for section in doc.docx.sections:  # type: ignore[union-attr]
        if abs(section.page_width.mm - width) > 1 or abs(section.page_height.mm - height) > 1:
            section.page_width = Mm(width)
            section.page_height = Mm(height)


def _add_hyperlinks(doc: DocxTemplate, targets: dict[str, str]) -> None:
    """Parte las runs que contienen un texto de `targets` y envuelve ese trozo en un hipervínculo.

    Cada trozo conserva el formato de su run: el enlace se ve como lo diseñó la plantilla. Solo
    toca runs de texto simple (sin tabuladores, saltos ni campos) que no estén ya en un enlace.
    """
    if not targets:
        return
    document = doc.docx
    assert document is not None
    part = document.part
    for run in list(document.element.body.iter(qn("w:r"))):
        parent = run.getparent()
        if parent is None or parent.tag == qn("w:hyperlink"):
            continue
        content = [child for child in run if child.tag != qn("w:rPr")]
        if not content or any(child.tag != qn("w:t") for child in content):
            continue
        pieces = split_links("".join(child.text or "" for child in content), targets)
        if all(url is None for _, url in pieces):
            continue
        anchor = run
        for piece, url in pieces:
            new_run = copy.deepcopy(run)
            for child in [c for c in new_run if c.tag != qn("w:rPr")]:
                new_run.remove(child)
            node = OxmlElement("w:t")
            node.text = piece
            node.set(qn("xml:space"), "preserve")
            new_run.append(node)
            if url is not None:
                link = OxmlElement("w:hyperlink")
                rel_id = part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
                link.set(qn("r:id"), rel_id)
                link.append(new_run)
                new_run = link
            anchor.addnext(new_run)
            anchor = new_run
        parent.remove(run)


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
    _add_hyperlinks(doc, links(context))
    _set_page_size(doc, page_size)
    output.parent.mkdir(parents=True, exist_ok=True)
    doc.save(output)
    return output
