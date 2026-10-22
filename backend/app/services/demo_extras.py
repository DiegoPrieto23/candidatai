"""Lo que la demo trae hecho además del embudo (fase 26.5).

`demo.seed` deja ofertas, eventos, hitos, contactos y CVs. Aquí se añade lo que dejarían el agente
y la candidata en las fichas, para que cada pantalla del portal tenga algo que enseñar: valoración
del encaje, carta, respuestas de screening, mensajes, dosieres de empresa (uno con bandera roja),
plan y repaso de entrevistas, oferta recibida, correos de empresas (con propuesta y sin ella),
huecos de skills, un encargo pendiente, contexto, una muestra de estilo y la tabla de salarios.

Todo pasa por los servicios de siempre, con el contenido de `demo/<idioma>/seed/extras.yaml`.
Lo que esos servicios fechan «ahora» se lleva después al momento que le toca en la historia.
"""

import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.models import Application, Event, Milestone, Reply
from app.schemas.cover_letter import CoverLetterBriefInput, CoverLetterContent
from app.schemas.cv import CvVerification
from app.schemas.interviews import InterviewPlanInput, PrepBlock
from app.schemas.llm_io import ApplicationAnswers, FitAssessment
from app.services import (
    agent_requests,
    answers,
    company_research,
    context,
    drafts,
    interviews,
    pipeline,
    process,
    received_offers,
    replies,
    skill_gaps,
    style_samples,
)
from app.services.documents import cover_letter as letter
from app.services.matching import service as matching
from app.services.normalize import normalize_company
from app.services.pipeline import EventType

# Destinos con la candidatura abierta (`replies` compara los correos con todas ellas).
OPEN_FATES = ("applied", "replied", "interview_scheduled", "offer")
# Formato de la tabla que cita `prepare-negotiation`; el mismo en los dos idiomas.
SALARIES = REPO_ROOT / "demo" / "salarios.example.csv"


class DemoExtrasError(ValueError):
    """El contenido de `extras.yaml` no casa con la demo; el mensaje dice dónde."""


@dataclass(frozen=True)
class SeededJob:
    """Una oferta de la demo ya escrita: su destino en la historia, su id y su empresa."""

    fate: str
    job_id: int
    title: str
    company: str


def load_extras(demo_dir: Path) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(
        (demo_dir / "seed" / "extras.yaml").read_text(encoding="utf-8")
    )
    return data


def populate(
    session: Session,
    jobs: list[SeededJob],
    now: datetime,
    demo_dir: Path,
    with_letter: bool,
    agent_name: str,
) -> None:
    """Rellena las fichas y las carpetas de la demo. `with_letter`: hay con qué renderizar."""
    extras = load_extras(demo_dir)
    first_event = (session.scalar(select(func.max(Event.id))) or 0) + 1
    featured = [job for job in jobs if job.fate == "cv_ready"]
    if len(featured) != len(extras["fit_assessments"]):
        raise DemoExtrasError("Hace falta una valoración por cada oferta de cvs.yaml.")
    by_fate: dict[str, list[SeededJob]] = {}
    for job in jobs:
        by_fate.setdefault(job.fate, []).append(job)

    _files(demo_dir, extras)
    for job, raw in zip(featured, extras["fit_assessments"], strict=True):
        matching.save_fit_assessment(
            session, job.job_id, FitAssessment.model_validate(raw), agent_name=agent_name
        )
    first, second = featured[0], featured[1]
    _letter_and_answers(session, first.job_id, extras, with_letter, agent_name)
    drafts.save_message_draft(
        session,
        second.job_id,
        drafts.MessageDraftInput.model_validate(extras["message_draft"]),
        agent_name=agent_name,
    )
    for job, raw in zip(featured, extras["company_research"], strict=True):
        company_research.save_company_research(
            session,
            job.job_id,
            company_research.CompanyResearchContent.model_validate(raw),
            agent_name=agent_name,
        )
    agent_requests.create(session, extras["agent_request"], job_id=by_fate["approved"][0].job_id)
    for skill in extras["skill_gaps"]:
        skill_gaps.set_mark(session, skill, "gap")

    # Los correos, de empresas con un solo proceso abierto: así su única candidata es la suya.
    open_companies = [job.company for job in jobs if job.fate in OPEN_FATES]
    applied = by_fate.get("applied", [])
    single = [job for job in applied if open_companies.count(job.company) == 1]
    if len(single) < len(extras["replies"]) or len(applied) <= len(extras["replies"]):
        raise DemoExtrasError("No hay candidaturas enviadas suficientes para los correos.")
    mailed = single[: len(extras["replies"])]
    _replies(session, mailed, extras["replies"], now, agent_name)
    followup = next(job for job in applied if job not in mailed)
    texts = extras["followup_draft"]
    drafts.save_message_draft(
        session,
        followup.job_id,
        drafts.MessageDraftInput(
            kind="followup",
            subject=texts["subject"].format(title=followup.title),
            body=texts["body"].format(title=followup.title, company=followup.company),
        ),
        agent_name=agent_name,
    )
    _interviews(session, by_fate, extras, now, agent_name)
    _received_offer(session, by_fate["offer"][0].job_id, extras["received_offer"], now)
    _retime(session, first_event, now)


def _files(demo_dir: Path, extras: dict[str, Any]) -> None:
    """Contexto, muestra de estilo y salarios: lo que vive en carpetas, no en la base de datos."""
    target = context.context_dir()
    target.mkdir(parents=True, exist_ok=True)
    for path in sorted((demo_dir / "contexto").glob("*.md")):
        shutil.copyfile(path, target / path.name)
    context.init()  # las carpetas de `documentos/`; no pisa los ficheros recién copiados
    sample = extras["style_sample"]
    style_samples.save_sample(sample["filename"], sample["text"].encode("utf-8"))
    shutil.copyfile(SALARIES, context.documents_dir() / "salarios.csv")


def _letter_and_answers(
    session: Session, job_id: int, extras: dict[str, Any], with_letter: bool, agent_name: str
) -> None:
    answers.save_application_answers(
        session,
        job_id,
        ApplicationAnswers(answers=extras["application_answers"]),
        agent_name=agent_name,
    )
    if not with_letter:
        return  # sin conversor a PDF tampoco hay CV: la carta se queda para el agente
    raw = extras["cover_letter"]
    letter.save_brief(session, job_id, CoverLetterBriefInput.model_validate(raw["brief"]))
    saved = letter.save_cover_letter(
        session,
        job_id,
        CoverLetterContent.model_validate(raw["content"]),
        agent_name=agent_name,
    )
    letter.save_verification(
        session, saved.document_id, CvVerification(passed=True), agent_name=agent_name
    )


def _applied_at(session: Session, job_id: int) -> datetime:
    application = session.get(Application, job_id)
    if application is None or application.applied_at is None:
        raise DemoExtrasError(f"La oferta {job_id} no tiene fecha de envío.")
    return application.applied_at


def _weekday_at(now: datetime, days: float, hour: int) -> datetime:
    """`days` desde hoy a la hora `hour` de Madrid, llevado al lunes si cae en fin de semana."""
    local = (now + timedelta(days=days)).astimezone(process.local_zone())
    while local.weekday() >= 5:
        local += timedelta(days=1)
    return local.replace(hour=hour, minute=0, second=0, microsecond=0)


def _replies(
    session: Session,
    jobs: list[SeededJob],
    specs: list[dict[str, Any]],
    now: datetime,
    agent_name: str,
) -> None:
    """Un correo por candidatura en `inbox/respuestas/`, leído como cualquier otro."""
    inbox = get_settings().replies_inbox_dir
    inbox.mkdir(parents=True, exist_ok=True)
    expected: list[tuple[str, SeededJob, dict[str, Any], datetime]] = []
    for n, (job, spec) in enumerate(zip(jobs, specs, strict=True), start=1):
        applied_at = _applied_at(session, job.job_id)
        received = min(now - timedelta(hours=3 * n), applied_at + timedelta(days=2))
        domain = _mail_domain(job.company)
        proposal = spec.get("proposal")
        meeting = None
        if proposal and proposal.get("milestone"):
            plan = proposal["milestone"]
            meeting = _weekday_at(now, plan["in_days"], plan["hour"])
        fields = {
            "company": job.company,
            "title": job.title,
            "date": meeting.date().isoformat() if meeting else "",
            "hour": meeting.hour if meeting else "",
        }
        message = EmailMessage()
        message["From"] = f"{spec['sender_name'].format(**fields)} <{spec['sender']}@{domain}>"
        message["To"] = "candidata@demo.invalid"
        message["Subject"] = spec["subject"].format(**fields)
        message["Date"] = format_datetime(received)
        message_id = f"<demo-{n}@{domain}>"
        message["Message-ID"] = message_id
        if "html" in spec:
            message.set_content(spec["html"].format(**fields), subtype="html")
        else:
            message.set_content(spec["body"].format(**fields))
        (inbox / f"demo-{n:02d}.eml").write_bytes(bytes(message))
        expected.append((message_id, job, spec, received))

    result = replies.poll_replies(session, now=now)
    if result.created != len(expected):
        raise DemoExtrasError(
            f"Se esperaban {len(expected)} correos de empresas y se guardaron {result.created}: "
            "revisa los nombres de las empresas de las candidaturas enviadas."
        )
    rows = {
        row.message_id: row.id
        for row in session.scalars(select(Reply).where(Reply.id.in_(result.reply_ids)))
    }
    for message_id, job, spec, received in expected:
        proposal = spec.get("proposal")
        if not proposal:
            continue  # queda «Nueva»: la clasifica `review-replies`
        milestone = None
        if proposal.get("milestone"):
            plan = proposal["milestone"]
            milestone = {
                "title": plan["title"],
                "starts_at": _weekday_at(now, plan["in_days"], plan["hour"]),
                "location": plan["location"],
            }
        replies.save_reply_proposal(
            session,
            rows[message_id],
            replies.ReplyProposal.model_validate(
                {
                    "job_id": job.job_id,
                    "event_type": proposal["event_type"],
                    "occurred_at": received,
                    "milestone": milestone,
                    "summary": proposal["summary"],
                    "confidence": "high",
                }
            ),
            agent_name=agent_name,
        )


def _mail_domain(company: str) -> str:
    """El dominio de los correos de una empresa, con su nombre sin espacios
    («bretemaanalytics.example»): `replies` lo reconoce como de esa empresa y de ninguna otra."""
    return normalize_company(company).replace(" ", "") + ".example"


def _milestone(session: Session, job_id: int) -> Milestone:
    row = session.scalars(
        select(Milestone)
        .where(Milestone.job_id == job_id, Milestone.kind == "interview")
        .order_by(Milestone.id)
    ).first()
    if row is None:
        raise DemoExtrasError(f"La oferta {job_id} no tiene entrevista.")
    return row


def _interviews(
    session: Session,
    by_fate: dict[str, list[SeededJob]],
    extras: dict[str, Any],
    now: datetime,
    agent_name: str,
) -> None:
    """Plan de la primera entrevista programada y repaso de las ya hechas (la de la oferta
    primero)."""
    upcoming = _milestone(session, by_fate["interview_scheduled"][0].job_id)
    today = now.astimezone(process.local_zone()).date()
    day = upcoming.starts_at.astimezone(process.local_zone()).date()
    topics = extras["interview_plan"]
    span = max((day - today).days, 0)
    blocks = [
        PrepBlock(date=today + timedelta(days=round(i * span / max(len(topics) - 1, 1))), **raw)
        for i, raw in enumerate(topics)
    ]
    interviews.save_interview_plan(
        session, upcoming.id, InterviewPlanInput(blocks=blocks), agent_name=agent_name, now=now
    )
    done = [*by_fate.get("offer", []), *by_fate.get("interview_rejected", [])]
    for job, raw in zip(done, extras["interview_notes"], strict=False):
        interviews.save_interview_notes(
            session,
            _milestone(session, job.job_id).id,
            interviews.InterviewNotesInput.model_validate(raw),
            now=now,
        )


def _received_offer(session: Session, job_id: int, raw: dict[str, Any], now: datetime) -> None:
    fields = {k: v for k, v in raw.items() if k not in ("start_in_days", "respond_in_days")}
    today = now.astimezone(process.local_zone()).date()
    received_offers.save_received_offer(
        session,
        job_id,
        received_offers.ReceivedOfferFields(
            **fields,
            start_date=today + timedelta(days=raw["start_in_days"]),
            respond_by=today + timedelta(days=raw["respond_in_days"]),
        ),
    )


def _retime(session: Session, first_event: int, now: datetime) -> None:
    """Los servicios fechan «ahora» lo que registran. La valoración del encaje va justo antes de
    la aprobación de su oferta; lo demás (carta, respuestas), unos minutos antes de `now`."""
    rows = session.scalars(select(Event).where(Event.id >= first_event).order_by(Event.id)).all()
    touched: set[int] = set()
    for i, event in enumerate(rows):
        when = now - timedelta(minutes=len(rows) - i)
        if event.type == EventType.FIT_ASSESSED:
            approved = session.scalars(
                select(Event.occurred_at).where(
                    Event.job_id == event.job_id, Event.type == EventType.APPROVED
                )
            ).first()
            if approved is not None:
                when = approved - timedelta(hours=1)
        event.occurred_at = when
        event.recorded_at = when
        touched.add(event.job_id)
    session.flush()
    for job_id in sorted(touched):
        pipeline.rebuild_projection(session, job_id)
