"""Respuestas de screening y paquete de candidatura (fase 10.3).

- `save_application_answers`: valida las `ApplicationAnswers` del agente, las guarda como
  `document` de `kind = answers` y registra `application_prepared` (actor `agent`).
- `save_user_answers`: la edición desde la UI. Crea un documento nuevo con `edited_by_user` y
  registra `application_prepared` con actor `user`; el anterior se conserva.
- `get_package`: lo que hace falta para enviar a mano: el CV elegido, las últimas respuestas y la
  carta vigente con su render seleccionado (fase 08c).

Solo en ofertas `approved` o `cv_ready`: después del envío el paquete se ve, pero no cambia.

Límite conocido: el código comprueba que las evidencias existen, no que la respuesta diga lo
mismo. Que el salario vaya siempre con `needs_user_input` (POLICIES §4) lo impone el skill
`preparar-candidatura`; aquí no se adivina qué pregunta es salarial.
"""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, Document, DocumentRender, Job
from app.schemas.cover_letter import CoverLetterContent
from app.schemas.llm_io import (
    EVIDENCE_EXTRACTION,
    EVIDENCE_USER,
    ApplicationAnswers,
    ScreeningAnswer,
)
from app.schemas.profile import CandidateProfile
from app.services import events, extractions
from app.services import profile as profile_service
from app.services.documents import cover_letter
from app.services.documents.checks import ContentIssue, citable_refs
from app.services.documents.service import selected_render_id
from app.services.pipeline import CV_STAGES, Actor, EventType, InvalidTransitionError, Stage

ANSWERS_KIND = "answers"
DEFAULT_LANGUAGE = "es"

EVIDENCE_LABELS = {
    EVIDENCE_EXTRACTION: "La oferta (su extracción)",
    EVIDENCE_USER: "Lo que contó el usuario",
}


class AnswersContentError(ValueError):
    """Las respuestas incumplen las reglas; `issues` dice dónde y por qué, para corregir."""

    def __init__(self, issues: list[ContentIssue]) -> None:
        self.issues = issues
        count = len(issues)
        noun = "problema" if count == 1 else "problemas"
        super().__init__(
            f"Las respuestas no son válidas ({count} {noun}): "
            + ", ".join(i.field for i in issues)
            + "."
        )


# --- Salidas --------------------------------------------------------------------------------


class SaveAnswersResult(BaseModel):
    ok: bool
    job_id: int
    document_id: int
    needs_user_input: int  # respuestas que esperan un dato del usuario


class AnswersView(BaseModel):
    document_id: int
    profile_version_id: int
    language: str
    edited_by_user: bool
    created_at: datetime
    answers: list[ScreeningAnswer]
    evidence: dict[str, str]  # evidencia citada -> su texto (en la versión del perfil usada)


class PackageCv(BaseModel):
    render_id: int
    document_id: int
    template_id: str
    pages: int
    pdf_url: str  # ruta de la API: `/renders/{id}/pdf`
    sent: bool  # es el render que se anotó al enviar
    verified: bool  # su documento pasó la verificación


class PackageCoverLetter(BaseModel):
    """La carta vigente para copiarla o adjuntarla (fase 08c)."""

    document_id: int
    text: str  # texto plano para pegar en el formulario
    word_count: int
    edited_by_user: bool
    verified: bool
    render_id: int | None  # el render seleccionado
    pdf_url: str | None  # ruta de la API: `/renders/{id}/pdf`


class JobPackage(BaseModel):
    job_id: int
    stage: Stage
    can_edit: bool  # las respuestas solo cambian en «approved» y «cv_ready»
    cv: PackageCv | None
    answers: AnswersView | None
    cover_letter: PackageCoverLetter | None  # la carta vigente con su render seleccionado


# --- Validación -----------------------------------------------------------------------------


def _profile_refs(profile: CandidateProfile) -> dict[str, str]:
    return citable_refs(profile)


def _validate(
    answers: ApplicationAnswers, refs: dict[str, str], require_evidence: bool
) -> list[ContentIssue]:
    issues: list[ContentIssue] = []
    for i, item in enumerate(answers.answers):
        field = f"answers[{i}]"
        if not item.answer.strip():
            if not item.needs_user_input:
                issues.append(
                    ContentIssue(
                        field=f"{field}.answer",
                        received="",
                        reason="Una respuesta vacía solo vale con `needs_user_input: true`.",
                    )
                )
        elif require_evidence and not item.evidence:
            issues.append(
                ContentIssue(
                    field=f"{field}.evidence",
                    received="[]",
                    reason="Una respuesta necesita al menos una evidencia (id del perfil, "
                    "`extraction` o `user`).",
                )
            )
        for k, ref in enumerate(item.evidence):
            if ref not in refs and ref not in EVIDENCE_LABELS:
                issues.append(
                    ContentIssue(
                        field=f"{field}.evidence[{k}]",
                        received=ref,
                        reason="La evidencia no existe en el perfil (p. ej. `exp-acme/a2` o el id "
                        "de una historia); valen también `extraction` y `user`.",
                    )
                )
    return issues


def _resolve(answers: list[ScreeningAnswer], refs: dict[str, str]) -> dict[str, str]:
    cited = dict.fromkeys(ref for item in answers for ref in item.evidence)
    return {
        ref: EVIDENCE_LABELS.get(ref) or refs.get(ref, "(no existe en el perfil)") for ref in cited
    }


# --- Utilidades -----------------------------------------------------------------------------


def _require_stage(session: Session, job_id: int) -> None:
    if session.get(Job, job_id) is None:
        raise events.JobNotFoundError(f"No existe la oferta {job_id}.")
    stage = events.current_stage(session, job_id)
    if stage not in CV_STAGES:
        raise InvalidTransitionError(
            f"La oferta {job_id} está en «{stage}»: las respuestas solo se preparan en ofertas "
            "aprobadas («approved» o «cv_ready»)."
        )


def _language(session: Session, job_id: int) -> str:
    try:
        language = extractions.get_extraction(session, job_id).extraction.posting_language
    except extractions.ExtractionNotFoundError:
        return DEFAULT_LANGUAGE
    language = language.lower()[:2]
    return language if language in {"es", "en"} else DEFAULT_LANGUAGE


def latest_answers(session: Session, job_id: int) -> Document | None:
    stmt = (
        select(Document)
        .where(Document.job_id == job_id, Document.kind == ANSWERS_KIND)
        .order_by(Document.id.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def _store(
    session: Session,
    job_id: int,
    answers: ApplicationAnswers,
    profile_version_id: int,
    actor: Actor,
    agent_name: str | None,
) -> SaveAnswersResult:
    edited = actor == Actor.USER
    doc = Document(
        job_id=job_id,
        profile_version_id=profile_version_id,
        kind=ANSWERS_KIND,
        language=_language(session, job_id),
        content=answers.model_dump(mode="json"),
        edited_by_user=edited,
    )
    session.add(doc)
    session.flush()
    events.record(
        session,
        job_id,
        EventType.APPLICATION_PREPARED,
        actor,
        payload={"document_id": doc.id, "edited_by_user": edited},
        agent_name=agent_name,
    )
    return SaveAnswersResult(
        ok=True,
        job_id=job_id,
        document_id=doc.id,
        needs_user_input=sum(1 for a in answers.answers if a.needs_user_input),
    )


# --- Operaciones ----------------------------------------------------------------------------


def save_application_answers(
    session: Session, job_id: int, answers: ApplicationAnswers, agent_name: str | None = None
) -> SaveAnswersResult:
    """Guarda las respuestas del agente con la versión vigente del perfil."""
    _require_stage(session, job_id)
    stored = profile_service.current(session)
    issues = _validate(answers, _profile_refs(stored.profile), require_evidence=True)
    if issues:
        raise AnswersContentError(issues)
    return _store(session, job_id, answers, stored.profile_version_id, Actor.AGENT, agent_name)


def save_user_answers(
    session: Session, job_id: int, answers: ApplicationAnswers
) -> SaveAnswersResult:
    """La edición del usuario: no exige evidencias (manda él), pero las que haya deben existir.

    Se valida contra la versión del perfil de las respuestas anteriores, que es la que citan.
    """
    _require_stage(session, job_id)
    previous = latest_answers(session, job_id)
    if previous is not None:
        version_id = previous.profile_version_id
        profile = profile_service.get_version(session, version_id).profile
    else:
        stored = profile_service.current(session)
        version_id, profile = stored.profile_version_id, stored.profile
    issues = _validate(answers, _profile_refs(profile), require_evidence=False)
    if issues:
        raise AnswersContentError(issues)
    return _store(session, job_id, answers, version_id, Actor.USER, None)


def _answers_view(session: Session, doc: Document) -> AnswersView:
    answers = ApplicationAnswers.model_validate(doc.content).answers
    profile = profile_service.get_version(session, doc.profile_version_id).profile
    return AnswersView(
        document_id=doc.id,
        profile_version_id=doc.profile_version_id,
        language=doc.language,
        edited_by_user=doc.edited_by_user,
        created_at=doc.created_at,
        answers=answers,
        evidence=_resolve(answers, _profile_refs(profile)),
    )


def _package_cv(session: Session, job_id: int) -> PackageCv | None:
    application = session.get(Application, job_id)
    sent_id = application.render_id if application else None
    render_id = sent_id or selected_render_id(session, job_id)
    if render_id is None:
        return None
    row = session.get(DocumentRender, render_id)
    if row is None:
        return None
    doc = session.get(Document, row.document_id)
    return PackageCv(
        render_id=row.id,
        document_id=row.document_id,
        template_id=row.template_id,
        pages=row.pages,
        pdf_url=f"/renders/{row.id}/pdf",
        sent=sent_id is not None,
        verified=bool(doc and doc.verification and doc.verification.get("passed")),
    )


def _package_letter(session: Session, job_id: int) -> PackageCoverLetter | None:
    found = cover_letter.selected_letter(session, job_id)
    if found is None:
        return None
    doc, render = found
    content = CoverLetterContent.model_validate(doc.content["letter"])
    return PackageCoverLetter(
        document_id=doc.id,
        text=cover_letter.plain_text(session, doc.id),
        word_count=cover_letter.word_count(content),
        edited_by_user=doc.edited_by_user,
        verified=bool(doc.verification and doc.verification.get("passed")),
        render_id=render.id if render else None,
        pdf_url=f"/renders/{render.id}/pdf" if render else None,
    )


def get_package(session: Session, job_id: int) -> JobPackage:
    if session.get(Job, job_id) is None:
        raise events.JobNotFoundError(f"No existe la oferta {job_id}.")
    stage = events.current_stage(session, job_id)
    doc = latest_answers(session, job_id)
    return JobPackage(
        job_id=job_id,
        stage=stage,
        can_edit=stage in CV_STAGES,
        cv=_package_cv(session, job_id),
        answers=_answers_view(session, doc) if doc else None,
        cover_letter=_package_letter(session, job_id),
    )
