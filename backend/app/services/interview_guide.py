"""Guía de preparación de una entrevista en PDF.

El agente la redacta con `prepare-interview` como contenido estructurado
(`schemas/interview_guide.py`) y la guarda con `save_interview_guide`; aquí se maqueta con un diseño
fijo (con el color de la marca de la empresa), se imprime con Chromium a
`<carpeta de datos>/entrevistas/` y se apunta en el hito (`milestones.prep_guide`).

Todo el texto se escapa: el agente no puede meter HTML, y lo que venga de webs (dosier de la
empresa, conceptos) se queda en texto. Las únicas URLs son las de las fuentes, que se enlazan
después del saneado, como en los CVs (`engines/html.add_links`).
"""

import re
import unicodedata
from datetime import date, datetime
from html import escape
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, Job
from app.models.base import utcnow
from app.schemas.interview_guide import (
    BulletsBlock,
    CalloutBlock,
    CodeBlock,
    GuideBlock,
    GuideInfo,
    HeadingBlock,
    InterviewGuideInput,
    Language,
    ParagraphBlock,
    QaBlock,
    TableBlock,
    guide_info,
)
from app.services.documents.engines.html import html_to_pdf
from app.services.interviews import check_can_prepare, interviews_dir
from app.services.process import local_zone, milestone_row

# Textos fijos del PDF, en el idioma de la guía.
LABELS: dict[Language, dict[str, str]] = {
    "es": {
        "eyebrow": "Preparación de entrevista",
        "question": "P:",
        "answer": "Idea de respuesta:",
        "caution": "Ojo:",
        "tip": "Consejo",
        "warning": "Ojo",
        "note": "Nota",
        "sources": "Fuentes",
        "all_day": "todo el día",
        "madrid": "hora de Madrid",
        "footer": "Guía generada con CandidatAI el {date}. Sale de tu perfil, la oferta y las "
        "fuentes citadas: revísala antes de la entrevista.",
    },
    "en": {
        "eyebrow": "Interview preparation",
        "question": "Q:",
        "answer": "Answer outline:",
        "caution": "Careful:",
        "tip": "Tip",
        "warning": "Careful",
        "note": "Note",
        "sources": "Sources",
        "all_day": "all day",
        "madrid": "Madrid time",
        "footer": "Guide generated with CandidatAI on {date}. It comes from your profile, the job "
        "posting and the sources cited: check it before the interview.",
    },
}
_WEEKDAYS = {
    "es": ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"),
    "en": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
}
_MONTHS = {
    "es": (
        "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
        "octubre", "noviembre", "diciembre",
    ),
    "en": (
        "January", "February", "March", "April", "May", "June", "July", "August", "September",
        "October", "November", "December",
    ),
}  # fmt: skip


class InterviewGuideView(BaseModel):
    """La guía guardada de una entrevista, con su contenido (`null` si no hay)."""

    milestone_id: int
    job_id: int
    info: GuideInfo | None
    guide: InterviewGuideInput | None


class SaveGuideResult(BaseModel):
    ok: bool = True
    milestone_id: int
    job_id: int
    file: str  # nombre del PDF dentro de `entrevistas/` de la carpeta de datos
    sections: int
    replaced: bool
    message: str


# --- Formato --------------------------------------------------------------------------------

_INLINE_CODE = re.compile(r"`([^`\n]+)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])")


def _emphasis(text: str) -> str:
    return _ITALIC.sub(r"<em>\1</em>", _BOLD.sub(r"<strong>\1</strong>", text))


def inline(text: str) -> str:
    """Texto del agente a HTML: escapado, con `**negrita**`, `*cursiva*`, `` `código` `` y saltos
    de línea. Dentro del código no se interpreta nada."""
    out: list[str] = []
    last = 0
    for match in _INLINE_CODE.finditer(text):
        out.append(_emphasis(escape(text[last : match.start()])))
        out.append(f"<code>{escape(match.group(1))}</code>")
        last = match.end()
    out.append(_emphasis(escape(text[last:])))
    return "".join(out).replace("\n", "<br>")


def _paragraphs(text: str) -> str:
    return "".join(f"<p>{inline(p.strip())}</p>" for p in re.split(r"\n\s*\n", text) if p.strip())


def _luminance(color: str) -> float:
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast_with_white(color: str) -> float:
    return 1.05 / (_luminance(color) + 0.05)


def ink(color: str) -> str:
    """El color de marca, oscurecido lo justo para leerse sobre blanco (contraste ≥ 4.5, WCAG AA).
    Un amarillo o un verde claro de marca sirven para la línea, pero no para los títulos."""
    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    current = color.upper()
    factor = 1.0
    while _contrast_with_white(current) < 4.5 and factor > 0:
        factor = round(factor - 0.05, 2)
        current = f"#{int(r * factor):02X}{int(g * factor):02X}{int(b * factor):02X}"
    return current


def when(starts_at: datetime, all_day: bool, language: Language) -> str:
    local = starts_at.astimezone(local_zone())
    weekday = _WEEKDAYS[language][local.weekday()]
    month = _MONTHS[language][local.month - 1]
    labels = LABELS[language]
    day = (
        f"{weekday}, {local.day} de {month} de {local.year}"
        if language == "es"
        else f"{weekday}, {local.day} {month} {local.year}"
    )
    day = day[0].upper() + day[1:]
    if all_day:
        return f"{day} · {labels['all_day']}"
    return f"{day} · {local:%H:%M} ({labels['madrid']})"


def _date(value: date, language: Language) -> str:
    month = _MONTHS[language][value.month - 1]
    if language == "es":
        return f"{value.day} de {month} de {value.year}"
    return f"{value.day} {month} {value.year}"


# --- Bloques --------------------------------------------------------------------------------


def _block(block: GuideBlock, labels: dict[str, str]) -> str:
    if isinstance(block, ParagraphBlock):
        return _paragraphs(block.text)
    if isinstance(block, HeadingBlock):
        return f"<h3>{inline(block.text)}</h3>"
    if isinstance(block, BulletsBlock):
        items = "".join(
            f"<li>{f'<strong>{inline(i.label)}:</strong> ' if i.label else ''}{inline(i.text)}</li>"
            for i in block.items
        )
        return f"<ul>{items}</ul>"
    if isinstance(block, TableBlock):
        head = "".join(f"<th>{inline(h)}</th>" for h in block.headers)
        rows = "".join(
            "<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in row) + "</tr>"
            for row in block.rows
        )
        return f'<table class="data"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'
    if isinstance(block, QaBlock):
        parts = []
        for item in block.items:
            caution = (
                f'<p class="caution"><strong>{labels["caution"]}</strong> '
                f"{inline(item.caution)}</p>"
                if item.caution
                else ""
            )
            parts.append(
                '<div class="qa">'
                f'<p class="q"><span class="tag">{labels["question"]}</span> '
                f"{inline(item.question)}</p>"
                f'<p class="a"><em class="lbl">{labels["answer"]}</em> {inline(item.answer)}</p>'
                f"{caution}</div>"
            )
        return "".join(parts)
    if isinstance(block, CalloutBlock):
        return (
            f'<div class="callout {block.tone}"><strong>{labels[block.tone]}.</strong> '
            f"{inline(block.text)}</div>"
        )
    if isinstance(block, CodeBlock):
        title = f'<p class="code-title">{inline(block.title)}</p>' if block.title else ""
        head = "".join(f"<th>{escape(c.label)}</th>" for c in block.columns)
        cells = "".join(f"<td><pre>{escape(c.code)}</pre></td>" for c in block.columns)
        caption = f'<p class="caption">{inline(block.caption)}</p>' if block.caption else ""
        return (
            f'<div class="code-block">{title}<table class="code"><thead><tr>{head}</tr></thead>'
            f"<tbody><tr>{cells}</tr></tbody></table>{caption}</div>"
        )
    raise TypeError(f"Bloque desconocido: {type(block).__name__}")


_CSS = """
@page { size: A4; margin: 18mm 17mm 18mm 17mm; }
* { box-sizing: border-box; }
body { font-family: "Segoe UI", Calibri, "Helvetica Neue", Arial, sans-serif; font-size: 10.5pt;
  line-height: 1.45; color: #1f2328; margin: 0; }
.cover { border-bottom: 1px solid #c9ccd1; padding-bottom: 10pt; margin-bottom: 16pt; }
.eyebrow { color: var(--ink); font-weight: 700; font-size: 9pt; letter-spacing: .06em;
  text-transform: uppercase; margin: 0 0 6pt; }
h1 { font-size: 24pt; line-height: 1.15; margin: 0 0 8pt; }
.company { color: var(--ink); font-size: 15pt; font-weight: 700; margin: 0; }
.subtitle { color: #57606a; font-style: italic; margin: 3pt 0 0; }
.meta { color: #57606a; font-size: 9.5pt; margin: 4pt 0 0; }
h2 { color: var(--ink); font-size: 15pt; margin: 18pt 0 8pt; padding-bottom: 4pt;
  border-bottom: 2.5pt solid var(--accent); break-after: avoid; }
h3 { color: var(--ink); font-size: 11.5pt; margin: 12pt 0 5pt; break-after: avoid; }
p { margin: 0 0 7pt; }
ul { margin: 0 0 8pt; padding-left: 16pt; }
li { margin-bottom: 4pt; }
code { font-family: Consolas, "Courier New", monospace; font-size: 9pt; background: #f1f3f5;
  padding: 0 2pt; border-radius: 2pt; }
table { width: 100%; border-collapse: collapse; margin: 6pt 0 10pt; break-inside: auto; }
tr { break-inside: avoid; }
table.data th { background: var(--ink); color: #fff; text-align: left; font-size: 9.5pt;
  padding: 5pt 6pt; border: 1px solid var(--ink); }
table.data td { border: 1px solid #6e7781; padding: 5pt 6pt; vertical-align: top;
  font-size: 9.5pt; }
.qa { margin: 0 0 9pt; break-inside: avoid; }
.qa .q { font-weight: 700; margin-bottom: 2pt; }
.qa .tag { color: var(--accent-strong); }
.qa .a { margin: 0 0 2pt 12pt; }
.qa .lbl { color: #8c959f; }
.qa .caution { margin: 0 0 0 12pt; color: #9a6700; font-size: 9.5pt; }
.callout { border-left: 3.5pt solid var(--ink); background: var(--tint); padding: 6pt 9pt;
  margin: 4pt 0 9pt; break-inside: avoid; }
.callout.warning { border-left-color: #bf8700; background: #fff8c5; }
.callout.note { border-left-color: #8c959f; background: #f6f8fa; }
.code-block { break-inside: avoid; margin: 4pt 0 10pt; }
.code-title { font-weight: 700; margin-bottom: 3pt; }
table.code th { background: #32383f; color: #fff; text-align: left; font-size: 9pt;
  padding: 4pt 6pt; border: 1px solid #32383f; }
table.code td { border: 1px solid #32383f; background: #f6f8fa; vertical-align: top;
  padding: 5pt 6pt; width: 50%; }
pre { font-family: Consolas, "Courier New", monospace; font-size: 8.5pt; margin: 0;
  white-space: pre-wrap; word-break: break-word; }
.caption { color: #57606a; font-style: italic; font-size: 9.5pt; }
.sources ol { padding-left: 16pt; font-size: 9pt; color: #57606a; }
.sources a { color: var(--ink); word-break: break-all; }
footer { margin-top: 18pt; padding-top: 6pt; border-top: 1px solid #c9ccd1; color: #8c959f;
  font-size: 8.5pt; font-style: italic; }
"""


def render_html(
    guide: InterviewGuideInput,
    company: str,
    starts_at: datetime,
    all_day: bool,
    generated: date,
) -> str:
    """El HTML de la guía, listo para imprimir. Las secciones salen numeradas."""
    labels = LABELS[guide.language]
    accent = guide.accent_color
    strong = ink(accent)
    # El fondo de los consejos: el color de marca muy claro.
    r, g, b = (int(accent[i : i + 2], 16) for i in (1, 3, 5))
    tint = f"#{(r + 255 * 9) // 10:02X}{(g + 255 * 9) // 10:02X}{(b + 255 * 9) // 10:02X}"
    variables = (
        f":root {{ --accent: {accent}; --ink: {strong}; --accent-strong: {strong}; "
        f"--tint: {tint}; }}"
    )
    sections = "".join(
        f"<section><h2>{n}. {inline(s.title)}</h2>"
        + "".join(_block(b, labels) for b in s.blocks)
        + "</section>"
        for n, s in enumerate(guide.sections, start=1)
    )
    sources = ""
    if guide.sources:
        items = "".join(f"<li>{inline(s.title)} — {escape(s.url)}</li>" for s in guide.sources)
        sources = f'<section class="sources"><h2>{labels["sources"]}</h2><ol>{items}</ol></section>'
    subtitle = f'<p class="subtitle">{inline(guide.subtitle)}</p>' if guide.subtitle else ""
    footer = labels["footer"].format(date=_date(generated, guide.language))
    return (
        f'<!doctype html><html lang="{guide.language}"><head><meta charset="utf-8">'
        f"<title>{escape(guide.title)} · {escape(company)}</title>"
        f"<style>{variables}{_CSS}</style></head><body>"
        f'<header class="cover"><p class="eyebrow">{labels["eyebrow"]}</p>'
        f"<h1>{inline(guide.title)}</h1>"
        f'<p class="company">{escape(company)}</p>{subtitle}'
        f'<p class="meta">{escape(when(starts_at, all_day, guide.language))}</p></header>'
        f"{sections}{sources}<footer>{escape(footer)}</footer></body></html>"
    )


# --- Guardar --------------------------------------------------------------------------------


def _slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.casefold()).strip("-")[:40] or "empresa"


def guide_path(file: str) -> Path:
    return interviews_dir() / file


def get_interview_guide(session: Session, milestone_id: int) -> InterviewGuideView:
    """La guía de la entrevista para leerla (simulacro) o actualizarla (`prepare-interview`)."""
    row = milestone_row(session, milestone_id)
    stored = row.prep_guide or {}
    return InterviewGuideView(
        milestone_id=row.id,
        job_id=row.job_id,
        info=guide_info(row.prep_guide),
        guide=InterviewGuideInput.model_validate(stored["guide"]) if stored.get("guide") else None,
    )


def guide_file(session: Session, milestone_id: int) -> Path:
    """El PDF de la guía de esa entrevista. `FileNotFoundError` (404) si no hay o se borró."""
    row = milestone_row(session, milestone_id)
    file = (row.prep_guide or {}).get("file")
    if not file:
        raise FileNotFoundError(f"La entrevista {milestone_id} no tiene guía de preparación.")
    path = guide_path(file)
    if not path.is_file():
        raise FileNotFoundError(f"No está el PDF de la guía ({file}): vuelve a prepararla.")
    return path


GUIDE_THUMBNAIL_PX = 240  # la miniatura de la ficha se ve a ~80 px: nítida en pantallas 2x y 3x


def guide_thumbnail(session: Session, milestone_id: int) -> Path:
    """La portada de la guía en PNG, para la miniatura de la ficha. Se guarda en la caché de vistas
    previas con la fecha y el tamaño del PDF en el nombre: si se vuelve a preparar, se rehace."""
    from app.services.documents.authoring import previews_dir
    from app.services.documents.preview import pdf_to_png

    pdf = guide_file(session, milestone_id)
    stat = pdf.stat()
    png = previews_dir() / f"guide-{milestone_id}-{stat.st_mtime_ns}-{stat.st_size}.png"
    if not png.is_file():
        pdf_to_png(pdf, png, width_px=GUIDE_THUMBNAIL_PX)
    return png


def save_interview_guide(
    session: Session,
    milestone_id: int,
    guide: InterviewGuideInput,
    agent_name: str | None = None,
    now: datetime | None = None,
) -> SaveGuideResult:
    """Maqueta la guía, la imprime a PDF y la apunta en la entrevista (sustituye a la anterior).

    Solo con una entrevista programada que aún no ha empezado, como el plan. Si Chromium no está,
    falla (`pdf_unavailable`) y no se guarda nada."""
    row = milestone_row(session, milestone_id)
    now = now or utcnow()
    check_can_prepare(session, row, now)
    company = session.execute(
        select(Company.name).join(Job, Job.company_id == Company.id).where(Job.id == row.job_id)
    ).scalar_one()
    file = f"{row.job_id}-{row.id}-{_slug(company)}-guia.pdf"
    output = guide_path(file)
    today = now.astimezone(local_zone()).date()
    html = render_html(guide, company, row.starts_at, row.all_day, today)
    targets = {s.url: s.url for s in guide.sources}
    html_to_pdf(html, lambda _name: None, output, "A4", targets=targets)

    previous = row.prep_guide or {}
    # Si cambió el nombre de la empresa, el PDF anterior sobra (solo se borra uno nuestro).
    old = previous.get("file")
    if old and old != file and re.fullmatch(rf"{row.job_id}-{row.id}-[a-z0-9-]+-guia\.pdf", old):
        guide_path(old).unlink(missing_ok=True)
    row.prep_guide = {
        "file": file,
        "saved_at": now.isoformat(),
        "agent_name": (agent_name or "")[:64] or None,
        "guide": guide.model_dump(mode="json"),
    }
    row.updated_at = now
    session.flush()
    return SaveGuideResult(
        milestone_id=row.id,
        job_id=row.job_id,
        file=file,
        sections=len(guide.sections),
        replaced=bool(previous),
        message=f"Guía guardada en entrevistas/{file} y enlazada en la ficha, bajo la entrevista.",
    )
