"""«Mi perfil» editable (fase 25.7): leer y guardar `data/profile.yaml` por secciones.

Solo la UI: quien pulsa «Guardar» es el usuario. Escribir lleva `require_ui` y leer el perfil
completo (con email y teléfono), `require_ui_read`. El agente no tiene nada equivalente: escribe el
perfil con `update-profile` y `expand`, que preguntan antes, y `get_profile` sigue sin contacto.
"""

import base64
import binascii
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from app.agent_interface.errors import ToolError
from app.api.deps import EmptyBody, SessionDep, require_ui, require_ui_read
from app.core.config import get_settings
from app.services import profile as profiles
from app.services import profile_editor, search_titles
from app.services import profile_suggestions as suggestions
from app.services.documents import photo
from app.services.profile import ProfileSection

router = APIRouter(tags=["profile"])


class SaveSectionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_hash: str | None = Field(description="El `file_hash` que leyó la UI.")
    content: Any = Field(description="La sección entera, como la devuelve `GET /profile/editable`.")
    dry_run: bool = False  # devuelve el diff sin escribir


class SalaryFloorBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_hash: str | None = Field(description="El `file_hash` que leyó la UI.")
    salary_floor_eur: int | None = Field(
        gt=0, le=10_000_000, description="Bruto anual en euros; `null` lo quita."
    )


class UndoBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_hash: str | None


@router.get(
    "/profile/editable",
    operation_id="get_editable_profile",
    dependencies=[Depends(require_ui_read)],
)
def get_editable_profile(session: SessionDep) -> profile_editor.EditableProfile:
    """El perfil del fichero tal cual (sin `private`), con su `file_hash` y si valida."""
    return profile_editor.get_editable(session)


@router.post("/profile", operation_id="create_profile", dependencies=[Depends(require_ui)])
def create_profile(
    session: SessionDep, body: profiles.MinimalProfile
) -> profile_editor.CreateResult:
    """«Empezar a mano»: crea tu perfil mínimo sin agente. `conflict` si ya existe el fichero."""
    return profile_editor.create_profile(session, body)


@router.put(
    "/profile/sections/{section}",
    operation_id="save_profile_section",
    dependencies=[Depends(require_ui)],
)
def save_profile_section(
    session: SessionDep, section: ProfileSection, body: SaveSectionBody
) -> profile_editor.SaveResult:
    """Guarda una sección: fusiona con lo que había (conserva comentarios), valida el perfil
    entero, copia el anterior, crea la versión y recalcula los scores. `conflict` si el fichero
    cambió; `referenced` si se borra lo que cita una historia STAR."""
    return profile_editor.save_section(
        session, section, body.content, body.file_hash, dry_run=body.dry_run
    )


@router.get(
    "/profile/salary-floor",
    operation_id="get_salary_floor",
    dependencies=[Depends(require_ui_read)],
)
def get_salary_floor() -> profile_editor.SalaryFloor:
    """Tu sueldo mínimo (`private.salary_floor_eur`). Solo la UI: el agente nunca ve la cifra."""
    return profile_editor.get_salary_floor()


@router.put(
    "/profile/salary-floor",
    operation_id="save_salary_floor",
    dependencies=[Depends(require_ui)],
)
def save_salary_floor(
    session: SessionDep, body: SalaryFloorBody
) -> profile_editor.SalaryFloorResult:
    """Guarda el sueldo mínimo en `private` (sin diff), crea la versión y recalcula los filtros."""
    return profile_editor.save_salary_floor(session, body.salary_floor_eur, body.file_hash)


@router.post("/profile/undo", operation_id="undo_profile", dependencies=[Depends(require_ui)])
def undo_profile(session: SessionDep, body: UndoBody) -> profile_editor.UndoResult:
    """Vuelve a la copia anterior al último guardado."""
    return profile_editor.undo_last(session, body.file_hash)


@router.get(
    "/profile/diff", operation_id="get_profile_diff", dependencies=[Depends(require_ui_read)]
)
def get_profile_diff(session: SessionDep) -> profiles.ProfileDiff:
    """Diff de las dos últimas versiones importadas, como `cai profile diff`: `private` oculto,
    pero con tu contacto, así que solo para la UI."""
    return profiles.diff_last_two(session)


# --- Foto del CV ---------------------------------------------------------------------------------


class UploadPhotoBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # En JSON para que `require_ui` lo compruebe (un formulario no puede). Unos 14 MB en base64.
    content_base64: str = Field(max_length=photo.MAX_PHOTO_BYTES * 4 // 3 + 8)
    # La foto antes de encuadrarla y el recuadro elegido, para volver a encuadrar desde ella.
    original_base64: str | None = Field(default=None, max_length=photo.MAX_PHOTO_BYTES * 4 // 3 + 8)
    crop: photo.PhotoCrop | None = None


def _profile_or_none() -> profiles.CandidateProfile | None:
    """El perfil, si existe y valida. La foto se puede gestionar igual sin él."""
    path = get_settings().data_dir / "profile.yaml"
    try:
        return profiles.load_from_yaml(path) if path.is_file() else None
    except Exception:  # a medio escribir: lo explica la propia página de «Mi perfil»
        return None


@router.get(
    "/profile/photo", operation_id="get_profile_photo", dependencies=[Depends(require_ui_read)]
)
def get_profile_photo() -> photo.PhotoInfo:
    """Si hay foto para el CV y cuál es."""
    return photo.photo_info(photo.current_photo(_profile_or_none()))


@router.get(
    "/profile/photo/file",
    operation_id="get_profile_photo_file",
    dependencies=[Depends(require_ui_read)],
    response_class=FileResponse,
)
def get_profile_photo_file() -> FileResponse:
    """La imagen, para enseñarla en «Mi perfil»."""
    found = photo.current_photo(_profile_or_none())
    if found is None:
        raise ToolError("not_found", "No hay foto.")
    return FileResponse(found, headers={"Cache-Control": "no-store"})


@router.get(
    "/profile/photo/original",
    operation_id="get_profile_photo_original",
    dependencies=[Depends(require_ui_read)],
    response_class=FileResponse,
)
def get_profile_photo_original() -> FileResponse:
    """La foto antes de encuadrarla, para volver a encuadrar. Sin original, la foto actual."""
    found = photo.original_photo() or photo.current_photo(_profile_or_none())
    if found is None:
        raise ToolError("not_found", "No hay foto.")
    return FileResponse(found, headers={"Cache-Control": "no-store"})


@router.put("/profile/photo", operation_id="save_profile_photo", dependencies=[Depends(require_ui)])
def save_profile_photo(session: SessionDep, body: UploadPhotoBody) -> photo.PhotoInfo:
    """Sube la foto (JPG, PNG o WebP, hasta 10 MB) y sustituye la anterior. Si se encuadró en la
    página, con la original y el recuadro."""
    try:
        content = base64.b64decode(body.content_base64, validate=True)
        original = (
            base64.b64decode(body.original_base64, validate=True)
            if body.original_base64 is not None
            else None
        )
        info = photo.save_photo(content, _profile_or_none(), original=original, crop_area=body.crop)
    except (binascii.Error, ValueError) as exc:  # `PhotoError` es un `ValueError`
        raise ToolError("invalid_request", str(exc)) from exc
    profile_editor.record_edit(
        session, "photo", None, "upload", None, profile_editor.file_hash(content)
    )
    return info


@router.delete(
    "/profile/photo", operation_id="delete_profile_photo", dependencies=[Depends(require_ui)]
)
def delete_profile_photo(session: SessionDep, body: EmptyBody) -> photo.PhotoInfo:
    """Quita la foto: los CV siguientes salen sin ella."""
    info = photo.delete_photo(_profile_or_none())
    profile_editor.record_edit(session, "photo", None, "delete", None, None)
    return info


# --- Puestos que sugerir en «Buscar ofertas» ---------------------------------------------------


@router.get(
    "/profile/role-suggestions",
    operation_id="list_role_suggestions",
    dependencies=[Depends(require_ui_read)],
)
def list_role_suggestions(session: SessionDep) -> list[search_titles.RoleSuggestion]:
    """Títulos de lo que apruebas que tus puestos aún no cubren, para añadirlos con un clic."""
    return search_titles.role_suggestions(session)


# --- Propuestas de tu agente (fase 41.2) ------------------------------------------------------


@router.get(
    "/profile/suggestions",
    operation_id="list_profile_suggestions",
    dependencies=[Depends(require_ui_read)],
)
def list_profile_suggestions(session: SessionDep) -> suggestions.PendingSuggestions:
    """Lo que tu agente propone para tu perfil (hoy, el resumen en inglés), pendiente de revisar."""
    return suggestions.pending(session)


@router.post(
    "/profile/suggestions/{suggestion_id}/used",
    operation_id="use_profile_suggestion",
    dependencies=[Depends(require_ui)],
)
def use_profile_suggestion(
    session: SessionDep, suggestion_id: int, body: EmptyBody
) -> suggestions.PendingSuggestions:
    """La pasaste al formulario: deja de estar pendiente. El perfil se guarda con «Guardar»."""
    suggestions.resolve(session, suggestion_id, "used")
    return suggestions.pending(session)


@router.post(
    "/profile/suggestions/{suggestion_id}/discard",
    operation_id="discard_profile_suggestion",
    dependencies=[Depends(require_ui)],
)
def discard_profile_suggestion(
    session: SessionDep, suggestion_id: int, body: EmptyBody
) -> suggestions.PendingSuggestions:
    suggestions.resolve(session, suggestion_id, "discarded")
    return suggestions.pending(session)
