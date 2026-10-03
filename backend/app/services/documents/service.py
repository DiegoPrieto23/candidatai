"""CVs de una oferta: guardar el contenido, renderizarlo, verlo y verificarlo (ADR-014).

- `save_content`: valida el `CvContent` del agente, lo guarda (`document`) y hace el primer render.
- `render`: combina un documento con una plantilla y unas opciones; crea un `document_render` sin
  tocar el documento ni necesitar al agente.
- `get_content`: el contenido con sus evidencias resueltas y sus renders (para el verificador).
- `save_verification`: guarda el veredicto del verificador. La oferta pasa a `cv_ready` cuando un
  mismo documento está verificado y tiene un render que cabe (`services/pipeline.py`).

Los ficheros van en `data/cvs/<job_id>/<document_id>/<render_id>/` y en la BD se guardan relativos a
`data/`. Si el render falla, se borran sus ficheros y la transacción no deja nada a medias.
"""

import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Document, DocumentRender, Job
from app.schemas.cv import CvContent, CvRenderOptions, CvVerification, SectionName
from app.schemas.llm_io import JobExtraction
from app.services import events, extractions
from app.services import profile as profile_service
from app.services.documents import checks, context, options, pdf, photo, templates
from app.services.documents.engines import render_files
from app.services.documents.options import RenderWarning
from app.services.pipeline import CV_STAGES, Actor, EventType, InvalidTransitionError, Stage

CV_KIND = "cv"
CVS_DIR = "cvs"  # data/cvs/<job_id>/<document_id>/<render_id>/
PREVIEW_PNG = "preview.png"
SOURCE_PNG = "source.png"  # primera página del original importado (la crea `build-docx`)


class DocumentNotFoundError(LookupError):
    pass


class RenderNotFoundError(LookupError):
    pass


class FileNotAvailableError(LookupError):
    """El fichero no existe o su ruta queda fuera de las carpetas que se pueden servir."""


# --- Salidas --------------------------------------------------------------------------------


class RenderResult(BaseModel):
    render_id: int
    job_id: int
    document_id: int
    template_id: str
    template_hash: str
    options: options.ResolvedOptions
    docx_path: str | None
    pdf_path: str
    pages: int
    max_pages: int
    keyword_coverage: checks.KeywordCoverage
    warnings: list[RenderWarning]
    selected: bool
    # La plantilla cambió (o ya no existe) desde este render: volver a renderizar daría otro CV.
    template_changed: bool = False
    created_at: datetime


class SaveContentResult(BaseModel):
    ok: bool
    job_id: int
    document_id: int
    render: RenderResult


class CvView(BaseModel):
    job_id: int
    document_id: int
    profile_version_id: int
    created_at: datetime
    content: CvContent
    evidence: dict[str, str]  # evidencia citada -> su texto en la versión del perfil del CV
    verification: CvVerification | None
    renders: list[RenderResult]


class SaveVerificationResult(BaseModel):
    ok: bool
    job_id: int
    document_id: int
    passed: bool
    stage: Stage
    note: str | None = None  # por qué no pasa a `cv_ready`, si no pasa


# --- Utilidades -----------------------------------------------------------------------------


def _job(session: Session, job_id: int) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise events.JobNotFoundError(f"No existe la oferta {job_id}.")
    return job


def _document(session: Session, document_id: int) -> Document:
    doc = session.get(Document, document_id)
    if doc is None or doc.kind != CV_KIND:
        raise DocumentNotFoundError(f"No existe el CV {document_id}.")
    return doc


def _require_cv_stage(session: Session, job_id: int) -> None:
    stage = events.current_stage(session, job_id)
    if stage not in CV_STAGES:
        raise InvalidTransitionError(
            f"La oferta {job_id} está en «{stage}»: solo se generan CVs de ofertas aprobadas "
            "(«approved» o «cv_ready»)."
        )


def _extraction(session: Session, job_id: int) -> JobExtraction | None:
    try:
        return extractions.get_extraction(session, job_id).extraction
    except extractions.ExtractionNotFoundError:
        return None


def _file_stem(name: str) -> str:
    """«Lucía Varela Otero» -> «CV-Lucia-Varela-Otero»: sin tildes ni signos, con mayúsculas."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    words = re.findall(r"[A-Za-z0-9]+", plain)
    return "-".join(["CV", *words])


class _TemplateHashes:
    """Hash actual de cada plantilla, calculado una vez por consulta."""

    def __init__(self) -> None:
        self._hashes: dict[str, str | None] = {}

    def changed(self, template_id: str, rendered_hash: str) -> bool:
        if template_id not in self._hashes:
            try:
                self._hashes[template_id] = templates.get(template_id).file_hash()
            except templates.TemplateNotFoundError:
                self._hashes[template_id] = None
        return self._hashes[template_id] != rendered_hash


def _to_result(
    row: DocumentRender, job_id: int, hashes: _TemplateHashes | None = None
) -> RenderResult:
    resolved = options.ResolvedOptions.model_validate(row.options)
    return RenderResult(
        render_id=row.id,
        job_id=job_id,
        document_id=row.document_id,
        template_id=row.template_id,
        template_hash=row.template_hash,
        options=resolved,
        docx_path=row.docx_path,
        pdf_path=row.pdf_path or "",
        pages=row.pages,
        max_pages=resolved.max_pages,
        keyword_coverage=checks.KeywordCoverage.model_validate(row.keyword_coverage),
        warnings=[RenderWarning.model_validate(w) for w in row.warnings],
        selected=row.selected,
        template_changed=hashes.changed(row.template_id, row.template_hash) if hashes else False,
        created_at=row.created_at,
    )


def _renders(session: Session, document_id: int) -> list[DocumentRender]:
    stmt = (
        select(DocumentRender)
        .where(DocumentRender.document_id == document_id)
        .order_by(DocumentRender.id)
    )
    return list(session.scalars(stmt))


def is_too_long(warnings: list[RenderWarning] | list[dict[str, Any]]) -> bool:
    return any(
        (w.code if isinstance(w, RenderWarning) else w.get("code")) == "too_long" for w in warnings
    )


# --- Render ---------------------------------------------------------------------------------


def render(
    session: Session,
    document_id: int,
    render_options: CvRenderOptions,
    actor: Actor = Actor.AGENT,
    agent_name: str | None = None,
) -> RenderResult:
    """Renderiza un CV con una plantilla y unas opciones, y registra `cv_rendered`.

    Si falla, borra los ficheros del render y relanza: la fila ya volcada en la sesión
    desaparece con el rollback de quien la gestiona (`session_scope` o la petición de la API).
    No reutilices la sesión tras un error sin hacer rollback.
    """
    doc = _document(session, document_id)
    _require_cv_stage(session, doc.job_id)
    job = _job(session, doc.job_id)
    content = CvContent.model_validate(doc.content)
    profile = profile_service.get_version(session, doc.profile_version_id).profile
    extraction = _extraction(session, job.id)

    offer = options.offer_context(job.url, job.location_raw, extraction, content.language)
    photo_source = photo.find_photo(profile)
    resolved = options.resolve(
        profile, render_options, offer, photo_available=photo_source is not None
    )
    template = templates.get(resolved.template_id)

    row = DocumentRender(
        document_id=doc.id,
        template_id=template.id,
        template_hash=template.file_hash(),
        options=resolved.model_dump(mode="json"),
        pages=0,
        keyword_coverage={},
        warnings=[],
        selected=False,
    )
    session.add(row)
    session.flush()

    data_dir = get_settings().data_dir
    render_dir = data_dir / CVS_DIR / str(job.id) / str(doc.id) / str(row.id)
    filename = _file_stem(profile.personal.name)
    try:
        ctx = context.build_context(
            content, profile, resolved.hidden_sections, resolved.accent_color
        )
        photo_file = None
        if resolved.photo and photo_source is not None:
            meta_photo = template.meta.photo
            photo_file = photo.prepared_photo(photo_source, meta_photo.shape, meta_photo.size_mm)
        docx_file, pdf_file = render_files(
            template, ctx, render_dir, filename, resolved.page_size, photo_file
        )
        info = pdf.read_pdf(pdf_file)
    except BaseException:
        shutil.rmtree(render_dir, ignore_errors=True)
        raise

    warnings = checks.render_warnings(
        content, template, resolved, info.pages, pdf.missing_fonts(template.meta.fonts, info.fonts)
    )
    too_long = is_too_long(warnings)
    already_selected = any(r.selected for r in _renders(session, doc.id) if r.id != row.id)

    row.docx_path = docx_file.relative_to(data_dir).as_posix() if docx_file else None
    row.pdf_path = pdf_file.relative_to(data_dir).as_posix()
    row.pages = info.pages
    row.keyword_coverage = checks.keyword_coverage(info.text, extraction).model_dump(mode="json")
    row.warnings = [w.model_dump(mode="json") for w in warnings]
    # El primer render que cabe queda como el que se enviará; la UI puede cambiarlo (`select`).
    row.selected = not too_long and not already_selected
    session.flush()

    events.record(
        session,
        job.id,
        EventType.CV_RENDERED,
        actor,
        payload={
            "document_id": doc.id,
            "render_id": row.id,
            "template_id": template.id,
            "too_long": too_long,
        },
        agent_name=agent_name,
    )
    return _to_result(row, job.id)


def select_render(session: Session, render_id: int) -> RenderResult:
    """Marca el render que se enviará: como mucho uno `selected` por documento.

    No cambia la etapa de la oferta, así que no registra ningún evento.
    """
    row = session.get(DocumentRender, render_id)
    if row is None:
        raise RenderNotFoundError(f"No existe el render {render_id}.")
    doc = _document(session, row.document_id)
    for other in _renders(session, doc.id):
        other.selected = other.id == row.id
    session.flush()
    return _to_result(row, doc.job_id, _TemplateHashes())


def get_render(session: Session, render_id: int) -> RenderResult:
    row = session.get(DocumentRender, render_id)
    if row is None:
        raise RenderNotFoundError(f"No existe el render {render_id}.")
    return _to_result(row, _document(session, row.document_id).job_id)


class JobCv(BaseModel):
    """La sección «CV» de la ficha: el CV vigente de la oferta, si lo tiene."""

    job_id: int
    stage: Stage
    can_render: bool  # solo se renderiza en «approved» y «cv_ready»
    cv: CvView | None


def get_job_cv(session: Session, job_id: int) -> JobCv:
    _job(session, job_id)
    stage = events.current_stage(session, job_id)
    cv = get_content(session, job_id=job_id) if latest_document(session, job_id) else None
    return JobCv(job_id=job_id, stage=stage, can_render=stage in CV_STAGES, cv=cv)


def _inside(root: Path, relative: str) -> Path:
    """`root/relative` si existe y, ya resuelta, sigue dentro de `root`."""
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise FileNotAvailableError("El fichero no existe o no se puede servir.")
    return path


def render_file(session: Session, render_id: int, kind: Literal["pdf", "docx"]) -> Path:
    """Ruta del PDF o del DOCX de un render, siempre dentro de `data/cvs/`.

    Más estrecho que `data/`: ahí también hay secretos (p. ej. el token de captura de la 09b), y una
    ruta guardada en la BD nunca debe poder servirlos.
    """
    row = session.get(DocumentRender, render_id)
    if row is None:
        raise RenderNotFoundError(f"No existe el render {render_id}.")
    relative = row.pdf_path if kind == "pdf" else row.docx_path
    if not relative:
        raise FileNotAvailableError(f"El render {render_id} no tiene {kind.upper()}.")
    data_dir = get_settings().data_dir
    path = _inside(data_dir, relative)
    if not path.is_relative_to((data_dir / CVS_DIR).resolve()):
        raise FileNotAvailableError("El fichero no existe o no se puede servir.")
    return path


def template_preview(template_id: str) -> Path:
    """`preview.png` de una plantilla, dentro de `templates/` o de `data/templates/`."""
    template = templates.get(template_id)
    for root in (templates.BUILTIN_TEMPLATES_DIR, get_settings().user_templates_dir):
        if template.path.resolve().is_relative_to(root.resolve()):
            return _inside(root, f"{template.id}/{PREVIEW_PNG}")
    raise FileNotAvailableError("La plantilla no está en una carpeta de plantillas.")


# --- Contenido ------------------------------------------------------------------------------


def save_content(
    session: Session,
    job_id: int,
    content: CvContent,
    render_options: CvRenderOptions | None = None,
    agent_name: str | None = None,
) -> SaveContentResult:
    """Valida y guarda el contenido de un CV y hace su primer render."""
    _job(session, job_id)
    _require_cv_stage(session, job_id)
    stored = profile_service.current(session)
    checks.validate_content(content, stored.profile, _extraction(session, job_id))

    doc = Document(
        job_id=job_id,
        profile_version_id=stored.profile_version_id,
        kind=CV_KIND,
        language=content.language,
        content=content.model_dump(mode="json"),
    )
    session.add(doc)
    session.flush()
    events.record(
        session,
        job_id,
        EventType.CV_GENERATED,
        Actor.AGENT,
        payload={"document_id": doc.id},
        agent_name=agent_name,
    )
    result = render(session, doc.id, render_options or CvRenderOptions(), Actor.AGENT, agent_name)
    return SaveContentResult(ok=True, job_id=job_id, document_id=doc.id, render=result)


def latest_document(session: Session, job_id: int) -> Document | None:
    stmt = (
        select(Document)
        .where(Document.job_id == job_id, Document.kind == CV_KIND)
        .order_by(Document.id.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def selected_render_id(session: Session, job_id: int) -> int | None:
    """Render seleccionado («Usar este para enviar») del último CV de la oferta, si lo hay."""
    doc = latest_document(session, job_id)
    if doc is None:
        return None
    stmt = select(DocumentRender.id).where(
        DocumentRender.document_id == doc.id, DocumentRender.selected.is_(True)
    )
    return session.scalars(stmt).first()


def get_content(
    session: Session, job_id: int | None = None, document_id: int | None = None
) -> CvView:
    """Un CV (por su id, o el último de la oferta) con sus evidencias resueltas y sus renders."""
    if (job_id is None) == (document_id is None):
        raise ValueError("Indica `job_id` o `document_id`, uno de los dos.")
    if document_id is not None:
        doc = _document(session, document_id)
    else:
        assert job_id is not None
        _job(session, job_id)
        found = latest_document(session, job_id)
        if found is None:
            raise DocumentNotFoundError(f"La oferta {job_id} aún no tiene CV.")
        doc = found

    content = CvContent.model_validate(doc.content)
    profile = profile_service.get_version(session, doc.profile_version_id).profile
    refs = profile.evidence_refs()
    hashes = _TemplateHashes()
    cited = [
        ref
        for item in [*content.experience, *content.projects]
        for bullet in item.bullets
        for ref in bullet.evidence
    ]
    return CvView(
        job_id=doc.job_id,
        document_id=doc.id,
        profile_version_id=doc.profile_version_id,
        created_at=doc.created_at,
        content=content,
        evidence={ref: refs.get(ref, "(no existe en el perfil)") for ref in dict.fromkeys(cited)},
        verification=CvVerification.model_validate(doc.verification) if doc.verification else None,
        renders=[_to_result(r, doc.job_id, hashes) for r in _renders(session, doc.id)],
    )


def save_verification(
    session: Session,
    document_id: int,
    verification: CvVerification,
    agent_name: str | None = None,
) -> SaveVerificationResult:
    """Guarda la verificación y registra `cv_verified` (si pasa) o `cv_rejected`."""
    doc = _document(session, document_id)
    _require_cv_stage(session, doc.job_id)
    doc.verification = verification.model_dump(mode="json")
    if verification.passed:
        event_type, payload = EventType.CV_VERIFIED, {"document_id": doc.id, "passed": True}
    else:
        blockers = sum(1 for i in verification.issues if i.severity == "blocker")
        event_type, payload = EventType.CV_REJECTED, {"document_id": doc.id, "blockers": blockers}
    events.record(session, doc.job_id, event_type, Actor.AGENT, payload, agent_name=agent_name)
    stage = events.current_stage(session, doc.job_id)

    note = None
    if verification.passed and stage != Stage.CV_READY:
        note = (
            "Verificado, pero ningún render de este CV cabe en sus páginas: recorta el contenido "
            "o renderiza con otras opciones para pasar a «cv_ready»."
        )
    return SaveVerificationResult(
        ok=True,
        job_id=doc.job_id,
        document_id=doc.id,
        passed=verification.passed,
        stage=stage,
        note=note,
    )


# --- Plantillas -----------------------------------------------------------------------------


class AccentColors(BaseModel):
    default: str
    choices: list[str]


class TemplateInfo(BaseModel):
    """Lo que el agente y la UI necesitan de una plantilla para elegirla y ajustar la extensión."""

    id: str
    name: str
    engine: str
    origin: str
    description: str
    tags: list[str]
    ats_friendly: bool
    photo_supported: bool
    photo_shape: str
    columns: int
    page_size: str
    max_pages: int
    capacity: dict[str, int]
    sections: list[SectionName]
    accent_colors: AccentColors | None
    fonts: list[str]
    languages: list[str]
    has_preview: bool  # hay `preview.png` para la galería
    from_user_cv: bool  # creada desde un CV propio (tiene su original): etiqueta «Tu CV»
    has_source_preview: bool  # hay `source.png` (primera página del original)


class TemplateList(BaseModel):
    templates: list[TemplateInfo]
    invalid: list[templates.InvalidTemplate]
    fallback_template: str


def template_info(template: templates.Template) -> TemplateInfo:
    meta = template.meta
    accent = meta.options.accent_color
    return TemplateInfo(
        id=meta.id,
        name=meta.name,
        engine=meta.engine,
        origin=meta.origin,
        description=meta.description,
        tags=meta.tags,
        ats_friendly=meta.ats_friendly,
        photo_supported=meta.photo.supported,
        photo_shape=meta.photo.shape,
        columns=meta.layout.columns,
        page_size=meta.page.size,
        max_pages=meta.page.max_pages,
        capacity=meta.capacity.model_dump(),
        sections=list(meta.sections),
        accent_colors=AccentColors(default=accent.default, choices=accent.choices)
        if accent
        else None,
        fonts=meta.fonts,
        languages=list(meta.languages),
        has_preview=(template.path / PREVIEW_PNG).is_file(),
        from_user_cv=meta.origin == "user"
        and meta.source_file is not None
        and (template.path / meta.source_file).is_file(),
        has_source_preview=(template.path / SOURCE_PNG).is_file(),
    )


def list_cv_templates() -> TemplateList:
    from app.core.policies import get_policies

    found, invalid = templates.list_templates()
    return TemplateList(
        templates=[template_info(t) for t in found],
        invalid=invalid,
        fallback_template=get_policies().cv.fallback_template,
    )
