"""Qué cambió entre dos versiones de un CV, por sección, a partir del contenido estructurado (no
del PDF). Sin base de datos ni agente: `CvContent` entra y la lista de cambios sale."""

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Literal

from pydantic import BaseModel

from app.schemas.cv import CvContent

ChangeSection = Literal[
    "subtitle",
    "summary",
    "experience",
    "projects",
    "skills",
    "education",
    "certifications",
    "extra_sections",
    "languages",
]


class SectionChange(BaseModel):
    section: ChangeSection
    item: str | None = None  # el puesto, el proyecto o el grupo de skills, si es de uno concreto
    removed: list[str] = []
    added: list[str] = []
    reordered: bool = False  # mismo texto, en otro orden


def _delta(old: Iterable[str], new: Iterable[str]) -> tuple[list[str], list[str]]:
    """Lo que solo está en `old` y lo que solo está en `new`, cada uno en su orden."""
    old_list, new_list = list(old), list(new)
    only_old = Counter(old_list) - Counter(new_list)
    only_new = Counter(new_list) - Counter(old_list)

    def pick(items: list[str], left: Counter[str]) -> list[str]:
        picked = []
        for item in items:
            if left[item] > 0:
                left[item] -= 1
                picked.append(item)
        return picked

    return pick(old_list, only_old), pick(new_list, only_new)


def _list_change(
    section: ChangeSection, old: list[str], new: list[str], item: str | None = None
) -> list[SectionChange]:
    removed, added = _delta(old, new)
    if removed or added:
        return [SectionChange(section=section, item=item, removed=removed, added=added)]
    if old != new:
        return [SectionChange(section=section, item=item, reordered=True)]
    return []


def _blocks(
    section: ChangeSection,
    old: Mapping[str, list[str]],
    new: Mapping[str, list[str]],
    labels: Mapping[str, str],
) -> list[SectionChange]:
    """Bloques con su id (experiencias, proyectos, grupos): dentro de cada uno, sus textos; el orden
    de los bloques, aparte."""
    changes: list[SectionChange] = []
    for key in [*old, *(k for k in new if k not in old)]:
        changes += _list_change(section, old.get(key, []), new.get(key, []), labels.get(key, key))
    common_old = [k for k in old if k in new]
    common_new = [k for k in new if k in old]
    if common_old != common_new:
        changes.append(SectionChange(section=section, reordered=True))
    return changes


def diff(old: CvContent, new: CvContent, labels: Mapping[str, str]) -> list[SectionChange]:
    """Los cambios de `old` a `new`. `labels`: cómo se llama cada id (si falta, el propio id)."""
    changes: list[SectionChange] = []
    if old.subtitle != new.subtitle:
        changes.append(
            SectionChange(section="subtitle", removed=[old.subtitle], added=[new.subtitle])
        )
    if old.summary != new.summary:
        changes.append(SectionChange(section="summary", removed=[old.summary], added=[new.summary]))
    changes += _blocks(
        "experience",
        {e.experience_id: [b.text for b in e.bullets] for e in old.experience},
        {e.experience_id: [b.text for b in e.bullets] for e in new.experience},
        labels,
    )
    changes += _blocks(
        "projects",
        {p.project_id: [b.text for b in p.bullets] for p in old.projects},
        {p.project_id: [b.text for b in p.bullets] for p in new.projects},
        labels,
    )
    changes += _blocks(
        "skills",
        {g.group: g.items for g in old.skills},
        {g.group: g.items for g in new.skills},
        {},
    )
    changes += _list_change("education", old.education_ids, new.education_ids)
    changes += _list_change("certifications", old.certification_ids, new.certification_ids)
    changes += _blocks(
        "extra_sections",
        {s.section_id: s.item_ids for s in old.extra_sections},
        {s.section_id: s.item_ids for s in new.extra_sections},
        {},
    )
    changes += _list_change(
        "languages",
        [f"{item.language}: {item.level}" for item in old.languages],
        [f"{item.language}: {item.level}" for item in new.languages],
    )
    return changes
