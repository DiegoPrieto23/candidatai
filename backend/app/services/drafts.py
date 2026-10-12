"""Borradores de mensajes: seguimiento y agradecimiento (fase 15), LinkedIn y correo (fase 18).

El agente redacta (`save_message_draft`); la app **nunca envía nada** (regla dura 5). El usuario
copia el texto, lo manda él y pulsa «Ya lo he enviado» en la UI; solo un seguimiento registra un
evento (`followup_sent`). Como mucho `followups.max_followups` seguimientos (2) por candidatura;
un agradecimiento, solo tras una entrevista hecha.

Fase 18: un mensaje de LinkedIn (`linkedin`, ≤ 300 caracteres, sin asunto ni adjuntos) o un correo
de candidatura (`email`, con asunto y la lista de adjuntos que menciona) a un recruiter, al
responsable del puesto o a un compañero (`recipient_role`), desde que la oferta está aprobada. Puede
apuntar a un contacto del proceso o a una persona de tu red de LinkedIn.
"""

from datetime import datetime
from typing import Any, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.models import Contact, Event, Job, MessageDraft, Milestone, NetworkContact
from app.models.base import utcnow
from app.services import events, network
from app.services.pipeline import Actor, EventType, Stage

DraftKind = Literal["followup", "thank_you", "linkedin", "email"]
DraftStatus = Literal["draft", "sent", "discarded"]
RecipientRole = Literal["recruiter", "hiring_manager", "peer"]
# Candidaturas enviadas y vivas: las únicas a las que tiene sentido un seguimiento o un
# agradecimiento.
DRAFT_STAGES = (Stage.APPLIED, Stage.IN_PROCESS)
# Mensajes a personas (fase 18): desde que apruebas la oferta hasta que se cierra el proceso.
OUTREACH_KINDS = ("linkedin", "email")
OUTREACH_STAGES = (Stage.APPROVED, Stage.CV_READY, Stage.APPLIED, Stage.IN_PROCESS)
LINKEDIN_MAX_CHARS = 300
MAX_ATTACHMENTS = 10
KIND_NAMES: dict[str, str] = {
    "followup": "seguimiento",
    "thank_you": "agradecimiento",
    "linkedin": "mensaje de LinkedIn",
    "email": "correo",
}


class DraftNotFoundError(LookupError):
    pass


class DraftNotAllowedError(ValueError):
    """El borrador no se puede guardar o cambiar (tope de seguimientos, etapa, ya resuelto…)."""


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MessageDraftInput(_Input):
    kind: DraftKind = Field(
        description="`followup` (seguimiento), `thank_you` (agradecimiento), `linkedin` (mensaje "
        "o nota de invitación de LinkedIn, ≤ 300 caracteres) o `email` (correo de candidatura o a "
        "una persona de la empresa)."
    )
    subject: str | None = Field(
        default=None,
        min_length=1,
        max_length=300,
        description="Asunto del correo. Obligatorio salvo en `linkedin`, que no lleva.",
    )
    body: str = Field(min_length=1, max_length=10000, description="Texto del mensaje, sin firma.")
    milestone_id: int | None = Field(
        default=None,
        ge=1,
        description="Solo en `thank_you`: la entrevista que agradeces (por defecto, la última "
        "hecha).",
    )
    recipient_role: RecipientRole | None = Field(
        default=None,
        description="Solo en `linkedin` y `email` (obligatorio): `recruiter`, `hiring_manager` "
        "(responsable del puesto) o `peer` (compañero en el equipo).",
    )
    contact_id: int | None = Field(
        default=None, ge=1, description="Contacto del proceso al que va (de `get_job_contacts`)."
    )
    network_contact_id: int | None = Field(
        default=None,
        ge=1,
        description="Persona de tu red de LinkedIn a la que va (`network[].id` de "
        "`get_job_contacts`). No a la vez que `contact_id`.",
    )
    attachments: list[str] | None = Field(
        default=None,
        max_length=MAX_ATTACHMENTS,
        description="Solo en `email`: los adjuntos que menciona el correo (p. ej. «CV (PDF)», "
        "«Carta de presentación»). La app no adjunta nada: es la lista para el usuario.",
    )

    @model_validator(mode="after")
    def _by_kind(self) -> Self:
        if self.kind not in OUTREACH_KINDS:
            if self.subject is None:
                raise ValueError("Un seguimiento o un agradecimiento lleva asunto (`subject`).")
            extra = [
                name
                for name in ("recipient_role", "contact_id", "network_contact_id", "attachments")
                if getattr(self, name) is not None
            ]
            if extra:
                raise ValueError(f"{', '.join(extra)}: solo en `linkedin` y `email`.")
            return self
        if self.milestone_id is not None:
            raise ValueError("`milestone_id` solo va en un agradecimiento (`thank_you`).")
        if self.recipient_role is None:
            raise ValueError(
                "Indica a quién va: `recipient_role` (recruiter, hiring_manager o peer)."
            )
        if self.contact_id is not None and self.network_contact_id is not None:
            raise ValueError("`contact_id` o `network_contact_id`, no los dos.")
        if self.kind == "linkedin":
            if self.subject is not None or self.attachments is not None:
                raise ValueError("Un mensaje de LinkedIn no lleva asunto ni adjuntos.")
            if len(self.body) > LINKEDIN_MAX_CHARS:
                raise ValueError(
                    f"Un mensaje de LinkedIn tiene como mucho {LINKEDIN_MAX_CHARS} caracteres "
                    f"(este tiene {len(self.body)})."
                )
        elif self.subject is None:
            raise ValueError("Un correo lleva asunto (`subject`).")
        if self.attachments is not None:
            cleaned = [" ".join(a.split()) for a in self.attachments]
            if any(not a or len(a) > 200 for a in cleaned):
                raise ValueError("Cada adjunto es un nombre de 1 a 200 caracteres.")
            self.attachments = cleaned
        return self


class MessageDraftOut(BaseModel):
    id: int
    job_id: int
    kind: DraftKind
    milestone_id: int | None
    subject: str | None
    body: str
    status: DraftStatus
    event_id: int | None
    agent_name: str | None
    created_at: datetime
    updated_at: datetime
    recipient_role: RecipientRole | None = None
    contact_id: int | None = None
    network_contact_id: int | None = None
    recipient_name: str | None = None  # el del contacto o de la persona de la red al guardarlo
    attachments: list[str] | None = None


class SaveDraftResult(BaseModel):
    ok: bool = True
    draft_id: int
    job_id: int
    kind: DraftKind
    milestone_id: int | None
    replaced: bool  # sustituye al borrador vigente del mismo tipo (y entrevista)
    message: str


class DraftList(BaseModel):
    job_id: int
    followups_sent: int
    max_followups: int
    drafts: list[MessageDraftOut]  # vigentes (sin enviar ni descartar), el más reciente primero


class DraftSentBody(_Input):
    occurred_at: AwareDatetime | None = Field(
        default=None, description="Cuándo lo enviaste (por defecto, ahora)."
    )


class DraftActionResult(BaseModel):
    ok: bool = True
    draft_id: int
    status: DraftStatus
    event_id: int | None
    stage: Stage
    message: str


def _out(row: MessageDraft) -> MessageDraftOut:
    return MessageDraftOut.model_validate(row, from_attributes=True)


def followups_sent(session: Session, job_ids: list[int]) -> dict[int, int]:
    rows = session.execute(
        select(Event.job_id, func.count())
        .where(Event.type == EventType.FOLLOWUP_SENT, Event.job_id.in_(job_ids))
        .group_by(Event.job_id)
    ).all()
    return {job_id: count for job_id, count in rows}


def active_drafts(session: Session, job_ids: list[int]) -> list[MessageDraft]:
    """Borradores vigentes (sin enviar ni descartar) de esas ofertas."""
    return list(
        session.scalars(
            select(MessageDraft)
            .where(MessageDraft.job_id.in_(job_ids), MessageDraft.status == "draft")
            .order_by(MessageDraft.updated_at.desc(), MessageDraft.id.desc())
        )
    )


def thanked_milestones(session: Session, milestone_ids: list[int]) -> set[int]:
    """Entrevistas con un agradecimiento ya enviado."""
    return set(
        session.scalars(
            select(MessageDraft.milestone_id).where(
                MessageDraft.milestone_id.in_(milestone_ids),
                MessageDraft.kind == "thank_you",
                MessageDraft.status == "sent",
            )
        )
    )


def _interview_done(session: Session, job_id: int, milestone_id: int | None) -> Milestone:
    if milestone_id is not None:
        milestone = session.get(Milestone, milestone_id)
        if milestone is None or milestone.job_id != job_id:
            raise ValueError(f"La entrevista {milestone_id} no es de la oferta {job_id}.")
        if milestone.kind != "interview" or milestone.status != "done":
            raise DraftNotAllowedError(
                "Un agradecimiento va con una entrevista hecha: márcala como hecha antes."
            )
        return milestone
    milestone = session.scalars(
        select(Milestone)
        .where(
            Milestone.job_id == job_id,
            Milestone.kind == "interview",
            Milestone.status == "done",
        )
        .order_by(Milestone.starts_at.desc())
        .limit(1)
    ).first()
    if milestone is None:
        raise DraftNotAllowedError(
            "Esta oferta no tiene ninguna entrevista hecha: no hay nada que agradecer todavía."
        )
    return milestone


def _recipient_name(session: Session, job_id: int, data: MessageDraftInput) -> str | None:
    """El nombre del destinatario, tras comprobar que es de esta oferta (o de su empresa)."""
    if data.contact_id is not None:
        contact = session.get(Contact, data.contact_id)
        if contact is None or contact.job_id != job_id:
            raise ValueError(f"El contacto {data.contact_id} no es de la oferta {job_id}.")
        return contact.name
    if data.network_contact_id is not None:
        person = session.get(NetworkContact, data.network_contact_id)
        if person is None:
            raise ValueError(
                f"No existe la persona {data.network_contact_id} en la red del usuario."
            )
        if person.id not in network.people_ids(session, job_id):
            raise ValueError(
                f"{person.first_name} {person.last_name} no trabaja en la empresa de la oferta "
                f"{job_id} según tu red (mira `get_job_contacts`)."
            )
        return f"{person.first_name} {person.last_name}".strip()[:200]
    return None


def _same(column: Any, value: object) -> Any:
    return column.is_(None) if value is None else column == value


def save_message_draft(
    session: Session, job_id: int, data: MessageDraftInput, agent_name: str | None = None
) -> SaveDraftResult:
    """Guarda un borrador (o sustituye el vigente del mismo tipo y entrevista). No envía nada."""
    if session.get(Job, job_id) is None:
        raise events.JobNotFoundError(f"No existe la oferta {job_id}.")
    stage = events.current_stage(session, job_id)
    outreach = data.kind in OUTREACH_KINDS
    if outreach and stage not in OUTREACH_STAGES:
        raise DraftNotAllowedError(
            f"Solo se escribe a la empresa de una oferta aprobada y abierta (etapa «{stage}»)."
        )
    if not outreach and stage not in DRAFT_STAGES:
        raise DraftNotAllowedError(
            f"Solo se escribe a la empresa de una candidatura enviada y abierta (etapa «{stage}»)."
        )
    milestone_id: int | None = None
    recipient_name: str | None = None
    if outreach:
        recipient_name = _recipient_name(session, job_id, data)
    elif data.kind == "followup":
        if data.milestone_id is not None:
            raise ValueError("`milestone_id` solo va en un agradecimiento (`thank_you`).")
        limit = get_policies().followups.max_followups
        sent = followups_sent(session, [job_id]).get(job_id, 0)
        if sent >= limit:
            raise DraftNotAllowedError(
                f"Ya enviaste {sent} seguimientos a esta candidatura (máximo {limit}): "
                "no se propone otro."
            )
    else:
        milestone_id = _interview_done(session, job_id, data.milestone_id).id
        if thanked_milestones(session, [milestone_id]):
            raise DraftNotAllowedError("Ya enviaste el agradecimiento de esa entrevista.")

    # El vigente del mismo tipo y destinatario (y entrevista, en un agradecimiento).
    current = session.scalars(
        select(MessageDraft).where(
            MessageDraft.job_id == job_id,
            MessageDraft.kind == data.kind,
            _same(MessageDraft.milestone_id, milestone_id),
            _same(MessageDraft.recipient_role, data.recipient_role),
            _same(MessageDraft.contact_id, data.contact_id),
            _same(MessageDraft.network_contact_id, data.network_contact_id),
            MessageDraft.status == "draft",
        )
    ).first()
    now = utcnow()
    agent = (agent_name or "")[:64] or None
    if current is None:
        current = MessageDraft(
            job_id=job_id,
            kind=data.kind,
            milestone_id=milestone_id,
            status="draft",
            created_at=now,
        )
        session.add(current)
    replaced = current.id is not None
    current.subject = data.subject
    current.body = data.body
    current.agent_name = agent
    current.updated_at = now
    current.recipient_role = data.recipient_role
    current.contact_id = data.contact_id
    current.network_contact_id = data.network_contact_id
    current.recipient_name = recipient_name
    current.attachments = data.attachments
    session.flush()
    what = KIND_NAMES[data.kind]
    return SaveDraftResult(
        draft_id=current.id,
        job_id=job_id,
        kind=data.kind,
        milestone_id=milestone_id,
        replaced=replaced,
        message=f"Borrador de {what} guardado: el usuario lo revisa, lo copia y lo envía él. "
        "La app no envía nada.",
    )


def list_drafts(session: Session, job_id: int) -> DraftList:
    if session.get(Job, job_id) is None:
        raise events.JobNotFoundError(f"No existe la oferta {job_id}.")
    return DraftList(
        job_id=job_id,
        followups_sent=followups_sent(session, [job_id]).get(job_id, 0),
        max_followups=get_policies().followups.max_followups,
        drafts=[_out(row) for row in active_drafts(session, [job_id])],
    )


def _draft(session: Session, draft_id: int) -> MessageDraft:
    row = session.get(MessageDraft, draft_id)
    if row is None:
        raise DraftNotFoundError(f"No existe el borrador {draft_id}.")
    if row.status != "draft":
        verb = "enviado" if row.status == "sent" else "descartado"
        raise DraftNotAllowedError(f"Este borrador ya está marcado como {verb}.")
    return row


def mark_draft_sent(
    session: Session, draft_id: int, occurred_at: datetime | None = None
) -> DraftActionResult:
    """«Ya lo he enviado» (solo desde la UI): el usuario lo mandó desde su correo. Un seguimiento
    registra `followup_sent` (actor `user`, `payload.draft_id`)."""
    row = _draft(session, draft_id)
    event_id = None
    if row.kind == "followup":
        limit = get_policies().followups.max_followups
        if followups_sent(session, [row.job_id]).get(row.job_id, 0) >= limit:
            raise DraftNotAllowedError(
                f"Ya hay {limit} seguimientos enviados en esta candidatura: descarta este borrador."
            )
        event = events.record(
            session,
            row.job_id,
            EventType.FOLLOWUP_SENT,
            Actor.USER,
            payload={"draft_id": row.id},
            occurred_at=occurred_at,
        )
        event_id = event.id
    row.status = "sent"
    row.event_id = event_id
    row.updated_at = utcnow()
    session.flush()
    return DraftActionResult(
        draft_id=row.id,
        status="sent",
        event_id=event_id,
        stage=events.current_stage(session, row.job_id),
        message="Anotado como enviado.",
    )


def discard_draft(session: Session, draft_id: int) -> DraftActionResult:
    row = _draft(session, draft_id)
    row.status = "discarded"
    row.updated_at = utcnow()
    session.flush()
    return DraftActionResult(
        draft_id=row.id,
        status="discarded",
        event_id=None,
        stage=events.current_stage(session, row.job_id),
        message="Borrador descartado.",
    )
