"""Motores de plantillas: docx (docxtpl + LibreOffice/Word) y html (Jinja2 + Chromium).

`render_files` es el punto común del servicio de render y de las previews: devuelve el DOCX (solo
en docx) y el PDF.
"""

from pathlib import Path
from typing import Any

from app.schemas.cv import PageSize
from app.services.documents.templates import Template


def render_files(
    template: Template,
    context: dict[str, Any],
    out_dir: Path,
    stem: str,
    page_size: PageSize,
    photo_file: Path | None,
    file: Path | None = None,
) -> tuple[Path | None, Path]:
    """Renderiza la plantilla (o otro de sus ficheros, p. ej. `letter.*`) en
    `out_dir/<stem>.docx|pdf` y devuelve `(docx o None, pdf)`."""
    if template.meta.engine == "html":
        from app.services.documents.engines.html import render_pdf

        pdf_file = render_pdf(
            template, context, out_dir / f"{stem}.pdf", page_size, photo_file, file=file
        )
        return None, pdf_file

    from app.services.documents import pdf
    from app.services.documents.engines.docx import render_docx

    docx_file = render_docx(
        template, context, out_dir / f"{stem}.docx", page_size, photo_file, file=file
    )
    return docx_file, pdf.convert(docx_file, out_dir / f"{stem}.pdf")
