"""«Mi perfil» editable (fase 25.7, ADR-039): guardar una sección de `data/profile.yaml` desde
la UI.

Solo la UI escribe por aquí (las rutas llevan `require_ui`); el agente sigue escribiendo el perfil
con `update-profile` y `expand`, que preguntan antes, y no tiene ninguna herramienta de escritura.

Cada guardado:

1. comprueba que el fichero no ha cambiado desde que lo leyó la UI (`file_hash`, sha256 de sus
   bytes): si lo editó el usuario a mano o su agente, `ProfileConflictError` y no se escribe;
2. aplica la sección con ruamel.yaml en modo ida y vuelta y la **fusiona** con lo que había
   (por `id` en las listas), así que se conservan los comentarios, el orden y el estilo de lo que
   no cambia, también dentro de la sección. `content` es la sección **entera**, como la da
   `get_editable`: una clave que no venga se borra. Las listas de objetos sin `id` (`languages`,
   `skills`, `template_rules`) se sustituyen enteras si cambian, sin los comentarios de dentro;
3. genera los ids que falten a partir del nombre (`exp-acme`, `a3`, `st-…`), que ya no cambian
   aunque se renombre;
4. rechaza borrar algo que cita una historia STAR (`ProfileReferencedError`) y avisa si lo citan
   CVs o cartas ya generados (guardan su versión del perfil, así que se permite);
5. valida el perfil entero (los mismos `ProfileIssue` que `cai profile validate`);
6. con `dry_run`, devuelve el diff sin escribir. Si no, copia el fichero anterior a
   `data/profile-history/` (las `history_keep` últimas), lo sustituye de una vez e importa la
   versión (`import_profile`: crea versión y encola `rescore_all` solo si cambian los datos);
7. deja una fila en `profile_edits` (sección y hashes, sin el contenido).

«Deshacer» vuelve a escribir la copia más reciente de `profile-history/` por el mismo camino y la
quita de la lista, así que deshacer otra vez va un paso más atrás.
"""

import difflib
import hashlib
import io
import os
import re
import tempfile
import threading
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml as pyyaml
from pydantic import BaseModel, ValidationError
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import (
    DoubleQuotedScalarString,
    FoldedScalarString,
    LiteralScalarString,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import policies
from app.core.config import get_settings
from app.models import Document, Job, ProfileEdit
from app.schemas.profile import SALARY_FLOOR_KEY, CandidateProfile
from app.services import profile as profiles
from app.services.profile import ProfileIssue, ProfileSection, ProfileValidationError

# Leer, cambiar y escribir el fichero es una sección crítica: dos guardados seguidos (rutas
# síncronas en el threadpool de la API) no deben pisarse.
_LOCK = threading.Lock()

# Prefijo de los ids de primer nivel que genera el servidor (como en demo/profile.example.yaml).
ID_PREFIX = {
    "experience": "exp",
    "projects": "prj",
    "education": "edu",
    "certifications": "cert",
    "stories": "st",
}
# Campo del que sale el nombre del id.
ID_SOURCE = {
    "experience": "company",
    "projects": "name",
    "education": "title",
    "certifications": "name",
    "stories": "title",
    "extra_sections": "title",
}
LIST_SECTIONS = tuple(ID_SOURCE)


class ProfileConflictError(ValueError):
    """El fichero cambió desde que lo leyó la UI: no se sobrescribe a ciegas."""

    def __init__(self, current_hash: str | None, name: str = "profile.yaml") -> None:
        self.current_hash = current_hash
        super().__init__(
            f"data/{name} ha cambiado desde que lo abriste (lo editaste a mano o tu agente). "
            "Recarga para ver lo nuevo y vuelve a aplicar tu cambio."
        )


class ProfileReferencedError(ValueError):
    """Se borraría algo que cita una historia STAR."""

    def __init__(self, refs: dict[str, list[str]]) -> None:
        self.refs = refs  # evidencia -> títulos de las historias que la citan
        listed = "; ".join(f"«{ref}» (en {', '.join(titles)})" for ref, titles in refs.items())
        super().__init__(
            f"No se puede borrar lo que citan tus historias STAR: {listed}. Quita antes esa "
            "evidencia de la historia o borra la historia."
        )


class NothingToUndoError(LookupError):
    pass


class EditableProfile(BaseModel):
    """Lo que ve el editor de la UI: el perfil del fichero tal cual, con email y teléfono."""

    exists: bool
    file_hash: str | None  # sha256 de los bytes del fichero: va de vuelta en cada guardado
    profile: dict[str, Any] | None  # sin `private`; `None` si el YAML no se puede leer
    issues: list[ProfileIssue]  # el fichero no valida: se enseñan, pero se puede seguir editando
    profile_version_id: int | None  # la versión importada vigente
    undo_available: int  # copias en `profile-history/`
    # Las de `config/policies.yaml`, que se suman a `preferences.discard_title_keywords`.
    policy_discard_title_keywords: list[str] = []


class SaveResult(BaseModel):
    section: ProfileSection
    dry_run: bool
    changed: bool  # el fichero cambia (en `dry_run`, cambiaría)
    diff: str  # diff unificado del YAML; vacío si no cambia
    file_hash: str  # el del fichero después (en `dry_run`, el de ahora)
    profile_version_id: int | None
    version_created: bool
    rescore_queued: bool
    generated_ids: list[str]  # ids nuevos que puso el servidor
    warnings: list[str]  # p. ej. un CV generado cita lo que se borra


class UndoResult(BaseModel):
    restored_from: str  # nombre de la copia
    file_hash: str
    profile_version_id: int
    version_created: bool
    undo_available: int


# --- YAML de ida y vuelta -------------------------------------------------------------------


def round_trip_yaml() -> YAML:
    yaml = YAML()  # ida y vuelta: conserva comentarios
    yaml.preserve_quotes = True
    yaml.width = 4096  # no reparte líneas largas
    yaml.indent(mapping=2, sequence=4, offset=2)  # como demo/profile.example.yaml
    # `null` explícito (por defecto ruamel lo deja vacío, que cambiaría líneas que no se tocan).
    yaml.representer.add_representer(
        type(None), lambda r, _v: r.represent_scalar("tag:yaml.org,2002:null", "null")
    )
    return yaml


def file_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read(path: Path) -> bytes | None:
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _text(raw: bytes) -> str:
    # ruamel guardaría el \r en los comentarios: se trabaja con \n y se vuelve al final.
    return raw.decode("utf-8-sig").replace("\r\n", "\n")


def atomic_write(path: Path, text: str) -> None:
    """Escribe en un temporal junto al fichero y lo sustituye de una vez."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    draft = Path(name)
    try:
        # Bytes tal cual: `write_text` pasaría a CRLF en Windows y cambiaría todas las líneas.
        with os.fdopen(fd, "wb") as fh:
            fh.write(text.encode("utf-8"))
        os.replace(draft, path)
    except PermissionError as exc:  # en Windows, si otro programa tiene el fichero abierto
        raise ValueError(
            f"No se pudo escribir {path.name}: ciérralo si lo tienes abierto y reinténtalo."
        ) from exc
    finally:
        draft.unlink(missing_ok=True)


# --- Fusión de una sección -------------------------------------------------------------------


def _clean(value: Any) -> Any:
    """Lo que manda un formulario: `""` es «sin valor» y las listas no llevan huecos."""
    if isinstance(value, str):
        return value if value.strip() else None
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, list):
        items = [_clean(v) for v in value]
        return [v for v in items if v is not None]
    return value


def _blank(value: Any) -> bool:
    """Valores por defecto que no merece la pena escribir en una clave que no estaba."""
    return value is None or value is False or value == [] or value == {}


def _to_yaml(value: Any) -> Any:
    if isinstance(value, dict):
        node = CommentedMap()
        for key, item in value.items():
            if not _blank(item):
                node[key] = _to_yaml(item)
        return node
    if isinstance(value, list):
        seq = CommentedSeq([_to_yaml(v) for v in value])
        if value and all(not isinstance(v, (dict, list)) for v in value):
            seq.fa.set_flow_style()  # `[a, b]`, como las listas cortas del ejemplo
        return seq
    if isinstance(value, str):
        if "\n" in value.strip("\n"):
            return LiteralScalarString(value)
        return value if _reads_as_text(value) else DoubleQuotedScalarString(value)
    return value


def _reads_as_text(value: str) -> bool:
    """Si, sin comillas, YAML lo volvería a leer como este texto (y no `no` como False o
    `+34600000000` como número)."""
    try:
        return pyyaml.safe_load(value) == value
    except pyyaml.YAMLError:
        return False


def _same_scalar(old: Any, new: Any) -> bool:
    if isinstance(old, str) and isinstance(new, str):
        # Un `>` de YAML termina en salto de línea; el formulario puede no devolverlo.
        return old.rstrip("\n") == new.rstrip("\n")
    if isinstance(old, bool) or isinstance(new, bool):  # `True == 1` en Python
        return isinstance(old, bool) and isinstance(new, bool) and old == new
    if isinstance(old, str) or isinstance(new, str):
        return False
    return bool(old == new)  # ruamel lee los decimales como `ScalarFloat`: por valor


def _ids(items: Any) -> list[Any] | None:
    if not isinstance(items, list) or not all(isinstance(i, dict) and "id" in i for i in items):
        return None
    return [i["id"] for i in items]


def _merge(old: Any, new: Any) -> Any:
    """`new` sobre `old` conservando lo de `old` (comentarios, estilo) que no cambia."""
    if isinstance(new, dict):
        if not isinstance(old, CommentedMap):
            return _to_yaml(new)
        for key in list(old.keys()):
            if new.get(key) is None:
                del old[key]
        for key, value in new.items():
            if value is None:
                continue
            if key in old:
                old[key] = _merge(old[key], value)
            elif not _blank(value):
                old[key] = _to_yaml(value)
        return old
    if isinstance(new, list):
        if not isinstance(old, CommentedSeq):
            return _to_yaml(new)
        old_ids, new_ids = _ids(old), _ids(new)
        if old_ids is not None and new_ids is not None:
            by_id = {item["id"]: item for item in old}
            merged = [
                _merge(by_id[item["id"]], item) if item["id"] in by_id else _to_yaml(item)
                for item in new
            ]
            if old_ids == new_ids:  # mismo orden: en su sitio, con sus comentarios
                for i, item in enumerate(merged):
                    old[i] = item
                return old
            old.clear()
            old.extend(merged)
            return old
        if len(old) == len(new) and all(_same_scalar(a, b) for a, b in zip(old, new, strict=True)):
            return old
        seq = _to_yaml(new)
        if old.fa.flow_style() != seq.fa.flow_style():
            seq.fa.set_flow_style() if old.fa.flow_style() else seq.fa.set_block_style()
        return seq
    if _same_scalar(old, new):
        return old
    if isinstance(new, str) and isinstance(old, (FoldedScalarString, LiteralScalarString)):
        # Mismo final que tenía: `>` termina en salto de línea y `>-`, no.
        return type(old)(new.rstrip("\n") + ("\n" if old.endswith("\n") else ""))
    if isinstance(new, str) and isinstance(old, str) and type(old) is not str:
        return type(old)(new)  # con las mismas comillas que tenía
    return _to_yaml(new)


# --- Ids -------------------------------------------------------------------------------------


def slug(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    plain = re.sub(r"\([^)]*\)", " ", plain.lower())  # «(ficticia)» no va en el id
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")[:40].strip("-")


def _top_ids(data: dict[str, Any]) -> set[str]:
    return {
        str(item["id"])
        for section in LIST_SECTIONS
        for item in data.get(section) or []
        if isinstance(item, dict) and item.get("id")
    }


def _unique(base: str, taken: set[str]) -> str:
    candidate, n = base, 2
    while candidate in taken:
        candidate, n = f"{base}-{n}", n + 1
    taken.add(candidate)
    return candidate


def _name_of(section: str, item: dict[str, Any]) -> str:
    value = item.get(ID_SOURCE[section])
    if isinstance(value, dict):  # el título de una sección extra va por idioma
        value = value.get("es") or value.get("en")
    return str(value or "")


def _next_child_id(prefix: str, children: list[dict[str, Any]]) -> str:
    taken = {str(c.get("id")) for c in children if c.get("id")}
    n = 1
    while f"{prefix}{n}" in taken:
        n += 1
    return f"{prefix}{n}"


def assign_ids(section: str, value: Any, others: set[str]) -> list[str]:
    """Pone los ids que falten (en el sitio) y devuelve los nuevos. `others`: los de otras
    secciones, que también tienen que ser únicos."""
    if section not in LIST_SECTIONS or not isinstance(value, list):
        return []
    generated: list[str] = []
    taken = others | {str(i["id"]) for i in value if isinstance(i, dict) and i.get("id")}
    for item in value:
        if not isinstance(item, dict):
            continue
        if not item.get("id"):
            base = slug(_name_of(section, item)) or "item"
            prefix = ID_PREFIX.get(section)
            item["id"] = _unique(f"{prefix}-{base}" if prefix else base, taken)
            generated.append(item["id"])
        children_key = {"experience": "achievements", "extra_sections": "items"}.get(section)
        children = item.get(children_key) if children_key else None
        if isinstance(children, list):
            child_prefix = "a" if section == "experience" else (str(item["id"])[:1] or "i")
            for child in children:
                if isinstance(child, dict) and not child.get("id"):
                    child["id"] = _next_child_id(child_prefix, children)
                    generated.append(f"{item['id']}/{child['id']}")
    return generated


def evidence_keys(data: dict[str, Any]) -> set[str]:
    """Las referencias citables de un perfil sin validar (las mismas que `evidence_refs`)."""
    keys: set[str] = set()
    for exp in data.get("experience") or []:
        if isinstance(exp, dict) and exp.get("id"):
            keys.add(str(exp["id"]))
            for ach in exp.get("achievements") or []:
                if isinstance(ach, dict) and ach.get("id"):
                    keys.add(f"{exp['id']}/{ach['id']}")
    for section in ("projects", "education", "certifications"):
        for item in data.get(section) or []:
            if isinstance(item, dict) and item.get("id"):
                keys.add(str(item["id"]))
    for extra in data.get("extra_sections") or []:
        if isinstance(extra, dict) and extra.get("id"):
            for item in extra.get("items") or []:
                if isinstance(item, dict) and item.get("id"):
                    keys.add(f"{extra['id']}/{item['id']}")
    return keys


def _cited_by_stories(data: dict[str, Any], removed: set[str]) -> dict[str, list[str]]:
    cited: dict[str, list[str]] = {}
    for story in data.get("stories") or []:
        if not isinstance(story, dict):
            continue
        for ref in story.get("evidence") or []:
            if ref in removed:
                cited.setdefault(ref, []).append(str(story.get("title") or story.get("id")))
    return cited


def _strings(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value}
    if isinstance(value, dict):
        return {s for v in value.values() for s in _strings(v)}
    if isinstance(value, list):
        return {s for v in value for s in _strings(v)}
    return set()


def _cited_by_documents(session: Session, removed: set[str]) -> list[str]:
    """CVs y cartas generados que citan lo que se borra (sus evidencias son textos sueltos)."""
    if not removed:
        return []
    warnings: set[str] = set()
    rows = session.execute(
        select(Document.kind, Document.content, Job.title).join(Job, Job.id == Document.job_id)
    ).all()
    kinds = {"cv": "El CV", "cover_letter": "La carta"}
    for kind, content, title in rows:
        for ref in sorted(removed & _strings(content)):
            label = kinds.get(kind, "Un documento")
            warnings.add(
                f"{label} de «{title}» cita «{ref}»: no cambia (guarda su versión del perfil), "
                "pero si lo rehaces ya no podrá citarlo."
            )
    return sorted(warnings)


# --- Lectura ---------------------------------------------------------------------------------


def history_dir() -> Path:
    return get_settings().data_dir / "profile-history"


def _history() -> list[Path]:
    folder = history_dir()
    return sorted(folder.glob("*.yaml")) if folder.is_dir() else []


def _validate(text: str, path: Path) -> CandidateProfile:
    data = pyyaml.safe_load(text)
    if not isinstance(data, dict):
        issue = ProfileIssue(field="(perfil)", received=None, reason="Debe ser un objeto YAML.")
        raise ProfileValidationError(path, [issue])
    try:
        return CandidateProfile.model_validate(data)
    except ValidationError as exc:
        raise ProfileValidationError(path, profiles.issues_of(exc)) from exc


def get_editable(session: Session, path: Path | None = None) -> EditableProfile:
    path = path or profiles.default_path()
    raw = _read(path)
    try:
        version_id = profiles.current(session).profile_version_id
    except profiles.ProfileNotFoundError:
        version_id = None
    undo = len(_history())
    policy_words = list(policies.get_policies().hard_filters.discard_title_keywords)
    if raw is None:
        return EditableProfile(
            exists=False,
            file_hash=None,
            profile=None,
            issues=[],
            profile_version_id=version_id,
            undo_available=undo,
            policy_discard_title_keywords=policy_words,
        )
    data: Any = None
    issues: list[ProfileIssue] = []
    try:
        data = pyyaml.safe_load(_text(raw))
        profiles.load_from_yaml(path)
    except pyyaml.YAMLError:
        data = None
        issues = [ProfileIssue(field="(yaml)", received=None, reason="El YAML no se puede leer.")]
    except ProfileValidationError as exc:
        issues = exc.issues
    shown = {k: v for k, v in data.items() if k != "private"} if isinstance(data, dict) else None
    return EditableProfile(
        exists=True,
        file_hash=file_hash(raw),
        profile=shown,
        issues=issues,
        profile_version_id=version_id,
        undo_available=undo,
        policy_discard_title_keywords=policy_words,
    )


# --- Escritura -------------------------------------------------------------------------------


def record_edit(
    session: Session,
    target: str,
    section: str | None,
    action: str,
    before: str | None,
    after: str | None,
) -> None:
    """Una fila de `profile_edits`: lo que guardó la UI (perfil, contexto o muestra), sin texto."""
    session.add(
        ProfileEdit(
            target=target, section=section, action=action, hash_before=before, hash_after=after
        )
    )
    session.flush()


def _backup(raw: bytes) -> None:
    folder = history_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    (folder / f"{stamp}.yaml").write_bytes(raw)
    keep = policies.get_policies().profile_editing.history_keep
    for old in _history()[:-keep]:
        old.unlink(missing_ok=True)


def _diff(old: str, new: str) -> str:
    lines = difflib.unified_diff(
        old.splitlines(keepends=True),
        new.splitlines(keepends=True),
        fromfile="profile.yaml (ahora)",
        tofile="profile.yaml (con tu cambio)",
    )
    return "".join(lines)


def save_section(
    session: Session,
    section: ProfileSection,
    content: Any,
    expected_hash: str | None,
    dry_run: bool = False,
    path: Path | None = None,
) -> SaveResult:
    """Guarda una sección del perfil desde la UI (ver el docstring del módulo)."""
    path = path or profiles.default_path()
    with _LOCK:
        raw = _read(path)
        if raw is None:
            raise profiles.ProfileNotFoundError(
                f"No existe {path}: crea tu perfil con el skill `update-profile` o `cai profile "
                "init`."
            )
        current = file_hash(raw)
        if expected_hash != current:
            raise ProfileConflictError(current)
        newline = "\r\n" if b"\r\n" in raw else "\n"
        old_text = _text(raw)
        yaml = round_trip_yaml()
        data = yaml.load(old_text)
        if not isinstance(data, CommentedMap):
            raise ValueError("data/profile.yaml no es un objeto YAML: arréglalo en tu editor.")

        plain_old = pyyaml.safe_load(old_text) or {}
        value = _clean(content)
        others = _top_ids({k: v for k, v in plain_old.items() if k != section})
        generated = assign_ids(section, value, others)
        if value is None:
            data.pop(section, None)
        else:
            data[section] = _merge(data.get(section), value)

        buffer = io.StringIO()
        yaml.dump(data, buffer)
        new_text = buffer.getvalue()
        plain_new = pyyaml.safe_load(new_text) or {}
        removed = evidence_keys(plain_old) - evidence_keys(plain_new)
        cited = _cited_by_stories(plain_new, removed)
        if cited:
            raise ProfileReferencedError(cited)
        _validate(new_text, path)  # ProfileValidationError con todos los problemas
        warnings = _cited_by_documents(session, removed)

        changed = new_text != old_text
        diff = _diff(old_text, new_text) if changed else ""
        if dry_run or not changed:
            return SaveResult(
                section=section,
                dry_run=dry_run,
                changed=changed,
                diff=diff,
                file_hash=current,
                profile_version_id=None,
                version_created=False,
                rescore_queued=False,
                generated_ids=generated,
                warnings=warnings,
            )
        out = new_text.replace("\n", newline)
        atomic_write(path, out)
        _backup(raw)  # después: si la escritura falla, no queda una copia que no deshace nada
        # Dentro del lock: `import_profile` vuelve a leer el fichero.
        imported = profiles.import_profile(session, path)
    after = file_hash(out.encode("utf-8"))
    record_edit(session, "profile", section, "save", current, after)
    return SaveResult(
        section=section,
        dry_run=False,
        changed=True,
        diff=diff,
        file_hash=after,
        profile_version_id=imported.profile_version_id,
        version_created=imported.created,
        rescore_queued=imported.created,
        generated_ids=generated,
        warnings=warnings,
    )


def undo_last(session: Session, expected_hash: str | None, path: Path | None = None) -> UndoResult:
    """Vuelve a la copia más reciente de `profile-history/` (validada, versión y rescore)."""
    path = path or profiles.default_path()
    with _LOCK:
        raw = _read(path)
        current = file_hash(raw) if raw is not None else None
        if expected_hash != current:
            raise ProfileConflictError(current)
        history = _history()
        if not history:
            raise NothingToUndoError("No hay ningún cambio que deshacer.")
        latest = history[-1]
        backup = latest.read_bytes()
        _validate(_text(backup), latest)
        restored = backup.decode("utf-8-sig")  # sin BOM, como escribe `save_section`
        atomic_write(path, restored)
        latest.unlink()
        imported = profiles.import_profile(session, path)
    after = file_hash(restored.encode("utf-8"))  # el de los bytes que se han escrito
    record_edit(session, "profile", None, "undo", current, after)
    return UndoResult(
        restored_from=latest.name,
        file_hash=after,
        profile_version_id=imported.profile_version_id,
        version_created=imported.created,
        undo_available=len(_history()),
    )


# --- Sueldo mínimo (privado) -----------------------------------------------------------------


class SalaryFloor(BaseModel):
    """`private.salary_floor_eur` (bruto anual en euros) para la UI. Nunca sale hacia el agente."""

    salary_floor_eur: int | None
    file_hash: str | None


class SalaryFloorResult(BaseModel):
    """Sin diff: la cifra no se enseña ni en el historial (ADR-046)."""

    changed: bool
    file_hash: str
    profile_version_id: int | None
    rescore_queued: bool


def get_salary_floor(path: Path | None = None) -> SalaryFloor:
    path = path or profiles.default_path()
    raw = _read(path)
    if raw is None:
        return SalaryFloor(salary_floor_eur=None, file_hash=None)
    try:
        data = pyyaml.safe_load(_text(raw))
    except pyyaml.YAMLError:
        data = None
    private = data.get("private") if isinstance(data, dict) else None
    value = private.get(SALARY_FLOOR_KEY) if isinstance(private, dict) else None
    valid = isinstance(value, int) and not isinstance(value, bool) and value > 0
    return SalaryFloor(salary_floor_eur=value if valid else None, file_hash=file_hash(raw))


def save_salary_floor(
    session: Session, value: int | None, expected_hash: str | None, path: Path | None = None
) -> SalaryFloorResult:
    """Escribe `private.salary_floor_eur` como un guardado de sección (conflicto, copia, versión y
    recálculo), sin tocar el resto de `private`. `None` lo deja en `null`."""
    path = path or profiles.default_path()
    with _LOCK:
        raw = _read(path)
        if raw is None:
            raise profiles.ProfileNotFoundError(
                f"No existe {path}: crea tu perfil con el skill `update-profile` o `cai profile "
                "init`."
            )
        current = file_hash(raw)
        if expected_hash != current:
            raise ProfileConflictError(current)
        newline = "\r\n" if b"\r\n" in raw else "\n"
        old_text = _text(raw)
        yaml = round_trip_yaml()
        data = yaml.load(old_text)
        if not isinstance(data, CommentedMap):
            raise ValueError("data/profile.yaml no es un objeto YAML: arréglalo en tu editor.")
        private = data.get("private")
        if not isinstance(private, CommentedMap):
            if value is None:
                return SalaryFloorResult(
                    changed=False, file_hash=current, profile_version_id=None, rescore_queued=False
                )
            private = CommentedMap()
            data["private"] = private
        if value is None and SALARY_FLOOR_KEY not in private:
            return SalaryFloorResult(
                changed=False, file_hash=current, profile_version_id=None, rescore_queued=False
            )
        private[SALARY_FLOOR_KEY] = value
        buffer = io.StringIO()
        yaml.dump(data, buffer)
        new_text = buffer.getvalue()
        if new_text == old_text:
            return SalaryFloorResult(
                changed=False, file_hash=current, profile_version_id=None, rescore_queued=False
            )
        _validate(new_text, path)
        out = new_text.replace("\n", newline)
        atomic_write(path, out)
        _backup(raw)
        imported = profiles.import_profile(session, path)
    after = file_hash(out.encode("utf-8"))
    record_edit(session, "profile", "private", "save", current, after)
    return SalaryFloorResult(
        changed=True,
        file_hash=after,
        profile_version_id=imported.profile_version_id,
        rescore_queued=imported.created,
    )
