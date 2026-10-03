"""Cartas de presentación de una oferta (fase 08c, ADR-018).

- `save_brief`: las indicaciones de la carta para una oferta (las de la UI o las que dicta el
  usuario al agente). Mandan sobre `preferences.cover_letter` del perfil.
- `save_cover_letter`: valida el `CoverLetterContent` del agente, lo guarda (`document` de
  `kind = cover_letter`) con una copia de las indicaciones usadas y hace el primer render.
- `render_cover_letter`: un render nuevo con otras opciones; por defecto, a juego con el render
  seleccionado del CV de la oferta. Sin evento: no cambia nada del proceso.
- `get_cover_letter`, `save_verification`, `plain_text` y `select_render`.

Solo en ofertas `approved` o `cv_ready`. Los ficheros van con los del CV, en
`data/cvs/<job_id>/<document_id>/<render_id>/Carta-<Nombre>.pdf|docx`.
"""

import re
from datetime import date, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.models import CoverLetterBrief, Document, DocumentRender
from app.models.base import utcnow
from app.schemas.cover_letter import (
    EVIDENCE_EXTRACTION,
    EVIDENCE_USER,
    CoverLetterBriefInput,
    CoverLetterContent,
    CoverLetterRenderOptions,
)
from app.schemas.cv import CvContent, CvRenderOptions, CvVerification, PageSize
from app.schemas.llm_io import JobExtraction
from app.schemas.profile import CandidateProfile, CoverLetterPreferences
from app.services import events
from app.services import profile as profile_service
from app.services.documents import checks, context, options, pdf, photo, service, templates
from app.services.documents.checks import ContentIssue
from app.services.documents.options import (
    InvalidRenderOptionsError,
    OfferContext,
    RenderWarning,
    ResolvedOptions,
)
from app.services.matching.skills import alias_index
from app.services.pipeline import Actor, EventType, InvalidTransitionError, Stage

LETTER_KIND = "cover_letter"
FILE_PREFIX = "Carta"
LETTER_MAX_PAGES = 1
_WORD = re.compile(r"\w+")

EVIDENCE_LABELS = {
    EVIDENCE_EXTRACTION: "La oferta (su extracción)",
    EVIDENCE_USER: "Tus indicaciones para la carta",
}


class LetterNotFoundError(LookupError):
    pass


class CoverLetterContentError(ValueError):
    """La carta incumple las reglas; `issues` dice dónde y por qué, para corregir."""

    def __init__(self, issues: list[ContentIssue]) -> None:
        self.issues = issues
        count = len(issues)
        noun = "problema" if count == 1 else "problemas"
        super().__init__(
            f"La carta no es válida ({count} {noun}): " + ", ".join(i.field for i in issues) + "."
        )


# --- Modelos de salida ----------------------------------------------------------------------


class BriefView(BaseModel):
    instructions: str
    max_words: int | None
    updated_at: datetime


class InstructionsUsed(BaseModel):
    """Copia de las indicaciones vigentes al guardar la carta: respaldo de la evidencia `user`."""

    brief: BriefView | None
    # Como dict: si `CoverLetterPreferences` cambia, las cartas antiguas se siguen abriendo.
    preferences: dict[str, Any] | None
    max_words: int

    def has_user_instructions(self) -> bool:
        texts = [
            self.brief.instructions if self.brief else None,
            (self.preferences or {}).get("instructions"),
        ]
        return any(isinstance(t, str) and t.strip() for t in texts)


LetterTemplateSource = Literal["option", "cv", "rule", "default_template", "fallback"]


class LetterResolvedOptions(BaseModel):
    template_id: str  # la plantilla cuyo diseño de carta se usa
    template_source: LetterTemplateSource  # de dónde sale la plantilla base
    base_template_id: str  # la del CV (o la que piden las opciones), antes del respaldo
    cv_render_id: int | None  # render del CV del que se toman plantilla, foto y color
    letter_fallback: bool  # la plantilla base no tiene carta: se usa `carta-simple`
    photo: bool
    accent_color: str | None
    page_size: PageSize
    max_pages: int = LETTER_MAX_PAGES
    offer: OfferContext
    warnings: list[RenderWarning] = []


class LetterRenderResult(BaseModel):
    render_id: int
    job_id: int
    document_id: int
    template_id: str
    template_hash: str
    options: LetterResolvedOptions
    docx_path: str | None
    pdf_path: str
    pages: int
    warnings: list[RenderWarning]
    selected: bool
    created_at: datetime


class CoverLetterView(BaseModel):
    document_id: int
    profile_version_id: int
    created_at: datetime
    edited_by_user: bool
    content: CoverLetterContent
    evidence: dict[str, str]  # evidencia citada -> su texto (perfil de la carta o indicaciones)
    word_count: int
    instructions_used: InstructionsUsed
    verification: CvVerification | None
    renders: list[LetterRenderResult]


class CoverLetterInfo(BaseModel):
    """Lo que devuelve `get_cover_letter`: indicaciones vigentes y la carta, si la hay."""

    job_id: int
    stage: Stage
    brief: BriefView | None
    preferences: CoverLetterPreferences | None
    max_words: int  # límite resuelto ahora: oferta > perfil > políticas
    letter: CoverLetterView | None


class SaveBriefResult(BaseModel):
    ok: bool
    job_id: int
    brief: BriefView
    max_words: int  # límite resuelto con estas indicaciones


class SaveLetterResult(BaseModel):
    ok: bool
    job_id: int
    document_id: int
    word_count: int
    render: LetterRenderResult


class SaveLetterVerificationResult(BaseModel):
    ok: bool
    job_id: int
    document_id: int
    passed: bool


# --- Utilidades -----------------------------------------------------------------------------


def word_count(content: CoverLetterContent) -> int:
    """Palabras del cuerpo (los párrafos), sin saludo ni despedida. La UI muestra la misma cifra."""
    return sum(len(_WORD.findall(p.text)) for p in content.paragraphs)


def _require_stage(session: Session, job_id: int) -> Stage:
    service._job(session, job_id)
    stage = events.current_stage(session, job_id)
    if stage not in {Stage.APPROVED, Stage.CV_READY}:
        raise InvalidTransitionError(
            f"La oferta {job_id} está en «{stage}»: las cartas solo se preparan en ofertas "
            "aprobadas («approved» o «cv_ready»)."
        )
    return stage


def _brief(session: Session, job_id: int) -> BriefView | None:
    row = session.get(CoverLetterBrief, job_id)
    if row is None:
        return None
    return BriefView(
        instructions=row.instructions, max_words=row.max_words, updated_at=row.updated_at
    )


def _preferences(profile: CandidateProfile) -> CoverLetterPreferences | None:
    return profile.preferences.cover_letter


def resolve_max_words(brief: BriefView | None, prefs: CoverLetterPreferences | None) -> int:
    """Límite de palabras: el de la oferta > el del perfil > `cover_letter.max_words` (180)."""
    if brief and brief.max_words:
        return brief.max_words
    if prefs and prefs.max_words:
        return prefs.max_words
    return get_policies().cover_letter.max_words


def _letter_doc(session: Session, document_id: int) -> Document:
    doc = session.get(Document, document_id)
    if doc is None or doc.kind != LETTER_KIND:
        raise LetterNotFoundError(f"No existe la carta {document_id}.")
    return doc


def latest_letter(session: Session, job_id: int) -> Document | None:
    stmt = (
        select(Document)
        .where(Document.job_id == job_id, Document.kind == LETTER_KIND)
        .order_by(Document.id.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def _content(doc: Document) -> CoverLetterContent:
    return CoverLetterContent.model_validate(doc.content["letter"])


def _instructions(doc: Document) -> InstructionsUsed:
    return InstructionsUsed.model_validate(doc.content["instructions"])


def _today() -> date:
    """Hoy en la zona de la app (Europe/Madrid): la fecha que lleva la carta."""
    return datetime.now(ZoneInfo(get_policies().calendar.timezone)).date()


# --- Validación -----------------------------------------------------------------------------


def validate_letter(
    content: CoverLetterContent,
    profile: CandidateProfile,
    extraction: JobExtraction | None,
    used: InstructionsUsed,
) -> list[ContentIssue]:
    """Lo que el código comprueba sin IA (POLICIES §1 y §7). El resto, el rol `verificador`."""
    issues: list[ContentIssue] = []
    refs = checks.citable_refs(profile)
    has_user = used.has_user_instructions()

    for i, paragraph in enumerate(content.paragraphs):
        for k, ref in enumerate(paragraph.evidence):
            field = f"paragraphs[{i}].evidence[{k}]"
            if ref == EVIDENCE_USER and not has_user:
                issues.append(
                    ContentIssue(
                        field=field,
                        received=ref,
                        reason="`user` solo vale si hay indicaciones guardadas (las de la oferta "
                        "con `save_cover_letter_brief` o `preferences.cover_letter.instructions`).",
                    )
                )
            elif ref == EVIDENCE_EXTRACTION and extraction is None:
                issues.append(
                    ContentIssue(
                        field=field,
                        received=ref,
                        reason="La oferta aún no tiene extracción: no hay nada que citar.",
                    )
                )
            elif ref not in refs and ref not in EVIDENCE_LABELS:
                issues.append(
                    ContentIssue(
                        field=field,
                        received=ref,
                        reason="La evidencia no existe en el perfil (p. ej. `exp-acme/a2`); valen "
                        "también `extraction` (la oferta) y `user` (tus indicaciones).",
                    )
                )

    words = word_count(content)
    if words > used.max_words:
        issues.append(
            ContentIssue(
                field="paragraphs",
                received=str(words),
                reason=f"La carta tiene {words} palabras y el límite es {used.max_words}. "
                "Recórtala (cuenta solo el cuerpo, sin saludo ni despedida).",
            )
        )

    issues.extend(_skill_issues(content, profile, extraction))
    return issues


def _skill_issues(
    content: CoverLetterContent, profile: CandidateProfile, extraction: JobExtraction | None
) -> list[ContentIssue]:
    """Skills: las que se declaran (`keywords_targeted`) y las que se nombran en los párrafos.

    - Una skill fuera del perfil no puede aparecer como tuya. Las de la oferta se pueden nombrar
      en un párrafo que solo cite `extraction` o `user` (hablar del puesto no es
      atribuírselas); si el párrafo cita además el perfil, se rechaza.
    - Una skill básica (nivel B o `basic_skills`) solo si la oferta la pide.
    """
    issues: list[ContentIssue] = []
    index = alias_index()
    levels = {checks.skill_key(s.name, index): s.level for s in profile.skills}
    basics = {checks.skill_key(name, index) for name in profile.basic_skills}
    requested = {checks.skill_key(s, index): s for s in checks.requested_skills(extraction)}

    def is_basic(key: str) -> bool:
        return (key in basics and key not in levels) or levels.get(key) == "B"

    for k, keyword in enumerate(content.keywords_targeted):
        key = checks.skill_key(keyword, index)
        field = f"keywords_targeted[{k}]"
        if key not in levels and key not in basics:
            issues.append(
                ContentIssue(
                    field=field,
                    received=keyword,
                    reason="Esta skill no está en el perfil: no la declares como cubierta.",
                )
            )
        elif is_basic(key) and key not in requested:
            issues.append(
                ContentIssue(
                    field=field,
                    received=keyword,
                    reason="Es una skill básica y la oferta no la pide: quítala.",
                )
            )

    basic_names = [s.name for s in profile.skills if s.level == "B"] + [
        name for name in profile.basic_skills if checks.skill_key(name, index) not in levels
    ]
    for i, paragraph in enumerate(content.paragraphs):
        text = checks.fold_text(paragraph.text)
        field = f"paragraphs[{i}]"
        # Habla del puesto si cita la oferta y nada del perfil (si no, se la estaría atribuyendo).
        cites_offer = EVIDENCE_EXTRACTION in paragraph.evidence and all(
            ref in EVIDENCE_LABELS for ref in paragraph.evidence
        )
        for key, name in requested.items():
            if key in levels or key in basics or cites_offer:
                continue
            if checks.skill_mentioned(text, name, index):
                issues.append(
                    ContentIssue(
                        field=field,
                        received=name,
                        reason="Nombra una skill de la oferta que no está en tu perfil. Si hablas "
                        "del puesto, cita `extraction`; si la tienes, añádela primero al perfil.",
                    )
                )
        for name in basic_names:
            key = checks.skill_key(name, index)
            if key not in requested and checks.skill_mentioned(text, name, index):
                issues.append(
                    ContentIssue(
                        field=field,
                        received=name,
                        reason="Es una skill básica (nivel B o `basic_skills`) y la oferta no la "
                        "pide: no la menciones.",
                    )
                )
    return issues


# --- Indicaciones de la oferta --------------------------------------------------------------


def save_brief(session: Session, job_id: int, brief: CoverLetterBriefInput) -> SaveBriefResult:
    """Guarda (o sustituye) las indicaciones de la carta para una oferta. Sin evento."""
    service._job(session, job_id)
    row = session.get(CoverLetterBrief, job_id)
    if row is None:
        row = CoverLetterBrief(job_id=job_id)
        session.add(row)
    row.instructions = brief.instructions.strip()
    row.max_words = brief.max_words
    row.updated_at = utcnow()
    session.flush()
    view = _brief(session, job_id)
    assert view is not None
    try:
        prefs = _preferences(profile_service.current(session).profile)
    except profile_service.ProfileNotFoundError:
        prefs = None
    return SaveBriefResult(
        ok=True, job_id=job_id, brief=view, max_words=resolve_max_words(view, prefs)
    )


# --- Resolución de opciones -----------------------------------------------------------------


def _selected_cv_render(session: Session, job_id: int) -> DocumentRender | None:
    render_id = service.selected_render_id(session, job_id)
    return session.get(DocumentRender, render_id) if render_id else None


def resolve_letter(
    session: Session,
    job_id: int,
    profile: CandidateProfile,
    opts: CoverLetterRenderOptions,
    offer: OfferContext,
    photo_available: bool,
) -> LetterResolvedOptions:
    """Opciones de la carta: a juego con el render seleccionado del CV salvo que se pidan otras.

    1. plantilla base: la opción > la del render seleccionado del CV > las reglas del perfil;
    2. si la base no tiene diseño de carta: `carta-simple` y aviso `letter_fallback`;
    3. color y foto (`auto`): los del CV; tamaño de página: el del CV o el de la plantilla.
    """
    warnings: list[RenderWarning] = []
    cv_render = _selected_cv_render(session, job_id)
    source: LetterTemplateSource
    if cv_render is not None:
        # Foto, color y página del CV que se enviará, aunque se elija otra plantilla de carta.
        cv = ResolvedOptions.model_validate(cv_render.options)
        base_id, source, cv_render_id = cv_render.template_id, "cv", cv_render.id
    else:
        cv = options.resolve(profile, CvRenderOptions(), offer, photo_available)
        base_id, source, cv_render_id = cv.template_id, cv.template_source, None
        warnings.extend(cv.warnings)
    base_photo, base_accent, base_page = cv.photo, cv.accent_color, cv.page_size
    if opts.template_id is not None:
        base_id, source = opts.template_id, "option"

    fallback = False
    try:
        template = templates.get(base_id, kind="letter")
    except templates.TemplateNotFoundError:
        if opts.template_id is not None:
            raise
        template = templates.get(get_policies().cover_letter.fallback_template, kind="letter")
        fallback = True
        warnings.append(
            RenderWarning(
                code="letter_fallback",
                message=f"La plantilla «{base_id}» no tiene diseño de carta: se usa "
                f"«{template.id}» con su color.",
            )
        )
    meta = template.meta

    accent_option = meta.options.accent_color
    if opts.accent_color is not None:
        if accent_option is None:
            raise InvalidRenderOptionsError(
                f"La plantilla «{meta.id}» no admite color de acento (`accent_color`)."
            )
        if opts.accent_color not in accent_option.choices and not accent_option.free:
            raise InvalidRenderOptionsError(
                f"La plantilla «{meta.id}» admite estos colores: "
                f"{', '.join(accent_option.choices)}."
            )
        accent = opts.accent_color
    elif accent_option is None:
        accent = None
    elif base_accent and (base_accent in accent_option.choices or accent_option.free):
        accent = base_accent
    else:
        accent = accent_option.default

    photo_on = False
    if opts.photo == "include":
        if not meta.photo.supported:
            warnings.append(
                RenderWarning(
                    code="photo_excluded",
                    message=f"Pediste foto, pero el diseño de carta «{meta.id}» no la admite.",
                )
            )
        elif not photo_available:
            warnings.append(
                RenderWarning(
                    code="photo_excluded", message="Pediste foto, pero no hay foto disponible."
                )
            )
        else:
            photo_on = True
    elif opts.photo == "auto":
        photo_on = base_photo and meta.photo.supported and photo_available

    return LetterResolvedOptions(
        template_id=meta.id,
        template_source=source,
        base_template_id=base_id,
        cv_render_id=cv_render_id,
        letter_fallback=fallback,
        photo=photo_on,
        accent_color=accent,
        page_size=opts.page_size or base_page or meta.page.size,
        offer=offer,
        warnings=warnings,
    )


# --- Render ---------------------------------------------------------------------------------


def _to_result(row: DocumentRender, job_id: int) -> LetterRenderResult:
    return LetterRenderResult(
        render_id=row.id,
        job_id=job_id,
        document_id=row.document_id,
        template_id=row.template_id,
        template_hash=row.template_hash,
        options=LetterResolvedOptions.model_validate(row.options),
        docx_path=row.docx_path,
        pdf_path=row.pdf_path or "",
        pages=row.pages,
        warnings=[RenderWarning.model_validate(w) for w in row.warnings],
        selected=row.selected,
        created_at=row.created_at,
    )


def _renders(session: Session, document_id: int) -> list[DocumentRender]:
    stmt = (
        select(DocumentRender)
        .where(DocumentRender.document_id == document_id)
        .order_by(DocumentRender.id)
    )
    return list(session.scalars(stmt))


def _subtitle(session: Session, job_id: int, profile: CandidateProfile) -> str:
    """El subtítulo del CV de la oferta (la carta comparte cabecera) o el titular del perfil."""
    cv = service.latest_document(session, job_id)
    if cv is not None:
        return CvContent.model_validate(cv.content).subtitle
    return profile.headline


def render_cover_letter(
    session: Session, document_id: int, render_options: CoverLetterRenderOptions
) -> LetterRenderResult:
    """Renderiza una carta. No registra evento: un render no cambia nada del proceso.

    Si falla, borra los ficheros del render y relanza (como el render del CV).
    """
    doc = _letter_doc(session, document_id)
    _require_stage(session, doc.job_id)
    job = service._job(session, doc.job_id)
    content = _content(doc)
    profile = profile_service.get_version(session, doc.profile_version_id).profile
    extraction = service._extraction(session, job.id)

    offer = options.offer_context(job.url, job.location_raw, extraction, content.language)
    photo_source = photo.find_photo(profile)
    resolved = resolve_letter(
        session, job.id, profile, render_options, offer, photo_available=photo_source is not None
    )
    template = templates.get(resolved.template_id, kind="letter")
    assert template.letter_file is not None

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

    ctx = context.build_letter_context(
        content, profile, _subtitle(session, job.id, profile), resolved.accent_color, _today()
    )
    docx_file, pdf_file, info = service.write_files(
        template,
        ctx,
        service.render_dir(job.id, doc.id, row.id),
        service.file_stem(profile.personal.name, FILE_PREFIX),
        resolved.page_size,
        service.prepared_photo(template, resolved.photo, photo_source),
        file=template.letter_file,
    )

    warnings = list(resolved.warnings)
    if info.pages > LETTER_MAX_PAGES:
        warnings.append(
            RenderWarning(
                code="too_long",
                message=f"La carta ocupa {info.pages} páginas y el máximo es una. Recórtala.",
            )
        )
    missing = pdf.missing_fonts(template.meta.fonts, info.fonts)
    if missing:
        warnings.append(
            RenderWarning(
                code="font_substituted",
                message="Falta la fuente "
                + ", ".join(missing)
                + " y el PDF usa otra: instálala para que se vea como la plantilla.",
            )
        )
    service.store_files(session, row, docx_file, pdf_file, info.pages, warnings)
    return _to_result(row, job.id)


def select_render(session: Session, render_id: int) -> LetterRenderResult:
    """Marca el render de la carta que se enviará (uno por documento). Sin evento."""
    row = session.get(DocumentRender, render_id)
    if row is None:
        raise service.RenderNotFoundError(f"No existe el render {render_id}.")
    doc = _letter_doc(session, row.document_id)
    for other in _renders(session, doc.id):
        other.selected = other.id == row.id
    session.flush()
    return _to_result(row, doc.job_id)


# --- Contenido ------------------------------------------------------------------------------


def _store(
    session: Session,
    job_id: int,
    content: CoverLetterContent,
    actor: Actor,
    agent_name: str | None,
    edited_by_user: bool,
) -> Document:
    stored = profile_service.current(session)
    brief = _brief(session, job_id)
    prefs = _preferences(stored.profile)
    used = InstructionsUsed(
        brief=brief,
        preferences=prefs.model_dump(mode="json") if prefs else None,
        max_words=resolve_max_words(brief, prefs),
    )
    issues = validate_letter(content, stored.profile, service._extraction(session, job_id), used)
    if issues:
        raise CoverLetterContentError(issues)

    doc = Document(
        job_id=job_id,
        profile_version_id=stored.profile_version_id,
        kind=LETTER_KIND,
        language=content.language,
        content={
            "letter": content.model_dump(mode="json"),
            "instructions": used.model_dump(mode="json"),
        },
        edited_by_user=edited_by_user,
    )
    session.add(doc)
    session.flush()
    events.record(
        session,
        job_id,
        EventType.COVER_LETTER_GENERATED,
        actor,
        payload={"document_id": doc.id, "edited_by_user": edited_by_user},
        agent_name=agent_name,
    )
    return doc


def save_cover_letter(
    session: Session,
    job_id: int,
    content: CoverLetterContent,
    render_options: CoverLetterRenderOptions | None = None,
    agent_name: str | None = None,
) -> SaveLetterResult:
    """Valida y guarda la carta del agente con las indicaciones vigentes y hace su primer render."""
    _require_stage(session, job_id)
    doc = _store(session, job_id, content, Actor.AGENT, agent_name, edited_by_user=False)
    render = render_cover_letter(session, doc.id, render_options or CoverLetterRenderOptions())
    return SaveLetterResult(
        ok=True, job_id=job_id, document_id=doc.id, word_count=word_count(content), render=render
    )


def save_user_letter(
    session: Session, job_id: int, content: CoverLetterContent
) -> SaveLetterResult:
    """La edición a mano (UI): documento nuevo sin verificación, «Editada por ti».

    Siguen las comprobaciones del código (evidencias, palabras, skills). El render usa las
    opciones del render seleccionado de la carta anterior, si lo hay.
    """
    _require_stage(session, job_id)
    previous = latest_letter(session, job_id)
    render_options = CoverLetterRenderOptions()
    if previous is not None:
        chosen = next((r for r in _renders(session, previous.id) if r.selected), None)
        if chosen is not None:
            prev = LetterResolvedOptions.model_validate(chosen.options)
            render_options = CoverLetterRenderOptions(
                template_id=None if prev.template_source == "cv" else prev.template_id,
                photo="include" if prev.photo else "exclude",
                accent_color=prev.accent_color,
                page_size=prev.page_size,
            )
    doc = _store(session, job_id, content, Actor.USER, None, edited_by_user=True)
    render = render_cover_letter(session, doc.id, render_options)
    return SaveLetterResult(
        ok=True, job_id=job_id, document_id=doc.id, word_count=word_count(content), render=render
    )


def _view(session: Session, doc: Document) -> CoverLetterView:
    content = _content(doc)
    profile = profile_service.get_version(session, doc.profile_version_id).profile
    refs = checks.citable_refs(profile)
    cited = dict.fromkeys(ref for p in content.paragraphs for ref in p.evidence)
    return CoverLetterView(
        document_id=doc.id,
        profile_version_id=doc.profile_version_id,
        created_at=doc.created_at,
        edited_by_user=doc.edited_by_user,
        content=content,
        evidence={
            ref: EVIDENCE_LABELS.get(ref) or refs.get(ref, "(no existe en el perfil)")
            for ref in cited
        },
        word_count=word_count(content),
        instructions_used=_instructions(doc),
        verification=CvVerification.model_validate(doc.verification) if doc.verification else None,
        renders=[_to_result(r, doc.job_id) for r in _renders(session, doc.id)],
    )


def get_cover_letter(
    session: Session, job_id: int | None = None, document_id: int | None = None
) -> CoverLetterInfo:
    """Indicaciones vigentes y una carta (por su id, o la última de la oferta), si la hay."""
    if (job_id is None) == (document_id is None):
        raise ValueError("Indica `job_id` o `document_id`, no los dos.")
    doc: Document | None
    if document_id is not None:
        doc = _letter_doc(session, document_id)
        job_id = doc.job_id
    else:
        assert job_id is not None
        service._job(session, job_id)
        doc = latest_letter(session, job_id)
    try:
        prefs = _preferences(profile_service.current(session).profile)
    except profile_service.ProfileNotFoundError:
        prefs = None
    brief = _brief(session, job_id)
    return CoverLetterInfo(
        job_id=job_id,
        stage=events.current_stage(session, job_id),
        brief=brief,
        preferences=prefs,
        max_words=resolve_max_words(brief, prefs),
        letter=_view(session, doc) if doc else None,
    )


def save_verification(
    session: Session,
    document_id: int,
    verification: CvVerification,
    agent_name: str | None = None,
) -> SaveLetterVerificationResult:
    """Guarda el veredicto del verificador y registra `cover_letter_verified` (sin etapa)."""
    doc = _letter_doc(session, document_id)
    _require_stage(session, doc.job_id)
    doc.verification = verification.model_dump(mode="json")
    session.flush()
    blockers = sum(1 for i in verification.issues if i.severity == "blocker")
    events.record(
        session,
        doc.job_id,
        EventType.COVER_LETTER_VERIFIED,
        Actor.AGENT,
        payload={"document_id": doc.id, "passed": verification.passed, "blockers": blockers},
        agent_name=agent_name,
    )
    return SaveLetterVerificationResult(
        ok=True, job_id=doc.job_id, document_id=doc.id, passed=verification.passed
    )


def plain_text(session: Session, document_id: int) -> str:
    """La carta en texto plano para pegarla en un formulario: UTF-8 con saltos `\\r\\n`.

    Se genera al pedirla desde el contenido: no depende de la plantilla ni se guarda en disco.
    """
    doc = _letter_doc(session, document_id)
    content = _content(doc)
    name = profile_service.get_version(session, doc.profile_version_id).profile.personal.name
    blocks = [content.greeting, *(p.text.strip() for p in content.paragraphs)]
    blocks.append(f"{content.sign_off}\n{name}")
    text = "\n\n".join(block.strip() for block in blocks) + "\n"
    return text.replace("\r\n", "\n").replace("\n", "\r\n")
