"""CVs de una oferta: guardar el contenido, renderizarlo, verlo y verificarlo.

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
import time
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Document, DocumentRender, Job
from app.schemas.cv import CvContent, CvRenderOptions, CvVerification, PageSize, SectionName
from app.schemas.llm_io import JobExtraction
from app.schemas.profile import CandidateProfile
from app.services import events, extractions
from app.services import profile as profile_service
from app.services.documents import checks, context, layout, options, pdf, photo, templates
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


class CvFitCheck(BaseModel):
    """Cómo quedaría un CV, sin guardar nada: para ajustarlo antes de que exista la versión."""

    job_id: int
    fits: bool  # cabe en `max_pages`
    pages: int
    max_pages: int
    template_id: str
    warnings: list[RenderWarning]  # `too_long` y los de maquetación, con su `fix`


class CvTooLongError(ValueError):
    """El CV no cabe en las páginas pedidas: no se guarda. Nunca se publica una versión así."""

    def __init__(self, pages: int, max_pages: int) -> None:
        self.pages = pages
        self.max_pages = max_pages
        super().__init__(
            f"El CV ocupa {pages} páginas y el máximo es {max_pages}: no se ha guardado y la "
            "versión vigente sigue igual. Recorta contenido (nunca márgenes ni fuente), comprueba "
            "con `check_cv_fit` y vuelve a guardar."
        )


class CvView(BaseModel):
    job_id: int
    document_id: int
    profile_version_id: int
    created_at: datetime
    content: CvContent
    evidence: dict[str, str]  # evidencia citada -> su texto en la versión del perfil del CV
    # Experiencia o proyecto -> «Puesto · Empresa» o su nombre: el contenido solo lleva sus ids.
    labels: dict[str, str] = {}
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


def file_stem(name: str, prefix: str = "CV") -> str:
    """«Lucía Varela Otero» -> «CV-Lucia-Varela-Otero»: sin tildes ni signos, con mayúsculas."""
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    words = re.findall(r"[A-Za-z0-9]+", plain)
    return "-".join([prefix, *words])


def render_dir(job_id: int, document_id: int, render_id: int) -> Path:
    """`data/cvs/<job_id>/<document_id>/<render_id>/`: CVs y cartas (lo que la API puede servir)."""
    return get_settings().data_dir / CVS_DIR / str(job_id) / str(document_id) / str(render_id)


def write_files(
    template: templates.Template,
    ctx: dict[str, Any],
    out_dir: Path,
    stem: str,
    page_size: PageSize,
    photo_file: Path | None,
    file: Path | None = None,
) -> tuple[Path | None, Path, pdf.PdfInfo]:
    """Renderiza con el motor de la plantilla y lee el PDF. Si algo falla, borra `out_dir`."""
    try:
        docx_file, pdf_file = render_files(
            template, ctx, out_dir, stem, page_size, photo_file, file=file
        )
        return docx_file, pdf_file, pdf.read_pdf(pdf_file)
    except BaseException:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise


def store_files(
    session: Session,
    row: DocumentRender,
    docx_file: Path | None,
    pdf_file: Path,
    pages: int,
    warnings: list[RenderWarning],
) -> bool:
    """Guarda rutas, páginas y avisos del render; el primero que cabe queda seleccionado.

    Devuelve si es `too_long`.
    """
    data_dir = get_settings().data_dir
    too_long = is_too_long(warnings)
    already_selected = any(r.selected for r in _renders(session, row.document_id) if r.id != row.id)
    row.docx_path = docx_file.relative_to(data_dir).as_posix() if docx_file else None
    row.pdf_path = pdf_file.relative_to(data_dir).as_posix()
    row.pages = pages
    row.warnings = [w.model_dump(mode="json") for w in warnings]
    # El primer render que cabe queda como el que se enviará; la UI puede cambiarlo (`select`).
    row.selected = not too_long and not already_selected
    session.flush()
    return too_long


def prepared_photo(template: templates.Template, include: bool, source: Path | None) -> Path | None:
    if not include or source is None:
        return None
    return photo.prepared_photo(source, template.meta.photo.shape, template.meta.photo.size_mm)


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


class PreparedFiles(BaseModel):
    """Un render ya convertido en una carpeta temporal, antes de tocar la base."""

    staging: Path
    docx_file: Path | None
    pdf_file: Path
    pages: int
    text: str
    fonts: list[str]
    layout_warnings: list[RenderWarning]


def prepare_files(
    template: templates.Template,
    ctx: dict[str, Any],
    stem: str,
    page_size: PageSize,
    photo_file: Path | None,
    file: Path | None = None,
) -> PreparedFiles:
    """Renderiza y convierte en `data/tmp/renders/<id>/` sin escribir en la base.

    La conversión a PDF tarda segundos: así la base no queda bloqueada mientras tanto. Lanza
    `PdfConverterUnavailableError` si la plantilla es de Word y no hay con qué convertirla."""
    staging = get_settings().tmp_dir / "renders" / uuid.uuid4().hex
    docx_file, pdf_file, info = write_files(
        template, ctx, staging, stem, page_size, photo_file, file=file
    )
    try:
        # Fase 25.5: maquetación del PDF (avisos con su página y cómo arreglarlo; no bloquean).
        layout_warnings = layout.analyze(pdf_file, layout.expected_from_context(ctx))
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return PreparedFiles(
        staging=staging,
        docx_file=docx_file,
        pdf_file=pdf_file,
        pages=info.pages,
        text=info.text,
        fonts=info.fonts,
        layout_warnings=layout_warnings,
    )


def place_files(prepared: PreparedFiles, out_dir: Path) -> tuple[Path | None, Path]:
    """Mueve los ficheros preparados a su carpeta definitiva (misma unidad: es un renombrado)."""
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(out_dir, ignore_errors=True)
    shutil.move(prepared.staging, out_dir)
    docx_file = out_dir / prepared.docx_file.name if prepared.docx_file else None
    return docx_file, out_dir / prepared.pdf_file.name


def discard(prepared: PreparedFiles) -> None:
    shutil.rmtree(prepared.staging, ignore_errors=True)


STALE_RENDER_HOURS = 24


def sweep_stale_renders(now: float | None = None) -> int:
    """Borra los renders a medias de `data/tmp/renders/` con más de un día (la app se cerró entre
    convertir y guardar). Llevan el CV con tus datos: no deben quedarse ahí. Devuelve cuántos."""
    root = get_settings().tmp_dir / "renders"
    if not root.is_dir():
        return 0
    limit = (now if now is not None else time.time()) - STALE_RENDER_HOURS * 3600
    stale = [d for d in root.iterdir() if d.is_dir() and d.stat().st_mtime < limit]
    for folder in stale:
        shutil.rmtree(folder, ignore_errors=True)
    return len(stale)


class _PreparedRender(BaseModel):
    resolved: options.ResolvedOptions
    template_id: str
    template_hash: str
    files: PreparedFiles


def _prepare_render(
    job: Job,
    content: CvContent,
    profile: CandidateProfile,
    extraction: JobExtraction | None,
    render_options: CvRenderOptions,
) -> _PreparedRender:
    """Elige plantilla y opciones, y convierte. Solo lee: nada de escrituras en la base.

    Sin LibreOffice ni Word, una plantilla de Word que nadie eligió a mano se cambia por la HTML
    de reserva (aviso `docx_converter_missing`) en lugar de fallar y perder el CV."""
    offer = options.offer_context(job.url, job.location_raw, extraction, content.language)
    photo_source = photo.find_photo(profile)

    def attempt(resolved: options.ResolvedOptions) -> _PreparedRender:
        template = templates.get(resolved.template_id)
        ctx = context.build_context(
            content, profile, resolved.hidden_sections, resolved.accent_color
        )
        files = prepare_files(
            template,
            ctx,
            file_stem(profile.personal.name),
            resolved.page_size,
            prepared_photo(template, resolved.photo, photo_source),
        )
        return _PreparedRender(
            resolved=resolved,
            template_id=template.id,
            template_hash=template.file_hash(),
            files=files,
        )

    resolved = options.resolve(
        profile, render_options, offer, photo_available=photo_source is not None
    )
    try:
        return attempt(resolved)
    except pdf.PdfConverterUnavailableError:
        if resolved.template_source == "option":
            raise
        fallback = options.resolve(
            profile,
            render_options,
            offer,
            photo_available=photo_source is not None,
            docx_converter=False,
        )
        if fallback.template_id == resolved.template_id:
            raise
        return attempt(fallback)


def _store_render(
    session: Session,
    doc: Document,
    job: Job,
    content: CvContent,
    extraction: JobExtraction | None,
    prepared: _PreparedRender,
    actor: Actor,
    agent_name: str | None,
) -> RenderResult:
    """Guarda en la base un render ya preparado y registra `cv_rendered`."""
    resolved, files = prepared.resolved, prepared.files
    try:
        template = templates.get(prepared.template_id)
        row = DocumentRender(
            document_id=doc.id,
            template_id=prepared.template_id,
            template_hash=prepared.template_hash,
            options=resolved.model_dump(mode="json"),
            pages=0,
            keyword_coverage={},
            warnings=[],
            selected=False,
        )
        session.add(row)
        session.flush()
    except BaseException:
        discard(files)
        raise

    out_dir = render_dir(job.id, doc.id, row.id)
    try:
        docx_file, pdf_file = place_files(files, out_dir)
        warnings = checks.render_warnings(
            content,
            template,
            resolved,
            files.pages,
            pdf.missing_fonts(template.meta.fonts, files.fonts),
        )
        warnings += files.layout_warnings
        coverage = checks.keyword_coverage(files.text, extraction)
        row.keyword_coverage = coverage.model_dump(mode="json")
        too_long = store_files(session, row, docx_file, pdf_file, files.pages, warnings)
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
    except BaseException:
        discard(files)
        shutil.rmtree(out_dir, ignore_errors=True)
        raise
    return _to_result(row, job.id)


def render(
    session: Session,
    document_id: int,
    render_options: CvRenderOptions,
    actor: Actor = Actor.AGENT,
    agent_name: str | None = None,
) -> RenderResult:
    """Renderiza un CV con una plantilla y unas opciones, y registra `cv_rendered`.

    Convierte antes de escribir nada en la base. Si falla, borra los ficheros del render y
    relanza: la fila ya volcada en la sesión desaparece con el rollback de quien la gestiona
    (`session_scope` o la petición de la API). No reutilices la sesión tras un error sin hacer
    rollback.
    """
    doc = _document(session, document_id)
    _require_cv_stage(session, doc.job_id)
    job = _job(session, doc.job_id)
    content = CvContent.model_validate(doc.content)
    profile = profile_service.get_version(session, doc.profile_version_id).profile
    extraction = _extraction(session, job.id)
    prepared = _prepare_render(job, content, profile, extraction, render_options)
    return _store_render(session, doc, job, content, extraction, prepared, actor, agent_name)


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


def render_kind(session: Session, render_id: int) -> str:
    """`cv` o `cover_letter`: de qué documento es un render (la API selecciona con uno u otro)."""
    row = session.get(DocumentRender, render_id)
    doc = session.get(Document, row.document_id) if row is not None else None
    if row is None or doc is None:
        raise RenderNotFoundError(f"No existe el render {render_id}.")
    return doc.kind


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


def render_options_of(session: Session, doc: Document) -> CvRenderOptions:
    """El estilo del render seleccionado (o del último) de un CV, para repetirlo en otra versión.

    Si su plantilla ya no existe, la elige la app."""
    rows = _renders(session, doc.id)
    chosen = next((r for r in rows if r.selected), rows[-1] if rows else None)
    if chosen is None:
        return CvRenderOptions()
    resolved = options.ResolvedOptions.model_validate(chosen.options)
    try:
        template_id: str | None = templates.get(resolved.template_id).id
    except templates.TemplateNotFoundError:
        template_id = None
    return CvRenderOptions(
        template_id=template_id,
        photo="include" if resolved.photo else "exclude",
        accent_color=resolved.accent_color if template_id else None,
        max_pages=resolved.max_pages,
        hidden_sections=resolved.hidden_sections,
        page_size=resolved.page_size,
    )


def item_labels(profile: CandidateProfile) -> dict[str, str]:
    """Cómo se llama cada experiencia y proyecto, para enseñarlos en la UI."""
    labels = {exp.id: f"{exp.role} · {exp.company}" for exp in profile.experience}
    labels.update({prj.id: prj.name for prj in profile.projects})
    return labels


def check_fit(
    session: Session,
    job_id: int,
    content: CvContent,
    render_options: CvRenderOptions | None = None,
) -> CvFitCheck:
    """Prepara el PDF como lo haría `save_content`, lo mide y lo tira: no escribe nada."""
    job = _job(session, job_id)
    _require_cv_stage(session, job_id)
    stored = profile_service.current(session)
    extraction = _extraction(session, job_id)
    checks.validate_content(content, stored.profile, extraction)
    prepared = _prepare_render(
        job, content, stored.profile, extraction, render_options or CvRenderOptions()
    )
    files = prepared.files
    try:
        template = templates.get(prepared.template_id)
        warnings = checks.render_warnings(
            content,
            template,
            prepared.resolved,
            files.pages,
            pdf.missing_fonts(template.meta.fonts, files.fonts),
        )
        warnings += files.layout_warnings
        return CvFitCheck(
            job_id=job_id,
            fits=files.pages <= prepared.resolved.max_pages,
            pages=files.pages,
            max_pages=prepared.resolved.max_pages,
            template_id=prepared.template_id,
            warnings=warnings,
        )
    finally:
        discard(files)


def save_content(
    session: Session,
    job_id: int,
    content: CvContent,
    render_options: CvRenderOptions | None = None,
    agent_name: str | None = None,
    *,
    require_fit: bool = False,
) -> SaveContentResult:
    """Valida y guarda el contenido de un CV y hace su primer render. `require_fit`: si no cabe en
    las páginas, no crea la versión (`CvTooLongError`)."""
    job = _job(session, job_id)
    _require_cv_stage(session, job_id)
    stored = profile_service.current(session)
    extraction = _extraction(session, job_id)
    checks.validate_content(content, stored.profile, extraction)
    # Primero el PDF, sin escribir en la base (la conversión tarda); luego el documento y su render.
    prepared = _prepare_render(
        job, content, stored.profile, extraction, render_options or CvRenderOptions()
    )
    pages, limit = prepared.files.pages, prepared.resolved.max_pages
    if require_fit and pages > limit:
        discard(prepared.files)
        raise CvTooLongError(pages, limit)

    base = latest_document(session, job_id)
    doc = Document(
        job_id=job_id,
        profile_version_id=stored.profile_version_id,
        kind=CV_KIND,
        language=content.language,
        content=content.model_dump(mode="json"),
        base_document_id=base.id if base else None,
    )
    try:
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
    except BaseException:
        discard(prepared.files)
        raise
    result = _store_render(
        session, doc, job, content, extraction, prepared, Actor.AGENT, agent_name
    )
    return SaveContentResult(ok=True, job_id=job_id, document_id=doc.id, render=result)


def latest_document(session: Session, job_id: int) -> Document | None:
    """La versión vigente del CV: la última que «Volver» no ha dejado detrás."""
    stmt = (
        select(Document)
        .where(
            Document.job_id == job_id,
            Document.kind == CV_KIND,
            Document.superseded.is_(False),
        )
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
        labels=item_labels(profile),
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
    free: bool = False  # admite cualquier #RRGGBB (`carta-simple`)


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
    editable: bool = False  # es tuya (`data/templates/`): se puede renombrar y eliminar


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
        accent_colors=AccentColors(default=accent.default, choices=accent.choices, free=accent.free)
        if accent
        else None,
        fonts=meta.fonts,
        languages=list(meta.languages),
        has_preview=(template.path / PREVIEW_PNG).is_file(),
        from_user_cv=meta.origin == "user"
        and meta.source_file is not None
        and (template.path / meta.source_file).is_file(),
        has_source_preview=(template.path / SOURCE_PNG).is_file(),
        editable=template.path.resolve().parent == get_settings().user_templates_dir.resolve(),
    )


def list_cv_templates() -> TemplateList:
    from app.core.policies import get_policies

    found, invalid = templates.list_templates()
    return TemplateList(
        templates=[template_info(t) for t in found],
        invalid=invalid,
        fallback_template=get_policies().cv.fallback_template,
    )
