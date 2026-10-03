"""Genera las plantillas integradas de CV en `templates/` con python-docx (reproducible).

Uso (desde la raíz del repo):
    uv run --directory backend python ../scripts/build_builtin_templates.py [--no-preview]

Cada plantilla se crea desde cero: `template.docx` (con los marcadores de docxtpl de una pieza,
cada uno en su propio fragmento) y `template.yaml`. Dos ejecuciones dan exactamente los mismos
bytes: el zip se escribe con fecha fija y las propiedades del documento no llevan fechas.
También dibuja la foto FICTICIA del perfil demo (`demo/photo.png`, una silueta). Después, salvo
`--no-preview`, renderiza `preview.pdf` y `preview.png` con el perfil, el contenido y la foto
FICTICIOS de `demo/` (necesita LibreOffice o Word y, para las html, Chromium de Playwright).

Las plantillas html (`moderna-2col`) se escriben a mano (`template.html`, `style.css`, `fonts/`):
este script solo regenera su preview.
"""

import argparse
import io
import sys
import zipfile
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Mm, Pt, RGBColor
from docx.text.paragraph import Paragraph

from app.core.config import REPO_ROOT

TEMPLATES_DIR = REPO_ROOT / "templates"
_FIXED_ZIP_DATE = (1980, 1, 1, 0, 0, 0)
_FIXED_CORE_DATE = datetime(2026, 1, 1)

TEXT = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x55, 0x55, 0x55)


# --- Utilidades de python-docx --------------------------------------------------------------


def _bottom_border(paragraph: Paragraph, color: str = "808080") -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    borders = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    for key, value in {"w:val": "single", "w:sz": "4", "w:space": "1", "w:color": color}.items():
        bottom.set(qn(key), value)
    borders.append(bottom)
    p_pr.append(borders)


def _spacing(paragraph: Paragraph, before: float = 0, after: float = 0) -> None:
    paragraph.paragraph_format.space_before = Pt(before)
    paragraph.paragraph_format.space_after = Pt(after)


def _add(doc: Any, *runs: tuple[str, dict[str, Any]] | str, style: str | None = None) -> Paragraph:
    """Párrafo con un fragmento por elemento: cada marcador queda entero en su fragmento."""
    paragraph = doc.add_paragraph(style=style)
    for item in runs:
        text, fmt = (item, {}) if isinstance(item, str) else item
        run = paragraph.add_run(text)
        run.bold = fmt.get("bold")
        run.italic = fmt.get("italic")
        if "size" in fmt:
            run.font.size = Pt(fmt["size"])
        if "color" in fmt:
            run.font.color.rgb = fmt["color"]
    return paragraph


def _tag(doc: Any, tag: str) -> None:
    """Párrafo de control de docxtpl (`{%p … %}`): desaparece al renderizar."""
    doc.add_paragraph(tag)


def _base_document(font: str, size: float) -> Any:
    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Mm(210), Mm(297)
    for side in ("left_margin", "right_margin"):
        setattr(section, side, Mm(18))
    section.top_margin = section.bottom_margin = Mm(15)

    normal = doc.styles["Normal"]
    normal.font.name = font
    normal.font.size = Pt(size)
    normal.font.color.rgb = TEXT
    # El nombre de la fuente también para texto asiático y complejo: si no, Word usa otra.
    r_fonts = normal.element.get_or_add_rPr().get_or_add_rFonts()
    for attr in ("w:ascii", "w:hAnsi", "w:eastAsia", "w:cs"):
        r_fonts.set(qn(attr), font)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.line_spacing = 1.05

    bullet = doc.styles["List Bullet"]
    bullet.font.name = font
    bullet.font.size = Pt(size)
    bullet.paragraph_format.space_after = Pt(1)

    core = doc.core_properties
    core.author = core.last_modified_by = "Job Hunter"
    core.title = core.subject = core.keywords = core.comments = ""
    core.created = core.modified = _FIXED_CORE_DATE
    core.revision = 1
    return doc


def _section(doc: Any, name: str, body: Callable[[], None]) -> None:
    _tag(doc, f"{{%p if show.{name} %}}")
    _heading(doc, f"{{{{ labels.{name}|upper }}}}")
    body()
    _tag(doc, "{%p endif %}")


def _heading(doc: Any, text: str) -> None:
    heading = _add(doc, (text, {"bold": True, "size": 11}))
    _spacing(heading, before=8, after=3)
    _bottom_border(heading)


# Secciones extra del perfil (voluntariado, premios…): cada una con su propio título.
EXTRA_ITEM = (
    "{{ i.text }}",
    ("{% if i.date %} · {{ i.date }}{% endif %}", {"color": MUTED, "size": 9.5}),
)


def _extra_sections(doc: Any, heading: Callable[[Any, str], None]) -> None:
    _tag(doc, "{%p if show.extra_sections %}")
    _tag(doc, "{%p for x in extra_sections %}")
    heading(doc, "{{ x.title|upper }}")
    _tag(doc, "{%p for i in x.items %}")
    _add(doc, *EXTRA_ITEM, style="List Bullet")
    _tag(doc, "{%p endfor %}")
    _tag(doc, "{%p endfor %}")
    _tag(doc, "{%p endif %}")


def _save_reproducible(doc: Any, path: Path) -> None:
    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    out = io.BytesIO()
    with zipfile.ZipFile(buffer) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as dst:
        for info in sorted(src.infolist(), key=lambda i: i.filename):
            data = src.read(info.filename)
            fixed = zipfile.ZipInfo(info.filename, date_time=_FIXED_ZIP_DATE)
            fixed.compress_type = zipfile.ZIP_DEFLATED
            fixed.external_attr = 0o644 << 16
            dst.writestr(fixed, data)
    path.write_bytes(out.getvalue())


# --- ats-simple -----------------------------------------------------------------------------

ATS_SIMPLE_META: dict[str, Any] = {
    "id": "ats-simple",
    "name": "ATS sencilla",
    "engine": "docx",
    "origin": "builtin",
    "description": (
        "Una columna, sin foto ni tablas, con los datos de contacto en el cuerpo y tipografía "
        "estándar. La opción segura para portales con ATS."
    ),
    "tags": ["ats", "sobria"],
    "layout": {"columns": 1, "uses_tables": False},
    "ats_friendly": True,
    "photo": {"supported": False, "shape": "circle", "size_mm": 30},
    "page": {"size": "A4", "max_pages": 1},
    "capacity": {"summary_chars": 450, "experience_bullets": 9, "skill_groups": 4},
    "sections": [
        "summary",
        "experience",
        "projects",
        "education",
        "certifications",
        "extra_sections",
        "skills",
        "languages",
    ],
    "fonts": ["Calibri"],
    "languages": ["es", "en"],
    "letter": {"file": "letter.docx"},
}

CONTACT_LINE = (
    "{{ [contact.city, contact.phone, contact.email, contact.linkedin, contact.github]"
    "|select|join('  ·  ') }}"
)


def _ats_header(doc: Any) -> Paragraph:
    """Nombre, subtítulo y contacto de `ats-simple` (CV y carta). Devuelve la línea de contacto."""
    name = _add(doc, ("{{ name }}", {"bold": True, "size": 20}))
    _spacing(name, after=1)
    subtitle = _add(doc, ("{{ subtitle }}", {"size": 11.5, "color": MUTED}))
    _spacing(subtitle, after=2)
    return _add(doc, (CONTACT_LINE, {"size": 9.5}))


def build_ats_simple_letter(dest: Path) -> None:
    doc = _base_document("Calibri", 11)
    contact = _ats_header(doc)
    _spacing(contact, after=4)
    _bottom_border(contact)
    _letter_body(doc)
    _save_reproducible(doc, dest / "letter.docx")


def build_ats_simple(dest: Path) -> None:
    doc = _base_document("Calibri", 10.5)
    _ats_header(doc)

    _section(doc, "summary", lambda: _add(doc, "{{ summary }}"))

    def experience() -> None:
        _tag(doc, "{%p for e in experience %}")
        role = _add(
            doc,
            ("{{ e.role }}", {"bold": True}),
            " — ",
            "{{ e.company }}",
            "{% if e.city %}, {{ e.city }}{% endif %}",
        )
        _spacing(role, before=4)
        _add(doc, ("{{ e.start }} – {{ e.end }}", {"italic": True, "color": MUTED, "size": 9.5}))
        _tag(doc, "{%p for b in e.bullets %}")
        _add(doc, "{{ b }}", style="List Bullet")
        _tag(doc, "{%p endfor %}")
        _tag(doc, "{%p endfor %}")

    _section(doc, "experience", experience)

    def projects() -> None:
        _tag(doc, "{%p for p in projects %}")
        title = _add(
            doc,
            ("{{ p.name }}", {"bold": True}),
            ("{% if p.date %} · {{ p.date }}{% endif %}", {"color": MUTED, "size": 9.5}),
        )
        _spacing(title, before=3)
        _tag(doc, "{%p for b in p.bullets %}")
        _add(doc, "{{ b }}", style="List Bullet")
        _tag(doc, "{%p endfor %}")
        _tag(doc, "{%p endfor %}")

    _section(doc, "projects", projects)

    def education() -> None:
        _tag(doc, "{%p for ed in education %}")
        _add(
            doc,
            ("{{ ed.title }}", {"bold": True}),
            " — {{ ed.center }}",
            ("{% if ed.end %} · {% if ed.start %}{{ ed.start }} – {% endif %}{{ ed.end }}"
             "{% endif %}", {"color": MUTED, "size": 9.5}),
        )  # fmt: skip
        _tag(doc, "{%p if ed.detail %}")
        _add(doc, "{{ ed.detail }}")
        _tag(doc, "{%p endif %}")
        _tag(doc, "{%p endfor %}")

    _section(doc, "education", education)

    def certifications() -> None:
        _tag(doc, "{%p for c in certifications %}")
        _add(
            doc,
            ("{{ c.name }}", {"bold": True}),
            "{% if c.issuer %} — {{ c.issuer }}{% endif %}",
            ("{% if c.date %} · {{ c.date }}{% endif %}", {"color": MUTED, "size": 9.5}),
        )
        _tag(doc, "{%p endfor %}")

    _section(doc, "certifications", certifications)
    _extra_sections(doc, _heading)

    def skills() -> None:
        _tag(doc, "{%p for s in skills %}")
        _add(doc, ("{{ s.group }}: ", {"bold": True}), "{{ s.items|join(', ') }}")
        _tag(doc, "{%p endfor %}")

    _section(doc, "skills", skills)

    languages_line = "{% for l in languages %}{{ l.language }}: {{ l.level }}{% if not loop.last %}  ·  {% endif %}{% endfor %}"  # noqa: E501
    _section(doc, "languages", lambda: _add(doc, languages_line))

    dest.mkdir(parents=True, exist_ok=True)
    _save_reproducible(doc, dest / "template.docx")
    build_ats_simple_letter(dest)
    (dest / "template.yaml").write_text(
        yaml.safe_dump(ATS_SIMPLE_META, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


# --- clasica-foto ---------------------------------------------------------------------------

ACCENT_COLORS = ["#1F4E79", "#2E5E4E", "#7A2E39", "#3F3F46"]  # azul, verde, granate, grafito
ACCENT = "{{ accent_color[1:] }}"  # Word guarda el color sin «#»: va en el atributo `w:val`

CLASICA_FOTO_META: dict[str, Any] = {
    "id": "clasica-foto",
    "name": "Clásica con foto",
    "engine": "docx",
    "origin": "builtin",
    "description": (
        "Una columna, cabecera con foto circular y color de acento en el nombre y los títulos. "
        "Sobria, para enviar por email o a empresas sin ATS."
    ),
    "tags": ["clasica", "foto", "sobria"],
    "layout": {"columns": 1, "uses_tables": True},
    "ats_friendly": False,
    "photo": {"supported": True, "shape": "circle", "size_mm": 30},
    "page": {"size": "A4", "max_pages": 1},
    "capacity": {"summary_chars": 400, "experience_bullets": 8, "skill_groups": 4},
    "sections": list(ATS_SIMPLE_META["sections"]),
    "options": {"accent_color": {"default": ACCENT_COLORS[0], "choices": ACCENT_COLORS}},
    "fonts": ["Cambria", "Calibri"],
    "languages": ["es", "en"],
    "letter": {"file": "letter.docx"},
}

TEXT_WIDTH_MM = 210 - 2 * 18


def _accent_run(paragraph: Paragraph, text: str, **fmt: Any) -> None:
    """Fragmento con el color de acento (marcador en el atributo, no en el texto)."""
    run = paragraph.add_run(text)
    run.bold = fmt.get("bold")
    if "size" in fmt:
        run.font.size = Pt(fmt["size"])
    if "font" in fmt:
        run.font.name = fmt["font"]
        run._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:hAnsi"), fmt["font"])
    color = OxmlElement("w:color")
    color.set(qn("w:val"), ACCENT)
    run._r.get_or_add_rPr().append(color)


def _right_tab(paragraph: Paragraph) -> None:
    from docx.enum.text import WD_TAB_ALIGNMENT

    paragraph.paragraph_format.tab_stops.add_tab_stop(Mm(TEXT_WIDTH_MM), WD_TAB_ALIGNMENT.RIGHT)


def _no_table_borders(table: Any) -> None:
    tbl_pr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        element = OxmlElement(f"w:{edge}")
        element.set(qn("w:val"), "nil")
        borders.append(element)
    tbl_pr.append(borders)


def _header_text(container: Any) -> None:
    """Nombre, subtítulo y contacto (en el cuerpo o en la celda de la cabecera con foto)."""
    name = container.add_paragraph()
    _accent_run(name, "{{ name }}", bold=True, size=22, font="Cambria")
    _spacing(name, after=1)
    subtitle = _add(container, ("{{ subtitle }}", {"size": 12, "color": MUTED}))
    _spacing(subtitle, after=3)
    _add(container, (CONTACT_LINE, {"size": 9.5}))


def _classic_section(doc: Any, name: str, body: Callable[[], None]) -> None:
    _tag(doc, f"{{%p if show.{name} %}}")
    _classic_heading(doc, f"{{{{ labels.{name}|upper }}}}")
    body()
    _tag(doc, "{%p endif %}")


def _classic_heading(doc: Any, text: str) -> None:
    heading = doc.add_paragraph()
    _accent_run(heading, text, bold=True, size=11, font="Cambria")
    _spacing(heading, before=9, after=3)
    _bottom_border(heading, color=ACCENT)


def _clasica_header(doc: Any) -> None:
    """Cabecera de `clasica-foto` (CV y carta): con foto, una tabla sin bordes (foto | texto)."""
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT

    _tag(doc, "{%p if photo %}")
    photo_col = Mm(CLASICA_FOTO_META["photo"]["size_mm"] + 6)
    table = doc.add_table(rows=1, cols=2)
    table.autofit = False
    _no_table_borders(table)
    left, right = table.rows[0].cells
    # El ancho va en la rejilla (`gridCol`, lo que lee LibreOffice) y en cada celda (Word).
    for column, cell, width in zip(
        table.columns, (left, right), (photo_col, Mm(TEXT_WIDTH_MM) - photo_col), strict=True
    ):
        column.width = cell.width = width
    layout = OxmlElement("w:tblLayout")
    layout.set(qn("w:type"), "fixed")
    table._tbl.tblPr.append(layout)
    left.vertical_alignment = right.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
    left.paragraphs[0].add_run("{{ photo }}")
    _header_text(right)
    right.paragraphs[0]._p.getparent().remove(right.paragraphs[0]._p)  # el vacío inicial
    _tag(doc, "{%p else %}")
    _header_text(doc)
    _tag(doc, "{%p endif %}")


def build_clasica_foto_letter(dest: Path) -> None:
    doc = _base_document("Calibri", 11)
    _clasica_header(doc)
    rule = doc.add_paragraph()
    _spacing(rule, before=4)
    _bottom_border(rule, color=ACCENT)
    _letter_body(doc)
    _save_reproducible(doc, dest / "letter.docx")


def build_clasica_foto(dest: Path) -> None:
    doc = _base_document("Calibri", 10.5)
    _clasica_header(doc)

    _classic_section(doc, "summary", lambda: _add(doc, "{{ summary }}"))

    def experience() -> None:
        _tag(doc, "{%p for e in experience %}")
        role = _add(
            doc,
            ("{{ e.role }}", {"bold": True}),
            " · {{ e.company }}",
            "{% if e.city %}, {{ e.city }}{% endif %}",
            "	",
            ("{{ e.start }} – {{ e.end }}", {"color": MUTED, "size": 9.5}),
        )
        _right_tab(role)
        _spacing(role, before=4, after=1)
        _tag(doc, "{%p for b in e.bullets %}")
        _add(doc, "{{ b }}", style="List Bullet")
        _tag(doc, "{%p endfor %}")
        _tag(doc, "{%p endfor %}")

    _classic_section(doc, "experience", experience)

    def projects() -> None:
        _tag(doc, "{%p for p in projects %}")
        title = _add(
            doc,
            ("{{ p.name }}", {"bold": True}),
            "	",
            ("{{ p.date }}", {"color": MUTED, "size": 9.5}),
        )
        _right_tab(title)
        _spacing(title, before=3)
        _tag(doc, "{%p for b in p.bullets %}")
        _add(doc, "{{ b }}", style="List Bullet")
        _tag(doc, "{%p endfor %}")
        _tag(doc, "{%p endfor %}")

    _classic_section(doc, "projects", projects)

    def education() -> None:
        _tag(doc, "{%p for ed in education %}")
        line = _add(
            doc,
            ("{{ ed.title }}", {"bold": True}),
            " · {{ ed.center }}",
            "	",
            ("{% if ed.start %}{{ ed.start }} – {% endif %}{{ ed.end }}",
             {"color": MUTED, "size": 9.5}),
        )  # fmt: skip
        _right_tab(line)
        _spacing(line, before=2)
        _tag(doc, "{%p if ed.detail %}")
        _add(doc, "{{ ed.detail }}")
        _tag(doc, "{%p endif %}")
        _tag(doc, "{%p endfor %}")

    _classic_section(doc, "education", education)

    def certifications() -> None:
        _tag(doc, "{%p for c in certifications %}")
        line = _add(
            doc,
            ("{{ c.name }}", {"bold": True}),
            "{% if c.issuer %} · {{ c.issuer }}{% endif %}",
            "	",
            ("{{ c.date }}", {"color": MUTED, "size": 9.5}),
        )
        _right_tab(line)
        _tag(doc, "{%p endfor %}")

    _classic_section(doc, "certifications", certifications)
    _extra_sections(doc, _classic_heading)

    def skills() -> None:
        _tag(doc, "{%p for s in skills %}")
        _add(doc, ("{{ s.group }}: ", {"bold": True}), "{{ s.items|join(', ') }}")
        _tag(doc, "{%p endfor %}")

    _classic_section(doc, "skills", skills)

    languages_line = "{% for l in languages %}{{ l.language }}: {{ l.level }}{% if not loop.last %}  ·  {% endif %}{% endfor %}"  # noqa: E501
    _classic_section(doc, "languages", lambda: _add(doc, languages_line))

    dest.mkdir(parents=True, exist_ok=True)
    _save_reproducible(doc, dest / "template.docx")
    build_clasica_foto_letter(dest)
    (dest / "template.yaml").write_text(
        yaml.safe_dump(CLASICA_FOTO_META, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


# --- carta-simple (solo carta, fase 08c) ----------------------------------------------------

CARTA_SIMPLE_META: dict[str, Any] = {
    "id": "carta-simple",
    "name": "Carta sencilla",
    "engine": "docx",
    "kind": "letter",
    "origin": "builtin",
    "description": (
        "Carta de presentación de una columna, sin foto, con el color de acento del CV. Se usa "
        "cuando la plantilla del CV no trae su propio diseño de carta."
    ),
    "tags": ["carta", "sobria"],
    "layout": {"columns": 1, "uses_tables": False},
    "ats_friendly": True,
    "photo": {"supported": False, "shape": "circle", "size_mm": 30},
    "page": {"size": "A4", "max_pages": 1},
    "options": {
        "accent_color": {"default": ACCENT_COLORS[0], "choices": ACCENT_COLORS, "free": True}
    },
    "fonts": ["Calibri"],
    "languages": ["es", "en"],
    "letter": {"file": "letter.docx"},
}


def _letter_body(doc: Any) -> None:
    """Cuerpo común de las cartas docx: fecha, destinatario, saludo, párrafos y despedida."""
    date = _add(doc, ("{{ [place, date]|select|join(', ') }}", {"color": MUTED}))
    date.alignment = 2  # derecha
    _spacing(date, before=18, after=14)
    _tag(doc, "{%p if recipient %}")
    _spacing(_add(doc, ("{{ recipient }}", {"bold": True})), after=10)
    _tag(doc, "{%p endif %}")
    _spacing(_add(doc, "{{ greeting }}"), after=10)
    _tag(doc, "{%p for paragraph in paragraphs %}")
    body = _add(doc, "{{ paragraph }}")
    body.paragraph_format.line_spacing = 1.2
    _spacing(body, after=9)
    _tag(doc, "{%p endfor %}")
    _spacing(_add(doc, "{{ sign_off }}"), before=6, after=24)
    _add(doc, ("{{ name }}", {"bold": True}))


def build_carta_simple(dest: Path) -> None:
    doc = _base_document("Calibri", 11)
    name = doc.add_paragraph()
    _accent_run(name, "{{ name }}", bold=True, size=18)
    _spacing(name, after=1)
    subtitle = _add(doc, ("{{ subtitle }}", {"size": 11, "color": MUTED}))
    _spacing(subtitle, after=2)
    contact = _add(doc, (CONTACT_LINE, {"size": 9.5}))
    _spacing(contact, after=4)
    _bottom_border(contact, color=ACCENT)
    _letter_body(doc)

    dest.mkdir(parents=True, exist_ok=True)
    _save_reproducible(doc, dest / "letter.docx")
    (dest / "template.yaml").write_text(
        yaml.safe_dump(CARTA_SIMPLE_META, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )


BUILDERS: dict[str, Callable[[Path], None]] = {
    "ats-simple": build_ats_simple,
    "clasica-foto": build_clasica_foto,
    "carta-simple": build_carta_simple,
}
# Solo carta: sin preview de CV (la carta no tiene preview en la galería de CVs).
LETTER_ONLY = ("carta-simple",)


# --- Foto demo ------------------------------------------------------------------------------

DEMO_PHOTO = REPO_ROOT / "demo" / "photo.png"


def build_demo_photo(dest: Path = DEMO_PHOTO) -> Path:
    """Foto FICTICIA del perfil demo: una silueta dibujada, nunca una persona real."""
    from PIL import Image, ImageDraw

    side = 600
    image = Image.new("RGB", (side, side), (0xD9, 0xDE, 0xE5))
    draw = ImageDraw.Draw(image)
    figure = (0x8A, 0x96, 0xA6)
    draw.ellipse((190, 115, 410, 355), fill=figure)  # cabeza
    draw.ellipse((95, 390, 505, 800), fill=figure)  # hombros
    dest.parent.mkdir(parents=True, exist_ok=True)
    image.save(dest, format="PNG")
    return dest


def build_all(root: Path = TEMPLATES_DIR) -> list[Path]:
    built = []
    for template_id, builder in BUILDERS.items():
        builder(root / template_id)
        built.append(root / template_id)
    return built


# Integradas escritas a mano (motor html): solo se regenera su preview.
HANDWRITTEN = ("moderna-2col",)


def build_previews(root: Path = TEMPLATES_DIR) -> None:
    from app.services.documents import preview

    for template_id in (*BUILDERS, *HANDWRITTEN):
        if template_id not in LETTER_ONLY:
            preview.write_builtin_preview(root / template_id)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--no-preview", action="store_true", help="No generar las previews")
    args = parser.parse_args(argv)
    for path in build_all():
        print(f"Plantilla: {path.relative_to(REPO_ROOT).as_posix()}")
    print(f"Foto demo: {build_demo_photo().relative_to(REPO_ROOT).as_posix()}")
    if not args.no_preview:
        build_previews()
        print("Previews generadas con el perfil demo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
