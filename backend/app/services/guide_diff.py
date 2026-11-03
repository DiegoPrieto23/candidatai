"""Qué cambió entre dos versiones de una guía de entrevista, a partir del contenido estructurado (no
del PDF). Sin base de datos ni agente: dos guías entran y la lista de cambios sale."""

from typing import Literal

from pydantic import BaseModel

from app.schemas.interview_guide import (
    BulletsBlock,
    CalloutBlock,
    CodeBlock,
    GuideBlock,
    HeadingBlock,
    InterviewGuideInput,
    ParagraphBlock,
    QaBlock,
    TableBlock,
)
from app.services.documents.cv_diff import delta

GuidePart = Literal["cover", "section", "sources"]


class GuideChange(BaseModel):
    part: GuidePart
    section: str | None = None  # el título de la sección; sin él, es el orden de las secciones
    removed: list[str] = []
    added: list[str] = []
    reordered: bool = False  # mismo texto, en otro orden


def _texts(block: GuideBlock) -> list[str]:
    """Los textos de un bloque, tal como se comparan: cada viñeta, fila o pregunta es uno."""
    if isinstance(block, ParagraphBlock | HeadingBlock | CalloutBlock):
        return [block.text]
    if isinstance(block, BulletsBlock):
        return [f"{i.label}: {i.text}" if i.label else i.text for i in block.items]
    if isinstance(block, TableBlock):
        return [" | ".join(row) for row in [block.headers, *block.rows]]
    if isinstance(block, QaBlock):
        return [
            " — ".join(part for part in (i.question, i.answer, i.caution) if part)
            for i in block.items
        ]
    if isinstance(block, CodeBlock):
        columns = [f"{c.label}: {c.code}" for c in block.columns]
        return [text for text in (block.title, *columns, block.caption) if text]
    raise TypeError(f"Bloque desconocido: {type(block).__name__}")


def _sections(guide: InterviewGuideInput) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    for section in guide.sections:
        texts = sections.setdefault(section.title, [])
        for block in section.blocks:
            texts += _texts(block)
    return sections


def _change(
    part: GuidePart, old: list[str], new: list[str], section: str | None = None
) -> list[GuideChange]:
    removed, added = delta(old, new)
    if removed or added:
        return [GuideChange(part=part, section=section, removed=removed, added=added)]
    if old != new:
        return [GuideChange(part=part, section=section, reordered=True)]
    return []


def _cover(guide: InterviewGuideInput) -> list[str]:
    return [text for text in (guide.title, guide.subtitle) if text]


def diff(old: InterviewGuideInput, new: InterviewGuideInput) -> list[GuideChange]:
    """Los cambios de `old` a `new`. Las secciones se emparejan por título: renombrar una sale como
    quitar la antigua y añadir la nueva."""
    changes = _change("cover", _cover(old), _cover(new))
    old_sections, new_sections = _sections(old), _sections(new)
    for title in [*old_sections, *(t for t in new_sections if t not in old_sections)]:
        changes += _change(
            "section", old_sections.get(title, []), new_sections.get(title, []), title
        )
    common_old = [t for t in old_sections if t in new_sections]
    common_new = [t for t in new_sections if t in old_sections]
    if common_old != common_new:
        changes.append(GuideChange(part="section", reordered=True))
    changes += _change(
        "sources",
        [f"{s.title} — {s.url}" for s in old.sources],
        [f"{s.title} — {s.url}" for s in new.sources],
    )
    return changes
