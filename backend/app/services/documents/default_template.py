"""«Usar por defecto» en la página Plantillas: fija `preferences.cv.default_template`.

Toca solo esa clave y va por el editor de «Mi perfil» (`profile_editor`, fase 25.7): ruamel.yaml
en modo ida y vuelta (conserva comentarios, orden y formato), validación antes de escribir, copia
en `data/profile-history/`, versión nueva y auditoría. Si alguna regla de `template_rules` elige
otra plantilla, se explica.
"""

from pathlib import Path

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.schemas.profile import TemplateRule
from app.services import profile as profile_service
from app.services import profile_editor
from app.services.documents import templates


class DefaultTemplateResult(BaseModel):
    template_id: str
    profile_version_id: int
    created: bool
    conflicts: list[str]  # reglas que eligen otra plantilla, en una línea cada una


def _describe(rule: TemplateRule) -> str:
    when = rule.when
    parts = []
    if when.ats:
        parts.append("ATS " + ", ".join(when.ats))
    if when.country:
        parts.append("país " + ", ".join(when.country))
    if when.domain:
        parts.append("sector " + ", ".join(when.domain))
    if when.language:
        parts.append("idioma " + ", ".join(when.language))
    return " y ".join(parts)


def set_default_template(
    session: Session, template_id: str, path: Path | None = None
) -> DefaultTemplateResult:
    templates.validate(template_id)  # que exista y sea válida antes de apuntar a ella
    path = path or profile_service.default_path()
    state = profile_editor.get_editable(session, path)
    if not state.exists:
        raise profile_service.ProfileNotFoundError(
            f"No existe {path}: crea tu perfil con el skill `update-profile`."
        )
    preferences = (state.profile or {}).get("preferences")
    if not isinstance(preferences, dict) or not isinstance(preferences.get("cv"), dict):
        raise ValueError("El perfil no tiene `preferences.cv`.")
    preferences["cv"]["default_template"] = template_id
    # Por el editor de «Mi perfil» (fase 25.7): misma validación, copia, versión y auditoría.
    saved = profile_editor.save_section(
        session, "preferences", preferences, state.file_hash, path=path
    )
    loaded = profile_service.load_from_yaml(path)
    version_id = saved.profile_version_id or profile_service.current(session).profile_version_id
    conflicts = [
        f"Las ofertas con {_describe(rule)} seguirán usando «{rule.use}» (regla de "
        "`template_rules`)."
        for rule in loaded.preferences.cv.template_rules
        if rule.use != template_id
    ]
    return DefaultTemplateResult(
        template_id=template_id,
        profile_version_id=version_id,
        created=saved.version_created,
        conflicts=conflicts,
    )
