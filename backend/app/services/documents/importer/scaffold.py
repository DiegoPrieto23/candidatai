"""`cai templates scaffold-html`: punto de partida de una plantilla html recreada desde un PDF, una
imagen o un HTML.

Con lo que mide `inspect` (columnas, barra lateral, banda de cabecera, márgenes, colores, fuentes,
foto, secciones en su orden y en qué columna están, `capacity`) escribe en `data/templates/<id>/`:
`template.html` (Jinja2, solo variables del contrato), `style.css`, `template.yaml`, el original
(`source.<ext>`) y su primera página (`source.png`, para «Original | Recreación»). Es una base: el
agente la ajusta mirando el original hasta que se parezca. Si no renderiza, no deja nada.
"""

import re
import shutil
import tempfile
from pathlib import Path
from typing import Any, get_args

import yaml
from pydantic import BaseModel

from app.core.config import get_settings
from app.schemas.cv import SectionName, TemplateCapacity, TemplateMeta
from app.services.documents import templates
from app.services.documents.importer import ImportIssue, TemplateImportError, visual
from app.services.documents.importer.build import SOURCE_PNG, TemplateExistsError

CONTRACT_SECTIONS: tuple[str, ...] = get_args(SectionName)
# Lo que suele ir en una barra lateral o en la columna estrecha.
SIDE_DEFAULT = ("skills", "languages", "certifications")
DEFAULT_ACCENTS = ("#1F4E79", "#2E5E4E", "#7A2E39", "#3F3F46")


class ScaffoldResult(BaseModel):
    template_id: str
    path: str  # relativa a data/
    files: list[str]
    sections: list[str]
    side_sections: list[str]
    columns: int
    sidebar: str | None
    accent_color: str
    fonts: list[str]
    photo_supported: bool
    capacity: dict[str, int]
    max_pages: int
    ats_friendly: bool
    source_preview: bool
    next_steps: list[str]
    warnings: list[str]


# --- Colores --------------------------------------------------------------------------------


def _rgb(color: str) -> tuple[float, float, float]:
    value = color.lstrip("#")
    r, g, b = (int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return r, g, b


def luminance(color: str) -> float:
    r, g, b = _rgb(color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def saturation(color: str) -> float:
    values = _rgb(color)
    high, low = max(values), min(values)
    return 0.0 if high == 0 else (high - low) / high


def accent_of(report: visual.VisualInspection) -> str:
    """El color de acento: el de la barra o la banda si tienen color; si no, el más saturado."""
    for color in (report.layout.sidebar_color, report.layout.header_band_color):
        if color and saturation(color) > 0.25:
            return color
    colored = [c for c in report.colors if saturation(c.color) > 0.3 and luminance(c.color) > 0.08]
    return colored[0].color if colored else DEFAULT_ACCENTS[0]


def ink_of(report: visual.VisualInspection) -> str:
    dark = [
        c.color for c in report.colors if luminance(c.color) < 0.3 and saturation(c.color) < 0.4
    ]
    return dark[0] if dark else "#222222"


# --- Estructura -----------------------------------------------------------------------------


def _sections(report: visual.VisualInspection, requested: list[str] | None) -> list[str]:
    if requested:
        unknown = [s for s in requested if s not in CONTRACT_SECTIONS]
        if unknown:
            raise TemplateImportError(
                f"Secciones fuera del contrato: {', '.join(unknown)}. Usa: "
                f"{', '.join(CONTRACT_SECTIONS)}.",
                [ImportIssue(field="sections", received=", ".join(unknown), reason="no existe")],
            )
        return list(dict.fromkeys(requested))
    found: list[str] = []
    for section in report.sections:
        name = "extra_sections" if section.section == "extra" else section.section
        if name in CONTRACT_SECTIONS and name not in found:
            found.append(name)
    return found or list(CONTRACT_SECTIONS)


def _side_sections(
    report: visual.VisualInspection, sections: list[str], requested: list[str] | None
) -> list[str]:
    if requested is not None:
        return [s for s in requested if s in sections]
    if report.layout.columns < 2:
        return []
    by_column: dict[str, int] = {}
    for s in report.sections:
        name = "extra_sections" if s.section == "extra" else s.section
        by_column.setdefault(name, s.column)
    if by_column:
        main = by_column.get("experience", 0)
        return [s for s in sections if s in by_column and by_column[s] != main]
    return [s for s in sections if s in SIDE_DEFAULT]


def _contact_in_side(report: visual.VisualInspection, side: list[str]) -> bool:
    contact = next((s for s in report.sections if s.section == "contact"), None)
    experience = next((s for s in report.sections if s.section == "experience"), None)
    if contact is not None and experience is not None:
        return contact.column != experience.column
    return bool(side) and report.layout.sidebar is not None


# --- HTML -----------------------------------------------------------------------------------

_SNIPPETS: dict[str, str] = {
    "summary": """
{% if show.summary %}
<section class="sec sec-summary">
  <h2>{{ labels.summary }}</h2>
  <p class="summary">{{ summary }}</p>
</section>
{% endif %}""",
    "experience": """
{% if show.experience %}
<section class="sec sec-experience">
  <h2>{{ labels.experience }}</h2>
  {% for e in experience %}
  <article class="item">
    <div class="item-head">
      <span class="item-title">{{ e.role }}</span>
      <span class="item-dates">{{ e.start }}{% if e.end %} – {{ e.end }}{% endif %}</span>
    </div>
    <div class="item-sub">{{ e.company }}{% if e.city %} · {{ e.city }}{% endif %}</div>
    {% if e.bullets %}
    <ul class="bullets">
      {% for b in e.bullets %}<li>{{ b }}</li>{% endfor %}
    </ul>
    {% endif %}
  </article>
  {% endfor %}
</section>
{% endif %}""",
    "projects": """
{% if show.projects %}
<section class="sec sec-projects">
  <h2>{{ labels.projects }}</h2>
  {% for p in projects %}
  <article class="item">
    <div class="item-head">
      <span class="item-title">{{ p.name }}</span>
      <span class="item-dates">{{ p.date }}</span>
    </div>
    {% if p.url %}<div class="item-sub">{{ p.url }}</div>{% endif %}
    <ul class="bullets">{% for b in p.bullets %}<li>{{ b }}</li>{% endfor %}</ul>
  </article>
  {% endfor %}
</section>
{% endif %}""",
    "education": """
{% if show.education %}
<section class="sec sec-education">
  <h2>{{ labels.education }}</h2>
  {% for ed in education %}
  <article class="item">
    <div class="item-head">
      <span class="item-title">{{ ed.title }}</span>
      <span class="item-dates">{{ ed.start }}{% if ed.end %} – {{ ed.end }}{% endif %}</span>
    </div>
    <div class="item-sub">{{ ed.center }}</div>
    {% if ed.detail %}<p class="detail">{{ ed.detail }}</p>{% endif %}
  </article>
  {% endfor %}
</section>
{% endif %}""",
    "certifications": """
{% if show.certifications %}
<section class="sec sec-certifications">
  <h2>{{ labels.certifications }}</h2>
  <ul class="plain">
    {% for c in certifications %}
    <li>
      <strong>{{ c.name }}</strong>{% if c.issuer %} · {{ c.issuer }}{% endif %}
      {% if c.date %} <span class="muted">({{ c.date }})</span>{% endif %}
    </li>
    {% endfor %}
  </ul>
</section>
{% endif %}""",
    "extra_sections": """
{% if show.extra_sections %}
{% for x in extra_sections %}
<section class="sec sec-extra">
  <h2>{{ x.title }}</h2>
  <ul class="bullets">
    {% for i in x.items %}
    <li>{{ i.text }}{% if i.date %} <span class="muted">({{ i.date }})</span>{% endif %}</li>
    {% endfor %}
  </ul>
</section>
{% endfor %}
{% endif %}""",
    "skills": """
{% if show.skills %}
<section class="sec sec-skills">
  <h2>{{ labels.skills }}</h2>
  {% for s in skills %}
  <p class="skill"><strong>{{ s.group }}</strong>: {{ s.items | join(', ') }}</p>
  {% endfor %}
</section>
{% endif %}""",
    "languages": """
{% if show.languages %}
<section class="sec sec-languages">
  <h2>{{ labels.languages }}</h2>
  <ul class="plain">
    {% for l in languages %}
    <li><strong>{{ l.language }}</strong>{% if l.level %} · {{ l.level }}{% endif %}</li>
    {% endfor %}
  </ul>
</section>
{% endif %}""",
}

_CONTACT = """
<ul class="contact">
  {% if contact.email %}<li>{{ contact.email }}</li>{% endif %}
  {% if contact.phone %}<li>{{ contact.phone }}</li>{% endif %}
  {% if contact.city %}<li>{{ contact.city }}</li>{% endif %}
  {% if contact.linkedin %}<li>{{ contact.linkedin }}</li>{% endif %}
  {% if contact.github %}<li>{{ contact.github }}</li>{% endif %}
</ul>"""

_CONTACT_SECTION = (
    """
<section class="sec sec-contact">
  <h2>{{ labels.contact }}</h2>"""
    + _CONTACT
    + """
</section>"""
)

_PHOTO = """
{% if photo %}<img class="photo" src="{{ photo }}" alt="">{% endif %}"""


def _indent(text: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else line for line in text.strip("\n").splitlines())


def build_html(
    sections: list[str],
    side: list[str],
    contact_in_side: bool,
    photo: bool,
    photo_in_side: bool,
    side_left: bool,
    header_in_main: bool,
) -> str:
    """El `template.html` base: cabecera, columna principal y, si la hay, la lateral.

    Con barra lateral a sangre (`header_in_main`), la cabecera va dentro de la columna principal
    y la barra ocupa toda la altura; si no, la cabecera va arriba de lado a lado.
    """
    main = [s for s in sections if s not in side]
    identity = """
<div class="identity">
  <h1>{{ name }}</h1>
  {% if subtitle %}<p class="subtitle">{{ subtitle }}</p>{% endif %}"""
    if not contact_in_side:
        identity += "\n" + _indent(_CONTACT, 2)
    identity += "\n</div>"
    head_parts = [_PHOTO] if photo and not photo_in_side else []
    head_parts.append(identity)
    header = [
        '<header class="head">',
        _indent("\n".join(_indent(p, 0) for p in head_parts), 2),
        "</header>",
    ]
    main_parts = [_indent(_SNIPPETS[s], 0) for s in main]
    has_side = bool(side) or contact_in_side
    if not has_side:
        body = [*header, '<main class="main">', _indent("\n".join(main_parts), 2), "</main>"]
    else:
        side_parts = [_PHOTO] if photo and photo_in_side else []
        if contact_in_side:
            side_parts.append(_CONTACT_SECTION)
        side_parts.extend(_SNIPPETS[s] for s in side)
        aside = [
            '  <aside class="side">',
            _indent("\n".join(_indent(p, 0) for p in side_parts), 4),
            "  </aside>",
        ]
        main_block = [
            '  <main class="main">',
            *(_indent(line, 4) for line in (header if header_in_main else [])),
            _indent("\n".join(main_parts), 4),
            "  </main>",
        ]
        columns = [*aside, *main_block] if side_left else [*main_block, *aside]
        body = [
            *([] if header_in_main else header),
            '<div class="columns">',
            *columns,
            "</div>",
        ]
    lang = "{{ 'en' if labels.experience == 'Experience' else 'es' }}"
    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{lang}">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        "<title>{{ name }}</title>\n"
        '<link rel="stylesheet" href="style.css">\n'
        "<style>:root { --accent: {{ accent_color }}; }</style>\n"
        "</head>\n"
        "<body>\n" + "\n".join(body) + "\n</body>\n</html>\n"
    )


_SERIF = {"georgia", "times", "timesnewroman", "garamond", "cambria", "palatino", "baskerville"}


def _font_stack(font: str | None) -> str:
    # El nombre sale de un PDF no confiable: solo letras, números, espacios, puntos y guiones,
    # para que no pueda cerrar la regla CSS.
    font = re.sub(r"[^\w .-]", "", font or "").strip()
    if not font:
        return "sans-serif"
    generic = "serif" if font.casefold().replace(" ", "") in _SERIF else "sans-serif"
    return f'"{font}", {generic}'


def fonts_of(report: visual.VisualInspection) -> tuple[str | None, str | None]:
    """Fuente del texto (la de más caracteres) y la de los títulos de sección, si es otra."""
    usage: dict[str, int] = {}
    for b in report.text_blocks:
        family = visual.font_family(b.font)
        if family:
            usage[family] = usage.get(family, 0) + len(b.text)
    body = max(usage, key=lambda f: usage[f]) if usage else None
    titles = [
        visual.font_family(report.text_blocks[s.block].font)
        for s in report.sections
        if s.block is not None
    ]
    heading = max(set(titles), key=titles.count) if titles else None
    return body, (heading if heading and heading != body else None)


def side_is_left(report: visual.VisualInspection) -> bool:
    lay = report.layout
    if lay.sidebar is not None:
        return lay.sidebar == "left"
    return bool(lay.column_edges_mm) and lay.column_edges_mm[0] < report.page.width_mm / 2


def build_css(report: visual.VisualInspection, side: bool, photo_size_mm: float) -> str:
    lay = report.layout
    width = report.page.width_mm
    margins = {k: min(max(v, 8.0), 25.0) for k, v in lay.margins_mm.items()}
    left = side_is_left(report)
    edge = lay.column_edges_mm[0] if lay.column_edges_mm else width * (0.33 if left else 0.67)
    side_width = round(edge if left else width - edge, 1)
    ink = ink_of(report)
    sidebar_bg = lay.sidebar_color or "transparent"
    side_ink = "#FFFFFF" if lay.sidebar_color and luminance(lay.sidebar_color) < 0.5 else ink
    band = lay.header_band_color if lay.sidebar is None else None
    band_ink = "#FFFFFF" if band and luminance(band) < 0.5 else ink
    size = report.page.size if report.page.size != "other" else "A4"
    body_font, heading_font = fonts_of(report)
    gap = 8.0
    full_sidebar = lay.sidebar is not None and side
    lines = [
        f"/* Recreación de {Path(report.file).name}, generada por `cai templates scaffold-html`.",
        "   Ajústala mirando el original (source.png). Solo recursos locales: fonts/, nada remoto.",
        "*/",
        "",
        f"@page {{ size: {size}; margin: 0; }}",
        "",
        ":root {",
        f"  --ink: {ink};",
        "  --muted: #6B7079;",
        f"  --side-bg: {sidebar_bg};",
        f"  --side-ink: {side_ink};",
        f"  --band-bg: {band or 'transparent'};",
        f"  --band-ink: {band_ink if band else ink};",
        f"  --side-width: {side_width}mm;",
        "}",
        "",
        "* { box-sizing: border-box; }",
        "html, body { margin: 0; padding: 0; }",
        "body {",
        f"  font-family: {_font_stack(body_font)};",
        "  font-size: 10pt;",
        "  line-height: 1.35;",
        "  color: var(--ink);",
        "  -webkit-print-color-adjust: exact;",
        "  print-color-adjust: exact;",
        "}",
        "",
    ]
    if full_sidebar:
        # Barra lateral a sangre: la cabecera va dentro de la columna principal.
        lines.append(
            f".head {{ padding: 0 0 6mm; display: flex; align-items: center; gap: {gap}mm; }}"
        )
    else:
        lines += [
            ".head { background: var(--band-bg); color: var(--band-ink);",
            f"  padding: {margins['top']}mm {margins['right']}mm 6mm {margins['left']}mm;",
            f"  display: flex; align-items: center; gap: {gap}mm; }}",
        ]
    lines += [
        ".head h1 { margin: 0; font-size: 24pt; line-height: 1.1; }",
        ".subtitle { margin: 1.5mm 0 0; font-size: 12pt; }",
        ".head .contact { display: flex; flex-wrap: wrap; gap: 0 5mm; margin-top: 2mm; }",
        "",
        f".photo {{ width: {photo_size_mm}mm; height: {photo_size_mm}mm; border-radius: 50%;",
        "  object-fit: cover; display: block; }",
        "",
    ]
    outer_left, outer_right = margins["left"], margins["right"]
    if side:
        top = f"{margins['top']}mm" if full_sidebar else "6mm"
        side_pad = f"{top} {gap if left else outer_right}mm 10mm {outer_left if left else gap}mm"
        main_pad = f"{top} {outer_right if left else gap}mm 10mm {gap if left else outer_left}mm"
        min_height = f" min-height: {report.page.height_mm}mm;" if full_sidebar else ""
        lines += [
            f".columns {{ display: flex;{min_height} }}",
            ".side { width: var(--side-width); flex: none; background: var(--side-bg);",
            f"  color: var(--side-ink); padding: {side_pad}; }}",
            f".main {{ flex: 1; padding: {main_pad}; }}",
            ".side .photo { margin: 0 auto 6mm; }",
            "",
        ]
    else:
        lines += [f".main {{ padding: 6mm {outer_right}mm 10mm {outer_left}mm; }}", ""]
    heading_family = f" font-family: {_font_stack(heading_font)};" if heading_font else ""
    lines += [
        "h2 { font-size: 11pt; text-transform: uppercase; letter-spacing: 0.06em;",
        "  color: var(--accent); margin: 0 0 2mm; padding-bottom: 1mm;",
        f"  border-bottom: 0.4mm solid var(--accent);{heading_family} }}",
        ".side h2 { color: inherit; border-color: currentColor; }",
        ".sec { margin-bottom: 5mm; }",
        ".item { margin-bottom: 3mm; break-inside: avoid; }",
        ".item-head { display: flex; justify-content: space-between; gap: 4mm; }",
        ".item-title { font-weight: 700; }",
        ".item-dates, .muted { color: var(--muted); }",
        ".side .muted, .side .item-dates { color: inherit; opacity: 0.8; }",
        ".item-sub { font-style: italic; color: var(--muted); }",
        "a { color: inherit; text-decoration: none; }",
        ".summary, .detail, .skill { margin: 0 0 1.5mm; }",
        ".bullets { margin: 1mm 0 0; padding-left: 4.5mm; }",
        ".bullets li { margin-bottom: 0.8mm; }",
        ".bullets li::marker { color: var(--accent); }",
        ".contact, .plain { list-style: none; margin: 0; padding: 0; }",
        ".contact li, .plain li { margin-bottom: 1.2mm; overflow-wrap: anywhere; }",
        "",
    ]
    return "\n".join(lines)


# --- Entrada --------------------------------------------------------------------------------


def _capacity(measured: Any) -> TemplateCapacity:
    defaults = TemplateCapacity()
    return TemplateCapacity(
        summary_chars=measured.summary_chars or defaults.summary_chars,
        experience_bullets=measured.experience_bullets or defaults.experience_bullets,
        skill_groups=measured.skill_groups or defaults.skill_groups,
    )


def scaffold_html(
    source: Path,
    template_id: str,
    name: str | None = None,
    sections: list[str] | None = None,
    side: list[str] | None = None,
    force: bool = False,
) -> ScaffoldResult:
    from app.services.documents.preview import check_renders

    TemplateMeta.model_validate(
        {"id": template_id, "name": "x", "engine": "html", "origin": "user",
         "ats_friendly": False, "sections": ["summary"]}
    )  # fmt: skip
    if not visual.is_visual(source):
        raise TemplateImportError(
            f"`scaffold-html` es para PDF, imagen o HTML; {source.name} es Word: usa "
            "`build-docx`, que conserva el diseño exacto."
        )
    settings = get_settings()
    user_dir = settings.user_templates_dir
    folder = user_dir / template_id
    if folder.exists() and not force:
        raise TemplateExistsError(
            f"Ya existe la plantilla «{template_id}» en {folder}. Usa otro id o `--force` para "
            "sustituirla."
        )

    report = visual.inspect_visual(source)
    chosen = _sections(report, sections)
    side_sections = _side_sections(report, chosen, side)
    if sections is None:
        # En el orden del CV: primero la columna principal y después la lateral.
        chosen = [s for s in chosen if s not in side_sections] + side_sections
    contact_side = _contact_in_side(report, side_sections)
    photo_box = next((i for i in report.images if i.photo_candidate and i.page == 1), None)
    photo_size = round(min(max(photo_box.width_mm, 15), 60), 1) if photo_box else 32.0
    photo_in_side = bool(
        photo_box
        and report.layout.column_edges_mm
        and (side_sections or contact_side)
        and (
            (report.layout.sidebar == "left" and photo_box.x_mm < report.layout.column_edges_mm[0])
            or (
                report.layout.sidebar != "left"
                and photo_box.x_mm >= report.layout.column_edges_mm[0]
            )
        )
    )
    accent = accent_of(report)
    capacity = _capacity(report.capacity)
    pages = min(max(report.pages, 1), 3)
    fonts = [f for f in fonts_of(report) if f]
    warnings = list(report.notes)
    if (templates.BUILTIN_TEMPLATES_DIR / template_id / templates.META_FILE).is_file():
        warnings.append(f"«{template_id}» es también una integrada: la tuya la sustituye.")

    suffix = source.suffix.casefold()
    source_name = f"source{suffix}"
    meta = {
        "id": template_id,
        "name": name or template_id.replace("-", " ").capitalize(),
        "engine": "html",
        "origin": "user",
        "source_file": source_name,
        "description": f"Recreada desde {source.name} (aproximada; revisa la preview).",
        "tags": [],
        "layout": {"columns": 2 if (side_sections or contact_side) else 1, "uses_tables": False},
        "ats_friendly": False,
        "photo": {"supported": photo_box is not None, "shape": "circle", "size_mm": photo_size},
        "page": {
            "size": report.page.size if report.page.size != "other" else "A4",
            "max_pages": pages,
        },
        "capacity": capacity.model_dump(),
        "sections": chosen,
        "options": {
            "accent_color": {
                "default": accent,
                "choices": list(dict.fromkeys([accent, *DEFAULT_ACCENTS])),
            }
        },
        "fonts": fonts,
        "languages": ["es", "en"],
    }
    TemplateMeta.model_validate(meta)

    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="cai-scaffold-", dir=settings.tmp_dir))
    try:
        target = staging / template_id
        (target / "fonts").mkdir(parents=True)
        (target / "template.html").write_text(
            build_html(
                chosen,
                side_sections,
                contact_side,
                photo_box is not None,
                photo_in_side,
                side_is_left(report),
                header_in_main=report.layout.sidebar is not None,
            ),
            encoding="utf-8",
        )
        (target / "style.css").write_text(
            build_css(report, bool(side_sections or contact_side), photo_size), encoding="utf-8"
        )
        (target / "template.yaml").write_text(
            yaml.safe_dump(meta, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        shutil.copyfile(source, target / source_name)
        if source_name != SOURCE_PNG:
            # Un original .png ya es su propia vista: no se sustituye (su sha256 dice que la
            # subida está importada).
            shutil.copyfile(settings.data_dir / report.page_images[0], target / SOURCE_PNG)
        template = templates.Template(meta=templates.load_meta(target), path=target)
        try:
            unsafe = templates.unsafe_content(template)
            if unsafe:  # pragma: no cover - la base es nuestra; por si un dato del PDF se colase
                raise templates.TemplateInvalidError(template_id, unsafe)
            check_renders(template)
        except templates.TemplateInvalidError as exc:  # pragma: no cover - la base es nuestra
            issues = [
                ImportIssue(field=i.field, received=None, reason=i.reason) for i in exc.issues
            ]
            raise TemplateImportError(f"La base generada no renderiza: {exc}", issues) from exc
        if folder.exists():
            shutil.rmtree(folder)
        user_dir.mkdir(parents=True, exist_ok=True)
        shutil.move(str(target), str(folder))
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    relative = folder.relative_to(settings.data_dir).as_posix()
    return ScaffoldResult(
        template_id=template_id,
        path=relative,
        files=sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()),
        sections=chosen,
        side_sections=side_sections,
        columns=meta["layout"]["columns"],
        sidebar=report.layout.sidebar,
        accent_color=accent,
        fonts=fonts,
        photo_supported=photo_box is not None,
        capacity=capacity.model_dump(),
        max_pages=pages,
        ats_friendly=False,
        source_preview=True,
        next_steps=[
            f"Ajusta data/{relative}/template.html y style.css mirando data/{relative}/source.png.",
            f"cai templates validate {template_id}",
            f"cai templates compare {template_id} --source <fichero>",
        ],
        warnings=warnings,
    )
