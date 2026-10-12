"""«Usar por defecto» en la página Plantillas: fija `preferences.cv.default_template`.

Es la única escritura de `data/profile.yaml` desde la app (el resto lo hace el usuario o su agente
con `update-profile`), así que toca solo esa clave: se edita con ruamel.yaml en modo ida y
vuelta, que conserva comentarios, orden y formato; se valida el resultado antes de escribirlo y se
importa como versión nueva. No hace copia: la versión anterior queda en `profile_versions` (y
`cai profile diff` la muestra). Si alguna regla de `template_rules` elige otra plantilla, se
explica.
"""

import io
import os
from pathlib import Path

from pydantic import BaseModel
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.schemas.profile import TemplateRule
from app.services import profile as profile_service
from app.services.documents import templates


class DefaultTemplateResult(BaseModel):
    template_id: str
    profile_version_id: int
    created: bool
    conflicts: list[str]  # reglas que eligen otra plantilla, en una línea cada una


def _round_trip_yaml() -> YAML:
    yaml = YAML()  # ida y vuelta: conserva comentarios
    yaml.preserve_quotes = True
    yaml.width = 4096  # no reparte líneas largas
    yaml.indent(mapping=2, sequence=4, offset=2)  # como demo/profile.example.yaml
    # `null` explícito (por defecto ruamel lo deja vacío, que cambiaría líneas que no se tocan).
    yaml.representer.add_representer(
        type(None), lambda r, _v: r.represent_scalar("tag:yaml.org,2002:null", "null")
    )
    return yaml


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
    if not path.is_file():
        raise profile_service.ProfileNotFoundError(
            f"No existe {path}: crea tu perfil con el skill `update-profile`."
        )
    yaml = _round_trip_yaml()
    data = yaml.load(path.read_text(encoding="utf-8-sig"))
    try:
        cv = data["preferences"]["cv"]
    except (KeyError, TypeError) as exc:
        raise ValueError("El perfil no tiene `preferences.cv`.") from exc
    if not isinstance(cv, CommentedMap):
        raise ValueError("`preferences.cv` del perfil no es un objeto.")
    if "default_template" in cv:
        cv["default_template"] = template_id
    else:
        cv.insert(0, "default_template", template_id)
    buffer = io.StringIO()
    yaml.dump(data, buffer)

    # Se valida una copia antes de sustituir el perfil: un error no lo deja a medias.
    tmp_dir = get_settings().tmp_dir
    tmp_dir.mkdir(parents=True, exist_ok=True)
    draft = tmp_dir / "profile.default-template.yaml"
    # Bytes tal cual: `write_text` pasaría a CRLF en Windows y cambiaría todas las líneas.
    draft.write_bytes(buffer.getvalue().encode("utf-8"))
    try:
        loaded = profile_service.load_from_yaml(draft)
        os.replace(draft, path)
    finally:
        draft.unlink(missing_ok=True)
    result = profile_service.import_profile(session, path)
    conflicts = [
        f"Las ofertas con {_describe(rule)} seguirán usando «{rule.use}» (regla de "
        "`template_rules`)."
        for rule in loaded.preferences.cv.template_rules
        if rule.use != template_id
    ]
    return DefaultTemplateResult(
        template_id=template_id,
        profile_version_id=result.profile_version_id,
        created=result.created,
        conflicts=conflicts,
    )
