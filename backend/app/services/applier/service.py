"""Intentos de candidatura asistida: preparar, rellenar, revisar y enviar tras tu confirmación.

Flujo (POLICIES §5):
1. `prepare` (API): crea el intento y encola `apply_fill` (o `apply_open` en LinkedIn y en los
   portales de empleo, donde la ficha de la oferta no es el formulario). Con `form_url` se rellena
   esa URL (el formulario de la empresa) en vez de la de la oferta.
   «Rellenar esta página» (`fill_page`, tarea `apply_fill_page`): tras llegar tú al formulario de
   la empresa desde el portal, rellena la pestaña que tienes delante. Nunca una del portal.
2. `run_fill` (worker): abre la URL en el navegador persistente, rellena, captura y para. El
   intento queda `ready` (o `needs_user` si hay captcha, anti-bot, login o no hay formulario) y se
   registra `application_filled`.
3. Si completas algo a mano en el navegador, `rescan` vuelve a leer los campos y a capturar.
4. `confirm_submission` (solo la API de la UI): comprueba el nombre de la empresa que escribiste,
   que no quedan obligatorios vacíos y que revisaste la versión vigente; emite el token de un solo
   uso y encola `apply_submit`.
5. `run_submit` (worker): consume el token, pulsa el envío, captura la confirmación y registra
   `applied` con la captura como evidencia. Si no se reconoce la confirmación, no registra nada.
6. «Lo termino yo»: `focus` trae la pestaña al frente y deja enviar; `mark_manual_done` registra
   `applied_manually`.

Las funciones `run_*` las llama el worker: abren sus propias sesiones cortas, para no tener una
transacción abierta mientras el navegador trabaja. Ninguna tiene reintentos (POLICIES §5.4).
"""

import contextlib
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import session_scope
from app.core.policies import get_policies
from app.models import ApplicationAttempt, Company, DocumentRender, Job, Task
from app.models.base import utcnow
from app.schemas.llm_io import ApplicationAnswers
from app.services import answers as answers_service
from app.services import application_archive, container, events, normalize, prompts, tasks
from app.services import profile as profile_service
from app.services.applier import fields, guard, platforms, submit, tokens
from app.services.applier.browser import BrowserState, PreparedPage, get_host
from app.services.applier.fields import FieldReport, FillData
from app.services.applier.guard import Blocker
from app.services.applier.log import AttemptLog
from app.services.documents import cover_letter
from app.services.documents.service import selected_render_id
from app.services.pipeline import CV_STAGES, Actor, EventType, Stage

# Mientras el worker trabaja en el intento.
ACTIVE = frozenset({"queued", "filling", "submitting"})
# Se ve la pantalla de revisión y se puede volver a leer o terminar a mano.
REVIEWABLE = frozenset({"ready", "needs_user", "submit_failed", "submit_unconfirmed", "manual"})
# Se puede volver a leer y, de ahí, a confirmar: nunca tras un clic de envío (ver `_clicked`).
RESCANNABLE = frozenset({"ready", "needs_user", "manual"})
# Desde aquí se puede rellenar la pestaña que tienes delante («Rellenar esta página»).
PAGE_FILLABLE = frozenset({"manual", "needs_user"})
# Bloqueos que piden tu intervención con un aviso (pop-up) en la UI.
_PROMPT_KINDS: dict[str, prompts.PromptKind] = {
    "captcha": "captcha",
    "antibot": "anti_bot",
    "login": "login_required",
}
# Avisos que pone `prepare` y que se conservan al rellenar o volver a revisar.
_STICKY_WARNINGS = frozenset({"possible_duplicate"})

ErrorCode = Literal[
    "not_found", "invalid_stage", "invalid_state", "busy", "no_cv", "company_mismatch", "stale",
    "missing_required", "invalid_url", "wrong_page",
]  # fmt: skip


class ApplierError(ValueError):
    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class AttemptWarning(BaseModel):
    code: str
    message: str
    detail: str | None = None  # dato suelto del aviso (p. ej. el texto del botón de envío)


class PendingTask(BaseModel):
    """Tarea del worker para este intento que aún no ha terminado."""

    kind: str
    status: str  # queued | running
    waiting_seconds: int  # desde que se encoló (o desde que puede ejecutarse)


class AttemptView(BaseModel):
    id: int
    job_id: int
    company: str
    platform: str
    mode: str
    url: str
    domain: str  # a dónde se envía: se enseña al confirmar
    status: str
    fields: list[FieldReport]
    warnings: list[AttemptWarning]
    missing_required: int
    consents: list[FieldReport]  # consentimientos obligatorios que aceptarás al confirmar
    can_submit: bool
    can_rescan: bool  # nunca tras un clic de envío
    can_fill_page: bool  # «Rellenar esta página»: rellenar la pestaña que tienes delante
    submit_button: str | None  # el texto del botón que se pulsará, si se encontró
    pending_task: PendingTask | None
    has_screenshot: bool
    has_confirmation: bool
    error: str | None
    created_at: datetime
    updated_at: datetime


# --- Consultas ------------------------------------------------------------------------------


def _reports(attempt: ApplicationAttempt) -> list[FieldReport]:
    return [FieldReport.model_validate(item) for item in attempt.fields or []]


def _company_name(session: Session, job_id: int) -> str:
    job = session.get(Job, job_id)
    company = session.get(Company, job.company_id) if job else None
    return company.name if company else ""


def _pending_task(session: Session, attempt_id: int) -> PendingTask | None:
    stmt = (
        select(Task)
        .where(Task.kind.in_(tasks.NO_RETRY_KINDS), Task.status.in_(("queued", "running")))
        .order_by(Task.id)
    )
    for task in session.scalars(stmt):
        if task.payload.get("attempt_id") == attempt_id:
            waiting = max(0, int((utcnow() - task.run_after).total_seconds()))
            return PendingTask(kind=task.kind, status=task.status, waiting_seconds=waiting)
    return None


def _submit_button(attempt: ApplicationAttempt) -> str | None:
    for warning in attempt.warnings or []:
        if warning.get("code") == "submit_button":
            return warning.get("detail")
    return None


def view(session: Session, attempt: ApplicationAttempt) -> AttemptView:
    reports = _reports(attempt)
    missing = sum(1 for r in reports if r.missing)
    return AttemptView(
        id=attempt.id,
        job_id=attempt.job_id,
        company=_company_name(session, attempt.job_id),
        platform=attempt.platform,
        mode=attempt.mode,
        url=attempt.url,
        domain=urlsplit(attempt.url).hostname or "",
        status=attempt.status,
        fields=reports,
        warnings=[AttemptWarning.model_validate(w) for w in attempt.warnings or []],
        missing_required=missing,
        consents=[r for r in reports if r.kind == "consent" and r.required],
        can_submit=attempt.status == "ready"
        and attempt.mode == "fill"
        and missing == 0
        and events.current_stage(session, attempt.job_id) == Stage.CV_READY,
        can_rescan=attempt.mode == "fill"
        and attempt.status in RESCANNABLE
        and not _clicked(attempt),
        can_fill_page=_fill_page_problem(session, attempt) is None,
        submit_button=_submit_button(attempt),
        pending_task=_pending_task(session, attempt.id),
        has_screenshot=attempt.screenshot_path is not None,
        has_confirmation=attempt.confirmation_path is not None,
        error=attempt.error,
        created_at=attempt.created_at,
        updated_at=attempt.updated_at,
    )


def _get(session: Session, attempt_id: int) -> ApplicationAttempt:
    attempt = session.get(ApplicationAttempt, attempt_id)
    if attempt is None:
        raise ApplierError("not_found", f"No existe el intento de candidatura {attempt_id}.")
    return attempt


def latest(session: Session, job_id: int) -> ApplicationAttempt | None:
    stmt = (
        select(ApplicationAttempt)
        .where(ApplicationAttempt.job_id == job_id)
        .order_by(ApplicationAttempt.id.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def _no_docker() -> None:
    """En Docker no hay navegador visible (fase 26.3): nada que abra o use el de CandidatAI."""
    if container.in_docker():
        raise ApplierError("docker", container.ASSISTED_APPLY)


def refuse_in_docker(attempt_id: int | None) -> None:
    """Una tarea del navegador que quedó en cola antes de pasar a Docker: el intento queda
    fallido con el motivo, en vez de esperar a un navegador que no hay."""
    if attempt_id is not None:
        _fail(attempt_id, container.ASSISTED_APPLY)
    raise ApplierError("docker", container.ASSISTED_APPLY)


def view_by_id(attempt_id: int) -> AttemptView:
    with session_scope() as session:
        return view(session, _get(session, attempt_id))


class AssistedApplication(BaseModel):
    """Lo que necesita la sección «Candidatura asistida» de la ficha."""

    job_id: int
    company: str
    attempt: AttemptView | None  # el último intento
    # Lo que haría «Preparar»: `fill` (rellenar y revisar) u `open` (LinkedIn o un portal de
    # empleo: abrir la oferta; desde ahí llegas tú al formulario de la empresa).
    mode: Literal["fill", "open"]
    domain: str
    url: str  # la de la oferta: en un portal se abre en tu navegador, con tu sesión
    portal: str | None  # «Glassdoor», «InfoJobs»… si la oferta es de un portal de empleo
    # Fase 26.3: en Docker no hay navegador visible; la UI ofrece abrir la oferta en el tuyo.
    in_docker: bool = False
    can_prepare: bool
    reason: str | None  # por qué no se puede preparar ahora


def get_state(session: Session, job_id: int) -> AssistedApplication:
    job = session.get(Job, job_id)
    if job is None:
        raise events.JobNotFoundError(f"No existe la oferta {job_id}.")
    stage = events.current_stage(session, job_id)
    mode = _mode(platforms.detect(job.url))
    attempt = latest(session, job_id)
    reason: str | None = None
    docker = container.in_docker()
    if docker:
        reason = container.ASSISTED_APPLY
    elif (problem := platforms.url_problem(job.url)) is not None:
        reason = problem
    elif mode == "fill" and stage != Stage.CV_READY:
        reason = "Hace falta un CV listo (verificado y elegido) para rellenar el formulario."
    elif mode == "open" and stage not in CV_STAGES:
        reason = "La oferta ya no está pendiente de enviar."
    elif attempt is not None and attempt.status in ACTIVE:
        reason = "Hay un intento en marcha."
    elif mode == "fill" and selected_render_id(session, job_id) is None:
        reason = "No hay un CV elegido para enviar."
    return AssistedApplication(
        job_id=job_id,
        company=_company_name(session, job_id),
        attempt=view(session, attempt) if attempt else None,
        mode=mode,
        domain=urlsplit(job.url).hostname or "",
        url=job.url,
        portal=_portal(job.url),
        in_docker=docker,
        can_prepare=reason is None,
        reason=reason,
    )


def get_latest(session: Session, job_id: int) -> AttemptView | None:
    if session.get(Job, job_id) is None:
        raise events.JobNotFoundError(f"No existe la oferta {job_id}.")
    attempt = latest(session, job_id)
    return view(session, attempt) if attempt else None


def screenshot_file(
    session: Session, attempt_id: int, kind: Literal["review", "confirmation"]
) -> Path:
    """La captura de revisión o de confirmación de un intento."""
    attempt = _get(session, attempt_id)
    relative = attempt.screenshot_path if kind == "review" else attempt.confirmation_path
    if relative is None:
        raise ApplierError("not_found", "Ese intento no tiene esa captura.")
    root = get_settings().applications_dir.resolve()
    path = (get_settings().data_dir / relative).resolve()
    # Solo se sirve lo que hay dentro de `data/applications/` (como los renders en `data/cvs/`).
    if not path.is_relative_to(root) or not path.is_file():
        raise ApplierError("not_found", "La captura ya no está en disco.")
    return path


def _clicked(attempt: ApplicationAttempt) -> bool:
    """Si se usó la confirmación de envío: el clic pudo darse, así que no se vuelve a `ready`."""
    return attempt.token_used_at is not None


def _touch(attempt: ApplicationAttempt, status: str | None = None) -> None:
    if status is not None:
        attempt.status = status
    attempt.updated_at = utcnow()


# --- Preparar -------------------------------------------------------------------------------


def _mode(platform: str | None) -> Literal["fill", "open"]:
    """En LinkedIn y en los portales de empleo solo se abre la oferta."""
    return "open" if platform in ("linkedin", "board") else "fill"


def _portal(url: str) -> str | None:
    board = platforms.job_board(url)
    return platforms.BOARD_LABELS[board] if board else None


def prepare(session: Session, job_id: int, form_url: str | None = None) -> AttemptView:
    """Crea un intento y lo encola: rellenar (ATS conocido o web con formulario) o solo abrir
    (LinkedIn o un portal de empleo). Con `form_url` (el formulario de la empresa, p. ej. al que
    lleva el portal) se rellena esa URL. Los intentos anteriores que esperaban revisión se
    anulan."""
    _no_docker()
    job = session.get(Job, job_id)
    if job is None:
        raise events.JobNotFoundError(f"No existe la oferta {job_id}.")
    stage = events.current_stage(session, job_id)
    url = job.url
    if form_url is not None:
        url = form_url.strip()
        if (problem := platforms.fill_problem(url)) is not None:
            raise ApplierError("invalid_url", problem)
    platform = platforms.detect(url)
    mode = _mode(platform)
    if mode == "fill" and stage != Stage.CV_READY:
        raise ApplierError(
            "invalid_stage",
            "Para rellenar el formulario la oferta tiene que estar en «CV listo» "
            f"(está en «{stage}»).",
        )
    if mode == "open" and stage not in CV_STAGES:
        raise ApplierError("invalid_stage", f"La oferta está en «{stage}»: ya no se prepara.")
    if (problem := platforms.url_problem(url)) is not None:
        raise ApplierError("invalid_url", problem)
    previous = latest(session, job_id)
    if previous is not None and previous.status in ACTIVE:
        raise ApplierError(
            "busy", "Ya hay un intento en marcha para esta oferta: espera a que termine."
        )
    if mode == "fill" and selected_render_id(session, job_id) is None:
        raise ApplierError("no_cv", "No hay un CV elegido para enviar en esta oferta.")
    clicked_before = session.scalars(
        select(ApplicationAttempt.id).where(
            ApplicationAttempt.job_id == job_id, ApplicationAttempt.token_used_at.is_not(None)
        )
    ).first()
    for old in session.scalars(
        select(ApplicationAttempt).where(
            ApplicationAttempt.job_id == job_id, ApplicationAttempt.status.in_(REVIEWABLE)
        )
    ):
        old.token_hash = None
        _touch(old, "cancelled")
    warnings = []
    if clicked_before is not None:
        warnings.append(
            AttemptWarning(
                code="possible_duplicate",
                message="En un intento anterior ya se pulsó «Enviar»: comprueba en la web (o en "
                "tu correo) que no llegó antes de volver a enviar.",
            ).model_dump()
        )
    attempt = ApplicationAttempt(
        job_id=job_id,
        platform=platform or "generic",  # sin reconocer por la URL: se mira la página
        mode=mode,
        url=platforms.application_url(platform or "generic", url),
        status="queued",
        fields=[],
        warnings=warnings,
    )
    session.add(attempt)
    session.flush()
    tasks.enqueue(
        session, "apply_fill" if mode == "fill" else "apply_open", {"attempt_id": attempt.id}
    )
    return view(session, attempt)


def _fill_data(session: Session, job_id: int) -> FillData:
    personal = profile_service.current(session).profile.personal
    render_id = selected_render_id(session, job_id)
    render = session.get(DocumentRender, render_id) if render_id else None
    data_dir = get_settings().data_dir
    if render is None or not render.pdf_path or not (data_dir / render.pdf_path).is_file():
        raise ApplierError("no_cv", "No está el PDF del CV elegido para esta oferta.")
    first, last = fields.split_name(personal.name)
    letter_pdf: Path | None = None
    letter_text: str | None = None
    if (found := cover_letter.selected_letter(session, job_id)) is not None:
        doc, letter_render = found
        letter_text = cover_letter.plain_text(session, doc.id).replace("\r\n", "\n")
        if letter_render is not None and letter_render.pdf_path:
            pdf = data_dir / letter_render.pdf_path
            letter_pdf = pdf if pdf.is_file() else None
    answers: list[fields.PackageAnswer] = []
    if (doc := answers_service.latest_answers(session, job_id)) is not None:
        for item in ApplicationAnswers.model_validate(doc.content).answers:
            answers.append(
                fields.PackageAnswer(
                    question=item.question,
                    answer=item.answer,
                    needs_user_input=item.needs_user_input,
                )
            )
    return FillData(
        applicant=fields.Applicant(
            full_name=personal.name,
            first_name=first,
            last_name=last,
            email=personal.email,
            phone=personal.phone,
            linkedin=personal.linkedin,
            github=personal.github,
            city=personal.city,
        ),
        resume=data_dir / render.pdf_path,
        letter_pdf=letter_pdf,
        letter_text=letter_text,
        answers=answers,
    )


# --- En el navegador (hilo del navegador) ---------------------------------------------------


class _BrowserOutcome(BaseModel):
    platform: str
    status: Literal["ready", "needs_user"]
    url: str | None = None  # la página rellenada, si no es la del intento («Rellenar esta página»)
    fields: list[FieldReport] = []
    warnings: list[AttemptWarning] = []
    screenshot: str | None = None
    blocker: Blocker | None = None


def _screenshot(page: Any, job_id: int, attempt_id: int, name: str) -> str | None:
    settings = get_settings()
    folder = settings.applications_dir / str(job_id) / str(attempt_id)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
    except Exception:
        return None
    return path.relative_to(settings.data_dir).as_posix()


def _settle(page: Any) -> None:
    """Espera a que la página termine de cargar lo que pueda, sin pasarse del timeout."""
    with contextlib.suppress(Exception):
        page.wait_for_load_state("networkidle", timeout=10_000)


def _warnings(
    plans: list[fields.FieldPlan],
    reports: list[FieldReport],
    data: FillData,
    invisible_captcha: bool,
    blocked: int,
) -> list[AttemptWarning]:
    out: list[AttemptWarning] = []
    if invisible_captcha:
        out.append(
            AttemptWarning(
                code="invisible_captcha",
                message="La web usa un captcha invisible: al enviar podría pedirte resolverlo.",
            )
        )
    if blocked:
        out.append(
            AttemptWarning(
                code="submit_blocked",
                message="La página intentó enviar el formulario sola y se bloqueó.",
            )
        )
    if not any(p.kind == "resume" for p in plans):
        out.append(
            AttemptWarning(code="no_resume_field", message="No se ha encontrado dónde subir el CV.")
        )
    used = {p.source for p in plans if p.source}
    unused = [a for a in data.answers if f"Respuesta del paquete: «{a.question}»" not in used]
    if unused:
        out.append(
            AttemptWarning(
                code="unused_answers",
                message=f"{len(unused)} respuestas del paquete no encajan con ninguna pregunta "
                "del formulario: cópialas tú si hace falta.",
            )
        )
    if not data.answers:
        out.append(
            AttemptWarning(
                code="no_answers", message="No hay respuestas en el paquete de candidatura."
            )
        )
    missing = [r for r in reports if r.missing]
    if missing:
        out.append(
            AttemptWarning(
                code="missing_required",
                message=f"{len(missing)} campos obligatorios sin respuesta: complétalos en el "
                "navegador y pulsa «Volver a revisar», o termina tú.",
            )
        )
    return out


def _button_warning(page: Any) -> AttemptWarning:
    """Qué botón se pulsará al confirmar, para que lo veas antes."""
    label = submit.submit_button_label(page)
    if label is None:
        return AttemptWarning(
            code="no_submit_button",
            message="No se encuentra el botón de envío: tendrás que terminar tú.",
        )
    return AttemptWarning(
        code="submit_button", message=f"Al confirmar se pulsará «{label}».", detail=label
    )


def _blocked(
    page: Any, job_id: int, attempt_id: int, platform: str, blocker: Blocker
) -> _BrowserOutcome:
    return _BrowserOutcome(
        platform=platform,
        status="needs_user",
        blocker=blocker,
        warnings=[AttemptWarning(code=blocker.kind, message=blocker.message)],
        screenshot=_screenshot(page, job_id, attempt_id, "review"),
    )


def _fill_in_browser(
    state: BrowserState,
    attempt_id: int,
    job_id: int,
    url: str,
    platform: str,
    data: FillData,
    log: AttemptLog,
    min_similarity: int,
) -> _BrowserOutcome:
    page = state.new_page(attempt_id, job_id)
    with log.step("goto", platform=platform):
        response = page.goto(url, wait_until="domcontentloaded")
    _settle(page)
    return _fill_page_in_browser(
        page, attempt_id, job_id, url, platform, data, log, min_similarity, response
    )


def _fill_page_in_browser(
    page: Any,
    attempt_id: int,
    job_id: int,
    url: str,
    platform: str,
    data: FillData,
    log: AttemptLog,
    min_similarity: int,
    response: Any = None,
) -> _BrowserOutcome:
    """Rellena la página ya abierta (la del intento o la que tienes delante) y se para."""
    with log.step("guard"):
        found = guard.check(page, response)
    if found.blocker is not None:
        return _blocked(page, job_id, attempt_id, platform, found.blocker)
    opened: str | None = None  # el botón que se pulsó para abrir el formulario, si hizo falta
    if platforms.detect(url) is None:
        detected, frame_url = platforms.inspect(page)
        log.write("inspect", platform=detected, frame=frame_url is not None)
        if detected == "unknown" and frame_url is None:
            opened = _open_application_form(page, log)
            if opened is not None:
                if (problem := platforms.portal_problem(page.url)) is not None:
                    raise ApplierError("wrong_page", problem)
                found = guard.check(page)
                if found.blocker is not None:
                    return _blocked(page, job_id, attempt_id, detected, found.blocker)
                detected, frame_url = platforms.inspect(page)
                log.write("inspect", platform=detected, frame=frame_url is not None)
        if frame_url is not None:
            if (problem := platforms.url_problem(frame_url)) is not None:
                raise ApplierError("invalid_url", problem)
            with log.step("goto_frame", platform=detected):
                response = page.goto(platforms.application_url(detected, frame_url))
            _settle(page)
            found = guard.check(page, response)
            if found.blocker is not None:
                return _blocked(page, job_id, attempt_id, detected, found.blocker)
        platform = detected
    if platform == "unknown":
        return _blocked(
            page,
            job_id,
            attempt_id,
            platform,
            Blocker(kind="no_form", message=_NO_FORM),
        )
    guard.arm_submit_block(page)
    with log.step("discover"):
        descriptors = fields.discover(page)
    log.write("fields", count=len(descriptors))
    if not descriptors:
        return _blocked(
            page,
            job_id,
            attempt_id,
            platform,
            Blocker(
                kind="no_form", message="El formulario no tiene campos que se puedan rellenar."
            ),
        )
    plans = fields.plan(descriptors, data, min_similarity)
    errors = fields.apply(page, plans, log)
    with log.step("guard_after"):
        after = guard.check(page)
    reports = fields.read_state(page, plans, errors)
    warnings = _warnings(
        plans, reports, data, found.invisible_captcha or after.invisible_captcha,
        guard.blocked_submits(page),
    )  # fmt: skip
    if opened is not None:
        warnings.insert(
            0,
            AttemptWarning(
                code="form_opened",
                message=f"Para ver el formulario se pulsó «{opened}» (no envía nada).",
                detail=opened,
            ),
        )
    if after.blocker is not None:
        warnings.insert(0, AttemptWarning(code=after.blocker.kind, message=after.blocker.message))
    warnings.append(_button_warning(page))
    with log.step("screenshot"):
        shot = _screenshot(page, job_id, attempt_id, "review")
    return _BrowserOutcome(
        platform=platform,
        status="needs_user" if after.blocker else "ready",
        fields=reports,
        warnings=warnings,
        screenshot=shot,
        blocker=after.blocker,
    )


_NO_FORM = (
    "No se reconoce ningún formulario de candidatura. Si en la web hay que pulsar un botón para "
    "verlo, púlsalo en el navegador de CandidatAI y luego «Rellenar esta página»; si no, termina "
    "tú en la web."
)


def _open_application_form(page: Any, log: AttemptLog) -> str | None:
    """En una página sin formulario, pulsa el botón que lo abre («Enviar solicitud», «Apply
    now»…) y espera a que aparezca. Sin campos rellenos no se envía nada: solo se llega al
    formulario. Devuelve el texto del botón, o `None` si no lo hay."""
    found = platforms.find_apply_button(page)
    if not found:
        return None
    label = str(found["label"])[:80]
    with log.step("open_form", label=label):
        if found.get("blank") and found.get("href"):
            href = str(found["href"])
            if platforms.portal_problem(href) or platforms.url_problem(href):
                return None
            page.goto(href, wait_until="domcontentloaded")
        else:
            try:  # nunca un control de envío: solo el que abre el formulario
                fields.open_form_click(page.locator("[data-cai-apply='1']").first)
            except fields.SubmitControlError:
                return None
        _settle(page)
        for _ in range(20):  # el formulario puede cargarse un poco después
            detected, frame_url = platforms.inspect(page)
            if detected != "unknown" or frame_url is not None:
                break
            page.wait_for_timeout(500)
    return label


def _rescan_in_browser(
    state: BrowserState,
    attempt_id: int,
    job_id: int,
    platform: str,
    data: FillData,
    log: AttemptLog,
    min_similarity: int,
) -> _BrowserOutcome:
    page = state.page_for(attempt_id)
    if page is None:
        raise ApplierError(
            "invalid_state",
            "La pestaña preparada ya no existe (se cerró el navegador o el worker): vuelve a "
            "preparar la candidatura.",
        )
    found = guard.check(page)
    if found.blocker is not None:
        return _blocked(page, job_id, attempt_id, platform, found.blocker)
    guard.arm_submit_block(page)
    with log.step("discover"):
        descriptors = fields.discover(page)
    plans = fields.plan(descriptors, data, min_similarity)
    for p in plans:  # ya no se rellena nada: solo se lee lo que hay
        p.value, p.file = None, None
    reports = fields.read_state(page, plans, {})
    warnings = _warnings(plans, reports, data, found.invisible_captcha, guard.blocked_submits(page))
    warnings.append(_button_warning(page))
    return _BrowserOutcome(
        platform=platform,
        status="ready",
        fields=reports,
        warnings=warnings,
        screenshot=_screenshot(page, job_id, attempt_id, "review"),
    )


# --- Worker: rellenar y volver a revisar ----------------------------------------------------


def _fail(attempt_id: int, message: str, status: str = "failed") -> None:
    with session_scope() as session:
        attempt = session.get(ApplicationAttempt, attempt_id)
        if attempt is not None:
            attempt.error = message[:2000]
            _touch(attempt, status)


def _store_outcome(
    attempt_id: int, outcome: _BrowserOutcome, event: bool, expected: frozenset[str]
) -> dict[str, Any]:
    """Guarda lo que vio el navegador. Con `outcome.url` («Rellenar esta página»), el intento pasa
    a ser de rellenar y su URL es la de la página rellenada."""
    with session_scope() as session:
        attempt = _get(session, attempt_id)
        if attempt.status not in expected or _clicked(attempt):
            # Cambió mientras trabajaba el navegador (se anuló, terminas tú…): no se pisa.
            return {"attempt_id": attempt_id, "skipped": attempt.status}
        sticky = [w for w in attempt.warnings or [] if w.get("code") in _STICKY_WARNINGS]
        attempt.platform = outcome.platform
        if outcome.url is not None:
            attempt.url = outcome.url
            attempt.mode = "fill"
        attempt.fields = [r.model_dump() for r in outcome.fields]
        attempt.warnings = [*sticky, *(w.model_dump() for w in outcome.warnings)]
        if outcome.screenshot:
            attempt.screenshot_path = outcome.screenshot
        attempt.error = outcome.blocker.message if outcome.blocker else None
        attempt.token_hash = None
        _touch(attempt, outcome.status)
        if outcome.blocker is not None and outcome.blocker.kind in _PROMPT_KINDS:
            # Pop-up en la UI: lo resuelves tú y, con «Ya está», se vuelve a rellenar la página.
            prompts.request(
                session,
                _PROMPT_KINDS[outcome.blocker.kind],
                f"{outcome.blocker.message} Resuélvelo en el navegador de CandidatAI y pulsa "
                "«Ya está»: se rellenará el formulario.",
                url=attempt.url,
                attempt_id=attempt.id,
            )
        missing = sum(1 for r in outcome.fields if r.missing)
        filled = sum(1 for r in outcome.fields if r.status == "filled")
        if event and events.current_stage(session, attempt.job_id) == Stage.CV_READY:
            events.record(
                session,
                attempt.job_id,
                EventType.APPLICATION_FILLED,
                Actor.SYSTEM,
                payload={
                    "attempt_id": attempt.id,
                    "platform": outcome.platform,
                    "status": outcome.status,
                    "filled": filled,
                    "missing_required": missing,
                },
            )
        return {
            "attempt_id": attempt_id,
            "job_id": attempt.job_id,
            "status": outcome.status,
            "filled": filled,
            "missing_required": missing,
        }


def run_fill(attempt_id: int) -> dict[str, Any]:
    """Tarea `apply_fill`: rellena el formulario del intento y se para antes de enviar."""
    log = AttemptLog(attempt_id)
    with session_scope() as session:
        attempt = _get(session, attempt_id)
        if attempt.status != "queued":
            return {"attempt_id": attempt_id, "skipped": attempt.status}
        _touch(attempt, "filling")
        job_id, url, platform = attempt.job_id, attempt.url, attempt.platform
    try:
        with session_scope() as session:
            data = _fill_data(session, job_id)
        min_similarity = get_policies().applier.answer_min_similarity
        outcome = get_host().call(
            lambda state: _fill_in_browser(
                state, attempt_id, job_id, url, platform, data, log, min_similarity
            )
        )
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}" if not isinstance(exc, ApplierError) else str(exc)
        log.write("fill_failed", ok=False, error=message[:500])
        _fail(attempt_id, message)
        raise
    log.write("done", status=outcome.status)
    return _store_outcome(attempt_id, outcome, event=True, expected=frozenset({"filling"}))


def rescan(session: Session, attempt_id: int) -> AttemptView:
    """Vuelve a leer los campos y a capturar (tras completar algo en el navegador)."""
    _no_docker()
    attempt = _get(session, attempt_id)
    if _clicked(attempt):
        raise ApplierError(
            "invalid_state",
            "En este intento ya se pulsó «Enviar»: termina tú en la web o prepara uno nuevo.",
        )
    if attempt.mode != "fill" or attempt.status not in RESCANNABLE:
        raise ApplierError("invalid_state", f"No se puede volver a revisar en «{attempt.status}».")
    tasks.enqueue(session, "apply_rescan", {"attempt_id": attempt_id})
    return view(session, attempt)


def run_rescan(attempt_id: int) -> dict[str, Any]:
    """Tarea `apply_rescan`."""
    log = AttemptLog(attempt_id)
    with session_scope() as session:
        attempt = _get(session, attempt_id)
        if attempt.status not in RESCANNABLE or _clicked(attempt):
            return {"attempt_id": attempt_id, "skipped": attempt.status}
        job_id, platform = attempt.job_id, attempt.platform
        data = _fill_data(session, job_id)
    min_similarity = get_policies().applier.answer_min_similarity
    outcome = get_host().call(
        lambda state: _rescan_in_browser(
            state, attempt_id, job_id, platform, data, log, min_similarity
        )
    )
    log.write("rescan", status=outcome.status)
    return _store_outcome(attempt_id, outcome, event=False, expected=RESCANNABLE)


def _fill_page_problem(session: Session, attempt: ApplicationAttempt) -> str | None:
    """Por qué no se puede usar «Rellenar esta página» en este intento, o `None`."""
    if _clicked(attempt):
        return "En este intento ya se pulsó «Enviar»: termina tú en la web o prepara uno nuevo."
    if attempt.status not in PAGE_FILLABLE:
        return f"No se puede rellenar una página con el intento en «{attempt.status}»."
    if events.current_stage(session, attempt.job_id) != Stage.CV_READY:
        return "Para rellenar un formulario la oferta tiene que estar en «CV listo»."
    if selected_render_id(session, attempt.job_id) is None:
        return "No hay un CV elegido para enviar en esta oferta."
    return None


def fill_page(session: Session, attempt_id: int) -> AttemptView:
    """«Rellenar esta página»: encola rellenar la pestaña que tienes delante en el navegador de
    CandidatAI (el formulario de la empresa al que te llevó el portal). No envía nada."""
    _no_docker()
    attempt = _get(session, attempt_id)
    if (problem := _fill_page_problem(session, attempt)) is not None:
        raise ApplierError("invalid_state", problem)
    previous = attempt.status
    attempt.error = None
    _touch(attempt, "queued")
    tasks.enqueue(session, "apply_fill_page", {"attempt_id": attempt_id, "previous": previous})
    return view(session, attempt)


def _visible(page: Any) -> bool:
    try:
        return bool(page.evaluate("document.visibilityState === 'visible'"))
    except Exception:
        return False


def _current_page(state: BrowserState, attempt_id: int, job_id: int) -> Any:
    """La pestaña que tienes delante: la última visible (la activa de su ventana) o, si no hay
    ninguna, la del intento o la última abierta. Queda como pestaña del intento."""
    context = state.ensure_context()
    pages = [p for p in context.pages if not p.is_closed()]
    visible = [p for p in pages if _visible(p)]
    page = visible[-1] if visible else state.page_for(attempt_id) or (pages[-1] if pages else None)
    if page is None:
        raise ApplierError(
            "wrong_page", "No hay ninguna pestaña abierta en el navegador de CandidatAI."
        )
    state.pages[attempt_id] = PreparedPage(job_id=job_id, page=page)
    return page


def _fill_current_in_browser(
    state: BrowserState,
    attempt_id: int,
    job_id: int,
    data: FillData,
    log: AttemptLog,
    min_similarity: int,
) -> _BrowserOutcome:
    page = _current_page(state, attempt_id, job_id)
    url = page.url
    if (problem := platforms.fill_problem(url)) is not None:
        raise ApplierError("wrong_page", problem)
    log.write("fill_page", host=urlsplit(url).hostname or "")
    page.bring_to_front()
    _settle(page)
    platform = platforms.detect(url) or "generic"
    outcome = _fill_page_in_browser(
        page, attempt_id, job_id, url, platform, data, log, min_similarity
    )
    outcome.url = url
    return outcome


def run_fill_page(attempt_id: int, previous: str = "manual") -> dict[str, Any]:
    """Tarea `apply_fill_page`. Si la pestaña no es un formulario que se pueda rellenar (es del
    portal, de LinkedIn…), el intento vuelve a como estaba, con el motivo."""
    log = AttemptLog(attempt_id)
    with session_scope() as session:
        attempt = _get(session, attempt_id)
        if attempt.status != "queued":
            return {"attempt_id": attempt_id, "skipped": attempt.status}
        _touch(attempt, "filling")
        job_id = attempt.job_id
    try:
        with session_scope() as session:
            data = _fill_data(session, job_id)
        min_similarity = get_policies().applier.answer_min_similarity
        outcome = get_host().call(
            lambda state: _fill_current_in_browser(
                state, attempt_id, job_id, data, log, min_similarity
            )
        )
    except ApplierError as exc:
        if exc.code != "wrong_page":
            log.write("fill_page_failed", ok=False, error=str(exc)[:500])
            _fail(attempt_id, str(exc))
            raise
        log.write("wrong_page", ok=False)
        back = previous if previous in PAGE_FILLABLE else "manual"
        _fail(attempt_id, str(exc), back)
        return {"attempt_id": attempt_id, "status": back, "wrong_page": True}
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        log.write("fill_page_failed", ok=False, error=message[:500])
        _fail(attempt_id, message)
        raise
    log.write("done", status=outcome.status)
    return _store_outcome(attempt_id, outcome, event=True, expected=frozenset({"filling"}))


# --- Envío ----------------------------------------------------------------------------------


def _same_company(typed: str, company: str) -> bool:
    if not typed.strip() or not company.strip():
        return False
    return normalize.fold(typed) == normalize.fold(company) or (
        normalize.normalize_company(typed) == normalize.normalize_company(company)
    )


def confirm_submission(
    session: Session,
    attempt_id: int,
    company_confirmation: str,
    reviewed_at: datetime,
) -> AttemptView:
    """Tu confirmación de envío (solo desde la UI). Emite el token y encola `apply_submit`.

    `reviewed_at` es el `updated_at` del intento que viste: si cambió después (se volvió a leer o
    a rellenar), hay que revisar otra vez.
    """
    _no_docker()
    attempt = _get(session, attempt_id)
    if attempt.status != "ready" or attempt.mode != "fill":
        raise ApplierError(
            "invalid_state", f"Este intento no está listo para enviar («{attempt.status}»)."
        )
    if reviewed_at != attempt.updated_at:
        raise ApplierError(
            "stale", "El intento ha cambiado desde que lo revisaste: revísalo otra vez."
        )
    pending = (
        attempt.token_hash is not None
        and attempt.token_used_at is None
        and attempt.token_expires_at is not None
        and attempt.token_expires_at > utcnow()
    )
    if pending:
        raise ApplierError("busy", "Ya confirmaste este envío: espera a que lo haga el worker.")
    stage = events.current_stage(session, attempt.job_id)
    if stage != Stage.CV_READY:
        raise ApplierError("invalid_stage", f"La oferta está en «{stage}»: ya no se envía.")
    reports = _reports(attempt)
    if any(r.missing for r in reports):
        raise ApplierError(
            "missing_required", "Quedan campos obligatorios sin respuesta: no se puede enviar."
        )
    company = _company_name(session, attempt.job_id)
    if not _same_company(company_confirmation, company):
        raise ApplierError(
            "company_mismatch", "El nombre de la empresa no coincide: escríbelo tal cual aparece."
        )
    consents = [
        r.marker for r in reports if r.kind == "consent" and r.required and r.status != "filled"
    ]
    token = tokens.issue(attempt, get_policies().applier.token_ttl_seconds)
    session.flush()
    tasks.enqueue(
        session, "apply_submit", {"attempt_id": attempt_id, "token": token, "consents": consents}
    )
    return view(session, attempt)


class _SubmitResult(BaseModel):
    outcome: submit.SubmitOutcome
    screenshot: str | None


def _submit_in_browser(
    state: BrowserState,
    attempt_id: int,
    job_id: int,
    confirmation: tokens.SubmitConfirmation,
    log: AttemptLog,
    wait_seconds: float,
) -> _SubmitResult:
    page = state.page_for(attempt_id)
    if page is None:
        return _SubmitResult(
            outcome=submit.SubmitOutcome(
                result="failed",
                message="La pestaña preparada ya no existe (se cerró el navegador o el worker): "
                "vuelve a preparar la candidatura.",
            ),
            screenshot=None,
        )
    outcome = submit.click_submit(page, confirmation, attempt_id, log, wait_seconds)
    name = "confirmation" if outcome.result == "confirmed" else "after-submit"
    return _SubmitResult(outcome=outcome, screenshot=_screenshot(page, job_id, attempt_id, name))


_SUBMIT_STATUS = {
    "confirmed": "submitted",
    "blocked": "needs_user",
    "unconfirmed": "submit_unconfirmed",
    "failed": "submit_failed",
}


def run_submit(attempt_id: int, token: str, consents: list[str] | None = None) -> dict[str, Any]:
    """Tarea `apply_submit`: sin confirmación válida no se toca el navegador."""
    log = AttemptLog(attempt_id)
    try:
        with session_scope() as session:
            confirmation = tokens.consume(session, attempt_id, token, tuple(consents or ()))
            job_id = _get(session, attempt_id).job_id
            _scrub_token(session, attempt_id)
    except tokens.TokenError as exc:
        log.write("token_rejected", ok=False, error=str(exc)[:300])
        _reject_token(attempt_id, str(exc))
        raise
    log.write("token_ok")
    wait = get_policies().applier.confirm_wait_seconds
    try:
        result = get_host().call(
            lambda state: _submit_in_browser(state, attempt_id, job_id, confirmation, log, wait)
        )
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        log.write("submit_failed", ok=False, error=message[:500])
        _fail(attempt_id, f"Fallo al enviar (sin reintentos): {message}", "submit_failed")
        raise
    outcome = result.outcome
    with session_scope() as session:
        attempt = _get(session, attempt_id)
        attempt.error = None if outcome.result == "confirmed" else outcome.message
        if outcome.errors:
            attempt.warnings = [
                *(attempt.warnings or []),
                *(
                    AttemptWarning(code="form_error", message=e).model_dump()
                    for e in outcome.errors
                ),
            ]
        if result.screenshot:
            attempt.confirmation_path = result.screenshot
        elif outcome.result == "confirmed":
            attempt.warnings = [
                *(attempt.warnings or []),
                AttemptWarning(
                    code="no_evidence", message="No se pudo capturar la página de confirmación."
                ).model_dump(),
            ]
        _touch(attempt, _SUBMIT_STATUS[outcome.result])
    # El evento va aparte: si fallara, el intento sigue constando como enviado.
    recorded = False
    if outcome.result == "confirmed":
        try:
            with session_scope() as session:
                recorded = _record_applied(session, _get(session, attempt_id))
        except Exception as exc:
            log.write("applied_failed", ok=False, error=f"{type(exc).__name__}: {exc}"[:500])
            _fail(
                attempt_id,
                "Enviada, pero no se pudo registrar «applied»: márcala como enviada a mano.",
                "submitted",
            )
    log.write("submit_done", result=outcome.result, applied=recorded)
    return {"attempt_id": attempt_id, "result": outcome.result, "applied": recorded}


def _scrub_token(session: Session, attempt_id: int) -> None:
    """Borra el token de la tarea `apply_submit` del intento: ya no sirve y no debe quedar."""
    for task in session.scalars(select(Task).where(Task.kind == "apply_submit")):
        if task.payload.get("attempt_id") == attempt_id and "token" in task.payload:
            task.payload = {k: v for k, v in task.payload.items() if k != "token"}


def _reject_token(attempt_id: int, reason: str) -> None:
    """Confirmación que no valió (caducó en la cola, no coincide…): queda anotado y anulada."""
    with session_scope() as session:
        _scrub_token(session, attempt_id)
        attempt = session.get(ApplicationAttempt, attempt_id)
        if attempt is None or attempt.status != "ready" or attempt.token_hash is None:
            return  # no había confirmación pendiente: nada que anular
        attempt.token_hash = None
        attempt.error = f"No se envió: {reason} Confirma de nuevo si quieres enviarla."
        _touch(attempt)


def _record_applied(session: Session, attempt: ApplicationAttempt) -> bool:
    """`applied` con la captura de confirmación como evidencia. Actor `user`: lo desencadenó tu
    confirmación."""
    if events.current_stage(session, attempt.job_id) != Stage.CV_READY:
        return False  # ya se registró por otra vía mientras tanto
    payload: dict[str, Any] = {"channel": "ats_form", "attempt_id": attempt.id}
    if (render_id := selected_render_id(session, attempt.job_id)) is not None:
        payload["render_id"] = render_id
    if attempt.confirmation_path:
        payload["evidence"] = attempt.confirmation_path
    event = events.record(session, attempt.job_id, EventType.APPLIED, Actor.USER, payload=payload)
    application_archive.enqueue(session, attempt.job_id, event.id)
    return True


# --- Abrir, «Lo termino yo» y navegador -----------------------------------------------------


def run_open(attempt_id: int) -> dict[str, Any]:
    """Tarea `apply_open` (LinkedIn o un portal): solo abre la URL. El paquete se copia desde la
    ficha; en un portal, desde el formulario de la empresa se usa «Rellenar esta página»."""
    with session_scope() as session:
        attempt = _get(session, attempt_id)
        if attempt.status != "queued":
            return {"attempt_id": attempt_id, "skipped": attempt.status}
        job_id, url = attempt.job_id, attempt.url

    def _open(state: BrowserState) -> None:
        page = state.new_page(attempt_id, job_id)
        page.goto(url, wait_until="domcontentloaded")
        page.bring_to_front()

    try:
        get_host().call(_open)
    except Exception as exc:
        _fail(attempt_id, f"No se pudo abrir la oferta: {type(exc).__name__}: {exc}")
        raise
    with session_scope() as session:
        _touch(_get(session, attempt_id), "manual")
    return {"attempt_id": attempt_id, "status": "manual"}


def focus(session: Session, attempt_id: int) -> AttemptView:
    """«Lo termino yo»: encola traer la pestaña al frente y dejar que envíes tú."""
    _no_docker()
    attempt = _get(session, attempt_id)
    if attempt.status not in REVIEWABLE:
        raise ApplierError("invalid_state", f"No se puede abrir el intento en «{attempt.status}».")
    tasks.enqueue(session, "apply_focus", {"attempt_id": attempt_id})
    return view(session, attempt)


def run_focus(attempt_id: int) -> dict[str, Any]:
    """Tarea `apply_focus`. Si la pestaña se perdió, abre la URL de nuevo (sin rellenar)."""
    with session_scope() as session:
        attempt = _get(session, attempt_id)
        job_id, url = attempt.job_id, attempt.url

    def _focus(state: BrowserState) -> bool:
        page = state.page_for(attempt_id)
        reopened = page is None
        if page is None:
            page = state.new_page(attempt_id, job_id)
            page.goto(url, wait_until="domcontentloaded")
        else:
            # Si la página navegó, ya no tiene el bloqueo.
            with contextlib.suppress(Exception):
                guard.release_submit_block(page)
        page.bring_to_front()
        return reopened

    reopened = get_host().call(_focus)
    with session_scope() as session:
        attempt = _get(session, attempt_id)
        token_unused = attempt.token_hash is not None and attempt.token_used_at is None
        if token_unused:
            attempt.token_hash = None  # terminas tú: una confirmación pendiente ya no vale
        if reopened:
            attempt.error = "La pestaña preparada se había cerrado: se ha abierto sin rellenar."
        _touch(attempt, "manual")
    return {"attempt_id": attempt_id, "reopened": reopened}


_MANUAL_CHANNEL = {
    "linkedin": "linkedin_manual",
    "board": "portal_manual",
    "unknown": "portal_manual",
}


def mark_manual_done(session: Session, job_id: int) -> events.AddEventResult:
    """«Marcar como enviada» tras terminar tú: `applied_manually` con el canal de la web."""
    attempt = latest(session, job_id)
    if attempt is not None and attempt.status in ACTIVE:
        raise ApplierError(
            "busy", "El navegador está trabajando en esta candidatura: espera a que termine."
        )
    channel = _MANUAL_CHANNEL.get(attempt.platform, "ats_form") if attempt else "portal_manual"
    result = events.add_user_event(session, job_id, "applied_manually", channel=channel)
    if attempt is not None and attempt.status != "submitted":
        attempt.token_hash = None
        _touch(attempt, "manual_done")
    return result


def open_browser(session: Session) -> None:
    """«Preparar navegador»: encola abrir el navegador para que inicies tus sesiones."""
    _no_docker()
    tasks.enqueue(session, "browser_open", {})


def _start_page() -> str:
    """La página de inicio del navegador de CandidatAI: para qué sirve y enlaces a los portales
    para iniciar sesión. HTML local, sin datos tuyos."""
    links = "".join(f'<li><a href="{url}">{label}</a></li>' for label, url in platforms.LOGIN_LINKS)
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        "<title>Navegador de CandidatAI</title><style>"
        "body{font:16px/1.5 system-ui,sans-serif;max-width:40rem;margin:3rem auto;padding:0 1rem;"
        "color:#1f2933}h1{font-size:1.4rem}li{margin:.3rem 0}"
        "p.note{color:#52606d;font-size:.9rem}</style></head><body>"
        "<h1>Navegador de CandidatAI</h1>"
        "<p>Aquí abre CandidatAI las ofertas y rellena los formularios. Tiene su propio perfil, "
        "separado de tu Chrome: inicia sesión en los portales que uses y las sesiones se quedan "
        "guardadas para las próximas candidaturas.</p>"
        f"<ul>{links}</ul>"
        "<p>Después, en la ficha de la oferta, pulsa «Preparar candidatura».</p>"
        '<p class="note">Las cuentas y las contraseñas las introduces tú: CandidatAI no las lee. '
        "Puedes dejar esta ventana abierta.</p></body></html>"
    )


def run_browser_open() -> dict[str, Any]:
    """Tarea `browser_open`: abre el navegador (o lo trae al frente), con la página de inicio si
    no hay nada abierto."""

    def _open(state: BrowserState) -> None:
        context = state.ensure_context()
        pages = [p for p in context.pages if not p.is_closed()]
        page = pages[0] if pages else context.new_page()
        if page.url == "about:blank":
            page.set_content(_start_page())
        page.bring_to_front()

    get_host().call(_open)
    return {"opened": True}


# --- Arranque del worker --------------------------------------------------------------------


def recover_interrupted(session: Session, attempt_ids: list[int]) -> int:
    """Intentos cuyas tareas quedaron a medias al cerrarse el worker. Nunca se repiten: un envío
    a medias queda `submit_unconfirmed` (míralo en la web) y un rellenado, `failed`."""
    count = 0
    for attempt_id in attempt_ids:
        attempt = session.get(ApplicationAttempt, attempt_id)
        if attempt is None:
            continue
        if attempt.status == "submitting":
            attempt.error = "El worker se cerró durante el envío: comprueba en la web si llegó."
            _touch(attempt, "submit_unconfirmed")
            count += 1
        elif attempt.status in ("queued", "filling"):
            attempt.error = "El worker se cerró antes de terminar: vuelve a preparar."
            _touch(attempt, "failed")
            count += 1
    return count
