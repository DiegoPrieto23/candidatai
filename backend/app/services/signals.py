"""Observaciones del código sobre una oferta que no son riesgo de inyección (fase 16).

Viven en `jobs.signals` (JSON), separadas de `risk_flags`, que sigue significando solo «posible
inyección» (aviso en la ficha, `<untrusted_job_posting risk_flags=…>`). Claves:

- `possibly_closed`: la última comprobación dice que puede estar cerrada (`services/liveness.py`).
  Nunca cierra la oferta: la UI propone descartarla.
- `liveness`: resultado de la última comprobación, sea cual sea.
- `open_confirmed`: el usuario dijo «Sigue abierta»; ese mismo motivo ya no vuelve a avisar.
- `reposted`: publicada varias veces en el mismo canal (`services/reposts.py`).
- Oferta dudosa (fase 25.3, `services/doubtful.py`): `salary_range_wide`, `employer_hidden`,
  `fixed_term`, `ai_screening` y `stale_repost` (este en `services/reposts.py`). No cambian el
  score ni los filtros duros, salvo que el usuario lo pida en `preferences.exclude_signals`.

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


# --- Oferta dudosa (fase 25.3) -----------------------------------------------------------------

SignalOrigin = Literal["extraction", "text", "company"]  # de dónde sale: extracción, texto o nombre


class SalaryRangeSignal(BaseModel):
    min: int
    max: int
    currency: str | None = None
    pct: int  # cuánto supera el máximo al mínimo, en %
    threshold_pct: float


class EmployerHiddenSignal(BaseModel):
    # `agency`: agencia que no dice para quién; `agency_for_client`: agencia que sí lo dice;
    # `unnamed`: el nombre de la empresa no dice quién es («Confidencial», «Importante empresa»).
    reason: Literal["agency", "agency_for_client", "unnamed"]
    origin: SignalOrigin
    client: str | None = None  # para quién, si lo dice
    matched: str | None = None  # el patrón de `config/doubtful_patterns.yaml`, si salió de ahí


class FixedTermSignal(BaseModel):
    origin: SignalOrigin = "extraction"


class AiScreeningSignal(BaseModel):
    origin: SignalOrigin
    matched: str | None = None  # la frase del texto, si salió de ahí


class StaleRepostSignal(BaseModel):
    count: int  # días distintos con publicación nueva en el mismo canal (todo el historial)
    channel: str
    first_seen: date
    last_seen: date
    span_days: int


class JobSignals(BaseModel):
    possibly_closed: ClosedSignal | None = None
    liveness: LivenessCheck | None = None
    open_confirmed: OpenConfirmed | None = None
    reposted: RepostSignal | None = None
    salary_range_wide: SalaryRangeSignal | None = None
    employer_hidden: EmployerHiddenSignal | None = None
    fixed_term: FixedTermSignal | None = None
    ai_screening: AiScreeningSignal | None = None
    stale_repost: StaleRepostSignal | None = None


DoubtfulCode = Literal[
    "salary_range_wide", "employer_hidden", "fixed_term", "stale_repost", "ai_screening"
]
DOUBTFUL_CODES: tuple[DoubtfulCode, ...] = (
    "salary_range_wide",
    "employer_hidden",
    "fixed_term",
    "stale_repost",
    "ai_screening",
)


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
