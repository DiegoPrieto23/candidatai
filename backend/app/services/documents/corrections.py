"""Corregir un CV ya generado: lo que el usuario pide cambiar, cómo lo aplica el agente y las
versiones que van quedando.

- `request_correction`: el texto del usuario se guarda aquí. La orden al agente solo lleva el
  `job_id`; el skill `correct-cv` lee el texto con `get_cv_correction` y lo trata como dato. Hay una
  pendiente por oferta como mucho: pedir otra antes de que se atienda la sustituye.
- Leerla anota qué versión tenía delante el agente: si el CV cambia mientras trabaja, o el usuario
  pide otra cosa, su versión se rechaza en lugar de pisar lo nuevo.
- `save_corrected`: la versión nueva del agente, con el estilo de la vigente salvo que pida otro.
  Si no cabe en las páginas, no se crea: en la ficha nunca aparece una corrección a medias. Las
  páginas que pide el texto del usuario («que ocupe 1 página») mandan sobre lo que pase el agente:
  es lo que se le ha pedido y no depende de que lo interprete bien.
- `check_fit`: lo mismo sin guardar, para que el agente ajuste el texto antes.
- `save_user_edit`: la edición directa del usuario, sin agente. Solo cambia textos; lo que el perfil
  no respalde se avisa pero se guarda, porque lo decide quien lo escribe.
- `restore_version`: «Volver». No borra ni renderiza: cambia cuál es la vigente.
"""

import re
from collections.abc import Iterable
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import AgentRequest, CvCorrection, Document
from app.models.base import utcnow
from app.schemas.cv import CvContent, CvRenderOptions
from app.schemas.llm_io import JobExtraction
from app.schemas.profile import CandidateProfile
from app.services import events
from app.services import profile as profile_service
from app.services.documents import checks, cv_diff, service
from app.services.pipeline import Actor, EventType

MAX_INSTRUCTION = 2000
MAX_NOTE = 2000
CORRECT_ACTION = "correct-cv"

CorrectionStatus = Literal["pending", "applied", "declined", "cancelled"]
Instruction = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_INSTRUCTION)
]


class CorrectionNotFoundError(LookupError):
    pass


class CorrectionClosedError(ValueError):
    pass


class CvVersionConflictError(ValueError):
    """La versión editada ya no es la vigente: guardar pisaría lo que ha cambiado mientras."""


class CvEditNotAllowedError(ValueError):
    """La edición directa solo cambia textos; añadir, quitar o reordenar va por una corrección."""


class CorrectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: Instruction


class CorrectionView(BaseModel):
    id: int
    job_id: int
    instruction: str
    status: CorrectionStatus
    note: str | None
    created_at: datetime
    closed_at: datetime | None


class PendingCorrection(BaseModel):
    """Lo que `correct-cv` tiene que hacer: la versión vigente y lo que pide el usuario."""

    job_id: int
    document_id: int | None
    correction: CorrectionView | None
    # Páginas que pide su texto («que ocupe 1 página»), si las pide: la app las exige al guardar.
    max_pages: int | None = None
    current_pages: int | None = None  # las que ocupa ahora la versión vigente


class DeclineResult(BaseModel):
    ok: bool = True
    correction_id: int
    job_id: int
    status: CorrectionStatus


class CvVersion(BaseModel):
    document_id: int
    created_at: datetime
    current: bool
    origin: Literal["generated", "correction", "edit"]
    instruction: str | None  # la corrección que la originó
    note: str | None
    verified: bool | None  # `None`: sin verificar
    render: service.RenderResult | None  # el seleccionado o, si no hay, el último
    changes: list[cv_diff.SectionChange]  # frente a la versión de la que sale


class CvHistory(BaseModel):
    job_id: int
    versions: list[CvVersion]  # la más nueva primero
    correction: CorrectionView | None  # la pendiente o, si no hay, la última


class CvEditInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_document_id: int = Field(ge=1)
    content: CvContent


class EditWarning(BaseModel):
    code: Literal["skill", "number"]
    field: str
    value: str


class EditResult(BaseModel):
    ok: bool = True
    job_id: int
    document_id: int
    render: service.RenderResult
    warnings: list[EditWarning]


# --- Correcciones ---------------------------------------------------------------------------


def _view(row: CvCorrection) -> CorrectionView:
    return CorrectionView(
        id=row.id,
        job_id=row.job_id,
        instruction=row.instruction,
        status=row.status,
        note=row.note,
        created_at=row.created_at,
        closed_at=row.closed_at,
    )


def pending_row(session: Session, job_id: int) -> CvCorrection | None:
    stmt = select(CvCorrection).where(
        CvCorrection.job_id == job_id, CvCorrection.status == "pending"
    )
    return session.scalars(stmt.order_by(CvCorrection.id.desc())).first()


_NUMBERS = {"una": 1, "un": 1, "one": 1, "dos": 2, "two": 2, "tres": 3, "three": 3}
_PAGES = re.compile(
    r"\b(\d{1,2}|una|un|one|dos|two|tres|three)(?:\s+sola)?[\s-]+(?:p[aá]ginas?|hojas?|pages?)\b",
    re.IGNORECASE,
)
_ONE_PAGER = re.compile(r"\bone[\s-]?pager\b", re.IGNORECASE)


def requested_pages(instruction: str) -> int | None:
    """Las páginas que pide el texto del usuario. Si nombra varias («de 2 hojas a 1 página»), la
    menor: de un CV ya hecho solo se pide acortar. «La página 2» no es una longitud."""
    found = [
        _NUMBERS.get(match.group(1).casefold()) or int(match.group(1))
        for match in _PAGES.finditer(instruction)
    ]
    if _ONE_PAGER.search(instruction):
        found.append(1)
    pages = [n for n in found if n >= 1]
    return min(pages) if pages else None


def _target_options(
    session: Session, row: CvCorrection, current: Document | None, given: CvRenderOptions | None
) -> CvRenderOptions:
    """Con qué se renderiza la versión corregida: lo que pase el agente o, si no, el estilo de la
    vigente. Las páginas que pide el texto del usuario mandan sobre las dos."""
    options = given
    if options is None:
        options = service.render_options_of(session, current) if current else CvRenderOptions()
    pages = requested_pages(row.instruction)
    return options.model_copy(update={"max_pages": pages}) if pages else options


def request_correction(session: Session, job_id: int, data: CorrectionInput) -> CorrectionView:
    """Guarda lo que hay que corregir; si ya había algo pendiente en esta oferta, lo sustituye."""
    service._job(session, job_id)
    service._require_cv_stage(session, job_id)
    if service.latest_document(session, job_id) is None:
        raise service.DocumentNotFoundError(f"La oferta {job_id} aún no tiene CV.")
    row = pending_row(session, job_id)
    if row is not None and row.base_document_id is not None:
        # El agente ya la ha leído: si se reescribiera, daría por aplicado lo que no ha visto.
        _close(row, "cancelled")
        row = None
    if row is None:
        row = CvCorrection(job_id=job_id, status="pending", instruction=data.instruction)
        session.add(row)
    else:
        row.instruction = data.instruction
    session.flush()
    return _view(row)


def get_pending(session: Session, job_id: int) -> PendingCorrection:
    """Lo que lee el agente (la UI usa `get_history`): anota la versión de la que parte."""
    service._job(session, job_id)
    row = pending_row(session, job_id)
    current = service.latest_document(session, job_id)
    if row is not None and current is not None:
        row.base_document_id = current.id
        session.flush()
    renders = service._renders(session, current.id) if current else []
    shown = next((r for r in renders if r.selected), renders[-1] if renders else None)
    return PendingCorrection(
        job_id=job_id,
        document_id=current.id if current else None,
        correction=_view(row) if row else None,
        max_pages=requested_pages(row.instruction) if row else None,
        current_pages=shown.pages if shown else None,
    )


def check_fit(
    session: Session,
    job_id: int,
    correction_id: int,
    content: CvContent,
    render_options: CvRenderOptions | None = None,
) -> service.CvFitCheck:
    """Cómo quedaría esta corrección, con las mismas opciones que usará `save_corrected`."""
    row = _row(session, correction_id)
    if row.job_id != job_id:
        raise CorrectionNotFoundError(f"La corrección {correction_id} no es de la oferta {job_id}.")
    current = service.latest_document(session, job_id)
    options = _target_options(session, row, current, render_options)
    return service.check_fit(session, job_id, content, options)


def _row(session: Session, correction_id: int) -> CvCorrection:
    row = session.get(CvCorrection, correction_id)
    if row is None:
        raise CorrectionNotFoundError(f"No existe la corrección {correction_id}.")
    return row


def _close(row: CvCorrection, status: CorrectionStatus, note: str | None = None) -> None:
    row.status = status
    row.note = note
    row.closed_at = utcnow()


def _require_pending(row: CvCorrection) -> None:
    if row.status != "pending":
        raise CorrectionClosedError(f"La corrección {row.id} ya está cerrada ({row.status}).")


def decline(session: Session, correction_id: int, reason: str) -> DeclineResult:
    """El agente no puede aplicar nada de lo pedido: se queda sin versión nueva, con el motivo."""
    row = _row(session, correction_id)
    _require_pending(row)
    _close(row, "declined", reason.strip()[:MAX_NOTE])
    session.flush()
    return DeclineResult(correction_id=row.id, job_id=row.job_id, status="declined")


def cancel_pending(session: Session, job_id: int) -> None:
    """Sin tocar los encargos: lo usa `agent_requests.cancel`, que ya cancela el suyo."""
    row = pending_row(session, job_id)
    if row is not None:
        _close(row, "cancelled")
        session.flush()


def cancel(session: Session, correction_id: int) -> CorrectionView:
    """Desde la UI: ya no la quieres. Se lleva el encargo que la esperaba, si lo había."""
    row = _row(session, correction_id)
    _require_pending(row)
    _close(row, "cancelled")
    session.execute(
        update(AgentRequest)
        .where(
            AgentRequest.action == CORRECT_ACTION,
            AgentRequest.job_id == row.job_id,
            AgentRequest.status == "pending",
        )
        .values(status="cancelled", completed_at=utcnow())
    )
    session.flush()
    return _view(row)


def save_corrected(
    session: Session,
    job_id: int,
    correction_id: int,
    content: CvContent,
    render_options: CvRenderOptions | None = None,
    note: str | None = None,
    agent_name: str | None = None,
) -> service.SaveContentResult:
    """Guarda la versión corregida. Se puede repetir con la misma corrección si la verificación
    falla: todas sus versiones se comparan con la que había antes de corregir. Si no cabe en las
    páginas no se crea la versión ni se cierra la corrección (`service.CvTooLongError`)."""
    row = _row(session, correction_id)
    if row.job_id != job_id:
        raise CorrectionNotFoundError(f"La corrección {correction_id} no es de la oferta {job_id}.")
    if row.status not in ("pending", "applied"):
        raise CorrectionClosedError(
            f"La corrección {correction_id} está cerrada ({row.status}): vuelve a leer "
            "`get_cv_correction`."
        )
    earlier = session.scalars(
        select(Document).where(Document.correction_id == row.id).order_by(Document.id)
    ).first()
    current = service.latest_document(session, job_id)
    current_id = current.id if current else None
    # Un reintento sale de un intento anterior de esta corrección; la primera vez, de lo leído.
    stale = (
        current is None or current.correction_id != row.id
        if row.status == "applied"
        else row.base_document_id is not None and row.base_document_id != current_id
    )
    if stale:
        raise CvVersionConflictError(
            "El CV ha cambiado mientras trabajabas: vuelve a leerlo con `get_cv_correction` y "
            "`get_cv_content`, y aplica la corrección sobre la versión vigente."
        )
    options = _target_options(session, row, current, render_options)
    result = service.save_content(
        session, job_id, content, options, agent_name=agent_name, require_fit=True
    )
    doc = session.get(Document, result.document_id)
    assert doc is not None
    doc.correction_id = row.id
    if earlier is not None:
        doc.base_document_id = earlier.base_document_id
    _close(row, "applied", note.strip()[:MAX_NOTE] if note and note.strip() else None)
    session.flush()
    return result


# --- Versiones ------------------------------------------------------------------------------


def _documents(session: Session, job_id: int) -> list[Document]:
    stmt = select(Document).where(Document.job_id == job_id, Document.kind == service.CV_KIND)
    return list(session.scalars(stmt.order_by(Document.id)))


def _content(doc: Document) -> CvContent:
    return CvContent.model_validate(doc.content)


def _origin(doc: Document) -> Literal["generated", "correction", "edit"]:
    if doc.edited_by_user:
        return "edit"
    return "correction" if doc.correction_id is not None else "generated"


def get_history(session: Session, job_id: int) -> CvHistory:
    """Todas las versiones del CV de la oferta, con qué cambió cada una, y la última corrección."""
    service._job(session, job_id)
    docs = _documents(session, job_id)
    by_id = {doc.id: doc for doc in docs}
    current = service.latest_document(session, job_id)
    hashes = service._TemplateHashes()
    corrections = {
        row.id: row
        for row in session.scalars(select(CvCorrection).where(CvCorrection.job_id == job_id))
    }
    profiles: dict[int, CandidateProfile] = {}
    versions = []
    for position, doc in enumerate(docs):
        previous = by_id.get(doc.base_document_id) if doc.base_document_id else None
        if previous is None and position > 0:
            previous = docs[position - 1]  # los anteriores a guardar de qué versión salen
        if doc.profile_version_id not in profiles:
            stored = profile_service.get_version(session, doc.profile_version_id)
            profiles[doc.profile_version_id] = stored.profile
        profile = profiles[doc.profile_version_id]
        rows = service._renders(session, doc.id)
        chosen = next((r for r in rows if r.selected), rows[-1] if rows else None)
        correction = corrections.get(doc.correction_id) if doc.correction_id else None
        versions.append(
            CvVersion(
                document_id=doc.id,
                created_at=doc.created_at,
                current=current is not None and doc.id == current.id,
                origin=_origin(doc),
                instruction=correction.instruction if correction else None,
                note=correction.note if correction else None,
                verified=doc.verification.get("passed") if doc.verification else None,
                render=service._to_result(chosen, job_id, hashes) if chosen else None,
                changes=cv_diff.diff(
                    _content(previous), _content(doc), service.item_labels(profile)
                )
                if previous
                else [],
            )
        )
    versions.reverse()
    last = session.scalars(
        select(CvCorrection)
        .where(CvCorrection.job_id == job_id, CvCorrection.status != "cancelled")
        .order_by(CvCorrection.id.desc())
    ).first()
    return CvHistory(job_id=job_id, versions=versions, correction=_view(last) if last else None)


def restore_version(session: Session, document_id: int) -> service.JobCv:
    """Hace vigente una versión anterior. Las más nuevas se conservan y se puede volver a ellas; si
    la versión no tiene render elegido, se elige el último que cabe."""
    doc = service._document(session, document_id)
    service._require_cv_stage(session, doc.job_id)
    for other in _documents(session, doc.job_id):
        other.superseded = other.id > doc.id
    rows = service._renders(session, doc.id)
    if not any(r.selected for r in rows):
        fitting = [r for r in rows if not service.is_too_long(r.warnings)]
        if fitting:
            fitting[-1].selected = True
    session.flush()
    return service.get_job_cv(session, doc.job_id)


# --- Edición directa ------------------------------------------------------------------------


def _shape(content: CvContent) -> dict[str, Any]:
    """El contenido sin sus textos editables: lo que una edición directa no puede tocar."""
    shape = content.model_dump(mode="json", exclude={"subtitle", "summary"})
    for block in (*shape["experience"], *shape["projects"]):
        for bullet in block["bullets"]:
            bullet["text"] = ""
    shape["skills"] = [len(group["items"]) for group in shape["skills"]]
    return shape


def _editable_texts(content: CvContent) -> Iterable[tuple[str, str]]:
    yield "subtitle", content.subtitle
    yield "summary", content.summary
    for i, exp in enumerate(content.experience):
        for b, bullet in enumerate(exp.bullets):
            yield f"experience.{i}.bullets.{b}", bullet.text
    for i, prj in enumerate(content.projects):
        for b, bullet in enumerate(prj.bullets):
            yield f"projects.{i}.bullets.{b}", bullet.text
    for g, group in enumerate(content.skills):
        yield f"skills.{g}.group", group.group
        for s, item in enumerate(group.items):
            yield f"skills.{g}.items.{s}", item


def _check_edit(old: CvContent, new: CvContent) -> None:
    if _shape(old) != _shape(new):
        raise CvEditNotAllowedError(
            "Aquí solo se cambian textos. Para añadir, quitar o reordenar, pide una corrección."
        )
    blank = [field for field, text in _editable_texts(new) if not text.strip()]
    if blank:
        raise CvEditNotAllowedError(f"Hay textos vacíos: {', '.join(blank)}.")
    if old == new:
        raise CvEditNotAllowedError("No hay cambios que guardar.")


_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def _numbers(text: str) -> set[str]:
    return set(_NUMBER.findall(text))


def _edit_warnings(
    old: CvContent, new: CvContent, profile: CandidateProfile, extraction: JobExtraction | None
) -> list[EditWarning]:
    """Lo que el código puede ver sin IA: skills fuera del perfil (o básicas que la oferta no pide)
    y cifras nuevas que no están en el perfil. Si una frase dice lo mismo que su evidencia no lo
    puede saber."""
    warnings: list[EditWarning] = []
    old_skills = {item for group in old.skills for item in group.items}
    try:
        checks.validate_content(new, profile, extraction)
    except checks.CvContentError as exc:
        for issue in exc.issues:
            if issue.field.startswith("skills[") and issue.received not in old_skills:
                field = issue.field.replace("[", ".").replace("]", "")
                warnings.append(EditWarning(code="skill", field=field, value=issue.received or ""))
    known_numbers = _numbers(" ".join(profile.evidence_refs().values()))
    before = dict(_editable_texts(old))
    for field, text in _editable_texts(new):
        if field.startswith("skills.") or text == before.get(field):
            continue
        for number in sorted(_numbers(text) - _numbers(before.get(field, "")) - known_numbers):
            warnings.append(EditWarning(code="number", field=field, value=number))
    return warnings


def save_user_edit(session: Session, job_id: int, data: CvEditInput) -> EditResult:
    """Versión nueva con los textos del usuario, sin verificar y con el mismo estilo."""
    job = service._job(session, job_id)
    service._require_cv_stage(session, job_id)
    current = service.latest_document(session, job_id)
    if current is None:
        raise service.DocumentNotFoundError(f"La oferta {job_id} aún no tiene CV.")
    if current.id != data.base_document_id:
        raise CvVersionConflictError(
            "El CV ha cambiado mientras lo editabas: vuelve a abrirlo para no pisar lo nuevo."
        )
    old = _content(current)
    _check_edit(old, data.content)
    # El mismo perfil de la versión editada: solo cambian los textos que ha escrito el usuario.
    profile = profile_service.get_version(session, current.profile_version_id).profile
    extraction = service._extraction(session, job_id)
    warnings = _edit_warnings(old, data.content, profile, extraction)
    prepared = service._prepare_render(
        job, data.content, profile, extraction, service.render_options_of(session, current)
    )
    doc = Document(
        job_id=job_id,
        profile_version_id=current.profile_version_id,
        kind=service.CV_KIND,
        language=data.content.language,
        content=data.content.model_dump(mode="json"),
        edited_by_user=True,
        base_document_id=current.id,
    )
    try:
        session.add(doc)
        session.flush()
        events.record(
            session,
            job_id,
            EventType.CV_GENERATED,
            Actor.USER,
            payload={"document_id": doc.id, "edited_by_user": True},
        )
    except BaseException:
        service.discard(prepared.files)
        raise
    render = service._store_render(
        session, doc, job, data.content, extraction, prepared, Actor.USER, None
    )
    return EditResult(job_id=job_id, document_id=doc.id, render=render, warnings=warnings)
