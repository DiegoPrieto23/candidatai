"""Borradores de seguimiento y de agradecimiento (fase 15).

El agente redacta (`save_message_draft`); la app **nunca envía nada** (regla dura 5). El usuario
copia el texto, lo manda desde su correo y, si es un seguimiento, pulsa «Ya lo he enviado» en la
UI, que registra `followup_sent`. Como mucho `followups.max_followups` seguimientos (2) por
candidatura; un agradecimiento, solo tras una entrevista hecha.
"""

from datetime import datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.models import Event, Job, MessageDraft, Milestone
from app.models.base import utcnow
from app.services import events
from app.services.pipeline import Actor, EventType, Stage

DraftKind = Literal["followup", "thank_you"]
DraftStatus = Literal["draft", "sent", "discarded"]
# Candidaturas enviadas y vivas: las únicas a las que tiene sentido escribir.
DRAFT_STAGES = (Stage.APPLIED, Stage.IN_PROCESS)


class DraftNotFoundError(LookupError):
    pass


class DraftNotAllowedError(ValueError):
    """El borrador no se puede guardar o cambiar (tope de seguimientos, etapa, ya resuelto…)."""


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MessageDraftInput(_Input):
    kind: DraftKind = Field(description="`followup` (seguimiento) o `thank_you` (agradecimiento).")
    subject: str = Field(min_length=1, max_length=300, description="Asunto del correo.")
    body: str = Field(min_length=1, max_length=10000, description="Texto del correo, sin firma.")
    milestone_id: int | None = Field(
        default=None,
        ge=1,
        description="Solo en `thank_you`: la entrevista que agradeces (por defecto, la última "
        "hecha).",
    )


class MessageDraftOut(BaseModel):
    id: int
    job_id: int
    kind: DraftKind
    milestone_id: int | None
    subject: str
    body: str
    status: DraftStatus
    event_id: int | None
    agent_name: str | None
    created_at: datetime
    updated_at: datetime


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


def save_message_draft(
    session: Session, job_id: int, data: MessageDraftInput, agent_name: str | None = None
) -> SaveDraftResult:
    """Guarda un borrador (o sustituye el vigente del mismo tipo y entrevista). No envía nada."""
    if session.get(Job, job_id) is None:
        raise events.JobNotFoundError(f"No existe la oferta {job_id}.")
    stage = events.current_stage(session, job_id)
    if stage not in DRAFT_STAGES:
        raise DraftNotAllowedError(
            f"Solo se escribe a la empresa de una candidatura enviada y abierta (etapa «{stage}»)."
        )
    milestone_id: int | None = None
    if data.kind == "followup":
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

    current = session.scalars(
        select(MessageDraft).where(
            MessageDraft.job_id == job_id,
            MessageDraft.kind == data.kind,
            MessageDraft.milestone_id.is_(None)
            if milestone_id is None
            else MessageDraft.milestone_id == milestone_id,
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
    session.flush()
    what = "seguimiento" if data.kind == "followup" else "agradecimiento"
    return SaveDraftResult(
        draft_id=current.id,
        job_id=job_id,
        kind=data.kind,
        milestone_id=milestone_id,
        replaced=replaced,
        message=f"Borrador de {what} guardado: el usuario lo revisa, lo copia y lo envía él "
        "desde su correo. La app no envía nada.",
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
