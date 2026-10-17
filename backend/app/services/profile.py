"""Perfil del candidato: validar `data/profile.yaml`, versionarlo y exponer su vista pública.

`data/profile.yaml` es lo que edita la persona (o su agente con el skill `update-profile`); lo
que usa la app es la última versión importada en `profile_versions`. Ver `docs/POLICIES.md` §1 y §4.
"""

import difflib
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, get_args

import yaml
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.core.validation import describe_error
from app.models import ProfileVersion
from app.schemas.profile import CandidateProfile, ProfileConsistencyError
from app.services import tasks

EXAMPLE_PATH = REPO_ROOT / "demo" / "profile.example.yaml"

ProfileSection = Literal[
    "personal",
    "headline",
    "summary",
    "experience",
    "projects",
    "education",
    "certifications",
    "extra_sections",
    "languages",
    "skills",
    "basic_skills",
    "stories",
    "preferences",
]
# Lista blanca: un campo nuevo de `personal` o una sección nueva no salen hasta añadirlos aquí.
PUBLIC_SECTIONS: tuple[ProfileSection, ...] = get_args(ProfileSection)
PUBLIC_PERSONAL_FIELDS = (
    "name",
    "linkedin",
    "github",
    "city",
    "profile_location",
    "availability",
    "mobility",
)
HIDDEN = "<oculto>"


class ProfileIssue(BaseModel):
    field: str  # p. ej. `experience[1].achievements[0].id`
    received: str | None
    reason: str


class ProfileValidationError(ValueError):
    """El fichero no es un perfil válido. `issues` trae un problema por campo."""

    def __init__(self, path: Path, issues: list[ProfileIssue]) -> None:
        self.path = path
        self.issues = issues
        count = len(issues)
        noun = "error" if count == 1 else "errores"
        super().__init__(f"Perfil no válido ({count} {noun}): {path}")


class ProfileNotFoundError(LookupError):
    pass


NO_PROFILE = (
    "Aún no hay perfil importado: crea data/profile.yaml (skill `update-profile`) y ejecuta "
    "`cai profile import`."
)


class EvidenceNotFoundError(LookupError):
    pass


class ImportResult(BaseModel):
    profile_version_id: int
    created: bool  # False si el contenido es igual al de la versión actual
    content_hash: str


class StoredProfile(BaseModel):
    profile_version_id: int
    created_at: datetime
    profile: CandidateProfile


class PublicProfile(BaseModel):
    """Lo que devuelve `get_profile`: sin email, teléfono ni `private`."""

    profile_version_id: int
    created_at: datetime
    profile: dict[str, Any]


class ProfileDiff(BaseModel):
    from_version: int | None  # None si solo hay una versión
    to_version: int
    diff: str  # diff unificado del YAML de las dos versiones; vacío si no hay con qué comparar


def default_path() -> Path:
    return get_settings().data_dir / "profile.yaml"


def field_path(loc: tuple[str | int, ...]) -> str:
    """`("experience", 1, "achievements", 0, "id")` -> `experience[1].achievements[0].id`."""
    out = ""
    for part in loc:
        if part == "[key]":  # Pydantic lo añade cuando falla la clave de un diccionario
            continue
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out or "(perfil)"


def issues_of(exc: ValidationError) -> list[ProfileIssue]:
    """Los problemas de un `ValidationError` del perfil, uno por campo."""
    issues: list[ProfileIssue] = []
    for error in exc.errors(include_url=False):
        cause = (error.get("ctx") or {}).get("error")
        if isinstance(cause, ProfileConsistencyError):
            issues.extend(
                ProfileIssue(field=field_path(i.loc), received=i.received, reason=i.reason)
                for i in cause.issues
            )
            continue
        received, reason = describe_error(error)
        field = field_path(error["loc"])
        issues.append(ProfileIssue(field=field, received=received, reason=reason))
    return issues


def load_from_yaml(path: Path) -> CandidateProfile:
    """Lee y valida un perfil. Lanza `ProfileValidationError` con todos los problemas a la vez."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise ProfileNotFoundError(f"No existe {path}. Créalo con `cai profile init`.") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f"línea {mark.line + 1}, columna {mark.column + 1}: " if mark else ""
        problem = getattr(exc, "problem", None) or str(exc)
        issue = ProfileIssue(field="(yaml)", received=None, reason=f"{where}{problem}")
        raise ProfileValidationError(path, [issue]) from exc
    if not isinstance(data, dict):
        issue = ProfileIssue(field="(perfil)", received=None, reason="Debe ser un objeto YAML.")
        raise ProfileValidationError(path, [issue])
    try:
        return CandidateProfile.model_validate(data)
    except ValidationError as exc:
        raise ProfileValidationError(path, issues_of(exc)) from exc


def content_hash(profile: CandidateProfile) -> str:
    """sha256 de los datos validados: comentarios, espacios u orden de claves no cuentan."""
    canonical = json.dumps(
        profile.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _latest(session: Session, limit: int = 1) -> list[ProfileVersion]:
    stmt = select(ProfileVersion).order_by(ProfileVersion.id.desc()).limit(limit)
    return list(session.scalars(stmt))


def import_profile(session: Session, path: Path) -> ImportResult:
    """Valida el fichero y crea una versión nueva, salvo que sea igual a la actual.

    Una versión nueva encola `rescore_all`: el worker recalcula los matches de las ofertas abiertas.
    """
    profile = load_from_yaml(path)
    digest = content_hash(profile)
    latest = _latest(session)
    if latest and latest[0].content_hash == digest:
        return ImportResult(profile_version_id=latest[0].id, created=False, content_hash=digest)
    version = ProfileVersion(data=profile.model_dump(mode="json"), content_hash=digest)
    session.add(version)
    session.flush()
    tasks.enqueue(session, "rescore_all")
    return ImportResult(profile_version_id=version.id, created=True, content_hash=digest)


def _stored(version: ProfileVersion) -> StoredProfile:
    return StoredProfile(
        profile_version_id=version.id,
        created_at=version.created_at,
        profile=CandidateProfile.model_validate(version.data),
    )


def current(session: Session) -> StoredProfile:
    """La versión vigente (la última importada)."""
    latest = _latest(session)
    if not latest:
        raise ProfileNotFoundError(NO_PROFILE)
    return _stored(latest[0])


def get_version(session: Session, version_id: int) -> StoredProfile:
    version = session.get(ProfileVersion, version_id)
    if version is None:
        raise ProfileNotFoundError(f"No existe la versión de perfil {version_id}.")
    return _stored(version)


def public_view(
    profile: CandidateProfile, sections: list[ProfileSection] | None = None
) -> dict[str, Any]:
    """El perfil sin teléfono, email ni `private` (lo que devuelve la MCP), por secciones."""
    data = profile.model_dump(mode="json")
    wanted = [s for s in PUBLIC_SECTIONS if sections is None or s in sections]
    view: dict[str, Any] = {"schema_version": data["schema_version"]}
    for section in wanted:
        view[section] = data[section]
    if "personal" in view:
        view["personal"] = {k: data["personal"][k] for k in PUBLIC_PERSONAL_FIELDS}
    return view


def get_public_profile(
    session: Session, sections: list[ProfileSection] | None = None
) -> PublicProfile:
    stored = current(session)
    return PublicProfile(
        profile_version_id=stored.profile_version_id,
        created_at=stored.created_at,
        profile=public_view(stored.profile, sections),
    )


def _diffable_yaml(data: dict[str, Any]) -> list[str]:
    # `private` no se enseña ni en local: el agente que lee el diff no necesita esos datos.
    shown = {**data, "private": HIDDEN} if data.get("private") else data
    text = yaml.safe_dump(shown, allow_unicode=True, sort_keys=False, width=100)
    return text.splitlines(keepends=True)


def diff_last_two(session: Session) -> ProfileDiff:
    """Diff unificado entre las dos últimas versiones. `private` sale como `<oculto>`."""
    versions = _latest(session, limit=2)
    if not versions:
        raise ProfileNotFoundError(NO_PROFILE)
    new = versions[0]
    if len(versions) == 1:
        return ProfileDiff(from_version=None, to_version=new.id, diff="")
    old = versions[1]
    old_lines, new_lines = _diffable_yaml(old.data), _diffable_yaml(new.data)
    if old.data.get("private") != new.data.get("private"):
        new_lines = [*new_lines, "# private: ha cambiado\n"]
    diff = difflib.unified_diff(
        old_lines, new_lines, fromfile=f"versión {old.id}", tofile=f"versión {new.id}"
    )
    return ProfileDiff(from_version=old.id, to_version=new.id, diff="".join(diff))


def init_profile(dest: Path | None = None) -> Path:
    """Copia el perfil de ejemplo a `data/profile.yaml`. Nunca sobrescribe uno existente."""
    dest = dest or default_path()
    if dest.exists():
        raise FileExistsError(f"Ya existe {dest}: no se sobrescribe.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(EXAMPLE_PATH, dest)
    return dest


def resolve_evidence(profile: CandidateProfile, ref: str) -> str:
    """Texto de una evidencia (`exp-acme/a2`, `prj-x`…), con su métrica y la marca NDA si la hay.

    Recibe el perfil de una versión concreta: un CV se verifica contra la versión con la que se
    redactó, no contra la actual.
    """
    refs = profile.evidence_refs()
    if ref not in refs:
        raise EvidenceNotFoundError(f"La evidencia «{ref}» no existe en el perfil.")
    return refs[ref]
