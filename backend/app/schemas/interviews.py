"""Plan de preparación de una entrevista (fase 17). Lo redacta el agente con `preparar-entrevista`
y se guarda en el hito (`milestones.prep_plan`). Ver `services/interviews.py`."""

import datetime as dt
import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

MAX_BLOCKS = 60
# Nombre del dosier dentro de `<carpeta de datos>/entrevistas/`: sin carpetas ni `..`.
_DOSSIER_NAME = re.compile(r"^[\w][\w.-]{0,150}\.md$")


def _dossier_name(value: str) -> str:
    if not _DOSSIER_NAME.fullmatch(value) or ".." in value:
        raise ValueError(
            "Debe ser solo el nombre del fichero dentro de data/entrevistas/, terminado en .md "
            "(p. ej. `42-acme.md`)."
        )
    return value


DossierName = Annotated[str, AfterValidator(_dossier_name)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PrepBlock(_Strict):
    date: dt.date = Field(description="Día del bloque (calendario de Europe/Madrid).")
    minutes: int = Field(ge=15, le=120, description="Duración: entre 15 y 120 minutos.")
    topic: str = Field(min_length=1, max_length=200, description="Qué se prepara.")
    detail: str | None = Field(
        default=None, max_length=1000, description="Cómo: qué repasar, qué historia ensayar…"
    )


class InterviewPlanInput(_Strict):
    dossier: DossierName | None = Field(
        default=None, description="Nombre del dosier en data/entrevistas/ (p. ej. `42-acme.md`)."
    )
    blocks: list[PrepBlock] = Field(
        min_length=1,
        max_length=MAX_BLOCKS,
        description="Bloques de 30-60 min, desde hoy hasta el día de la entrevista.",
    )


class InterviewPlan(InterviewPlanInput):
    """Lo guardado: los bloques por fecha, más quién y cuándo."""

    saved_at: dt.datetime
    agent_name: str | None = None
