"""Respuestas de las empresas por correo (fase 15).

1. **Ingesta** (`poll_replies`): lee la carpeta de respuestas por IMAP en solo lectura
   (`JH_IMAP_REPLIES_FOLDER`, por defecto la bandeja de entrada) y `data/inbox/respuestas/`. Sin
   candidaturas en `applied` o `in_process` no se abre el buzón. De IMAP se piden primero solo las
   cabeceras (`FROM`, `DATE`, `MESSAGE-ID`, `SUBJECT`) y el cuerpo solo de los correos que casan
   con un proceso; de los demás no se guarda nada.
2. **Coincidencia** (`_match`): el correo es posterior al envío y su remitente es un contacto de la
   ficha, o su dominio es el de la empresa (contactos o URL de la oferta), o es un ATS o un portal
   aprobado y nombra a la empresa, o la parte principal del dominio es el nombre de la empresa.
3. **Contenido no confiable**: se guarda como texto visible (sin lo oculto), con la detección de
   frases de inyección (también en el texto oculto) y se entrega envuelto en `<untrusted_email>`.
4. **Propuestas**: el agente guarda una propuesta (`save_reply_proposal`) que no registra eventos.
   Solo la UI, con la acción del usuario, la acepta (`accept_reply`) o la ignora (fase 15.2).
"""

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from email import message_from_bytes, policy
from email.utils import parseaddr
from typing import Any, Literal, Self

import lxml.html
from lxml.etree import ParserError
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.policies import get_policies
from app.models import Application, Company, Contact, Job, Milestone, Reply
from app.models.base import utcnow
from app.schemas.sources import Issue
from app.services import events, platforms
from app.services.ingestion.email.mailboxes import (
    ImapFactory,
    MailboxError,
    RawMail,
    read_imap_matching,
    read_local,
)
from app.services.ingestion.email.message import (
    AlertMessage,
    clean_header,
    message_id_of,
    parse_date,
    parse_message,
)
from app.services.normalize import fold, normalize_company
from app.services.pipeline import TRANSITIONS, Actor, EventType, Stage
from app.services.process import (
    MilestoneCreate,
    create_milestone,
    local_zone,
    start_of_local_day,
)
from app.services.untrusted import (
    EXCERPT_MAX_CHARS,
    RiskFlag,
    find_hidden_text,
    find_injection_phrases,
    hidden_reason,
    wrap_untrusted_email,
)

logger = logging.getLogger(__name__)

ReplyStatus = Literal["new", "proposed", "accepted", "ignored"]
REPLY_STATUSES: tuple[ReplyStatus, ...] = ("new", "proposed", "accepted", "ignored")
OPEN_PROCESS_STAGES = (Stage.APPLIED, Stage.IN_PROCESS)
MatchReason = Literal["contact", "domain", "ats", "company_name"]
_STRENGTH: dict[str, int] = {"contact": 0, "domain": 1, "ats": 2, "company_name": 3}

# Eventos que puede proponer el agente; `none`: nada que registrar (acuse de recibo, publicidad).
ProposalEvent = Literal[
    "reply_received", "interview_scheduled", "test_assigned", "offer_received", "rejected", "none"
]
# El hito que crea cada evento al aceptarlo (fase 10: `process.create_milestone`).
MILESTONE_KINDS: dict[str, Literal["interview", "test"]] = {
    "interview_scheduled": "interview",
    "test_assigned": "test",
}


class ReplyNotFoundError(LookupError):
    pass


class ReplyResolvedError(ValueError):
    """La respuesta ya la aceptó o la ignoró el usuario."""


# --- Esquemas -------------------------------------------------------------------------------


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ReplyMilestone(_Input):
    """Hito que propone el correo: entrevista (`interview_scheduled`) o prueba (`test_assigned`)."""

    title: str | None = Field(default=None, max_length=200, description="Por defecto, el tipo.")
    starts_at: AwareDatetime = Field(description="Inicio (ISO 8601 con zona, p. ej. +02:00).")
    ends_at: AwareDatetime | None = None
    all_day: bool = Field(default=False, description="Todo el día (p. ej. el plazo de una prueba).")
    location: str | None = Field(default=None, max_length=500, description="Lugar o enlace.")

    @model_validator(mode="after")
    def _ends_after_start(self) -> Self:
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("`ends_at` debe ser posterior a `starts_at`.")
        return self


class ReplyProposal(_Input):
    job_id: int = Field(ge=1, description="Oferta del correo: una de sus `candidates`.")
    event_type: ProposalEvent = Field(
        description="Evento a registrar si el usuario acepta; `none` si no hay nada que registrar."
    )
    occurred_at: AwareDatetime | None = Field(
        default=None, description="Cuándo pasó (por defecto, la fecha del correo)."
    )
    milestone: ReplyMilestone | None = Field(
        default=None,
        description="Solo con `interview_scheduled` o `test_assigned` y una fecha clara.",
    )
    summary: str = Field(
        min_length=1, max_length=500, description="Qué dice el correo, en una o dos frases."
    )
    confidence: Literal["high", "medium", "low"]
    injection_suspected: bool = Field(
        default=False, description="El correo trae instrucciones dirigidas a una IA."
    )

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if self.milestone is not None:
            if self.event_type not in MILESTONE_KINDS:
                raise ValueError("`milestone` solo va con `interview_scheduled` o `test_assigned`.")
            if self.confidence == "low":
                raise ValueError(
                    "Con `confidence: low` no se propone hito: deja `milestone` vacío."
                )
        return self


class ReplyCandidate(BaseModel):
    job_id: int
    title: str
    company: str
    stage: Stage
    applied_at: datetime | None
    reason: MatchReason
    upcoming: list[dict[str, Any]]  # hitos programados: kind, title, starts_at, all_day


class ReplyListItem(BaseModel):
    reply_id: int
    status: ReplyStatus
    received_at: datetime | None
    sender: str
    risk_flags: list[str]
    candidate_job_ids: list[int]
    job_id: int | None
    proposal_event: str | None
    confidence: str | None


class ReplyList(BaseModel):
    replies: list[ReplyListItem]
    counts: dict[str, int]  # por estado, de todas


class ReplyDetail(BaseModel):
    """Lo que ve el agente: el correo envuelto como contenido no confiable y las candidatas."""

    reply_id: int
    status: ReplyStatus
    received_at: datetime | None
    timezone: str
    risk_flags: list[str]
    content: str
    candidates: list[ReplyCandidate]
    proposal: ReplyProposal | None


class SaveReplyProposalResult(BaseModel):
    ok: bool
    reply_id: int
    job_id: int
    status: ReplyStatus
    stage: Stage
    valid_now: bool  # el evento es válido en la etapa actual de la oferta
    message: str


class RepliesPollResult(BaseModel):
    processes: int  # candidaturas abiertas con las que se compara
    checked: int  # correos mirados (solo cabeceras en IMAP)
    created: int  # respuestas nuevas guardadas
    reply_ids: list[int]
    errors: list[Issue]
    message: str


# --- Dominios -------------------------------------------------------------------------------

_SECOND_LEVEL = frozenset({"co", "com", "org", "net", "gob", "gov", "ac", "edu", "nom"})


def base_domain(host: str) -> str:
    """Dominio registrable aproximado: `mail.acme.com` -> `acme.com`, `x.acme.co.uk` ->
    `acme.co.uk`."""
    labels = [part for part in host.lower().strip(".").split(".") if part]
    if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def _in_domains(domain: str, domains: Iterable[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in domains)


def _host_of(url: str) -> str:
    match = re.match(r"^https?://([^/:?#]+)", url.strip(), re.IGNORECASE)
    return match.group(1).lower() if match else ""


@dataclass(frozen=True)
class _Domains:
    ats: tuple[str, ...]
    portals: tuple[str, ...]  # aprobados como remitentes de avisos
    personal: tuple[str, ...]
    alerts: tuple[str, ...]  # remitentes de las alertas de empleo (`email_alerts.platforms`)

    def is_ats(self, domain: str) -> bool:
        return _in_domains(domain, self.ats)

    def is_portal(self, domain: str) -> bool:
        return platforms.platform_of_host(domain) is not None or _in_domains(domain, self.alerts)

    def is_personal(self, domain: str) -> bool:
        return _in_domains(domain, self.personal)


def _domains() -> _Domains:
    policies = get_policies()
    ats = {*policies.replies.ats_sender_domains}
    for domains in policies.cv.ats_platforms.values():
        ats.update(domains)
    return _Domains(
        ats=tuple(sorted(ats)),
        portals=tuple(policies.replies.portal_sender_domains),
        personal=tuple(policies.replies.personal_mail_domains),
        alerts=tuple(d for ds in policies.email_alerts.platforms.values() for d in ds),
    )


# --- Procesos abiertos y coincidencia -------------------------------------------------------


@dataclass
class _Process:
    job_id: int
    company_key: str  # nombre normalizado: «acme analytics»
    since: datetime  # 00:00 (hora local) del día del envío
    contact_emails: set[str] = field(default_factory=set)
    domains: set[str] = field(default_factory=set)  # dominios de la empresa

    @property
    def compact(self) -> str:
        return self.company_key.replace(" ", "")


def _open_processes(session: Session, domains: _Domains, now: datetime) -> list[_Process]:
    max_days = get_policies().replies.max_days
    floor = start_of_local_day(now - timedelta(days=max_days))
    rows = session.execute(
        select(Job.id, Job.url, Company.name, Application.applied_at)
        .join(Application, Application.job_id == Job.id)
        .join(Company, Company.id == Job.company_id)
        .where(Application.stage.in_(OPEN_PROCESS_STAGES))
    ).all()
    processes: dict[int, _Process] = {}
    for job_id, url, company, applied_at in rows:
        since = start_of_local_day(applied_at) if applied_at else floor
        process = _Process(job_id, normalize_company(company), max(since, floor))
        host = _host_of(url or "")
        if (
            host
            and not domains.is_ats(host)
            and not domains.is_portal(host)
            and not domains.is_personal(host)
        ):
            process.domains.add(base_domain(host))
        processes[job_id] = process
    if processes:
        contacts = session.execute(
            select(Contact.job_id, Contact.email).where(
                Contact.job_id.in_(list(processes)), Contact.email.is_not(None)
            )
        ).all()
        for job_id, email in contacts:
            address = (email or "").strip().lower()
            if "@" not in address:
                continue
            processes[job_id].contact_emails.add(address)
            domain = address.rpartition("@")[2]
            if not domains.is_personal(domain) and not domains.is_ats(domain):
                processes[job_id].domains.add(base_domain(domain))
    return list(processes.values())


def _names_company(company_key: str, text: str) -> bool:
    return len(company_key) >= 2 and f" {company_key} " in f" {fold(text)} "


def _match(
    process: _Process, domains: _Domains, sender: str, sender_name: str, subject: str
) -> MatchReason | None:
    if sender in process.contact_emails:
        return "contact"
    domain = sender.rpartition("@")[2]
    if not domain or domains.is_personal(domain):
        return None
    if domains.is_ats(domain) or _in_domains(domain, domains.portals):
        return "ats" if _names_company(process.company_key, f"{sender_name} {subject}") else None
    if domains.is_portal(domain):
        return None  # avisos y alertas de portales no aprobados
    base = base_domain(domain)
    if base in process.domains:
        return "domain"
    label = base.split(".")[0].replace("-", "")
    compact = process.compact
    if not label or not compact:
        return None
    if (
        label == compact
        or (len(compact) >= 4 and label.startswith(compact))
        or (len(label) >= 4 and compact.startswith(label))
    ):
        return "company_name"
    return None


def _candidates(
    processes: list[_Process],
    domains: _Domains,
    sender: str,
    sender_name: str,
    subject: str,
    received_at: datetime | None,
) -> list[dict[str, Any]]:
    found: list[tuple[int, int, str]] = []
    for process in processes:
        if received_at is not None and received_at < process.since:
            continue  # anterior al envío
        reason = _match(process, domains, sender, sender_name, subject)
        if reason is not None:
            found.append((_STRENGTH[reason], -process.job_id, reason))
    found.sort()
    return [{"job_id": -neg_id, "reason": reason} for _, neg_id, reason in found]


# --- Texto del correo -----------------------------------------------------------------------

_BLOCK_TAGS = ("p", "div", "li", "tr", "h1", "h2", "h3", "h4", "table", "blockquote")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")


def _html_to_text(html: str) -> str:
    """Texto visible de un correo HTML: sin scripts, estilos ni lo oculto (el «preheader» o las
    instrucciones escondidas, que la detección de riesgo revisa aparte)."""
    try:
        root = lxml.html.document_fromstring(html)
    except (ParserError, ValueError):
        return ""
    for node in list(root.iter()):
        if not isinstance(node.tag, str):
            continue
        if node.tag in ("script", "style", "head", "title") or hidden_reason(node) is not None:
            node.drop_tree()
    # En HTML, los saltos de línea del código no cuentan: solo los de `<br>` y los bloques.
    for node in root.iter():
        if node.text:
            node.text = node.text.replace("\n", " ")
        if node.tail:
            node.tail = node.tail.replace("\n", " ")
    for node in root.iter("br"):
        node.tail = "\n" + (node.tail or "")
    for node in root.iter(*_BLOCK_TAGS):
        node.tail = "\n" + (node.tail or "")
    return root.text_content()


def body_text(message: AlertMessage, limit: int) -> str:
    raw = message.text if message.text and message.text.strip() else None
    if raw is None and message.html:
        raw = _html_to_text(message.html)
    text = _CONTROL.sub("", (raw or "").replace("\r\n", "\n").replace("\r", "\n"))
    lines = [" ".join(line.split()) for line in text.split("\n")]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()[:limit]


def _risk(message: AlertMessage, text: str) -> tuple[list[str], str | None]:
    visible = find_injection_phrases(f"{message.sender_name}\n{message.subject}\n{text}")
    hidden = [
        match
        for block in (find_hidden_text(message.html) if message.html else [])
        for match in find_injection_phrases(block.text)
    ]
    flags: list[str] = []
    if hidden:
        flags.append(RiskFlag.HIDDEN_TEXT.value)
    if visible or hidden:
        flags.append(RiskFlag.INJECTION_PHRASE.value)
    matches = visible + hidden
    return flags, matches[0].excerpt[:EXCERPT_MAX_CHARS] if matches else None


# --- Ingesta --------------------------------------------------------------------------------


def _is_known(session: Session, message_id: str) -> bool:
    stmt = select(Reply.id).where(Reply.message_id == message_id).limit(1)
    return session.scalars(stmt).first() is not None


def replies_enabled() -> bool:
    """Si hay de dónde leer respuestas: IMAP configurado o correos en `data/inbox/respuestas/`."""
    from app.services.ingestion.email.mailboxes import has_local_mail

    settings = get_settings()
    return settings.imap_configured or has_local_mail(settings.replies_inbox_dir)


def has_open_processes(session: Session) -> bool:
    stmt = select(Application.job_id).where(Application.stage.in_(OPEN_PROCESS_STAGES)).limit(1)
    return session.scalars(stmt).first() is not None


def poll_replies(
    session: Session, *, imap_factory: ImapFactory | None = None, now: datetime | None = None
) -> RepliesPollResult:
    """Guarda las respuestas nuevas de las empresas de tus procesos. Idempotente."""
    settings = get_settings()
    limits = get_policies().replies
    domains = _domains()
    processes = _open_processes(session, domains, now or utcnow())
    result = RepliesPollResult(
        processes=len(processes), checked=0, created=0, reply_ids=[], errors=[], message=""
    )
    if not processes:
        result.message = "Respuestas: no hay candidaturas enviadas abiertas; no se lee el correo."
        return result
    own = (settings.imap_user or "").strip().lower()

    def candidates_of(
        sender: str, name: str, subject: str, when: datetime | None
    ) -> list[dict[str, Any]]:
        if not sender or sender == own:
            return []
        return _candidates(processes, domains, sender, name, subject, when)

    def wanted(header: bytes) -> bool:
        result.checked += 1
        parsed = message_from_bytes(header, policy=policy.default)
        message_id = message_id_of(header, parsed.get("Message-ID"))
        if parsed.get("Message-ID") and _is_known(session, message_id):
            return False
        name, address = parseaddr(str(parsed.get("From", "")))
        return bool(
            candidates_of(
                address.strip().lower(),
                clean_header(name, 200),
                clean_header(str(parsed.get("Subject", "")), 300),
                parse_date(parsed.get("Date")),
            )
        )

    mails: list[tuple[RawMail, str]] = []
    if settings.imap_configured:
        earliest = min(p.since for p in processes).astimezone(local_zone()).date()
        since: date = earliest - timedelta(days=1)  # SINCE va por días en la zona del servidor
        try:
            kwargs = {"factory": imap_factory} if imap_factory else {}
            folder = settings.imap_replies_folder
            for raw in read_imap_matching(settings, folder, since, wanted, **kwargs):
                mails.append((raw, "imap"))
        except MailboxError as exc:
            result.errors.append(Issue(code=exc.code, message=exc.message))
    try:
        for raw in read_local(settings.replies_inbox_dir):
            result.checked += 1
            mails.append((raw, "local"))
    except OSError as exc:
        result.errors.append(
            Issue(
                code="inbox_error",
                message=f"No se pudo leer data/inbox/respuestas/ ({type(exc).__name__}).",
            )
        )

    seen: set[str] = set()
    for raw, origin in mails:
        try:
            message = parse_message(raw.raw)
        except Exception:  # un correo roto no para a los demás
            logger.warning("Correo ilegible: %s", raw.origin, exc_info=True)
            result.errors.append(
                Issue(code="invalid_message", message="Correo ilegible.", item=raw.origin)
            )
            continue
        if message.message_id in seen or _is_known(session, message.message_id):
            continue
        seen.add(message.message_id)
        candidates = candidates_of(
            message.sender, message.sender_name, message.subject, message.received_at
        )
        if not candidates:
            continue  # no es de ninguno de tus procesos: no se guarda nada
        text = body_text(message, limits.max_body_chars)
        flags, excerpt = _risk(message, text)
        reply = Reply(
            message_id=message.message_id,
            origin=origin,
            sender=message.sender[:320],
            sender_name=message.sender_name,
            subject=message.subject,
            received_at=message.received_at,
            body_text=text,
            risk_flags=flags,
            risk_excerpt=excerpt,
            candidates=candidates,
            status="new",
            created_at=utcnow(),
        )
        session.add(reply)
        session.flush()
        result.created += 1
        result.reply_ids.append(reply.id)
    result.message = _describe(result)
    return result


def _describe(result: RepliesPollResult) -> str:
    if result.created:
        text = (
            f"Respuestas: {result.created} correo{'s' if result.created != 1 else ''} nuevo"
            f"{'s' if result.created != 1 else ''} de tus procesos"
        )
    else:
        text = "Respuestas: ningún correo nuevo de tus procesos"
    if result.errors:
        text += f"; {len(result.errors)} avisos"
    return text + "."


# --- Consultas y propuestas -----------------------------------------------------------------


def _reply(session: Session, reply_id: int) -> Reply:
    row = session.get(Reply, reply_id)
    if row is None:
        raise ReplyNotFoundError(f"No existe la respuesta {reply_id}.")
    return row


def _candidate_ids(row: Reply) -> list[int]:
    return [int(c["job_id"]) for c in row.candidates]


def _list_item(row: Reply) -> ReplyListItem:
    proposal = row.proposal or {}
    return ReplyListItem(
        reply_id=row.id,
        status=row.status,  # type: ignore[arg-type]
        received_at=row.received_at,
        sender=row.sender,
        risk_flags=list(row.risk_flags),
        candidate_job_ids=_candidate_ids(row),
        job_id=row.job_id,
        proposal_event=proposal.get("event_type"),
        confidence=proposal.get("confidence"),
    )


def status_counts(session: Session) -> dict[str, int]:
    from sqlalchemy import func

    rows = session.execute(select(Reply.status, func.count()).group_by(Reply.status)).all()
    counts = dict.fromkeys(REPLY_STATUSES, 0)
    counts.update({status: count for status, count in rows})
    return counts


def list_replies(session: Session, status: ReplyStatus | None = None, limit: int = 50) -> ReplyList:
    """Respuestas guardadas, la más reciente primero. Sin texto del correo."""
    query = select(Reply)
    if status is not None:
        query = query.where(Reply.status == status)
    query = query.order_by(Reply.received_at.desc().nulls_last(), Reply.id.desc()).limit(limit)
    return ReplyList(
        replies=[_list_item(row) for row in session.scalars(query)],
        counts=status_counts(session),
    )


def candidates_view(session: Session, row: Reply) -> list[ReplyCandidate]:
    ids = _candidate_ids(row)
    if not ids:
        return []
    jobs = {
        job_id: (title, company, stage, applied_at)
        for job_id, title, company, stage, applied_at in session.execute(
            select(Job.id, Job.title, Company.name, Application.stage, Application.applied_at)
            .join(Company, Company.id == Job.company_id)
            .join(Application, Application.job_id == Job.id)
            .where(Job.id.in_(ids))
        ).all()
    }
    upcoming: dict[int, list[dict[str, Any]]] = {job_id: [] for job_id in ids}
    for milestone in session.scalars(
        select(Milestone)
        .where(Milestone.job_id.in_(ids), Milestone.status == "scheduled")
        .order_by(Milestone.starts_at)
    ):
        upcoming[milestone.job_id].append(
            {
                "kind": milestone.kind,
                "title": milestone.title,
                "starts_at": milestone.starts_at.isoformat(),
                "all_day": milestone.all_day,
            }
        )
    out: list[ReplyCandidate] = []
    for candidate in row.candidates:
        job_id = int(candidate["job_id"])
        if job_id not in jobs:
            continue
        title, company, stage, applied_at = jobs[job_id]
        out.append(
            ReplyCandidate(
                job_id=job_id,
                title=title,
                company=company,
                stage=Stage(stage),
                applied_at=applied_at,
                reason=candidate["reason"],
                upcoming=upcoming[job_id],
            )
        )
    return out


def _proposal(row: Reply) -> ReplyProposal | None:
    return ReplyProposal.model_validate(row.proposal) if row.proposal else None


def email_text(row: Reply) -> str:
    when = row.received_at.astimezone(local_zone()).isoformat() if row.received_at else "?"
    sender = f"{row.sender_name} <{row.sender}>" if row.sender_name else row.sender
    return f"De: {sender}\nAsunto: {row.subject}\nFecha: {when}\n\n{row.body_text}"


def get_reply(session: Session, reply_id: int) -> ReplyDetail:
    row = _reply(session, reply_id)
    return ReplyDetail(
        reply_id=row.id,
        status=row.status,  # type: ignore[arg-type]
        received_at=row.received_at,
        timezone=get_policies().calendar.timezone,
        risk_flags=list(row.risk_flags),
        content=wrap_untrusted_email(row.id, email_text(row), list(row.risk_flags)),
        candidates=candidates_view(session, row),
        proposal=_proposal(row),
    )


def event_valid_in(event_type: str, stage: Stage) -> bool:
    if event_type == "none":
        return True
    return stage in TRANSITIONS[EventType(event_type)].allowed_from


def save_reply_proposal(
    session: Session, reply_id: int, proposal: ReplyProposal, agent_name: str | None = None
) -> SaveReplyProposalResult:
    """Guarda (o sustituye) la propuesta del agente. No registra ningún evento: nada cambia de
    etapa hasta que el usuario la acepta en la UI."""
    row = _reply(session, reply_id)
    if row.status in ("accepted", "ignored"):
        raise ReplyResolvedError(
            f"La respuesta {reply_id} ya la resolvió el usuario («{row.status}»)."
        )
    if proposal.job_id not in _candidate_ids(row):
        valid = ", ".join(str(i) for i in _candidate_ids(row)) or "ninguna"
        raise ValueError(
            f"La oferta {proposal.job_id} no es candidata de este correo. Candidatas: {valid}."
        )
    application = session.get(Application, proposal.job_id)
    stage = Stage(application.stage) if application else Stage.CLOSED
    row.proposal = proposal.model_dump(mode="json")
    row.status = "proposed"
    row.job_id = proposal.job_id
    row.proposed_at = utcnow()
    row.proposed_by = (agent_name or "")[:64] or None
    session.flush()
    valid = event_valid_in(proposal.event_type, stage)
    message = "Propuesta guardada: el usuario la revisa en «Respuestas»."
    if not valid:
        message += f" Ojo: «{proposal.event_type}» no es válido ahora en la etapa «{stage}»."
    return SaveReplyProposalResult(
        ok=True,
        reply_id=row.id,
        job_id=proposal.job_id,
        status="proposed",
        stage=stage,
        valid_now=valid,
        message=message,
    )


# --- Decisión del usuario (UI) --------------------------------------------------------------


class ReplyDecision(_Input):
    """Lo que acepta el usuario: la propuesta del agente tal cual o cambiada, o la suya."""

    job_id: int = Field(ge=1, description="Oferta del correo: una de sus candidatas.")
    event_type: ProposalEvent
    occurred_at: AwareDatetime | None = Field(
        default=None, description="Cuándo pasó (por defecto, la fecha del correo)."
    )
    milestone: ReplyMilestone | None = None
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _milestone_kind(self) -> Self:
        if self.milestone is not None and self.event_type not in MILESTONE_KINDS:
            raise ValueError("`milestone` solo va con `interview_scheduled` o `test_assigned`.")
        return self


class ReplyDecisionResult(BaseModel):
    ok: bool = True
    reply_id: int
    status: ReplyStatus
    job_id: int | None
    event_id: int | None
    milestone_id: int | None
    stage: Stage | None
    message: str


class ReplyJob(BaseModel):
    job_id: int
    title: str
    company: str
    stage: Stage
    reason: MatchReason


class ReplyInboxItem(BaseModel):
    """Una respuesta en la UI: cabeceras, ofertas candidatas y propuesta (sin el cuerpo)."""

    reply_id: int
    status: ReplyStatus
    received_at: datetime | None
    sender: str
    sender_name: str
    subject: str
    risk_flags: list[str]
    candidates: list[ReplyJob]
    job_id: int | None
    proposal: ReplyProposal | None
    proposed_by: str | None
    valid_now: bool | None  # el evento propuesto es válido en la etapa actual de su oferta
    event_id: int | None
    resolved_at: datetime | None


class ReplyInbox(BaseModel):
    replies: list[ReplyInboxItem]
    counts: dict[str, int]  # por estado, de todas


class ReplyView(ReplyInboxItem):
    body_text: str  # texto visible del correo: la UI lo muestra como texto, nunca como HTML


_JobRefs = dict[int, tuple[str, str, Stage]]


def _job_refs(session: Session, ids: set[int]) -> _JobRefs:
    if not ids:
        return {}
    rows = session.execute(
        select(Job.id, Job.title, Company.name, Application.stage)
        .join(Company, Company.id == Job.company_id)
        .join(Application, Application.job_id == Job.id)
        .where(Job.id.in_(ids))
    ).all()
    return {job_id: (title, company, Stage(stage)) for job_id, title, company, stage in rows}


def _inbox_fields(row: Reply, refs: _JobRefs) -> dict[str, Any]:
    candidates = []
    for candidate in row.candidates:
        job_id = int(candidate["job_id"])
        if job_id in refs:
            title, company, stage = refs[job_id]
            candidates.append(
                ReplyJob(
                    job_id=job_id,
                    title=title,
                    company=company,
                    stage=stage,
                    reason=candidate["reason"],
                )
            )
    proposal = _proposal(row)
    valid_now = None
    if proposal is not None and row.status == "proposed" and proposal.job_id in refs:
        valid_now = event_valid_in(proposal.event_type, refs[proposal.job_id][2])
    return {
        "reply_id": row.id,
        "status": row.status,
        "received_at": row.received_at,
        "sender": row.sender,
        "sender_name": row.sender_name,
        "subject": row.subject,
        "risk_flags": list(row.risk_flags),
        "candidates": candidates,
        "job_id": row.job_id,
        "proposal": proposal,
        "proposed_by": row.proposed_by,
        "valid_now": valid_now,
        "event_id": row.event_id,
        "resolved_at": row.resolved_at,
    }


def inbox(
    session: Session,
    status: ReplyStatus | None = None,
    job_id: int | None = None,
    limit: int = 100,
) -> ReplyInbox:
    """Bandeja «Respuestas» de la UI, la más reciente primero. Con `job_id`, las asignadas a esa
    oferta (propuestas o aceptadas para ella)."""
    query = select(Reply)
    if status is not None:
        query = query.where(Reply.status == status)
    if job_id is not None:
        query = query.where(Reply.job_id == job_id)
    query = query.order_by(Reply.received_at.desc().nulls_last(), Reply.id.desc()).limit(limit)
    rows = list(session.scalars(query))
    refs = _job_refs(session, {i for row in rows for i in _candidate_ids(row)})
    return ReplyInbox(
        replies=[ReplyInboxItem(**_inbox_fields(row, refs)) for row in rows],
        counts=status_counts(session),
    )


def reply_view(session: Session, reply_id: int) -> ReplyView:
    row = _reply(session, reply_id)
    refs = _job_refs(session, set(_candidate_ids(row)))
    return ReplyView(**_inbox_fields(row, refs), body_text=row.body_text)


def _ensure_open(row: Reply) -> None:
    if row.status in ("accepted", "ignored"):
        verb = "aceptaste" if row.status == "accepted" else "ignoraste"
        raise ReplyResolvedError(f"Esta respuesta ya la {verb}.")


def accept_reply(session: Session, reply_id: int, decision: ReplyDecision) -> ReplyDecisionResult:
    """Acepta la propuesta (o la cambiada por el usuario). Solo se llama desde la UI.

    Registra el evento como `user` con `payload.reply_id`; con hito, lo crea
    `process.create_milestone` (que registra `interview_scheduled` o `test_assigned`). Con `none`
    se archiva sin evento. Si el evento no es válido en la etapa de la oferta, no cambia nada.
    """
    row = _reply(session, reply_id)
    _ensure_open(row)
    if decision.job_id not in _candidate_ids(row):
        raise ValueError(f"La oferta {decision.job_id} no es candidata de este correo.")
    occurred_at = decision.occurred_at or row.received_at
    extra: dict[str, Any] = {"reply_id": row.id}
    event_id: int | None = None
    milestone_id: int | None = None
    if decision.event_type == "none":
        message = "Archivada sin registrar nada."
    elif decision.milestone is not None:
        milestone = decision.milestone
        created = create_milestone(
            session,
            decision.job_id,
            MilestoneCreate(
                kind=MILESTONE_KINDS[decision.event_type],
                title=milestone.title,
                starts_at=milestone.starts_at,
                ends_at=milestone.ends_at,
                all_day=milestone.all_day,
                location=milestone.location,
                notes=decision.note,
                occurred_at=occurred_at,
            ),
            payload_extra=extra,
        )
        event_id, milestone_id = created.event_id, created.id
        message = "Registrado, con su hito en el calendario."
    else:
        if decision.note:
            extra["note"] = decision.note
        event = events.record(
            session,
            decision.job_id,
            decision.event_type,
            Actor.USER,
            payload=extra,
            occurred_at=occurred_at,
        )
        event_id = event.id
        message = "Registrado en la oferta."
    row.status = "accepted"
    row.job_id = decision.job_id
    row.event_id = event_id
    row.resolved_at = utcnow()
    session.flush()
    return ReplyDecisionResult(
        reply_id=row.id,
        status="accepted",
        job_id=decision.job_id,
        event_id=event_id,
        milestone_id=milestone_id,
        stage=events.current_stage(session, decision.job_id),
        message=message,
    )


def ignore_reply(session: Session, reply_id: int) -> ReplyDecisionResult:
    """Ignora la respuesta: no registra nada y deja de estar pendiente."""
    row = _reply(session, reply_id)
    _ensure_open(row)
    row.status = "ignored"
    row.resolved_at = utcnow()
    session.flush()
    return ReplyDecisionResult(
        reply_id=row.id,
        status="ignored",
        job_id=row.job_id,
        event_id=None,
        milestone_id=None,
        stage=None,
        message="Ignorada: no se registra nada.",
    )
