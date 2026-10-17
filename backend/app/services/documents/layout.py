"""Maquetación del PDF renderizado (fase 25.5): avisos, nunca bloqueos.

Un CV puede caber en una página y aun así salir mal. Sobre el PDF ya renderizado (con `pypdfium2`,
que da la caja de cada línea de texto) se miran cinco cosas, con umbrales en `layout` de
`config/policies.yaml`:

- `orphan_heading`: un título (de sección o de puesto) al pie de una página y su contenido en la
  siguiente. Los títulos no se adivinan por la fuente: salen del contexto del render (`labels` de
  las secciones que hay y el `role` de cada experiencia).
- `large_gap`: un hueco vertical grande entre dos líneas, o al pie de una página que no es la
  última.
- `footer_overlap`: texto en la zona del pie o fuera del margen mínimo.
- `nearly_empty_last_page`: más de una página y la última casi vacía.
- `text_layer`: el nombre, el correo y el teléfono no están en el texto del PDF tal cual (iconos o
  glifos rotos) o el nombre no sale antes que el primer título.

Cada aviso lleva su página y, si se puede arreglar sin tocar el contenido, la opción de render
que lo arregla (`fix`). `too_long` (`checks.py`) sigue siendo lo único que impide seleccionar.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.policies import LayoutPolicy, get_policies
from app.services.documents.options import RenderWarning
from app.services.normalize import fold

CODES = frozenset(
    {"orphan_heading", "large_gap", "footer_overlap", "nearly_empty_last_page", "text_layer"}
)

_SECTIONS = (
    "summary",
    "experience",
    "projects",
    "education",
    "certifications",
    "skills",
    "languages",
)


@dataclass
class Line:
    """Una caja de texto de pdfium, en puntos y con el origen arriba a la izquierda."""

    page: int  # 1, 2…
    left: float
    top: float
    right: float
    bottom: float
    text: str


@dataclass
class Page:
    number: int
    width: float
    height: float
    lines: list[Line] = field(default_factory=list)
    text: str = ""


@dataclass
class Expected:
    """Lo que debe estar en el texto del PDF (del contexto del render)."""

    name: str | None = None
    email: str | None = None
    phone: str | None = None
    headings: list[str] = field(default_factory=list)


def expected_from_context(ctx: dict[str, Any]) -> Expected:
    labels = ctx.get("labels") or {}
    headings = [str(labels[s]) for s in _SECTIONS if ctx.get(s) and labels.get(s)]
    headings += [str(e["role"]) for e in ctx.get("experience") or [] if e.get("role")]
    contact = ctx.get("contact") or {}
    return Expected(
        name=ctx.get("name") or None,
        email=contact.get("email") or None,
        phone=contact.get("phone") or None,
        headings=headings,
    )


def read_pages(path: Path) -> list[Page]:
    import pypdfium2  # solo al leer un PDF, no al arrancar

    pages: list[Page] = []
    pdf = pypdfium2.PdfDocument(path)
    try:
        for index in range(len(pdf)):
            page = pdf[index]
            textpage = page.get_textpage()
            try:
                width, height = page.get_size()
                current = Page(index + 1, width, height, text=textpage.get_text_range())
                for i in range(textpage.count_rects()):
                    left, bottom, right, top = textpage.get_rect(i)
                    text = textpage.get_text_bounded(left, bottom, right, top).strip()
                    if text:
                        current.lines.append(
                            Line(index + 1, left, height - top, right, height - bottom, text)
                        )
                current.lines.sort(key=lambda line: (line.top, line.left))
                pages.append(current)
            finally:
                textpage.close()
                page.close()
    finally:
        pdf.close()
    return pages


def _rows(lines: list[Line]) -> list[tuple[float, float]]:
    """Las franjas verticales ocupadas (las líneas de varias columnas se juntan)."""
    rows: list[tuple[float, float]] = []
    for line in sorted(lines, key=lambda x: x.top):
        if rows and line.top <= rows[-1][1]:
            rows[-1] = (rows[-1][0], max(rows[-1][1], line.bottom))
        else:
            rows.append((line.top, line.bottom))
    return rows


def _squash(text: str) -> str:
    """Sin tildes, mayúsculas ni espacios: los títulos con espaciado entre letras salen partidos
    en el texto del PDF («PERF IL»)."""
    return fold(text).replace(" ", "")


HEADING_EXTRA_CHARS = 40  # lo que puede seguir a un título en su línea («Data Engineer · Acme»)
_AFTER_HEADING = re.compile(r"^\s*($|[·|,–—:\-(])")


def _plain(text: str) -> str:
    """Minúsculas y sin tildes, pero con la puntuación (para ver qué sigue a un título)."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _is_heading(text: str, headings: list[str]) -> bool:
    """La línea es un título: empieza por uno (aunque lleve espaciado entre letras) y no sigue
    como una frase («Perfil orientado a…» no lo es): acaba ahí o sigue con un separador
    («Data Engineer · Acme»), y no es mucho más larga."""
    line = _plain(text).strip()
    for heading in headings:
        letters = [c for c in _plain(heading) if not c.isspace()]
        if not letters:
            continue
        match = re.match(r"\s*".join(re.escape(c) for c in letters), line)
        if match is None:
            continue
        rest = line[match.end() :]
        if len(rest.strip()) <= HEADING_EXTRA_CHARS and _AFTER_HEADING.match(rest):
            return True
    return False


def _pct(value: float) -> str:
    return f"{round(value * 100)} %"


def check(
    pages: list[Page], expected: Expected, policy: LayoutPolicy | None = None
) -> list[RenderWarning]:
    """Los avisos de maquetación de un PDF ya leído."""
    policy = policy or get_policies().layout
    warnings: list[RenderWarning] = []
    last = len(pages)
    for page in pages:
        if not page.lines:
            continue
        h, w = page.height, page.width
        rows = _rows(page.lines)
        # Título huérfano: al pie, con casi nada debajo, y hay página siguiente.
        if page.number < last:
            for line in page.lines:
                if line.top < h * (1 - policy.orphan_bottom_pct / 100):
                    continue
                below = [r for r in rows if r[0] > line.bottom]
                if len(below) <= 1 and _is_heading(line.text, expected.headings):
                    warnings.append(
                        RenderWarning(
                            code="orphan_heading",
                            message=f"«{line.text[:60]}» queda al pie de la página {page.number} "
                            "y su contenido pasa a la siguiente.",
                            page=page.number,
                            fix="content",
                        )
                    )
                    break
        # Huecos: entre dos líneas, o al pie de una página que no es la última.
        gap_limit = h * policy.large_gap_pct / 100
        gaps = [(rows[i][1], rows[i + 1][0]) for i in range(len(rows) - 1)]
        biggest = max((b - a for a, b in gaps), default=0.0)
        bottom_free = h - rows[-1][1]
        if biggest > gap_limit or (
            page.number < last and bottom_free > gap_limit + h * policy.bottom_margin_pct / 100
        ):
            size = max(biggest, bottom_free if page.number < last else 0.0)
            warnings.append(
                RenderWarning(
                    code="large_gap",
                    message=f"Hay un hueco de un {_pct(size / h)} de la página {page.number} "
                    "en medio del documento.",
                    page=page.number,
                    fix="template",
                )
            )
        # Pie y márgenes.
        footer = h * (1 - policy.footer_zone_pct / 100)
        edge = policy.edge_margin_pt
        out = [
            line
            for line in page.lines
            if line.bottom > footer or line.top < edge or line.left < edge or line.right > w - edge
        ]
        if out:
            warnings.append(
                RenderWarning(
                    code="footer_overlap",
                    message=f"En la página {page.number} hay texto en la zona del pie o fuera del "
                    f"margen («{out[0].text[:40]}»).",
                    page=page.number,
                    fix="template",
                )
            )
    # Última página casi vacía.
    if last > 1 and pages[-1].lines:
        rows = _rows(pages[-1].lines)
        used = (rows[-1][1] - rows[0][0]) / pages[-1].height
        if used < policy.last_page_min_pct / 100:
            warnings.append(
                RenderWarning(
                    code="nearly_empty_last_page",
                    message=f"La página {last} solo ocupa un {_pct(used)}: recorta unas líneas u "
                    "oculta una sección para que quepa en una menos.",
                    page=last,
                    fix="content",
                )
            )
    warnings.extend(_text_layer(pages, expected))
    return warnings


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def _text_layer(pages: list[Page], expected: Expected) -> list[RenderWarning]:
    text = "\n".join(p.text for p in pages)
    # Sin espacios: un nombre con espaciado entre letras («L U C Í A») o un correo partido en dos
    # líneas siguen estando.
    squashed = _squash(text)
    missing = []
    if expected.name and _squash(expected.name) not in squashed:
        missing.append("el nombre")
    if expected.email and re.sub(r"\s+", "", expected.email.lower()) not in re.sub(
        r"\s+", "", text.lower()
    ):
        missing.append("el correo")
    if expected.phone and _digits(expected.phone) not in _digits(text):
        missing.append("el teléfono")
    if missing:
        return [
            RenderWarning(
                code="text_layer",
                message=f"En el texto del PDF no está {', '.join(missing)} tal cual (iconos o "
                "glifos rotos): un ATS no lo leería. Prueba otra plantilla.",
                page=1,
                fix="template",
            )
        ]
    if expected.name and expected.headings:
        name_at = squashed.find(_squash(expected.name))
        first = min(
            (squashed.find(_squash(h)) for h in expected.headings if _squash(h) in squashed),
            default=-1,
        )
        if 0 <= first < name_at:
            return [
                RenderWarning(
                    code="text_layer",
                    message="En el texto del PDF el nombre sale después de los títulos: el orden "
                    "de lectura no es el de la página y un ATS lo leería revuelto.",
                    page=1,
                    fix="template",
                )
            ]
    return []


# Solo para los tests: con el conversor falso (sin maquetación real) `tests/conftest.py` lo apaga
# salvo en los que llevan `@pytest.mark.layout`. Para apagarlo de verdad, `layout.enabled` de
# `config/policies.yaml`.
ENABLED = True


def analyze(path: Path, expected: Expected) -> list[RenderWarning]:
    """Lee el PDF y devuelve sus avisos de maquetación (ninguno si está apagado)."""
    if not ENABLED or not get_policies().layout.enabled:
        return []
    return check(read_pages(path), expected)
