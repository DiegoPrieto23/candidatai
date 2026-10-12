"""Observaciones del código sobre una oferta que no son riesgo de inyección (fase 16, ADR-028).

Viven en `jobs.signals` (JSON), separadas de `risk_flags`, que sigue significando solo «posible
inyección» (aviso en la ficha, `<untrusted_job_posting risk_flags=…>`). Claves:

- `possibly_closed`: la última comprobación dice que puede estar cerrada (`services/liveness.py`).
  Nunca cierra la oferta: la UI propone descartarla.
- `liveness`: resultado de la última comprobación, sea cual sea.
- `open_confirmed`: el usuario dijo «Sigue abierta»; ese mismo motivo ya no vuelve a avisar.
- `reposted`: publicada varias veces en el mismo canal (`services/reposts.py`).

Son observaciones, no veredictos: el usuario decide.
"""

import logging
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from app.models import Job

logger = logging.getLogger(__name__)

LivenessStatus = Literal["open", "possibly_closed", "unknown", "skipped"]
ClosedReason = Literal[
    "http_404", "http_410", "redirected", "closed_text", "expired_date", "ats_missing"
]


class ClosedSignal(BaseModel):
    since: datetime  # primera comprobación que lo detectó
    checked_at: datetime  # última comprobación que lo confirma
    reason: ClosedReason
    detail: str
    http_status: int | None = None


class LivenessCheck(BaseModel):
    checked_at: datetime
    status: LivenessStatus
    reason: str | None = None
    detail: str = ""
    http_status: int | None = None


class OpenConfirmed(BaseModel):
    at: datetime
    reason: str | None = None  # el motivo del aviso que el usuario descartó


class RepostSignal(BaseModel):
    count: int  # días distintos en que apareció una publicación nueva
    dates: list[date]
    channel: str
    window_days: int


class JobSignals(BaseModel):
    possibly_closed: ClosedSignal | None = None
    liveness: LivenessCheck | None = None
    open_confirmed: OpenConfirmed | None = None
    reposted: RepostSignal | None = None


def read(job: Job) -> JobSignals:
    """Las señales tipadas de una oferta. Una clave mal formada (editada a mano) se ignora."""
    raw: dict[str, Any] = dict(job.signals or {})
    values: dict[str, Any] = {}
    for key in JobSignals.model_fields:
        if raw.get(key) is None:
            continue
        try:
            values[key] = getattr(JobSignals.model_validate({key: raw[key]}), key)
        except ValidationError:
            logger.warning("Señal «%s» no válida en la oferta %s: se ignora", key, job.id)
    return JobSignals(**values)


def set_signal(job: Job, key: str, value: BaseModel | None) -> None:
    """Escribe (o borra, con `None`) una señal. Asigna un dict nuevo para que SQLAlchemy lo vea."""
    data = dict(job.signals or {})
    if value is None:
        if key not in data:
            return
        data.pop(key)
    else:
        data[key] = value.model_dump(mode="json")
    job.signals = data
