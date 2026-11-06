"""Plantillas integradas que el usuario ha eliminado de su lista (`data/templates-hidden.json`).

Las integradas viven en el repositorio y una actualización las repondría, así que «eliminar» una de
ellas la quita de la lista (de la galería, del selector de cada oferta y de lo que ve el agente) sin
borrar nada del programa, y se puede restaurar. Seguir existiendo es lo que permite que un CV ya
hecho con esa plantilla se pueda volver a renderizar y que la app tenga siempre sus plantillas de
respaldo.
"""

import json
from pathlib import Path

from app.core.config import get_settings

HIDDEN_FILE = "templates-hidden.json"


def _path() -> Path:
    return get_settings().data_dir / HIDDEN_FILE


def hidden_ids() -> set[str]:
    """Los `id` quitados de la lista. Un fichero ausente o roto cuenta como ninguno."""
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    if not isinstance(data, list):
        return set()
    return {item for item in data if isinstance(item, str)}


def _write(ids: set[str]) -> None:
    path = _path()
    if not ids:
        path.unlink(missing_ok=True)
        return
    path.write_text(json.dumps(sorted(ids), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def hide(template_id: str) -> None:
    _write(hidden_ids() | {template_id})


def restore(template_id: str) -> bool:
    """Vuelve a poner una plantilla en la lista. `False` si no estaba quitada."""
    ids = hidden_ids()
    if template_id not in ids:
        return False
    _write(ids - {template_id})
    return True
