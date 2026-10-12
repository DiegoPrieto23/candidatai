"""Ofertas recibidas: datos, comparación y vista para el agente (fase 21).

El usuario anota en la ficha la oferta que le ha hecho la empresa (fijo, variable, beneficios,
modalidad, fechas). Es una por oferta de empleo: si la empresa la mejora, se sobrescribe y queda
una nota en el historial, sin cifras (el historial lo leen los agentes).

- **Privacidad** (POLICIES §4): con `amounts_private` (por defecto) fijo y variable no salen nunca
  por la interfaz para agentes (`agent_view`). La comparación con `private.salary_floor_eur` y con
  el rango publicado se calcula aquí y solo la sirve la API a la UI (`compare`): el agente nunca
  recibe el mínimo ni las diferencias.
- **Sin recomendaciones**: la comparación da diferencias, nunca una cifra que pedir.
- Guardar los datos de una oferta sin `offer_received` lo registra (actor `user`), así que solo
  vale en una etapa en la que ese evento sea válido.
"""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Company, Job, ReceivedOffer
from app.models.base import utcnow
from app.schemas.llm_io import Salary
from app.services import events, extractions
from app.services import profile as profile_service
from app.services.events import JobNotFoundError
from app.services.pipeline import Actor, EventType
from app.services.process import offer_received

WorkMode = Literal["remote", "hybrid", "onsite"]
OfferPeriod = Literal["year", "month"]
MAX_AMOUNT = 10_000_000
# Clave del mínimo en `private` del perfil (bruto anual en euros).
FLOOR_KEY = "salary_floor_eur"
MONTHS_PER_YEAR = 12

FIELD_LABELS = {
    "base_salary": "fijo",
    "variable": "variable",
    "currency": "moneda",
    "period": "periodo",
    "benefits": "beneficios",
    "work_mode": "modalidad",
    "location": "ubicación",
    "start_date": "incorporación",
    "respond_by": "fecha de respuesta",
    "notes": "notas",
    "amounts_private": "privacidad de los importes",
}


class ReceivedOfferNotFoundError(LookupError):
    pass


# --- Entrada (solo la UI) -------------------------------------------------------------------


class ReceivedOfferFields(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    base_salary: int | None = Field(default=None, ge=0, le=MAX_AMOUNT, description="Fijo bruto.")
    variable: int | None = Field(
        default=None, ge=0, le=MAX_AMOUNT, description="Variable o bonus bruto objetivo, anual."
    )
    currency: str = Field(default="EUR", description="Código ISO 4217 (EUR, USD, GBP…).")
    period: OfferPeriod = Field(default="year", description="El fijo es anual o mensual.")
    benefits: str | None = Field(default=None, max_length=4000)
    work_mode: WorkMode | None = None
    location: str | None = Field(default=None, max_length=200)
    start_date: date | None = Field(default=None, description="Fecha de incorporación.")
    respond_by: date | None = Field(default=None, description="Hasta cuándo tienes para responder.")
    notes: str | None = Field(
        default=None, max_length=4000, description="Notas. Las ve el agente: sin tus cifras."
    )
    amounts_private: bool = Field(
        default=True, description="Fijo y variable no salen nunca hacia el agente."
    )

    @field_validator("currency")
    @classmethod
    def _iso_currency(cls, value: str) -> str:
        value = value.upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("La moneda es un código de 3 letras (EUR, USD…).")
        return value

    @field_validator("benefits", "location", "notes")
    @classmethod
    def _empty_to_none(cls, value: str | None) -> str | None:
        return value or None


# --- Salidas --------------------------------------------------------------------------------


class ReceivedOfferOut(BaseModel):
    """Los datos tal cual, para la ficha (UI)."""

    job_id: int
    base_salary: int | None
    variable: int | None
    currency: str
    period: OfferPeriod
    benefits: str | None
    work_mode: WorkMode | None
    location: str | None
    start_date: date | None
    respond_by: date | None
    notes: str | None
    amounts_private: bool
    created_at: datetime
    updated_at: datetime


class ReceivedOfferAgentView(BaseModel):
    """Lo que ve el agente (`get_received_offer`). Sin el mínimo ni diferencias; los importes,
    solo si el usuario los ha marcado como no privados."""

    job_id: int
    amounts_private: bool
    base_salary: int | None = Field(description="Fijo bruto. Vacío si los importes son privados.")
    variable: int | None = Field(description="Variable bruto. Vacío si son privados.")
    currency: str | None
    period: OfferPeriod | None
    benefits: str | None
    work_mode: WorkMode | None
    location: str | None
    start_date: date | None
    respond_by: date | None
    notes: str | None
    updated_at: datetime


class OfferComparison(BaseModel):
    """Una oferta recibida en la tabla comparativa (solo UI)."""

    job_id: int
    title: str
    company: str
    stage: str | None
    offer: ReceivedOfferOut
    annual_base: int | None  # fijo anualizado
    annual_total: int | None  # fijo anual + variable (anual); None sin fijo
    approximate: bool  # fijo mensual ×12: no cuenta pagas extra
    floor_diff_base: int | None  # fijo anual − mínimo (solo en EUR)
    floor_diff_total: int | None  # total anual − mínimo (solo en EUR)
    published: Salary | None  # rango de la extracción vigente
    published_annual_min: int | None
    published_annual_max: int | None
    published_diff_min: int | None  # fijo anual − mínimo publicado (misma moneda)
    published_diff_max: int | None  # fijo anual − máximo publicado (misma moneda)
    remarks: list[str]  # por qué falta alguna diferencia


class OfferComparisonView(BaseModel):
    floor_eur: int | None  # `private.salary_floor_eur`; None si no está en el perfil
    offers: list[OfferComparison]


# --- Lógica ---------------------------------------------------------------------------------


def _out(row: ReceivedOffer) -> ReceivedOfferOut:
    return ReceivedOfferOut.model_validate(row, from_attributes=True)


def _require_job(session: Session, job_id: int) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    return job


def offer_row(session: Session, job_id: int) -> ReceivedOffer | None:
    return session.scalars(select(ReceivedOffer).where(ReceivedOffer.job_id == job_id)).first()


def get_received_offer(session: Session, job_id: int) -> ReceivedOfferOut | None:
    """Los datos de la oferta recibida para la UI, o `None` si aún no hay."""
    _require_job(session, job_id)
    row = offer_row(session, job_id)
    return _out(row) if row else None


def save_received_offer(
    session: Session, job_id: int, data: ReceivedOfferFields
) -> ReceivedOfferOut:
    """Crea o sustituye los datos de la oferta recibida (solo desde la UI).

    Sin `offer_received` previo, lo registra (falla con `InvalidTransitionError` si la etapa no lo
    admite, y entonces no se guarda nada). Al cambiar datos ya guardados deja una `note` con los
    campos cambiados, sin valores.
    """
    _require_job(session, job_id)
    values = data.model_dump()
    now = utcnow()
    with session.begin_nested():
        row = offer_row(session, job_id)
        if row is None:
            row = ReceivedOffer(job_id=job_id, created_at=now, updated_at=now, **values)
            session.add(row)
            session.flush()
            if not offer_received(session, job_id):
                events.record(
                    session,
                    job_id,
                    EventType.OFFER_RECEIVED,
                    Actor.USER,
                    {"note": "Datos de la oferta anotados en la ficha."},
                )
        else:
            changed = [k for k, v in values.items() if getattr(row, k) != v]
            if changed:
                for key in changed:
                    setattr(row, key, values[key])
                row.updated_at = now
                labels = ", ".join(FIELD_LABELS[k] for k in changed)
                events.record(
                    session,
                    job_id,
                    EventType.NOTE,
                    Actor.USER,
                    {"note": f"Oferta recibida actualizada ({labels})."},
                )
    session.flush()
    return _out(row)


def delete_received_offer(session: Session, job_id: int) -> None:
    """Borra los datos anotados. El `offer_received` del historial se queda."""
    _require_job(session, job_id)
    row = offer_row(session, job_id)
    if row is None:
        raise ReceivedOfferNotFoundError(f"La oferta {job_id} no tiene datos de oferta recibida.")
    session.delete(row)
    session.flush()


def agent_view(session: Session, job_id: int) -> ReceivedOfferAgentView:
    """La oferta recibida tal como la ve el agente. Nunca el mínimo ni las diferencias."""
    _require_job(session, job_id)
    row = offer_row(session, job_id)
    if row is None:
        raise ReceivedOfferNotFoundError(
            f"La oferta {job_id} no tiene datos de oferta recibida: el usuario los anota en la "
            "ficha («Oferta recibida»)."
        )
    hidden = row.amounts_private
    return ReceivedOfferAgentView(
        job_id=job_id,
        amounts_private=hidden,
        base_salary=None if hidden else row.base_salary,
        variable=None if hidden else row.variable,
        currency=None if hidden else row.currency,
        period=None if hidden else row.period,  # type: ignore[arg-type]
        benefits=row.benefits,
        work_mode=row.work_mode,  # type: ignore[arg-type]
        location=row.location,
        start_date=row.start_date,
        respond_by=row.respond_by,
        notes=row.notes,
        updated_at=row.updated_at,
    )


def _floor(session: Session) -> int | None:
    try:
        stored = profile_service.current(session)
    except profile_service.ProfileNotFoundError:
        return None
    value: Any = stored.profile.private.get(FLOOR_KEY)
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        return None
    return int(value)


def _annual(amount: int | None, period: str) -> int | None:
    if amount is None:
        return None
    return amount * MONTHS_PER_YEAR if period == "month" else amount


def _published_annual(salary: Salary | None) -> tuple[int | None, int | None]:
    if salary is None or salary.period not in ("year", "month"):
        return None, None
    factor = MONTHS_PER_YEAR if salary.period == "month" else 1
    low = salary.min * factor if salary.min is not None else None
    high = salary.max * factor if salary.max is not None else None
    return low, high


def _diff(value: int | None, reference: int | None) -> int | None:
    return None if value is None or reference is None else value - reference


def _compare_one(
    row: ReceivedOffer,
    job: Job,
    company: str,
    stage: str | None,
    published: Salary | None,
    floor: int | None,
) -> OfferComparison:
    remarks: list[str] = []
    # `period` es el del fijo; el variable (bonus objetivo) es siempre anual.
    annual_base = _annual(row.base_salary, row.period)
    annual_total = None if annual_base is None else annual_base + (row.variable or 0)
    approximate = row.period == "month" and annual_base is not None
    if approximate:
        remarks.append("Fijo mensual ×12: no incluye pagas extra.")
    if annual_base is None:
        remarks.append("Sin fijo anotado: no hay total.")

    floor_base = floor_total = None
    if floor is None:
        remarks.append(f"Sin mínimo en el perfil (`private.{FLOOR_KEY}`).")
    elif row.currency != "EUR":
        remarks.append("El mínimo está en euros y la oferta no: no se compara.")
    else:
        floor_base, floor_total = _diff(annual_base, floor), _diff(annual_total, floor)

    pub_min, pub_max = _published_annual(published)
    diff_min = diff_max = None
    if published is None:
        remarks.append("La oferta publicada no indica salario.")
    elif published.currency is None:
        remarks.append("El rango publicado no indica moneda: no se compara.")
    elif published.currency.upper() != row.currency:
        remarks.append(f"El rango publicado está en {published.currency}: no se compara.")
    elif published.period not in ("year", "month"):
        what = "es por hora" if published.period == "hour" else "no indica periodo"
        remarks.append(f"El rango publicado {what}: no se compara.")
    else:
        diff_min, diff_max = _diff(annual_base, pub_min), _diff(annual_base, pub_max)
    return OfferComparison(
        job_id=job.id,
        title=job.title,
        company=company,
        stage=stage,
        offer=_out(row),
        annual_base=annual_base,
        annual_total=annual_total,
        approximate=approximate,
        floor_diff_base=floor_base,
        floor_diff_total=floor_total,
        published=published,
        published_annual_min=pub_min,
        published_annual_max=pub_max,
        published_diff_min=diff_min,
        published_diff_max=diff_max,
        remarks=remarks,
    )


def _published(extraction: Any) -> Salary | None:
    """El rango de la extracción vigente; `None` si no lo indica o está mal formado."""
    salary_data = (extraction.data or {}).get("salary") if extraction else None
    if not salary_data:
        return None
    try:
        published = Salary.model_validate(salary_data)
    except ValidationError:
        return None
    return None if published.min is None and published.max is None else published


def compare(session: Session) -> OfferComparisonView:
    """Las ofertas recibidas lado a lado, con las diferencias. Solo para la UI (POLICIES §4)."""
    floor = _floor(session)
    rows = session.execute(
        select(ReceivedOffer, Job, Company.name, Application.stage)
        .join(Job, Job.id == ReceivedOffer.job_id)
        .join(Company, Company.id == Job.company_id)
        .outerjoin(Application, Application.job_id == Job.id)
        .order_by(ReceivedOffer.respond_by.is_(None), ReceivedOffer.respond_by, ReceivedOffer.id)
    ).all()
    latest = extractions.latest_rows(session, [job.id for _, job, _, _ in rows])
    offers = []
    for row, job, company, stage in rows:
        extraction = latest.get(job.id)
        offers.append(_compare_one(row, job, company, stage, _published(extraction), floor))
    return OfferComparisonView(floor_eur=floor, offers=offers)
