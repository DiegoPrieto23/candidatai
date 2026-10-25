"""«Mi perfil» editable (fase 25.7): leer y guardar `data/profile.yaml` por secciones.

Solo la UI: quien pulsa «Guardar» es el usuario. Escribir lleva `require_ui` y leer el perfil
completo (con email y teléfono), `require_ui_read`. El agente no tiene nada equivalente: escribe el
perfil con `update-profile` y `expand`, que preguntan antes, y `get_profile` sigue sin contacto.
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import SessionDep, require_ui, require_ui_read
from app.services import profile as profiles
from app.services import profile_editor
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
