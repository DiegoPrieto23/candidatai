"""«Es lo mismo que…» (página Skills, fase 14): añade un sinónimo a `config/skill_aliases.yaml`.

Es la única escritura de ese fichero desde la app. Se edita con ruamel.yaml en modo ida y vuelta,
que conserva comentarios, orden y el estilo `[a, b]` de cada línea; se escribe en un temporal junto
al fichero y se sustituye de una vez, para no dejarlo a medias. Cambiar los alias cambia el
`scoring_key`, así que se encola `rescore_all` y el worker recalcula las ofertas abiertas (la
caché de alias depende de la fecha del fichero: el worker ve el cambio sin reiniciarse).

Nunca se propone un alias solo: lo decide el usuario en la UI (fuera de alcance, fase 14). Ver
`docs/POLICIES.md` §2 y ADR-026.
"""

import io
import os
import tempfile
import threading
from pathlib import Path

import yaml as pyyaml
from pydantic import BaseModel
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from sqlalchemy.orm import Session

from app.core import policies
from app.schemas.profile import CandidateProfile
from app.services import profile as profiles
from app.services import tasks
from app.services.matching import skills

# Leer, cambiar y escribir el fichero es una sección crítica: dos «Es lo mismo que…» seguidos
# (rutas síncronas en el threadpool de la API) no deben pisarse.
_LOCK = threading.Lock()


class AliasConflictError(ValueError):
    """El sinónimo ya apunta a otra skill: se cambiaría lo que significa otra entrada."""


class AliasResult(BaseModel):
    ok: bool = True
    skill: str  # el sinónimo, como lo escriben las ofertas
    canonical: str  # la entrada de `skill_aliases.yaml` a la que se añade
    profile_skill: str
    added: bool  # False si ya era sinónimo (no se toca el fichero)
    rescore_queued: bool


def _round_trip_yaml() -> YAML:
    yaml = YAML()  # ida y vuelta: conserva comentarios y orden
    yaml.preserve_quotes = True
    yaml.width = 4096  # no reparte líneas largas
    return yaml


def _canonical_name(key: str, fallback: str) -> str:
    """La entrada de `skill_aliases.yaml` de una forma canónica (o `fallback`, si no hay)."""
    for name, aliases in policies.get_skill_aliases().items():
        if skills.skill_key(name) == key:
            return name
        if any(skills.skill_key(a) == key for a in aliases):
            return name
    return fallback


def _load(path: Path, yaml: YAML) -> tuple[object, str]:
    """El YAML de ida y vuelta y su fin de línea (en Windows, git suele dejarlo en CRLF)."""
    if not path.is_file():
        return None, "\n"
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8-sig").replace("\r\n", "\n")  # ruamel guardaría el \r en comentarios
    return yaml.load(text), newline


def _write(path: Path, data: CommentedMap, yaml: YAML, newline: str = "\n") -> None:
    buffer = io.StringIO()
    yaml.dump(data, buffer)
    text = buffer.getvalue().replace("\n", newline)
    parsed = pyyaml.safe_load(text)  # lo que se escribe tiene que poder leerse
    if not isinstance(parsed, dict):
        raise ValueError(f"{path.name} quedaría inválido; no se ha tocado.")
    fd, name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    draft = Path(name)
    try:
        # Bytes tal cual: `write_text` pasaría a CRLF en Windows y cambiaría todas las líneas.
        with os.fdopen(fd, "wb") as fh:
            fh.write(text.encode("utf-8"))
        os.replace(draft, path)
    except PermissionError as exc:  # en Windows, si otro programa tiene el fichero abierto
        raise ValueError(
            f"No se pudo escribir config/{path.name}: ciérralo si lo tienes abierto y reinténtalo."
        ) from exc
    finally:
        draft.unlink(missing_ok=True)


def add_alias(
    session: Session, skill: str, profile_skill: str, path: Path | None = None
) -> AliasResult:
    """Hace de `skill` un sinónimo de `profile_skill` (una skill o un básico del perfil).

    Si ya hay una entrada para esa skill, se añade a su lista; si no, se crea al final con el
    nombre del perfil. Falla si el sinónimo ya apunta a otra skill o si el perfil ya lo cubre."""
    path = path or policies.SKILL_ALIASES_PATH
    alias = skill.strip()
    alias_key = skills.skill_key(alias)
    if not alias_key:
        raise ValueError("La skill no puede quedar vacía.")
    profile = profiles.current(session).profile
    names = [s.name for s in profile.skills] + list(profile.basic_skills)
    wanted = skills.skill_key(profile_skill)
    match = next((n for n in names if skills.skill_key(n) == wanted), None)
    if match is None:
        raise ValueError(f"«{profile_skill}» no está entre las skills de tu perfil.")

    with _LOCK:  # el índice se lee dentro: otro alias recién escrito cuenta
        result = _add_locked(alias, alias_key, match, profile, path)
    if result.added:
        tasks.enqueue(session, "rescore_all")
    return result


def _add_locked(
    alias: str,
    alias_key: str,
    match: str,
    profile: CandidateProfile,
    path: Path,
) -> AliasResult:
    index = skills.alias_index()
    target = skills.canonical(match, index)
    current = index.get(alias_key, alias_key)
    if current == target:
        return AliasResult(
            skill=alias,
            canonical=_canonical_name(target, match),
            profile_skill=match,
            added=False,
            rescore_queued=False,
        )
    if alias_key in index:
        raise AliasConflictError(
            f"«{alias}» ya es sinónimo de «{_canonical_name(current, current)}» en "
            f"config/{path.name}. Cámbialo a mano si de verdad son lo mismo."
        )
    levels = skills.profile_levels(profile, index)
    if current in levels:
        raise AliasConflictError(f"«{alias}» ya la cubre tu perfil como «{levels[current][0]}».")

    yaml = _round_trip_yaml()
    data, newline = _load(path, yaml)
    if data is None:
        data = CommentedMap()
    if not isinstance(data, CommentedMap):
        raise ValueError(f"config/{path.name} debe ser un diccionario nombre -> sinónimos.")
    entry = next((k for k in data if skills.skill_key(str(k)) == target), None)
    if entry is None:
        entry = match
        data[entry] = None
    seq = data[entry]
    if not isinstance(seq, CommentedSeq):
        seq = CommentedSeq(list(seq or []))
        seq.fa.set_flow_style()  # como el resto: `Nombre: [a, b]`
        data[entry] = seq
    seq.append(alias)
    # Se escribe antes de encolar el recálculo: si el encolado fallara, el `scoring_key` distinto
    # haría que el siguiente `rescore_all` o `get_match` lo recalcule igual.
    _write(path, data, yaml, newline)
    return AliasResult(
        skill=alias, canonical=str(entry), profile_skill=match, added=True, rescore_queued=True
    )
