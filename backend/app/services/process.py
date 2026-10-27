"""Ficha de proceso (fase 10): hitos con fecha, contactos, notas y documentos usados.

Los hitos que mueven la oferta registran su evento: crear una entrevista registra
`interview_scheduled`; una prueba, `test_assigned`; marcar una entrevista como hecha,
`interview_done`. Reprogramar o cancelar una entrevista o una prueba deja una `note`. Los plazos
y los hitos `other` no registran eventos: no cambian la etapa. Todos los eventos llevan
`payload.milestone_id`.

Borrar un hito anotado por error es la única excepción a que los eventos solo se añaden: se borran
también los suyos y la etapa se recalcula, como si nunca se hubiera anotado.
"""

from datetime import date, datetime, time, timedelta
from typing import Any, Literal, Self
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.models import (
    AgentRequest,
    AgentRun,
    Application,
    Contact,
    Event,
    Job,
    MessageDraft,
    Milestone,
    Reply,
)
from app.models.base import utcnow
from app.schemas.interview_guide import GuideInfo, guide_info
from app.schemas.interviews import InterviewPlan
from app.services import events
from app.services.events import JobNotFoundError
from app.services.pipeline import (
    Actor,
    EventType,
    InvalidTransitionError,
    Stage,
    rebuild_projection,
)

MilestoneKind = Literal["interview", "test", "deadline", "other"]
# Papel de un contacto en el proceso (fase 18) y referencia pedida o dada.
ContactRelation = Literal["referral", "recruiter", "hiring_manager"]
ReferralStatus = Literal["requested", "given"]
MilestoneStatus = Literal["scheduled", "done", "cancelled"]
# Qué ronda es una entrevista: RR. HH. o encaje cultural, técnica, caso práctico, final u otra.
InterviewType = Literal["hr", "technical", "case", "final", "other"]
MAX_PREP_INSTRUCTIONS = 4000

DEFAULT_TITLES: dict[str, str] = {
    "interview": "Entrevista",
    "test": "Prueba técnica",
    "deadline": "Plazo",
    "other": "Hito",
}
# Evento que registra crear el hito (los demás tipos no cambian la etapa).
CREATE_EVENTS: dict[str, EventType] = {
    "interview": EventType.INTERVIEW_SCHEDULED,
    "test": EventType.TEST_ASSIGNED,
}


class MilestoneNotFoundError(LookupError):
    pass


class ContactNotFoundError(LookupError):
    pass


def local_zone() -> ZoneInfo:
    return ZoneInfo(get_policies().calendar.timezone)


def start_of_local_day(value: datetime | date) -> datetime:
    """Las 00:00 (Europe/Madrid) del día de `value`, como fecha con zona."""
    day = value.astimezone(local_zone()).date() if isinstance(value, datetime) else value
    return datetime.combine(day, time(0, 0), tzinfo=local_zone())


# --- Entradas -------------------------------------------------------------------------------


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MilestoneFields(_Input):
    title: str | None = Field(default=None, max_length=200, description="Por defecto, el tipo.")
    starts_at: AwareDatetime = Field(description="Inicio (ISO 8601 con zona).")
    ends_at: AwareDatetime | None = None
    all_day: bool = Field(default=False, description="Todo el día: cuenta solo la fecha.")
    location: str | None = Field(default=None, max_length=500, description="Lugar o enlace.")
    notes: str | None = Field(default=None, max_length=4000)
    interview_type: InterviewType | None = Field(
        default=None,
        description="Solo en entrevistas: qué ronda es. Si no se manda al editar, no cambia.",
    )

    @model_validator(mode="after")
    def _ends_after_start(self) -> Self:
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("`ends_at` debe ser posterior a `starts_at`.")
        return self


class MilestoneCreate(MilestoneFields):
    kind: MilestoneKind
    occurred_at: AwareDatetime | None = Field(
        default=None,
        description="Cuándo te lo comunicaron (fecha del evento). Por defecto, ahora.",
    )


class PrepInstructionsInput(_Input):
    instructions: str | None = Field(
        default=None,
        max_length=MAX_PREP_INSTRUCTIONS,
        description="Lo que quieres que tengan en cuenta la guía y el simulacro. Vacío las borra.",
    )


class MilestoneStatusChange(_Input):
    status: Literal["done", "cancelled"]
    occurred_at: AwareDatetime | None = None
    note: str | None = Field(default=None, max_length=2000)


class ContactFields(_Input):
    name: str = Field(min_length=1, max_length=200)
    role: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    linkedin: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)
    relation: ContactRelation | None = Field(
        default=None, description="Papel en el proceso: referencia, recruiter o responsable."
    )


class ReferralChange(_Input):
    referral: ReferralStatus | None = Field(
        description="`requested` (pedida), `given` (dada) o `null` para quitar la marca."
    )


# --- Salidas --------------------------------------------------------------------------------


class MilestoneOut(BaseModel):
    id: int
    job_id: int
    kind: MilestoneKind
    title: str
    starts_at: datetime
    ends_at: datetime | None
    all_day: bool
    location: str | None
    notes: str | None
    status: MilestoneStatus
    event_id: int | None
    created_at: datetime
    updated_at: datetime
    # Entrevistas (fase 17, `services/interviews.py`): plan de preparación y repaso posterior.
    prep_plan: InterviewPlan | None = None
    guide: GuideInfo | None = None  # guía de preparación en PDF
    debrief_notes: str | None = None
    next_steps: str | None = None
    debriefed_at: datetime | None = None
    interview_type: InterviewType | None = None
    # Indicaciones del usuario para «Preparar» y «Simulacro» (solo se escriben desde la UI).
    prep_instructions: str | None = None


class ContactOut(BaseModel):
    id: int
    job_id: int
    name: str
    role: str | None
    email: str | None
    phone: str | None
    linkedin: str | None
    notes: str | None
    created_at: datetime
    relation: ContactRelation | None = None
    referral: ReferralStatus | None = None
    referral_at: datetime | None = None
    network_contact_id: int | None = None  # sale de tu red de LinkedIn (fase 18)


class NoteOut(BaseModel):
    event_id: int
    actor: str
    text: str
    occurred_at: datetime


def milestone_out(row: Milestone) -> MilestoneOut:
    out = MilestoneOut.model_validate(row, from_attributes=True)
    out.guide = guide_info(row.prep_guide)
    return out


def contact_out(row: Contact) -> ContactOut:
    return ContactOut.model_validate(row, from_attributes=True)


# --- Hitos ----------------------------------------------------------------------------------


def _job(session: Session, job_id: int) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    return job


def milestone_row(session: Session, milestone_id: int) -> Milestone:
    row = session.get(Milestone, milestone_id)
    if row is None:
        raise MilestoneNotFoundError(f"No existe el hito {milestone_id}.")
    return row


def _normalized_times(fields: MilestoneFields) -> tuple[datetime, datetime | None]:
    """En un hito de todo el día, `ends_at` es el último día incluido: se guarda como las 00:00
    del día siguiente (el fin exclusivo del iCalendar). Un solo día: `ends_at` vacío."""
    if fields.all_day:
        start = start_of_local_day(fields.starts_at)
        if fields.ends_at is None:
            return start, None
        last_day = fields.ends_at.astimezone(local_zone()).date()
        end = start_of_local_day(last_day + timedelta(days=1))
        return start, end if end > start + timedelta(hours=25) else None
    return fields.starts_at, fields.ends_at


def _when(value: datetime, all_day: bool) -> str:
    local = value.astimezone(local_zone())
    return local.strftime("%d/%m/%Y") if all_day else local.strftime("%d/%m/%Y %H:%M")


def create_milestone(
    session: Session,
    job_id: int,
    data: MilestoneCreate,
    payload_extra: dict[str, Any] | None = None,
) -> MilestoneOut:
    """Crea un hito y, si es una entrevista o una prueba, registra su evento (actor `user`).

    `payload_extra` se añade al `payload` del evento (p. ej. `reply_id` al aceptar un correo).

    Si el evento no es válido en la etapa de la oferta (p. ej. una entrevista antes de enviar la
    candidatura), no se guarda nada y se lanza `InvalidTransitionError`.
    """
    _job(session, job_id)
    starts_at, ends_at = _normalized_times(data)
    now = utcnow()
    row = Milestone(
        job_id=job_id,
        kind=data.kind,
        title=data.title or DEFAULT_TITLES[data.kind],
        starts_at=starts_at,
        ends_at=ends_at,
        all_day=data.all_day,
        location=data.location or None,
        notes=data.notes or None,
        interview_type=data.interview_type if data.kind == "interview" else None,
        status="scheduled",
        sequence=0,
        created_at=now,
        updated_at=now,
    )
    with session.begin_nested():  # si el evento no es válido, el hito tampoco queda
        session.add(row)
        session.flush()
        event_type = CREATE_EVENTS.get(data.kind)
        if event_type is not None:
            payload: dict[str, Any] = {
                "milestone_id": row.id,
                "title": row.title,
                "starts_at": starts_at.isoformat(),
                **(payload_extra or {}),
            }
            event = events.record(
                session, job_id, event_type, Actor.USER, payload, occurred_at=data.occurred_at
            )
            row.event_id = event.id
    session.flush()
    return milestone_out(row)


def update_milestone(session: Session, milestone_id: int, data: MilestoneFields) -> MilestoneOut:
    """Cambia los datos de un hito programado. Reprogramar una entrevista o una prueba deja una
    `note` en la oferta con la fecha nueva."""
    row = milestone_row(session, milestone_id)
    if row.status != "scheduled":
        raise ValueError("Solo se edita un hito programado; uno hecho o cancelado queda así.")
    starts_at, ends_at = _normalized_times(data)
    moved = starts_at != row.starts_at or data.all_day != row.all_day
    title = data.title or DEFAULT_TITLES[row.kind]
    if moved and row.kind in CREATE_EVENTS:  # primero el evento: si falla, el hito no cambia
        text = f"{title} reprogramada para el {_when(starts_at, data.all_day)}."
        events.record(
            session,
            row.job_id,
            EventType.NOTE,
            Actor.USER,
            {"note": text, "milestone_id": row.id},
        )
    row.title = title
    row.starts_at = starts_at
    row.ends_at = ends_at
    row.all_day = data.all_day
    row.location = data.location or None
    row.notes = data.notes or None
    if row.kind == "interview" and "interview_type" in data.model_fields_set:
        row.interview_type = data.interview_type
    row.sequence += 1
    row.updated_at = utcnow()
    session.flush()
    return milestone_out(row)


def set_prep_instructions(
    session: Session, milestone_id: int, data: PrepInstructionsInput
) -> MilestoneOut:
    """Guarda lo que el usuario quiere que tengan en cuenta «Preparar» y «Simulacro» en una
    entrevista programada. No es un cambio de estado de la oferta: no registra evento."""
    row = milestone_row(session, milestone_id)
    if row.kind != "interview":
        raise ValueError("Las indicaciones de preparación solo van en una entrevista.")
    if row.status != "scheduled":
        raise ValueError("Solo se preparan las entrevistas programadas.")
    row.prep_instructions = data.instructions or None
    row.updated_at = utcnow()
    session.flush()
    return milestone_out(row)


def set_milestone_status(
    session: Session,
    milestone_id: int,
    change: MilestoneStatusChange,
    now: datetime | None = None,
) -> MilestoneOut:
    """Marca un hito como hecho o cancelado.

    Entrevista hecha: `interview_done`. Cancelar una entrevista o una prueba: `note`. El resto no
    registra eventos. Un hito hecho o cancelado no vuelve atrás: se crea otro. Una entrevista no
    se da por hecha antes de su día (una prueba sí: se puede entregar antes del plazo).
    """
    row = milestone_row(session, milestone_id)
    if row.status != "scheduled":
        raise ValueError(f"El hito ya está «{row.status}»; si hay una fecha nueva, crea otro hito.")
    today = (now or utcnow()).astimezone(local_zone()).date()
    if (
        change.status == "done"
        and row.kind == "interview"
        and row.starts_at.astimezone(local_zone()).date() > today
    ):
        raise ValueError(
            f"La entrevista es el {_when(row.starts_at, row.all_day)}: se marca como hecha a "
            "partir de ese día. Si se ha adelantado, cambia antes su fecha."
        )
    payload: dict[str, Any] = {"milestone_id": row.id}
    if change.note:
        payload["note"] = change.note
    if change.status == "done" and row.kind == "interview":
        events.record(
            session,
            row.job_id,
            EventType.INTERVIEW_DONE,
            Actor.USER,
            payload,
            occurred_at=change.occurred_at,
        )
    elif change.status == "cancelled" and row.kind in CREATE_EVENTS:
        cancelled = f"{row.title} del {_when(row.starts_at, row.all_day)} cancelada."
        payload["note"] = f"{cancelled} {change.note}" if change.note else cancelled
        events.record(
            session,
            row.job_id,
            EventType.NOTE,
            Actor.USER,
            payload,
            occurred_at=change.occurred_at,
        )
    row.status = change.status
    row.sequence += 1
    row.updated_at = utcnow()
    session.flush()
    return milestone_out(row)


class MilestoneDeleted(BaseModel):
    ok: bool = True
    milestone_id: int
    job_id: int
    deleted_events: int
    stage: Stage | None  # la etapa recalculada


def delete_milestone(session: Session, milestone_id: int) -> MilestoneDeleted:
    """Borra un hito anotado por error con sus eventos (el que registró al crearse, el de hecha y
    las notas de reprogramar o cancelar) y recalcula la etapa: no cuenta en el historial ni en el
    embudo. Con él se van su plan, su guía (también el PDF), su repaso y sus indicaciones.

    Si lo que pasó después en la oferta depende de él (p. ej. una oferta recibida tras la única
    entrevista), no se borra nada y se lanza `InvalidTransitionError`: se cancela en su lugar.
    """
    from app.services.interview_guide import guide_path  # evita la importación circular

    row = milestone_row(session, milestone_id)
    job_id, title = row.job_id, row.title
    guide = (row.prep_guide or {}).get("file")
    own = [
        e
        for e in session.scalars(select(Event).where(Event.job_id == job_id))
        if e.id == row.event_id or (e.payload or {}).get("milestone_id") == row.id
    ]
    event_ids = [e.id for e in own]
    try:
        with session.begin_nested():
            # Lo que apunta al hito o a sus eventos se queda, sin el enlace.
            for model in (AgentRun, AgentRequest, MessageDraft):
                session.execute(
                    update(model).where(model.milestone_id == row.id).values(milestone_id=None)
                )
            if event_ids:
                for model in (Reply, MessageDraft):
                    session.execute(
                        update(model).where(model.event_id.in_(event_ids)).values(event_id=None)
                    )
            session.delete(row)
            session.flush()
            for event in own:
                session.delete(event)
            session.flush()
            rebuild_projection(session, job_id)
    except InvalidTransitionError as exc:
        raise InvalidTransitionError(
            f"No se puede borrar «{title}»: lo que pasó después en la oferta depende de "
            f"este hito ({exc}). Si no llegó a celebrarse, cancélalo."
        ) from exc
    if guide:
        guide_path(guide).unlink(missing_ok=True)
    app = session.get(Application, job_id)
    return MilestoneDeleted(
        milestone_id=milestone_id,
        job_id=job_id,
        deleted_events=len(own),
        stage=Stage(app.stage) if app else None,
    )


def get_milestone(session: Session, milestone_id: int) -> MilestoneOut:
    return milestone_out(milestone_row(session, milestone_id))


def job_milestones(session: Session, job_id: int) -> list[MilestoneOut]:
    stmt = (
        select(Milestone)
        .where(Milestone.job_id == job_id)
        .order_by(Milestone.starts_at, Milestone.id)
    )
    return [milestone_out(row) for row in session.scalars(stmt)]


# --- Contactos ------------------------------------------------------------------------------


def contact_row(session: Session, contact_id: int) -> Contact:
    row = session.get(Contact, contact_id)
    if row is None:
        raise ContactNotFoundError(f"No existe el contacto {contact_id}.")
    return row


def _apply_contact(row: Contact, data: ContactFields) -> None:
    row.name = data.name
    row.role = data.role or None
    row.email = data.email or None
    row.phone = data.phone or None
    row.linkedin = data.linkedin or None
    row.notes = data.notes or None
    row.relation = data.relation


def add_contact(session: Session, job_id: int, data: ContactFields) -> ContactOut:
    _job(session, job_id)
    row = Contact(job_id=job_id, created_at=utcnow())
    _apply_contact(row, data)
    session.add(row)
    session.flush()
    return contact_out(row)


def update_contact(session: Session, contact_id: int, data: ContactFields) -> ContactOut:
    row = contact_row(session, contact_id)
    _apply_contact(row, data)
    session.flush()
    return contact_out(row)


def set_referral(session: Session, contact_id: int, data: ReferralChange) -> ContactOut:
    """Marca (o quita) «referencia pedida / dada» en un contacto del proceso (fase 18).

    No es un evento: no cambia la etapa. La lee el embudo para medir si las referencias convierten.
    """
    row = contact_row(session, contact_id)
    if row.referral != data.referral:
        row.referral = data.referral
        row.referral_at = utcnow() if data.referral is not None else None
        session.flush()
    return contact_out(row)


def delete_contact(session: Session, contact_id: int) -> None:
    session.delete(contact_row(session, contact_id))
    session.flush()


# --- Ficha ----------------------------------------------------------------------------------


class FollowupStatus(BaseModel):
    """Seguimiento de una candidatura enviada (solo en `applied`)."""

    due: bool
    days_waiting: int | None  # días desde el envío o el último seguimiento
    days_without_reply: int  # el umbral


class ProcessDocuments(BaseModel):
    """Documentos usados: el CV enviado (o el seleccionado si aún no se envió)."""

    cv_render_id: int | None
    cv_sent: bool  # el render es el que se anotó al enviar
    answers_document_id: int | None = None  # respuestas de screening (fase 10.3)
    cover_letter_document_id: int | None = None  # carta vigente (fase 08c)


class ProcessView(BaseModel):
    job_id: int
    stage: Stage | None
    applied_at: datetime | None
    channel: str | None
    followup: FollowupStatus | None
    milestones: list[MilestoneOut]
    contacts: list[ContactOut]
    notes: list[NoteOut]
    documents: ProcessDocuments
    offer_received: bool = False  # hay un `offer_received`: «Dudas antes de aceptar» (fase 17)


def followup_status(
    application: Application | None,
    last_followup_at: datetime | None,
    days_without_reply: int,
    now: datetime,
    followups_sent: int = 0,
) -> FollowupStatus | None:
    """Con `followups.max_followups` seguimientos enviados (fase 15) ya no toca otro."""
    if application is None or application.stage != Stage.APPLIED:
        return None
    anchors = [d for d in (application.applied_at, last_followup_at) if d is not None]
    if not anchors:
        anchors = [application.last_event_at]
    days = (now - max(anchors)).days
    capped = followups_sent >= get_policies().followups.max_followups
    return FollowupStatus(
        due=days >= days_without_reply and not capped,
        days_waiting=days,
        days_without_reply=days_without_reply,
    )


def last_followup_at(session: Session, job_id: int) -> datetime | None:
    stmt = (
        select(Event.occurred_at)
        .where(Event.job_id == job_id, Event.type == EventType.FOLLOWUP_SENT)
        .order_by(Event.occurred_at.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def offer_received(session: Session, job_id: int) -> bool:
    """Si la oferta tiene un `offer_received` (la empresa ha hecho una propuesta)."""
    stmt = select(Event.id).where(Event.job_id == job_id, Event.type == EventType.OFFER_RECEIVED)
    return session.scalars(stmt.limit(1)).first() is not None


def get_process(session: Session, job_id: int, now: datetime | None = None) -> ProcessView:
    """La ficha de proceso de una oferta."""
    # Import diferido: el servicio de documentos importa `events`, que no debe depender de él.
    from app.services.answers import latest_answers
    from app.services.documents.cover_letter import latest_letter
    from app.services.documents.service import selected_render_id
    from app.services.drafts import followups_sent

    _job(session, job_id)
    application = session.get(Application, job_id)
    notes = [
        NoteOut(
            event_id=e.id,
            actor=e.actor,
            text=str(e.payload.get("note", "")),
            occurred_at=e.occurred_at,
        )
        for e in session.scalars(
            select(Event)
            .where(Event.job_id == job_id, Event.type == EventType.NOTE)
            .order_by(Event.occurred_at.desc(), Event.id.desc())
        )
        if e.payload.get("note")
    ]
    contacts = session.scalars(select(Contact).where(Contact.job_id == job_id).order_by(Contact.id))
    sent_render = application.render_id if application else None
    answers_doc = latest_answers(session, job_id)
    letter_doc = latest_letter(session, job_id)
    return ProcessView(
        job_id=job_id,
        stage=Stage(application.stage) if application else None,
        applied_at=application.applied_at if application else None,
        channel=application.channel if application else None,
        followup=followup_status(
            application,
            last_followup_at(session, job_id),
            get_policies().followups.days_without_reply,
            now or utcnow(),
            followups_sent(session, [job_id]).get(job_id, 0),
        ),
        milestones=job_milestones(session, job_id),
        contacts=[contact_out(c) for c in contacts],
        notes=notes,
        documents=ProcessDocuments(
            cv_render_id=sent_render or selected_render_id(session, job_id),
            cv_sent=sent_render is not None,
            answers_document_id=answers_doc.id if answers_doc else None,
            cover_letter_document_id=letter_doc.id if letter_doc else None,
        ),
        offer_received=offer_received(session, job_id),
    )


def default_end(row: MilestoneOut | Milestone) -> datetime:
    """Fin para el calendario: el indicado, el día siguiente (todo el día) o una hora después."""
    if row.ends_at is not None:
        return row.ends_at
    if row.all_day:
        return start_of_local_day(row.starts_at.astimezone(local_zone()).date() + timedelta(days=1))
    return row.starts_at + timedelta(minutes=get_policies().calendar.default_duration_minutes)
