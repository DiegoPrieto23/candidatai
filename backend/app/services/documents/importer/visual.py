"""`cai templates inspect` para PDF, imagen y HTML (fase 08b): lo que hace falta para recrear el
diseño con el motor html.

- La página (o páginas) en PNG en `data/tmp/inspect/<fichero>/`, para que el agente la vea.
- PDF (y HTML, que se imprime antes con Chromium sin red ni JavaScript): bloques de texto (líneas)
  con posición, tamaño, fuente, negrita y cursiva; fuentes; imágenes y si parecen una foto.
- Todos: paleta de colores dominante y estimación de columnas, barra lateral y márgenes, a partir
  de la imagen de la página.
- Como en Word: secciones en su orden (las que no están en el contrato, `extra`), `capacity`
  medida y estimación de ATS. En una imagen no hay texto: secciones y `capacity` las lee el
  agente en la imagen (`capacity_note`).
"""

import ctypes
import itertools
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Literal

import numpy as np
from PIL import Image, ImageOps
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.documents.importer import TemplateImportError
from app.services.documents.importer.inspect import (
    _BULLET_GLYPHS,
    AtsEstimate,
    MeasuredCapacity,
    PageInfo,
    classify_title,
)

VisualFormat = Literal["pdf", "image", "html"]
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")
HTML_SUFFIXES = (".html", ".htm")
VISUAL_SUFFIXES = (".pdf", *IMAGE_SUFFIXES, *HTML_SUFFIXES)

PT_TO_MM = 25.4 / 72
PAGE_PNG_WIDTH = 1000  # px de las páginas que ve el agente
ANALYSIS_WIDTH = 420  # px para la paleta y las columnas
MAX_PAGES_RENDERED = 3

_SUBSET = re.compile(r"^[A-Z]{6}\+")
_STYLE_SUFFIX = re.compile(r"(PSMT|MT|PS)$")


class TextBlock(BaseModel):
    """Una línea de texto del PDF. Posición desde la esquina superior izquierda, en mm."""

    index: int
    page: int
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    size_pt: float
    font: str | None
    bold: bool
    italic: bool
    text: str


class ImageBox(BaseModel):
    page: int
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float
    photo_candidate: bool  # casi cuadrada y de tamaño de foto de CV


class ColorShare(BaseModel):
    color: str
    share: float  # fracción de la página


class LayoutEstimate(BaseModel):
    columns: int
    column_edges_mm: list[float]  # dónde se separan las columnas (x)
    sidebar: Literal["left", "right"] | None  # barra lateral de color a sangre
    sidebar_color: str | None
    header_band_color: str | None  # banda de color de lado a lado arriba
    background: str
    margins_mm: dict[str, float]


class VisualSection(BaseModel):
    section: str  # una del contrato, `contact` o `extra`
    title: str
    block: int | None  # índice del bloque de texto del título (PDF y HTML)
    column: int  # 0 = la primera por la izquierda


class VisualInspection(BaseModel):
    file: str
    format: VisualFormat
    pages: int
    page: PageInfo
    page_images: list[str]  # relativas a data/
    fonts: list[str]
    colors: list[ColorShare]
    layout: LayoutEstimate
    text_blocks: list[TextBlock]
    images: list[ImageBox]
    sections: list[VisualSection]
    capacity: MeasuredCapacity
    capacity_note: str | None
    ats: AtsEstimate
    notes: list[str]


# --- Imagen de la página: paleta, columnas y márgenes ------------------------------------------


def _hex(rgb: tuple[int, int, int] | np.ndarray) -> str:
    r, g, b = (int(v) for v in rgb[:3])
    return f"#{r:02X}{g:02X}{b:02X}"


def _distance(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    return max(abs(int(x) - int(y)) for x, y in zip(a, b, strict=False))


def palette(image: Image.Image, count: int = 8) -> list[ColorShare]:
    """Colores dominantes (los muy parecidos, juntos), de más a menos superficie."""
    small = image.convert("RGB")
    small.thumbnail((ANALYSIS_WIDTH, ANALYSIS_WIDTH * 2))
    quantized = small.quantize(colors=count * 2, method=Image.Quantize.MEDIANCUT)
    raw_palette = quantized.getpalette() or []
    total = small.width * small.height
    merged: list[tuple[tuple[int, int, int], int]] = []
    for pixels, idx in sorted(quantized.getcolors() or [], reverse=True):
        rgb = tuple(raw_palette[idx * 3 : idx * 3 + 3])
        for i, (known, n) in enumerate(merged):
            if _distance(known, rgb) <= 24:
                merged[i] = (known, n + pixels)
                break
        else:
            merged.append((rgb, pixels))  # type: ignore[arg-type]
    shares = [
        ColorShare(color=_hex(rgb), share=round(n / total, 3))
        for rgb, n in sorted(merged, key=lambda item: -item[1])
        if n / total >= 0.004
    ]
    return shares[:count]


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Tramos `[inicio, fin)` donde `mask` es verdadero."""
    runs, start = [], None
    for i, value in enumerate(mask):
        if value and start is None:
            start = i
        elif not value and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(mask)))
    return runs


def layout(image: Image.Image, width_mm: float) -> LayoutEstimate:
    """Columnas, barra lateral, banda de cabecera y márgenes estimados sobre la imagen."""
    small = image.convert("RGB")
    small.thumbnail((ANALYSIS_WIDTH, ANALYSIS_WIDTH * 2))
    arr = np.asarray(small).astype(np.int16)
    h, w, _ = arr.shape
    mm_per_px = width_mm / w

    # Fondo: el color más frecuente (agrupando el ruido de JPEG), con su valor medio real.
    pixels = arr.reshape(-1, 3)
    bins = pixels // 8
    keys, inverse, counts = np.unique(bins, axis=0, return_inverse=True, return_counts=True)
    background = tuple(
        int(round(v)) for v in pixels[inverse.ravel() == counts.argmax()].mean(axis=0)
    )
    busy = np.abs(arr - np.array(background)).max(axis=2) > 40

    # Barra lateral a sangre: columnas desde un borde casi llenas de otro color.
    body = busy[int(h * 0.25) : int(h * 0.95)]
    col_fill = body.mean(axis=0)
    sidebar: Literal["left", "right"] | None = None
    sidebar_color = None
    edges: list[float] = []
    for side in ("left", "right"):
        series = col_fill if side == "left" else col_fill[::-1]
        run = 0
        while run < w and series[run] > 0.85:
            run += 1
        if 0.15 * w <= run <= 0.5 * w:
            sidebar = side  # type: ignore[assignment]
            x = run if side == "left" else w - run
            edges = [round(x * mm_per_px, 1)]
            region = (
                arr[int(h * 0.25) : int(h * 0.95), :run]
                if side == "left"
                else arr[int(h * 0.25) : int(h * 0.95), w - run :]
            )
            sidebar_color = _hex(np.median(region.reshape(-1, 3), axis=0))
            break

    if sidebar is None:
        # Calles: columnas vacías en el interior con contenido a los dos lados.
        min_gap = max(int(3 / mm_per_px), 2)
        lo, hi = int(w * 0.2), int(w * 0.8)
        for start, end in _runs(col_fill[lo:hi] < 0.004):
            start, end = start + lo, end + lo
            if end - start < min_gap:
                continue
            if col_fill[:start].mean() > 0.02 and col_fill[end:].mean() > 0.02:
                edges.append(round((start + end) / 2 * mm_per_px, 1))

    # Banda de color de lado a lado en la parte de arriba.
    header_band_color = None
    full_rows = np.zeros(h, dtype=bool)
    full_rows[: int(h * 0.3)] = busy[: int(h * 0.3)].mean(axis=1) > 0.9
    if full_rows.sum() > h * 0.03:
        band = arr[full_rows]
        header_band_color = _hex(np.median(band.reshape(-1, 3), axis=0))
    else:
        full_rows[:] = False

    # Márgenes: del borde de la página al contenido sobre el fondo (sin banda ni barra lateral).
    content = busy.copy()
    if header_band_color is not None:
        last_band = int(np.flatnonzero(full_rows)[-1])
        content[: last_band + 1] = False
    if sidebar is not None:
        edge_px = int(round(edges[0] / mm_per_px))
        if sidebar == "left":
            content[:, :edge_px] = False
        else:
            content[:, edge_px:] = False

    def first(fill: np.ndarray) -> int:
        hits = np.flatnonzero(fill > 0.002)
        return int(hits[0]) if hits.size else 0

    def last(fill: np.ndarray) -> int:
        hits = np.flatnonzero(fill > 0.002)
        return int(len(fill) - 1 - hits[-1]) if hits.size else 0

    rows_fill, cols_fill = content.mean(axis=1), content.mean(axis=0)
    margins = {
        "top": round(first(rows_fill) * mm_per_px, 1),
        "right": round(last(cols_fill) * mm_per_px, 1),
        "bottom": round(last(rows_fill) * mm_per_px, 1),
        "left": round(first(cols_fill) * mm_per_px, 1),
    }
    return LayoutEstimate(
        columns=len(edges) + 1,
        column_edges_mm=edges,
        sidebar=sidebar,
        sidebar_color=sidebar_color,
        header_band_color=header_band_color,
        background=_hex(background),
        margins_mm=margins,
    )


def page_info(
    width_mm: float, height_mm: float, columns: int, margins: dict[str, float]
) -> PageInfo:
    kind: Literal["A4", "Letter", "other"] = "other"
    if abs(width_mm - 210) < 3 and abs(height_mm - 297) < 3:
        kind = "A4"
    elif abs(width_mm - 215.9) < 3 and abs(height_mm - 279.4) < 3:
        kind = "Letter"
    return PageInfo(
        width_mm=round(width_mm, 1),
        height_mm=round(height_mm, 1),
        size=kind,
        columns=columns,
        margins_mm=margins,
    )


# --- PDF: texto, fuentes e imágenes ---------------------------------------------------------


def font_family(name: str | None) -> str | None:
    """`ABCDEF+Arial-BoldMT` → `Arial`; `Lato-Regular` → `Lato`."""
    if not name:
        return None
    base = _SUBSET.sub("", name).split(",")[0].split("-")[0]
    return _STYLE_SUFFIX.sub("", base) or base


class _Char:
    __slots__ = ("text", "left", "right", "top", "bottom", "oy", "size", "font", "bold", "italic")

    def __init__(self, **values: object) -> None:
        for key, value in values.items():
            setattr(self, key, value)


def _chars(textpage: object) -> list[_Char | None]:
    """Caracteres con su caja y su fuente; `None` es un salto de línea."""
    import pypdfium2.raw as pdfium_c

    raw = textpage.raw  # type: ignore[attr-defined]
    chars: list[_Char | None] = []
    buffer = ctypes.create_string_buffer(256)
    flags = ctypes.c_int()
    ox, oy = ctypes.c_double(), ctypes.c_double()
    matrix = pdfium_c.FS_MATRIX()
    for i in range(textpage.count_chars()):  # type: ignore[attr-defined]
        text = textpage.get_text_range(i, 1)  # type: ignore[attr-defined]
        if text in ("\r", "\n", "\r\n"):
            chars.append(None)
            continue
        if text == " " and pdfium_c.FPDFText_IsGenerated(raw, i) == 1:
            # Espacio deducido por pdfium de un hueco: con `letter-spacing` parte las palabras
            # («HABI L IDADES»). Los espacios se ponen en `_line_text` según los huecos reales.
            continue
        # Caja holgada (avance del glifo): con la ajustada a la tinta, una «I» deja huecos.
        left, bottom, right, top = textpage.get_charbox(i, loose=True)  # type: ignore[attr-defined]
        pdfium_c.FPDFText_GetCharOrigin(raw, i, ctypes.byref(ox), ctypes.byref(oy))
        # Tamaño efectivo: el de la fuente por la escala de la matriz (Chromium dibuja en px ×
        # 0,75, así que sin ella 10 pt saldrían 13,3).
        pdfium_c.FPDFText_GetMatrix(raw, i, ctypes.byref(matrix))
        scale = abs(matrix.a * matrix.d - matrix.b * matrix.c) ** 0.5 or 1.0
        size = pdfium_c.FPDFText_GetFontSize(raw, i) * scale
        length = pdfium_c.FPDFText_GetFontInfo(raw, i, buffer, 256, ctypes.byref(flags))
        font = buffer.value.decode("utf-8", "replace") if length else None
        name = (font or "").casefold()
        chars.append(
            _Char(
                text=text,
                left=left,
                right=right,
                top=top,
                bottom=bottom,
                oy=oy.value,
                size=size,
                font=_SUBSET.sub("", font) if font else None,
                # El peso que da pdfium no es fiable (una cursiva sale con 645): nombre y flags.
                bold=bool(flags.value & (1 << 18))
                or any(w in name for w in ("bold", "black", "heavy", "semibold", "demi")),
                italic=bool(flags.value & (1 << 6)) or "italic" in name or "oblique" in name,
            )
        )
    return chars


def _lines(chars: list[_Char | None]) -> list[list[_Char]]:
    """Agrupa los caracteres en líneas: mismo renglón y sin saltos grandes (otra columna)."""
    lines: list[list[_Char]] = []
    current: list[_Char] = []
    for ch in chars:
        if ch is None:
            if current:
                lines.append(current)
                current = []
            continue
        if current and ch.text.strip():
            visible = [c for c in current if c.text.strip()]
            prev = visible[-1] if visible else current[-1]
            size = max(prev.size, ch.size, 1)
            new_row = abs(ch.oy - prev.oy) > size * 0.45
            jump = ch.left - prev.right > size * 1.6 or ch.right < prev.left - size
            if new_row or jump:
                lines.append(current)
                current = []
        if ch.text.strip() or current:
            current.append(ch)
    if current:
        lines.append(current)
    return [line for line in lines if "".join(c.text for c in line).strip()]


def _block(index: int, page: int, line: list[_Char], page_height: float) -> TextBlock:
    visible = [c for c in line if c.text.strip()]
    left = min(c.left for c in visible)
    right = max(c.right for c in visible)
    top = max(c.top for c in visible)
    bottom = min(c.bottom for c in visible)
    sizes = Counter(round(c.size, 1) for c in visible)
    fonts = Counter(c.font for c in visible)
    return TextBlock(
        index=index,
        page=page,
        x_mm=round(left * PT_TO_MM, 1),
        y_mm=round((page_height - top) * PT_TO_MM, 1),
        width_mm=round((right - left) * PT_TO_MM, 1),
        height_mm=round((top - bottom) * PT_TO_MM, 1),
        size_pt=sizes.most_common(1)[0][0],
        font=fonts.most_common(1)[0][0],
        bold=sum(c.bold for c in visible) > len(visible) / 2,
        italic=sum(c.italic for c in visible) > len(visible) / 2,
        text=_line_text(line),
    )


def _line_text(line: list[_Char]) -> str:
    """El texto de la línea, con un espacio donde hay un hueco de palabra.

    Chromium no escribe los espacios como caracteres: se deducen de los huecos. El umbral es el
    hueco típico entre letras de la línea (que con `letter-spacing` no es cero) más un 12 % del
    cuerpo de letra, así que «H A B I L I D A D E S» espaciado sigue siendo una palabra.
    """
    gaps = [
        b.left - a.right for a, b in itertools.pairwise(line) if a.text.strip() and b.text.strip()
    ]
    typical = float(np.median(gaps)) if gaps else 0.0
    parts: list[str] = []
    previous: _Char | None = None
    for ch in line:
        if (
            previous is not None
            and ch.text.strip()
            and previous.text.strip()
            and ch.left - previous.right > max(typical, 0) + max(ch.size, previous.size) * 0.12
        ):
            parts.append(" ")
        parts.append(ch.text)
        previous = ch
    return " ".join("".join(parts).split())


def _pdf_content(path: Path) -> tuple[int, float, float, list[TextBlock], list[ImageBox]]:
    import pypdfium2
    import pypdfium2.raw as pdfium_c

    try:
        document = pypdfium2.PdfDocument(path)
    except Exception as exc:
        raise TemplateImportError(f"No se puede leer {path.name} como PDF: {exc}") from exc
    try:
        pages = len(document)
        if not pages:
            raise TemplateImportError(f"{path.name} no tiene páginas.")
        width, height = document[0].get_size()
        blocks: list[TextBlock] = []
        images: list[ImageBox] = []
        for number in range(min(pages, MAX_PAGES_RENDERED)):
            page = document[number]
            page_height = page.get_height()
            textpage = page.get_textpage()
            for line in _lines(_chars(textpage)):
                blocks.append(_block(len(blocks), number + 1, line, page_height))
            for obj in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE], max_depth=3):
                left, bottom, right, top = obj.get_bounds()
                w_mm, h_mm = (right - left) * PT_TO_MM, (top - bottom) * PT_TO_MM
                ratio = w_mm / h_mm if h_mm else 0
                images.append(
                    ImageBox(
                        page=number + 1,
                        x_mm=round(left * PT_TO_MM, 1),
                        y_mm=round((page_height - top) * PT_TO_MM, 1),
                        width_mm=round(w_mm, 1),
                        height_mm=round(h_mm, 1),
                        photo_candidate=0.7 <= ratio <= 1.35 and 15 <= w_mm <= 70,
                    )
                )
        return pages, width * PT_TO_MM, height * PT_TO_MM, blocks, images
    finally:
        document.close()


# --- Secciones y capacidad ------------------------------------------------------------------


def _column_of(x_mm: float, edges: list[float]) -> int:
    return sum(1 for edge in edges if x_mm >= edge - 1)


def _sections(blocks: list[TextBlock], edges: list[float]) -> list[VisualSection]:
    """Títulos de sección. Los `extra` tienen que parecerse a los conocidos (misma fuente y
    tamaño): así un nombre grande o un puesto en negrita no cuentan como sección."""
    if not blocks:
        return []
    body = Counter(b.size_pt for b in blocks for _ in b.text).most_common(1)[0][0]
    largest = max(b.size_pt for b in blocks)
    candidates = []
    for b in blocks:
        upper = b.text.isupper() and len(b.text) > 3
        heading = b.bold or b.size_pt > body * 1.12 or upper
        section = classify_title(b.text, heading, b.text.lstrip().startswith(_BULLET_GLYPHS))
        if section and (heading or section != "extra"):
            candidates.append((b, section))
    known_styles = {(b.font, b.size_pt, b.text.isupper()) for b, s in candidates if s != "extra"}
    found = []
    for b, section in candidates:
        if section == "extra":
            style = (b.font, b.size_pt, b.text.isupper())
            if known_styles and style not in known_styles:
                continue
            if not known_styles and (b.size_pt >= largest or b.index < 2):
                continue  # sin títulos conocidos: el nombre (lo más grande, arriba) no es sección
        found.append(
            VisualSection(
                section=section, title=b.text, block=b.index, column=_column_of(b.x_mm, edges)
            )
        )
    return found


LineKind = Literal["bullet", "continuation", "other"]


def _line_kinds(blocks: list[TextBlock], base_x: float) -> list[LineKind]:
    """Qué es cada línea de una sección: un logro, su continuación u otra cosa (rol, empresa,
    fechas). Un logro empieza con viñeta de texto o con sangría: las viñetas de las listas HTML
    se dibujan y no son texto."""
    kinds: list[LineKind] = []
    previous: TextBlock | None = None
    for b in blocks:
        in_list = bool(kinds) and kinds[-1] in ("bullet", "continuation")
        same_row = previous is not None and abs(b.y_mm - previous.y_mm) < 1
        indented = base_x + 1.5 < b.x_mm < base_x + 15
        if b.text.lstrip().startswith(_BULLET_GLYPHS):
            kind: LineKind = "bullet"
        elif same_row:
            kind = "other"  # fechas a la derecha del rol
        elif in_list and b.text[:1].islower():
            kind = "continuation"
        elif indented and not b.bold:
            kind = "bullet"
        else:
            kind = "other"
        kinds.append(kind)
        previous = b
    return kinds


def _capacity(
    blocks: list[TextBlock], sections: list[VisualSection], pages: int
) -> MeasuredCapacity:
    """Como en Word, pero por líneas: cada sección va de su título al siguiente de su columna."""
    by_section: dict[str, list[TextBlock]] = {}
    base_x: dict[str, float] = {}
    for i, section in enumerate(sections):
        following = [s for s in sections[i + 1 :] if s.column == section.column]
        end = following[0].block if following else len(blocks)
        assert section.block is not None
        title = blocks[section.block]
        block = [
            b for b in blocks[section.block + 1 : end] if b.page in (title.page, title.page + 1)
        ]
        by_section.setdefault(section.section, []).extend(block)
        base_x.setdefault(section.section, title.x_mm)

    summary = by_section.get("summary")
    experience = by_section.get("experience")
    per_experience: list[int] = []
    if experience is not None:
        current = 0
        for kind in _line_kinds(experience, base_x["experience"]):
            if kind == "bullet":
                current += 1
            elif kind == "other" and current:
                per_experience.append(current)  # rol o empresa: empieza otra experiencia
                current = 0
        if current:
            per_experience.append(current)
    skills = by_section.get("skills")
    groups = None
    if skills is not None:
        # Grupos con nombre en negrita («Datos» y debajo sus skills): cuentan los nombres.
        named = [b for b in skills if b.bold]
        groups = len(named) if named and len(named) < len(skills) else len(skills)
    return MeasuredCapacity(
        summary_chars=sum(len(b.text) for b in summary) if summary is not None else None,
        experience_bullets=sum(per_experience) if experience is not None else None,
        bullets_per_experience=per_experience,
        skill_groups=groups,
        pages=pages,
    )


def _ats(columns: int, has_text: bool, header_band: bool) -> AtsEstimate:
    reasons = []
    if not has_text:
        reasons.append("No tiene texto seleccionable (es una imagen): un ATS no lee nada.")
    if columns > 1:
        reasons.append("Usa varias columnas: un ATS puede mezclar el orden del texto.")
    if header_band:
        reasons.append(
            "Cabecera en una banda de color: suele hacerse con capas que un ATS lee mal."
        )
    reasons.append("Plantilla html: solo PDF, sin Word para portales que lo pidan.")
    return AtsEstimate(ats_friendly=False, reasons=reasons)


# --- Entrada --------------------------------------------------------------------------------


def _out_dir(source: Path) -> Path:
    safe = re.sub(r"[^\w.-]+", "-", source.stem).strip("-") or "cv"
    folder = get_settings().tmp_dir / "inspect" / safe
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _relative(path: Path) -> str:
    return path.resolve().relative_to(get_settings().data_dir.resolve()).as_posix()


def open_image(path: Path) -> Image.Image:
    try:
        with Image.open(path) as image:
            return ImageOps.exif_transpose(image).convert("RGB")
    except Exception as exc:
        raise TemplateImportError(f"No se puede abrir {path.name} como imagen: {exc}") from exc


def print_html(source: Path, output: Path) -> Path:
    """Imprime un HTML a PDF con el motor html: saneado, sin red ni JavaScript.

    No sirve ningún otro fichero: su carpeta es `data/uploads/`, con los demás CVs subidos, y un
    HTML ajeno podría incrustarlos. Imágenes y fuentes propias del HTML no se ven (el agente
    recrea el diseño mirando la página).
    """
    from app.services.documents.engines import html as html_engine

    text = source.read_text(encoding="utf-8", errors="replace")
    return html_engine.html_to_pdf(text, lambda _relative: None, output)


def source_pages_png(source: Path, out_dir: Path) -> tuple[VisualFormat, list[Path], Path | None]:
    """El original como PNG por página (hasta 3) y, si lo hay, el PDF del que salen."""
    from app.services.documents.preview import pdf_to_png

    suffix = source.suffix.casefold()
    if suffix in IMAGE_SUFFIXES:
        image = open_image(source)
        image.thumbnail((PAGE_PNG_WIDTH, PAGE_PNG_WIDTH * 2))
        png = out_dir / "page-1.png"
        image.save(png, format="PNG", optimize=True)
        return "image", [png], None
    if suffix in HTML_SUFFIXES:
        pdf_file = print_html(source, out_dir / "source.pdf")
        kind: VisualFormat = "html"
    elif suffix == ".pdf":
        pdf_file = source
        kind = "pdf"
    else:
        raise TemplateImportError(
            f"Formato no admitido: {suffix or 'sin extensión'}. Admite .docx, .pdf, .png, .jpg "
            "y .html."
        )
    import pypdfium2

    try:
        count = len(pypdfium2.PdfDocument(pdf_file))
    except Exception as exc:
        raise TemplateImportError(f"No se puede leer {source.name} como PDF: {exc}") from exc
    pngs = [
        pdf_to_png(pdf_file, out_dir / f"page-{n + 1}.png", PAGE_PNG_WIDTH, page_index=n)
        for n in range(min(count, MAX_PAGES_RENDERED))
    ]
    return kind, pngs, pdf_file


def inspect_visual(path: Path) -> VisualInspection:
    out_dir = _out_dir(path)
    kind, pngs, pdf_file = source_pages_png(path, out_dir)
    with Image.open(pngs[0]) as first_page:
        image = first_page.convert("RGB")

    notes: list[str] = []
    if pdf_file is not None:
        pages, width_mm, height_mm, blocks, images = _pdf_content(pdf_file)
        if kind == "html":
            notes.append(
                "HTML impreso con Chromium sin red ni JavaScript: recursos remotos y scripts "
                "del original no cuentan."
            )
    else:
        pages, blocks, images = 1, [], []
        ratio = image.height / image.width
        width_mm = 215.9 if abs(ratio - 279.4 / 215.9) < abs(ratio - 297 / 210) else 210.0
        height_mm = width_mm * ratio

    estimate = layout(image, width_mm)
    sections = _sections(blocks, estimate.column_edges_mm)
    capacity = _capacity(blocks, sections, pages)
    capacity_note = None
    if not blocks:
        capacity_note = (
            "Sin texto que leer: mira la imagen de la página (`page_images`) y decide tú las "
            "secciones en su orden (pásalas a `scaffold-html --sections`) y la `capacity` "
            "(caracteres del perfil, logros por experiencia, grupos de habilidades)."
        )
        notes.append(capacity_note)
    elif not sections:
        notes.append(
            "No se reconoció ningún título de sección: decide las secciones mirando la imagen."
        )
    fonts = list(dict.fromkeys(f for b in blocks if (f := font_family(b.font))))
    return VisualInspection(
        file=str(path),
        format=kind,
        pages=pages,
        page=page_info(width_mm, height_mm, estimate.columns, estimate.margins_mm),
        page_images=[_relative(p) for p in pngs],
        fonts=fonts,
        colors=palette(image),
        layout=estimate,
        text_blocks=blocks,
        images=images,
        sections=sections,
        capacity=capacity,
        capacity_note=capacity_note,
        ats=_ats(estimate.columns, bool(blocks), estimate.header_band_color is not None),
        notes=notes,
    )


def is_visual(path: Path) -> bool:
    return path.suffix.casefold() in VISUAL_SUFFIXES
