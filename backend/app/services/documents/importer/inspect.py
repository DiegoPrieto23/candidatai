"""`jh templates inspect`: qué tiene un CV de Word, para decidir el mapeo y el `template.yaml`.

Da el diseño (página, columnas, fuentes, colores, tablas, cuadros de texto, imágenes, cabecera y
pie), los párrafos numerados con sus fragmentos fusionados, las secciones en su orden (también las
que no están en el contrato) y la `capacity` medida en el original, para que la plantilla respete
su extensión. La estimación de `ats_friendly` es honesta: dice los motivos.
"""

import re
import shutil
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Literal

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.ns import qn
from pydantic import BaseModel

from app.services.documents import pdf
from app.services.documents.importer import TemplateImportError, docx_xml
from app.services.normalize import fold

EMU_PER_MM = 36000
TWIPS_PER_MM = 56.6929

# Títulos de sección conocidos (sin tildes, en minúsculas y sin «:» final).
SECTION_TITLES: dict[str, str] = {
    **dict.fromkeys(
        [
            "perfil", "perfil profesional", "resumen", "resumen profesional", "sobre mi",
            "acerca de mi", "extracto", "profile", "summary", "professional summary", "about me",
            "about",
        ],
        "summary",
    ),
    **dict.fromkeys(
        [
            "experiencia", "experiencia profesional", "experiencia laboral", "trayectoria",
            "trayectoria profesional", "experience", "work experience",
            "professional experience", "employment", "employment history",
        ],
        "experience",
    ),
    **dict.fromkeys(
        ["proyectos", "proyectos destacados", "projects", "personal projects", "side projects"],
        "projects",
    ),
    **dict.fromkeys(
        [
            "formacion", "formacion academica", "educacion", "estudios", "titulacion",
            "education", "academic background",
        ],
        "education",
    ),
    **dict.fromkeys(
        [
            "certificaciones", "certificados", "licencias y certificaciones", "certifications",
            "certificates", "licenses & certifications", "licenses and certifications",
        ],
        "certifications",
    ),
    **dict.fromkeys(
        [
            "habilidades", "competencias", "aptitudes", "conocimientos", "tecnologias",
            "herramientas", "habilidades tecnicas", "competencias tecnicas", "skills",
            "technical skills", "core skills", "tech stack", "stack",
        ],
        "skills",
    ),
    **dict.fromkeys(["idiomas", "languages"], "languages"),
    **dict.fromkeys(["contacto", "datos de contacto", "contact", "contact details"], "contact"),
}  # fmt: skip

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
_PHONE = re.compile(r"\+?\d[\d\s().-]{7,}\d")
_BULLET_GLYPHS = ("•", "·", "▪", "■", "◦", "-", "–", "—", "*", "‣", "○", "●")


class PageInfo(BaseModel):
    width_mm: float
    height_mm: float
    size: Literal["A4", "Letter", "other"]
    columns: int
    margins_mm: dict[str, float]


class TableInfo(BaseModel):
    index: int
    rows: int
    columns: int
    nested: bool
    borderless: bool


class ImageInfo(BaseModel):
    paragraph: int
    width_mm: float
    height_mm: float
    floating: bool
    shape: Literal["circle", "rounded", "square"]
    photo_candidate: bool


class RunInfo(BaseModel):
    text: str
    bold: bool
    italic: bool
    size: float | None
    color: str | None
    font: str | None


class ParagraphInfo(BaseModel):
    index: int
    location: docx_xml.Location
    table: int | None
    row: int | None
    cell: int | None
    style: str | None
    text: str
    is_list: bool
    images: int
    runs: list[RunInfo]


class SectionInfo(BaseModel):
    section: str  # una del contrato, `contact` o `extra`
    title: str
    paragraph: int


class MeasuredCapacity(BaseModel):
    """Medida en el original; `null` si no se encontró la sección."""

    summary_chars: int | None
    experience_bullets: int | None
    bullets_per_experience: list[int]
    skill_groups: int | None
    pages: int | None


class AtsEstimate(BaseModel):
    ats_friendly: bool
    reasons: list[str]


class DocxInspection(BaseModel):
    file: str
    format: Literal["docx"]
    pages: int | None
    pages_note: str | None
    page: list[PageInfo]
    fonts: list[str]
    colors: list[str]
    tables: list[TableInfo]
    text_boxes: list[str]
    images: list[ImageInfo]
    header_text: list[str]
    footer_text: list[str]
    sections: list[SectionInfo]
    capacity: MeasuredCapacity
    ats: AtsEstimate
    paragraphs: list[ParagraphInfo]


# --- Diseño ---------------------------------------------------------------------------------


def _page_info(doc: DocxDocument) -> list[PageInfo]:
    pages = []
    for sect in doc.element.body.iter(qn("w:sectPr")):
        size = sect.find(qn("w:pgSz"))
        margins = sect.find(qn("w:pgMar"))
        cols = sect.find(qn("w:cols"))
        width = int(size.get(qn("w:w"), 11906)) / TWIPS_PER_MM if size is not None else 210
        height = int(size.get(qn("w:h"), 16838)) / TWIPS_PER_MM if size is not None else 297
        kind: Literal["A4", "Letter", "other"] = "other"
        if abs(width - 210) < 2 and abs(height - 297) < 2:
            kind = "A4"
        elif abs(width - 215.9) < 2 and abs(height - 279.4) < 2:
            kind = "Letter"
        margin_mm = {}
        if margins is not None:
            for side in ("top", "right", "bottom", "left"):
                value = margins.get(qn(f"w:{side}"))
                if value and value.lstrip("-").isdigit():
                    margin_mm[side] = round(int(value) / TWIPS_PER_MM, 1)
        columns = int(cols.get(qn("w:num"), "1")) if cols is not None else 1
        pages.append(
            PageInfo(
                width_mm=round(width, 1),
                height_mm=round(height, 1),
                size=kind,
                columns=max(columns, 1),
                margins_mm=margin_mm,
            )
        )
    return pages


def _theme_fonts(doc: DocxDocument) -> dict[str, str]:
    for rel in doc.part.rels.values():
        if rel.reltype.endswith("/theme") and not rel.is_external:
            from lxml import etree

            root = etree.fromstring(rel.target_part.blob)
            ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
            fonts = {}
            for kind in ("major", "minor"):
                latin = root.find(f".//a:{kind}Font/a:latin", ns)
                if latin is not None and latin.get("typeface"):
                    fonts[kind] = latin.get("typeface")
            return fonts
    return {}


def _font_name(rpr: Any, theme: dict[str, str]) -> str | None:
    """Fuente de un `w:rPr` (directa o del tema), o `None` si no la fija."""
    fonts = rpr.find(qn("w:rFonts")) if rpr is not None else None
    if fonts is None:
        return None
    name = fonts.get(qn("w:ascii")) or fonts.get(qn("w:hAnsi"))
    if name:
        return name
    theme_ref = fonts.get(qn("w:asciiTheme")) or fonts.get(qn("w:hAnsiTheme"))
    if theme_ref:
        return theme.get("major" if theme_ref.startswith("major") else "minor")
    return None


def _fonts(doc: DocxDocument, paras: list[docx_xml.Paragraph]) -> list[str]:
    """Fuentes que se ven, por caracteres: la del fragmento, la de su estilo (y los estilos en que
    se basa) o la del documento. Las de estilos que nadie usa no cuentan."""
    theme = _theme_fonts(doc)
    styles = {s.get(qn("w:styleId")): s for s in doc.styles.element.findall(qn("w:style"))}
    default_style = next(
        (
            sid
            for sid, s in styles.items()
            if s.get(qn("w:type")) == "paragraph" and s.get(qn("w:default")) in ("1", "true")
        ),
        None,
    )
    defaults = doc.styles.element.find(f"{qn('w:docDefaults')}/{qn('w:rPrDefault')}/{qn('w:rPr')}")

    def style_font(style_id: str | None) -> str | None:
        seen = set()
        while style_id and style_id not in seen and style_id in styles:
            seen.add(style_id)
            style = styles[style_id]
            name = _font_name(style.find(qn("w:rPr")), theme)
            if name:
                return name
            based = style.find(qn("w:basedOn"))
            style_id = based.get(qn("w:val")) if based is not None else None
        return None

    counts: Counter[str] = Counter()
    for p in paras:
        p_style = p.element.find(f"{qn('w:pPr')}/{qn('w:pStyle')}")
        p_style_id = p_style.get(qn("w:val")) if p_style is not None else default_style
        for run in p.runs:
            if not run.text.strip():
                continue
            rpr = run.elements[0].find(qn("w:rPr"))
            r_style = rpr.find(qn("w:rStyle")) if rpr is not None else None
            name = (
                _font_name(rpr, theme)
                or style_font(r_style.get(qn("w:val")) if r_style is not None else None)
                or style_font(p_style_id)
                or _font_name(defaults, theme)
                or theme.get("minor")
            )
            if name:
                counts[name] += len(run.text)
    return [name for name, _ in counts.most_common()]


def _colors(roots: Iterable[Any]) -> list[str]:
    counts: Counter[str] = Counter()
    for root in roots:
        for color in root.iter(qn("w:color")):
            value = color.get(qn("w:val"), "auto")
            if value != "auto" and re.fullmatch(r"[0-9A-Fa-f]{6}", value):
                counts["#" + value.upper()] += 1
        for shading in root.iter(qn("w:shd")):
            value = shading.get(qn("w:fill"), "auto")
            if value != "auto" and re.fullmatch(r"[0-9A-Fa-f]{6}", value):
                counts["#" + value.upper()] += 1
    return [c for c, _ in counts.most_common(10)]


def _borderless(tbl: Any) -> bool:
    borders = tbl.find(f"{qn('w:tblPr')}/{qn('w:tblBorders')}")
    if borders is None:
        # Sin bordes propios manda el estilo: «Table Grid» los tiene, «Normal Table» no.
        style = tbl.find(f"{qn('w:tblPr')}/{qn('w:tblStyle')}")
        return style is None or "grid" not in (style.get(qn("w:val")) or "").casefold()
    return all(b.get(qn("w:val")) in ("none", "nil", None) for b in borders)


def _tables(doc: DocxDocument) -> list[TableInfo]:
    result = []
    for i, tbl in enumerate(docx_xml.tables_in_order(doc)):
        rows = tbl.findall(docx_xml.W_TR)
        columns = max((len(r.findall(docx_xml.W_TC)) for r in rows), default=0)
        nested = any(a.tag == docx_xml.W_TBL for a in tbl.iterancestors())
        result.append(
            TableInfo(
                index=i, rows=len(rows), columns=columns, nested=nested,
                borderless=_borderless(tbl),
            )
        )  # fmt: skip
    return result


def _text_boxes(doc: DocxDocument) -> list[str]:
    boxes = []
    for box in doc.element.body.iter(docx_xml.W_TXBX):
        if any(a.tag == docx_xml.FALLBACK for a in box.iterancestors()):
            continue
        text = " / ".join(
            "".join(r.text for r in docx_xml.merged_runs(p)) for p in box.iter(docx_xml.W_P)
        )
        boxes.append(text.strip(" /"))
    return boxes


def _images(paras: list[docx_xml.Paragraph]) -> list[ImageInfo]:
    images = []
    ns_a = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
    ns_wp = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
    for p in paras:
        if not p.images:
            continue
        for drawing in p.element.iter(docx_xml.W_DRAWING):
            holder = drawing[0] if len(drawing) else None
            extent = holder.find(f"{ns_wp}extent") if holder is not None else None
            if extent is None:
                continue
            width = int(extent.get("cx", 0)) / EMU_PER_MM
            height = int(extent.get("cy", 0)) / EMU_PER_MM
            geometry = drawing.find(f".//{ns_a}prstGeom")
            prst = geometry.get("prst") if geometry is not None else "rect"
            shape: Literal["circle", "rounded", "square"] = (
                "circle" if prst == "ellipse" else "rounded" if prst == "roundRect" else "square"
            )
            ratio = width / height if height else 0
            images.append(
                ImageInfo(
                    paragraph=p.index,
                    width_mm=round(width, 1),
                    height_mm=round(height, 1),
                    floating=holder is not None and holder.tag == f"{ns_wp}anchor",
                    shape=shape,
                    photo_candidate=0.7 <= ratio <= 1.45 and 15 <= width <= 70,
                )
            )
    return images


# --- Secciones y capacidad ------------------------------------------------------------------


def _title_key(text: str) -> str:
    return fold(text).strip().rstrip(":").strip()


def section_of(p: docx_xml.Paragraph) -> str | None:
    """`summary`, `experience`… si el párrafo es un título de sección; `extra` si lo parece."""
    text = p.text.strip()
    if not text or len(text) > 50 or len(text.split()) > 6 or text.endswith("."):
        return None
    known = SECTION_TITLES.get(_title_key(text))
    if known:
        return known
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 3 or _EMAIL.search(text) or any(c.isdigit() for c in text):
        return None
    style = fold(p.style or "")
    looks_heading = style.startswith(("heading", "titulo", "title")) or text.isupper()
    return "extra" if looks_heading and not p.is_list else None


def _is_bullet(p: docx_xml.Paragraph) -> bool:
    return p.is_list or p.text.lstrip().startswith(_BULLET_GLYPHS)


def _sections(paras: list[docx_xml.Paragraph]) -> list[SectionInfo]:
    found = []
    for p in paras:
        if p.location in ("header", "footer"):
            continue
        section = section_of(p)
        if section:
            found.append(SectionInfo(section=section, title=p.text.strip(), paragraph=p.index))
    return found


def _capacity(
    paras: list[docx_xml.Paragraph], sections: list[SectionInfo], pages: int | None
) -> MeasuredCapacity:
    body = [p for p in paras if p.location not in ("header", "footer")]
    blocks: dict[str, list[docx_xml.Paragraph]] = {}
    for i, section in enumerate(sections):
        end = sections[i + 1].paragraph if i + 1 < len(sections) else len(paras)
        block = [p for p in body if section.paragraph < p.index < end and p.text.strip()]
        blocks.setdefault(section.section, []).extend(block)

    summary = blocks.get("summary")
    experience = blocks.get("experience")
    per_experience: list[int] = []
    if experience is not None:
        current = 0
        for p in experience:
            if _is_bullet(p):
                current += 1
            elif current:
                per_experience.append(current)
                current = 0
        if current:
            per_experience.append(current)
    skills = blocks.get("skills")
    return MeasuredCapacity(
        summary_chars=sum(len(p.text.strip()) for p in summary) if summary is not None else None,
        experience_bullets=sum(per_experience) if experience is not None else None,
        bullets_per_experience=per_experience,
        skill_groups=len(skills) if skills is not None else None,
        pages=pages,
    )


def _ats(
    page: list[PageInfo], tables: list[TableInfo], boxes: list[str], header_footer: list[str]
) -> AtsEstimate:
    reasons = []
    if any(p.columns > 1 for p in page):
        reasons.append("Usa varias columnas de sección: un ATS puede mezclar el orden del texto.")
    if any(t.columns > 1 or t.borderless for t in tables):
        reasons.append("Maqueta con tablas: muchos ATS leen mal las celdas o su orden.")
    if boxes:
        reasons.append("Tiene cuadros de texto: muchos ATS no los leen.")
    joined = " ".join(header_footer)
    if _EMAIL.search(joined) or _PHONE.search(joined):
        reasons.append("Tiene datos de contacto en la cabecera o el pie: muchos ATS no los leen.")
    return AtsEstimate(ats_friendly=not reasons, reasons=reasons)


# --- Entrada --------------------------------------------------------------------------------


def open_docx(path: Path) -> DocxDocument:
    if path.suffix.casefold() != ".docx":
        raise TemplateImportError(
            f"Formato no admitido todavía: {path.suffix or 'sin extensión'}. En esta fase solo "
            ".docx; PDF, imagen y HTML llegan con la fase 08b (exporta el original a Word si "
            "puedes)."
        )
    try:
        return Document(str(path))
    except Exception as exc:
        raise TemplateImportError(f"No se puede leer {path.name} como Word: {exc}") from exc


def count_pages(path: Path) -> tuple[int | None, str | None]:
    """Páginas del original convirtiéndolo a PDF; si no hay conversor, `None` y el motivo."""
    workdir = Path(tempfile.mkdtemp(prefix="jh-inspect-"))
    try:
        copy = workdir / "source.docx"
        shutil.copyfile(path, copy)
        pdf.convert(copy, workdir / "source.pdf")
        return pdf.read_pdf(workdir / "source.pdf").pages, None
    except pdf.PdfConversionError as exc:
        return None, f"No se pudieron contar las páginas: {exc}"
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _run_info(run: docx_xml.Run) -> RunInfo:
    return RunInfo(
        text=run.text, bold=run.bold, italic=run.italic, size=run.size, color=run.color,
        font=run.font,
    )  # fmt: skip


def inspect_docx(path: Path, with_pages: bool = True) -> DocxInspection:
    doc = open_docx(path)
    paras = docx_xml.paragraphs(doc)
    parts = docx_xml.header_footer_parts(doc)
    content_roots = [doc.element.body, *(element for _kind, element in parts)]
    pages, pages_note = count_pages(path) if with_pages else (None, "Sin contar páginas.")
    page = _page_info(doc)
    tables = _tables(doc)
    boxes = _text_boxes(doc)
    header_text = [p.text for p in paras if p.location == "header" and p.text.strip()]
    footer_text = [p.text for p in paras if p.location == "footer" and p.text.strip()]
    sections = _sections(paras)
    return DocxInspection(
        file=str(path),
        format="docx",
        pages=pages,
        pages_note=pages_note,
        page=page,
        fonts=_fonts(doc, paras),
        colors=_colors(content_roots),  # los de los estilos sin usar no dicen nada del diseño
        tables=tables,
        text_boxes=boxes,
        images=_images(paras),
        header_text=header_text,
        footer_text=footer_text,
        sections=sections,
        capacity=_capacity(paras, sections, pages),
        ats=_ats(page, tables, boxes, header_text + footer_text),
        paragraphs=[
            ParagraphInfo(
                index=p.index,
                location=p.location,
                table=p.table,
                row=p.row,
                cell=p.cell,
                style=p.style,
                text=p.text,
                is_list=p.is_list,
                images=p.images,
                runs=[_run_info(r) for r in p.runs],
            )
            for p in paras
        ],
    )
