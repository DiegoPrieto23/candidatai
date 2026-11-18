"""Historial del perfil para personas: qué cambió en cada versión, por bloques de «Mi perfil».

Compara los datos ya interpretados de dos versiones (`profile_versions.data`), no el texto del YAML:
el resultado no depende de comentarios, espacios ni orden de claves. Cada cambio dice en qué bloque
del editor cae, qué elemento toca (por su `id` o su nombre, para que cambiar el orden se vea como
«movido» y no como quitar y añadir) y, campo a campo, lo de antes y lo de ahora.

`private` (el sueldo mínimo) solo dice que ha cambiado, nunca sus valores. El resto lleva tu
contacto, así que todo esto es solo para la UI, como el diff de texto de siempre.
"""

from __future__ import annotations

import difflib
import json
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.profiles import ProfileVersion
from app.schemas.profile import CandidateProfile
from app.services import profile as profiles

Block = Literal[
    "personal",
    "experience",
    "projects",
    "education",
    "certifications",
    "extra",
    "languages",
    "skills",
    "stories",
    "cv",
    "letter",
    "search",
    "private",
]
BLOCK_ORDER: tuple[Block, ...] = (
    "personal",
    "experience",
    "projects",
    "education",
    "certifications",
    "extra",
    "languages",
    "skills",
    "stories",
    "cv",
    "letter",
    "search",
    "private",
)
ChangeKind = Literal["added", "removed", "changed", "moved"]

PAGE_SIZE = 20
LABEL_MAX = 90
# Las claves que no se enseñan: los ids son internos y `schema_version` no lo edita nadie.
_HIDDEN_KEYS = {"id"}


class FieldChange(BaseModel):
    """Un campo dentro de un elemento. En listas de textos, lo que entra y lo que sale."""

    path: list[str]  # p. ej. ["end"], ["summary", "es"], ["photo_policy", "by_country", "US"]
    before: Any = None
    after: Any = None
    added: list[str] = []
    removed: list[str] = []


class ItemChange(BaseModel):
    block: Block
    kind: ChangeKind
    label: str | None = None  # «Data Engineer · DataGal»; None: el bloque entero (p. ej. el CV)
    parent: str | None = None  # el elemento que lo contiene (la experiencia de un logro)
    within: str | None = None  # la lista anidada donde está: "achievements", "items"…
    fields: list[FieldChange] = []
    position: tuple[int, int] | None = None  # «movido»: de la posición a la posición (desde 1)
    hidden: bool = False  # `private`: ha cambiado, sin enseñar qué


class BlockCount(BaseModel):
    block: Block
    changes: int


class VersionEntry(BaseModel):
    id: int
    created_at: datetime
    origin: profiles.VersionOrigin | None
    first: bool  # la primera versión: no hay con qué compararla
    current: bool
    restorable: bool  # valida con el esquema de hoy y no es la actual
    summary: list[BlockCount]


class VersionPage(BaseModel):
    versions: list[VersionEntry]
    has_more: bool


class VersionChanges(BaseModel):
    id: int
    previous_id: int | None
    created_at: datetime
    origin: profiles.VersionOrigin | None
    current: bool
    restorable: bool
    changes: list[ItemChange]
    # Los bloques que cambiarían al volver a esta versión (frente a la actual).
    restore_blocks: list[Block]
    technical_diff: str  # el diff de texto de siempre, para «Ver el cambio técnico»


# --- Comparación -----------------------------------------------------------------------------


def _blank(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def _short(text: Any) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= LABEL_MAX else text[: LABEL_MAX - 1].rstrip() + "…"


def _text(value: Any) -> str:
    """Un valor de una lista para enseñarlo: un texto, o `clave: valor` si es un objeto."""
    if isinstance(value, dict):
        label = _item_label(value)
        if label:
            return label
        parts = [f"{k}: {_text(v)}" for k, v in value.items() if not _blank(v)]
        return _short("; ".join(parts))
    if isinstance(value, list):
        return ", ".join(_text(v) for v in value)
    return _short(value)


def _localized(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("es", "en"):
            if isinstance(value.get(key), str) and value[key].strip():
                return value[key]
        return None
    return value if isinstance(value, str) and value.strip() else None


def _label_key(item: dict[str, Any]) -> str | None:
    """El campo que por sí solo da el nombre de un elemento (no los nombres compuestos)."""
    if (item.get("role") and item.get("company")) or (item.get("title") and item.get("center")):
        return None
    return next((k for k in ("name", "language", "title", "text") if _localized(item.get(k))), None)


def _item_label(item: dict[str, Any]) -> str | None:
    """El nombre con el que una persona reconoce un elemento."""
    if item.get("role") and item.get("company"):
        return _short(f"{item['role']} · {item['company']}")
    if item.get("title") and item.get("center"):
        return _short(f"{item['title']} · {item['center']}")
    key = _label_key(item)
    return _short(_localized(item[key])) if key else None


def _key(item: Any, field: str | None) -> str:
    if isinstance(item, dict) and field and isinstance(item.get(field), str):
        return item[field].strip().casefold() if field != "id" else item[field]
    return json.dumps(item, sort_keys=True, ensure_ascii=False)


def _identity(old: list[Any], new: list[Any]) -> str | None:
    """El campo que identifica un elemento en las dos listas: su `id` o su nombre."""
    items = [*old, *new]
    for field in ("id", "name", "language"):
        if items and all(isinstance(i, dict) and isinstance(i.get(field), str) for i in items):
            return field
    return None


def _keys(items: list[Any], field: str | None) -> list[str]:
    """Las claves de una lista; repetidas, con su número de aparición para no mezclarlas."""
    seen: dict[str, int] = {}
    out: list[str] = []
    for item in items:
        key = _key(item, field)
        seen[key] = seen.get(key, 0) + 1
        out.append(key if seen[key] == 1 else f"{key}#{seen[key]}")
    return out


def _is_record_list(value: Any) -> bool:
    return isinstance(value, list) and any(isinstance(v, dict) for v in value)


def _leaves(value: Any, path: list[str], *, side: Literal["before", "after"]) -> list[FieldChange]:
    """Los campos con valor de un elemento entero (lo añadido o lo quitado)."""
    out: list[FieldChange] = []
    if isinstance(value, dict):
        for key, item in value.items():
            # Un `false` en algo nuevo es el valor por defecto («Confidencial: No»): no dice nada.
            if key in _HIDDEN_KEYS or _blank(item) or item is False:
                continue
            out.extend(_leaves(item, [*path, key], side=side))
        return out
    if isinstance(value, list):
        texts = [_text(v) for v in value if not _blank(v)]
        change = FieldChange(path=path)
        if side == "after":
            change.added = texts
        else:
            change.removed = texts
        return [change] if texts else []
    if _blank(value):
        return []
    return [FieldChange(path=path, **{side: value})]


def _diff_value(
    old: Any, new: Any, path: list[str], nested: list[tuple[str, list[Any], list[Any]]]
) -> list[FieldChange]:
    """Los campos que cambian entre dos valores. Las listas de registros con `id` (los logros de
    una experiencia) no salen aquí: se apuntan en `nested` para compararlas elemento a elemento."""
    if _blank(old) and _blank(new):
        return []
    if isinstance(old, dict) or isinstance(new, dict):
        old_d = old if isinstance(old, dict) else {}
        new_d = new if isinstance(new, dict) else {}
        out: list[FieldChange] = []
        for key in [*new_d, *(k for k in old_d if k not in new_d)]:
            if key in _HIDDEN_KEYS:
                continue
            out.extend(_diff_value(old_d.get(key), new_d.get(key), [*path, key], nested))
        return out
    if isinstance(old, list) or isinstance(new, list):
        old_l = old if isinstance(old, list) else []
        new_l = new if isinstance(new, list) else []
        if (_is_record_list(old_l) or _is_record_list(new_l)) and _identity(old_l, new_l) == "id":
            if old_l != new_l:
                nested.append((path[-1], old_l, new_l))
            return []
        if old_l == new_l:
            return []
        old_t, new_t = [_text(v) for v in old_l], [_text(v) for v in new_l]
        added = [t for t in new_t if t not in old_t]
        removed = [t for t in old_t if t not in new_t]
        if added or removed:
            return [FieldChange(path=path, added=added, removed=removed)]
        return [FieldChange(path=path, before=old_t, after=new_t)]  # el mismo contenido, otro orden
    if old == new:
        return []
    return [FieldChange(path=path, before=old, after=new)]


def _without_label(fields: list[FieldChange], item: Any, nested: bool) -> list[FieldChange]:
    """Sin el campo que ya es el nombre del elemento («Rust» no necesita «Nombre: Rust»). Los de
    una lista anidada (un logro) se titulan por su padre: ahí el texto se queda."""
    key = _label_key(item) if isinstance(item, dict) and not nested else None
    return [f for f in fields if f.path != [key]]


def _diff_list(
    block: Block,
    old: list[Any],
    new: list[Any],
    *,
    parent: str | None = None,
    list_name: str | None = None,
) -> list[ItemChange]:
    """Elemento a elemento: añadidos, quitados, cambiados y movidos."""
    field = _identity(old, new)
    old_keys, new_keys = _keys(old, field), _keys(new, field)
    old_by, new_by = dict(zip(old_keys, old, strict=True)), dict(zip(new_keys, new, strict=True))
    common_old = [k for k in old_keys if k in new_by]
    common_new = [k for k in new_keys if k in old_by]
    matcher = difflib.SequenceMatcher(a=common_old, b=common_new, autojunk=False)
    stayed = {
        k
        for block_ in matcher.get_matching_blocks()
        for k in common_old[block_.a : block_.a + block_.size]
    }

    changes: list[ItemChange] = []
    for index, key in enumerate(new_keys):
        item = new_by[key]
        label = _item_label(item) if isinstance(item, dict) else _short(item)
        if key not in old_by:
            changes.append(
                ItemChange(
                    block=block,
                    kind="added",
                    label=label,
                    parent=parent,
                    within=list_name,
                    fields=_without_label(_leaves(item, [], side="after"), item, bool(list_name)),
                )
            )
            continue
        before = old_by[key]
        nested: list[tuple[str, list[Any], list[Any]]] = []
        fields = _diff_value(before, item, [], nested)
        moved = key not in stayed
        if fields or moved:
            changes.append(
                ItemChange(
                    block=block,
                    kind="changed" if fields else "moved",
                    label=label,
                    parent=parent,
                    within=list_name,
                    fields=fields,
                    position=(old_keys.index(key) + 1, index + 1) if moved else None,
                )
            )
        for name, old_items, new_items in nested:
            changes.extend(_diff_list(block, old_items, new_items, parent=label, list_name=name))
    for key in old_keys:
        if key not in new_by:
            item = old_by[key]
            removed_label = _item_label(item) if isinstance(item, dict) else _short(item)
            changes.append(
                ItemChange(
                    block=block,
                    kind="removed",
                    label=removed_label,
                    parent=parent,
                    within=list_name,
                    fields=_without_label(_leaves(item, [], side="before"), item, bool(list_name)),
                )
            )
    return changes


def _whole(block: Block, old: Any, new: Any, path: list[str]) -> list[ItemChange]:
    """Un bloque sin elementos (el CV, la carta, tu búsqueda): un solo cambio con sus campos."""
    nested: list[tuple[str, list[Any], list[Any]]] = []
    fields = _diff_value(old, new, path, nested)
    out = [ItemChange(block=block, kind="changed", fields=fields)] if fields else []
    for name, old_items, new_items in nested:
        out.extend(_diff_list(block, old_items, new_items, list_name=name))
    return out


_LIST_BLOCKS: dict[str, Block] = {
    "experience": "experience",
    "projects": "projects",
    "education": "education",
    "certifications": "certifications",
    "extra_sections": "extra",
    "languages": "languages",
    "skills": "skills",
    "stories": "stories",
}
_PREFERENCE_BLOCKS: dict[str, Block] = {"cv": "cv", "cover_letter": "letter"}


def compare(old: dict[str, Any], new: dict[str, Any]) -> list[ItemChange]:
    """Lo que cambia de `old` a `new`, en el orden de los bloques de «Mi perfil»."""
    changes: list[ItemChange] = []
    personal: list[FieldChange] = []
    nested: list[tuple[str, list[Any], list[Any]]] = []
    for key in ("personal", "headline", "summary"):
        path = [] if key == "personal" else [key]
        personal.extend(_diff_value(old.get(key), new.get(key), path, nested))
    if personal:
        changes.append(ItemChange(block="personal", kind="changed", fields=personal))
    for name, old_items, new_items in nested:  # hoy ninguno: por si el esquema gana una lista
        changes.extend(_diff_list("personal", old_items, new_items, list_name=name))
    nested = []
    for key, block in _LIST_BLOCKS.items():
        changes.extend(_diff_list(block, old.get(key) or [], new.get(key) or []))
    basic = _diff_value(old.get("basic_skills"), new.get("basic_skills"), ["basic_skills"], nested)
    if basic:
        changes.append(ItemChange(block="skills", kind="changed", fields=basic))
    for name, old_items, new_items in nested:
        changes.extend(_diff_list("skills", old_items, new_items, list_name=name))
    old_prefs, new_prefs = old.get("preferences") or {}, new.get("preferences") or {}
    for key, block in _PREFERENCE_BLOCKS.items():
        changes.extend(_whole(block, old_prefs.get(key), new_prefs.get(key), []))
    rest = [k for k in [*new_prefs, *old_prefs] if k not in _PREFERENCE_BLOCKS]
    search_old = {k: old_prefs.get(k) for k in dict.fromkeys(rest)}
    search_new = {k: new_prefs.get(k) for k in dict.fromkeys(rest)}
    changes.extend(_whole("search", search_old, search_new, []))
    if (old.get("private") or {}) != (new.get("private") or {}):
        changes.append(ItemChange(block="private", kind="changed", hidden=True))
    order = {block: i for i, block in enumerate(BLOCK_ORDER)}
    return sorted(changes, key=lambda c: order[c.block])  # estable: dentro del bloque, su orden


def blocks_of(changes: list[ItemChange]) -> list[Block]:
    return list(dict.fromkeys(c.block for c in changes))


def summarize(changes: list[ItemChange]) -> list[BlockCount]:
    counts: dict[Block, int] = {}
    for change in changes:
        counts[change.block] = counts.get(change.block, 0) + 1
    return [BlockCount(block=block, changes=n) for block, n in counts.items()]


# --- Versiones -------------------------------------------------------------------------------


def _restorable(version: ProfileVersion, current: ProfileVersion) -> bool:
    if version.id == current.id or version.data == current.data:
        return False
    try:
        CandidateProfile.model_validate(version.data)
    except ValidationError:
        return False
    return True


def _latest(session: Session) -> ProfileVersion:
    latest = session.scalar(select(ProfileVersion).order_by(ProfileVersion.id.desc()).limit(1))
    if latest is None:
        raise profiles.ProfileNotFoundError(profiles.NO_PROFILE)
    return latest


def list_versions(session: Session, offset: int = 0, limit: int = PAGE_SIZE) -> VersionPage:
    """Las versiones de la más reciente a la más antigua, cada una con lo que cambió por bloque."""
    current = _latest(session)
    stmt = select(ProfileVersion).order_by(ProfileVersion.id.desc()).offset(offset).limit(limit + 1)
    rows = list(session.scalars(stmt))  # una más: la anterior a la última de la página
    entries: list[VersionEntry] = []
    for index, version in enumerate(rows[:limit]):
        previous = rows[index + 1] if index + 1 < len(rows) else None
        changes = compare(previous.data, version.data) if previous else []
        entries.append(
            VersionEntry(
                id=version.id,
                created_at=version.created_at,
                origin=version.origin,  # type: ignore[arg-type]  # lo escribe `import_profile`
                first=previous is None,
                current=version.id == current.id,
                restorable=_restorable(version, current),
                summary=summarize(changes),
            )
        )
    return VersionPage(versions=entries, has_more=len(rows) > limit)


def _get(session: Session, version_id: int) -> ProfileVersion:
    version = session.get(ProfileVersion, version_id)
    if version is None:
        raise profiles.ProfileNotFoundError(f"No existe la versión de perfil {version_id}.")
    return version


def _previous(session: Session, version_id: int) -> ProfileVersion | None:
    stmt = (
        select(ProfileVersion)
        .where(ProfileVersion.id < version_id)
        .order_by(ProfileVersion.id.desc())
        .limit(1)
    )
    return session.scalar(stmt)


def version_changes(session: Session, version_id: int) -> VersionChanges:
    """Lo que cambió una versión frente a la anterior, y lo que cambiaría volver a ella."""
    version = _get(session, version_id)
    previous = _previous(session, version_id)
    current = _latest(session)
    return VersionChanges(
        id=version.id,
        previous_id=previous.id if previous else None,
        created_at=version.created_at,
        origin=version.origin,  # type: ignore[arg-type]
        current=version.id == current.id,
        restorable=_restorable(version, current),
        changes=compare(previous.data, version.data) if previous else [],
        restore_blocks=blocks_of(compare(current.data, version.data)),
        technical_diff=profiles.diff_versions(previous, version) if previous else "",
    )
