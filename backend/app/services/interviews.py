"""Entrevistas (fase 17): plan de preparación y repaso posterior, guardados en el hito.

Lo redacta el agente con los skills `prepare-interview`, `mock-interview` y
`debrief-interview`; aquí solo se lee y se guarda. Nada de esto registra eventos ni cambia el
estado del hito: marcar una entrevista como hecha (`interview_done`) lo sigue haciendo el usuario
en la ficha (ADR-029). Las historias STAR nuevas que salgan de un repaso no se guardan aquí: entran
en el perfil solo con `update-profile` y la confirmación del usuario.
"""

from datetime import date, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Company, Contact, Job, Milestone
from app.models.base import utcnow
from app.schemas.interviews import InterviewPlan, InterviewPlanInput
from app.services import events
from app.services.pipeline import Stage
from app.services.process import (
    MilestoneOut,
    local_zone,
    milestone_out,
    milestone_row,
    offer_received,
    start_of_local_day,
)

MAX_NOTES = 10000
MAX_NEXT_STEPS = 4000


class InterviewNotAllowedError(ValueError):
    """El hito no admite eso: no es una entrevista, está cancelada, aún no ha pasado…"""


def interviews_dir() -> Path:
    """Carpeta de los dosieres (`<carpeta de datos>/entrevistas/`)."""
    return get_settings().data_dir / "entrevistas"


# --- Entradas -------------------------------------------------------------------------------


class InterviewNotesInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    notes: str = Field(
        min_length=1,
        max_length=MAX_NOTES,
        description="Cómo fue, con las palabras del usuario: preguntas, qué salió bien y mal, "
        "señales de la empresa. Sustituye al repaso anterior de ese hito.",
    )
    next_steps: str | None = Field(
        default=None,
        max_length=MAX_NEXT_STEPS,
        description="Próximos pasos: lo que dijeron, la ronda siguiente probable y qué preparar.",
    )


# --- Salidas --------------------------------------------------------------------------------


class InterviewContact(BaseModel):
    """Solo nombre y cargo: sin email ni teléfono."""

    name: str
    role: str | None


class InterviewsView(BaseModel):
    job_id: int
    job_title: str
    company: str
    stage: Stage | None
    offer_received: bool  # hay un `offer_received`: toca revisar dudas antes de aceptar
    today: date  # hoy en Europe/Madrid, para fechar el plan
    contacts: list[InterviewContact]
    interviews: list[MilestoneOut]  # hitos de tipo entrevista, por fecha


class SavePlanResult(BaseModel):
    ok: bool = True
    milestone_id: int
    job_id: int
    blocks: int
    replaced: bool
    message: str


class SaveNotesResult(BaseModel):
    ok: bool = True
    milestone_id: int
    job_id: int
    replaced: bool
    milestone_status: str
    message: str


# --- Lógica ---------------------------------------------------------------------------------


def _local_date(value: datetime) -> date:
    return value.astimezone(local_zone()).date()


def has_started(row: Milestone, now: datetime) -> bool:
    """Si la entrevista ya ha empezado. Una de todo el día cuenta como empezada al acabar ese día
    (Europe/Madrid): hasta entonces aún se prepara y no se repasa."""
    if row.all_day:
        return start_of_local_day(_local_date(row.starts_at) + timedelta(days=1)) <= now
    return row.starts_at <= now


def check_can_prepare(session: Session, row: Milestone, now: datetime) -> None:
    """Preparar o ensayar: entrevista programada, aún por empezar y con el proceso abierto. Lo usan
    `save_interview_plan` y los botones «Preparar» y «Simulacro»."""
    if row.kind != "interview":
        raise InterviewNotAllowedError(f"El hito {row.id} no es una entrevista (es «{row.kind}»).")
    if row.status != "scheduled" or has_started(row, now):
        raise InterviewNotAllowedError("Solo con una entrevista programada que aún no ha empezado.")
    if events.current_stage(session, row.job_id) == Stage.CLOSED:
        raise InterviewNotAllowedError("El proceso de esta oferta está cerrado.")


def check_can_debrief(row: Milestone, now: datetime) -> None:
    """Repasar: entrevista ya empezada y no cancelada. Lo usan `save_interview_notes` y el botón
    «Repasar»."""
    if row.kind != "interview":
        raise InterviewNotAllowedError(f"El hito {row.id} no es una entrevista (es «{row.kind}»).")
    if row.status == "cancelled":
        raise InterviewNotAllowedError("Esa entrevista está cancelada: no hay nada que repasar.")
    if not has_started(row, now):
        raise InterviewNotAllowedError("Esa entrevista aún no ha empezado.")


def get_interviews(session: Session, job_id: int, now: datetime | None = None) -> InterviewsView:
    """Las entrevistas de una oferta con su plan y su repaso, y los contactos del proceso."""
    row = session.execute(
        select(Job, Company.name)
        .join(Company, Company.id == Job.company_id)
        .where(Job.id == job_id)
    ).first()
    if row is None:
        raise events.JobNotFoundError(f"No existe la oferta {job_id}.")
    job, company = row
    milestones = session.scalars(
        select(Milestone)
        .where(Milestone.job_id == job_id, Milestone.kind == "interview")
        .order_by(Milestone.starts_at, Milestone.id)
    )
    contacts = session.scalars(select(Contact).where(Contact.job_id == job_id).order_by(Contact.id))
    return InterviewsView(
        job_id=job_id,
        job_title=job.title,
        company=company,
        stage=events.current_stage(session, job_id),
        offer_received=offer_received(session, job_id),
        today=_local_date(now or utcnow()),
        contacts=[InterviewContact(name=c.name, role=c.role) for c in contacts],
        interviews=[milestone_out(m) for m in milestones],
    )


def save_interview_plan(
    session: Session,
    milestone_id: int,
    plan: InterviewPlanInput,
    agent_name: str | None = None,
    now: datetime | None = None,
) -> SavePlanResult:
    """Guarda el plan de preparación de una entrevista programada (sustituye al anterior).

    Los bloques van de hoy al día de la entrevista (Europe/Madrid), ambos incluidos."""
    row = milestone_row(session, milestone_id)
    now = now or utcnow()
    check_can_prepare(session, row, now)
    today, day = _local_date(now), _local_date(row.starts_at)
    outside = sorted({b.date.isoformat() for b in plan.blocks if not today <= b.date <= day})
    if outside:
        raise InterviewNotAllowedError(
            f"Hay bloques fuera de plazo ({', '.join(outside)}): van de hoy ({today.isoformat()}) "
            f"al día de la entrevista ({day.isoformat()})."
        )
    blocks = sorted(plan.blocks, key=lambda b: b.date)
    saved = InterviewPlan(
        dossier=plan.dossier,
        blocks=blocks,
        saved_at=now,
        agent_name=(agent_name or "")[:64] or None,
    )
    replaced = row.prep_plan is not None
    row.prep_plan = saved.model_dump(mode="json")
    row.updated_at = now
    session.flush()
    minutes = sum(b.minutes for b in blocks)
    return SavePlanResult(
        milestone_id=row.id,
        job_id=row.job_id,
        blocks=len(blocks),
        replaced=replaced,
        message=f"Plan guardado en la ficha: {len(blocks)} bloques, {minutes} minutos en total.",
    )


def save_interview_notes(
    session: Session,
    milestone_id: int,
    data: InterviewNotesInput,
    now: datetime | None = None,
) -> SaveNotesResult:
    """Guarda el repaso de una entrevista que ya ha empezado (sustituye al anterior).

    No cambia el estado del hito: si sigue programado, el usuario la marca como hecha en la ficha.
    """
    row = milestone_row(session, milestone_id)
    now = now or utcnow()
    check_can_debrief(row, now)
    replaced = row.debrief_notes is not None
    row.debrief_notes = data.notes
    row.next_steps = data.next_steps or None
    row.debriefed_at = now
    row.updated_at = now
    session.flush()
    message = "Repaso guardado en la ficha."
    if row.status == "scheduled":
        message += (
            " La entrevista sigue como programada: recuerda al usuario que la marque como hecha "
            "en la ficha (así cuenta para el agradecimiento y el embudo)."
        )
    return SaveNotesResult(
        milestone_id=row.id,
        job_id=row.job_id,
        replaced=replaced,
        milestone_status=row.status,
        message=message,
    )
