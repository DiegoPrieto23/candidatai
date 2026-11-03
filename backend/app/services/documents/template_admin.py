"""Renombrar y eliminar desde la página Plantillas las plantillas propias (`data/templates/`).

Las integradas no se tocan: viven en el repositorio y una actualización las repondría.
"""

import shutil
from pathlib import Path

from pydantic import BaseModel, Field
from ruamel.yaml import YAML
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services import profile as profile_service
from app.services import profile_editor
from app.services.documents import templates, uploads
from app.services.documents.templates import META_FILE

MAX_NAME = 80


class TemplateNotEditableError(ValueError):
    """Es una plantilla integrada: ni se renombra ni se elimina."""


class RenameTemplateInput(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_NAME)


class DeleteTemplateResult(BaseModel):
    template_id: str
    default_cleared: bool  # era la plantilla por defecto: ahora la elige la app


def is_user_template(template: templates.Template) -> bool:
    user_dir = get_settings().user_templates_dir.resolve()
    return template.path.resolve().parent == user_dir


def _own_folder(template_id: str) -> Path:
    """La carpeta de una plantilla propia. Una rota también se puede eliminar."""
    try:
        template = templates.get(template_id)
    except templates.TemplateNotFoundError:
        template = None
    if template is not None:
        if not is_user_template(template):
            raise TemplateNotEditableError(
                f"«{template.meta.name}» es una plantilla integrada: solo se cambian las tuyas."
            )
        return template.path
    root = get_settings().user_templates_dir.resolve()
    folder = (root / template_id).resolve()
    if folder.parent != root or not (folder / META_FILE).is_file():
        raise templates.TemplateNotFoundError(f"La plantilla «{template_id}» no existe.")
    return folder


def rename_template(template_id: str, name: str) -> None:
    """Cambia solo el nombre que se ve. El `id` sigue igual: los CVs ya hechos lo usan."""
    clean = " ".join(name.split())
    if not clean:
        raise ValueError("El nombre no puede estar vacío.")
    path = _own_folder(template_id) / META_FILE
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.width = 4096
    with path.open(encoding="utf-8") as fh:
        data = yaml.load(fh)
    data["name"] = clean
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        yaml.dump(data, fh)


def _clear_default(session: Session, template_id: str, path: Path | None = None) -> bool:
    """Si era la plantilla por defecto, deja de serlo: por el editor del perfil, que valida, copia
    y versiona. Las reglas de `template_rules` no se tocan: las escribiste tú, y si piden una
    plantilla que falta la app avisa y sigue con la siguiente opción."""
    path = path or profile_service.default_path()
    state = profile_editor.get_editable(session, path)
    if not state.exists:
        return False
    preferences = (state.profile or {}).get("preferences")
    if not isinstance(preferences, dict) or not isinstance(preferences.get("cv"), dict):
        return False
    if preferences["cv"].get("default_template") != template_id:
        return False
    preferences["cv"]["default_template"] = None
    profile_editor.save_section(session, "preferences", preferences, state.file_hash, path=path)
    return True


def delete_template(session: Session, template_id: str) -> DeleteTemplateResult:
    """Elimina una plantilla propia y el CV subido del que salió (si no, volvería a salir como
    «pendiente de convertir»). Los CVs ya generados conservan sus PDF y su Word."""
    folder = _own_folder(template_id)
    source_uploads = [
        upload.name for upload in uploads.list_uploads() if upload.template_id == template_id
    ]
    default_cleared = _clear_default(session, template_id)
    shutil.rmtree(folder)
    for name in source_uploads:
        uploads.delete_upload(name)
    return DeleteTemplateResult(template_id=template_id, default_cleared=default_cleared)
