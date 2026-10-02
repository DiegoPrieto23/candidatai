"""Importación de CVs como plantillas (fase 08.3: `.docx`; la 08b añade PDF, imagen y HTML).

- `paths`: todo se lee y se escribe dentro de `data/`.
- `docx_xml`: párrafos numerados del Word, con sus fragmentos fusionados. `inspect` y `build`
  numeran igual, así que los índices del mapeo son los de `inspect`.
- `inspect`: qué tiene el CV (diseño, secciones, capacidad, aptitud para ATS).
- `mapping` y `build`: el mapeo párrafo → marcador que decide el agente, y la plantilla resultante.
"""

from pydantic import BaseModel


class ImportIssue(BaseModel):
    field: str
    received: str | None
    reason: str


class TemplateImportError(ValueError):
    """El mapeo o el fichero no sirven; `issues` dice dónde y por qué, para corregir."""

    def __init__(self, message: str, issues: list[ImportIssue] | None = None) -> None:
        self.issues = issues or []
        super().__init__(message)
