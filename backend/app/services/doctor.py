"""Comprobaciones del entorno local para `cai doctor`."""

import contextlib
import os
import shutil
import sys
import tempfile
import time
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.core.config import LEGACY_DB_FILENAME, LEGACY_ENV_PREFIX, REPO_ROOT, Settings
from app.services.documents import pdf

if TYPE_CHECKING:
    from app.services.ingestion.email.mailboxes import ImapFactory

MIN_PYTHON = (3, 12)
BUILTIN_TEMPLATES_DIR = REPO_ROOT / "templates"


class CheckStatus(StrEnum):
    OK = "ok"
    WARN = "warn"
    ERROR = "error"


class CheckResult(BaseModel):
    name: str
    status: CheckStatus
    detail: str


class DoctorReport(BaseModel):
    checks: list[CheckResult]

    @property
    def ok(self) -> bool:
        return all(c.status != CheckStatus.ERROR for c in self.checks)


def check_python(version: tuple[int, ...] | None = None) -> CheckResult:
    if version is None:
        version = tuple(sys.version_info[:3])
    shown = ".".join(str(n) for n in version)
    if version[:2] >= MIN_PYTHON:
        return CheckResult(name="Python", status=CheckStatus.OK, detail=shown)
    wanted = ".".join(str(n) for n in MIN_PYTHON)
    return CheckResult(
        name="Python", status=CheckStatus.ERROR, detail=f"{shown}; se necesita {wanted} o superior"
    )


def check_data_dir(data_dir: Path) -> CheckResult:
    name = "Directorio de datos"
    if not data_dir.is_dir():
        return CheckResult(name=name, status=CheckStatus.ERROR, detail=f"{data_dir} no existe")
    try:
        with tempfile.TemporaryFile(dir=data_dir):
            pass
    except OSError as exc:
        return CheckResult(
            name=name, status=CheckStatus.ERROR, detail=f"{data_dir} no es escribible: {exc}"
        )
    return CheckResult(name=name, status=CheckStatus.OK, detail=f"{data_dir} (escribible)")


def legacy_env_names(env_file: Path | None = None) -> list[str]:
    """Variables `JH_*` de antes de la fase 23 que siguen en el entorno o en `.env` (solo los
    nombres: los valores no se leen aquí)."""
    from dotenv import dotenv_values

    names = {n.upper() for n in os.environ if n.upper().startswith(LEGACY_ENV_PREFIX)}
    env_file = env_file or REPO_ROOT / ".env"
    if env_file.is_file():
        names |= {
            n.upper() for n in dotenv_values(env_file) if n.upper().startswith(LEGACY_ENV_PREFIX)
        }
    return sorted(names)


def check_legacy_names(settings: Settings, env_file: Path | None = None) -> CheckResult:
    """Lo que queda del nombre anterior (Job Hunter, fase 23): sigue funcionando, pero conviene
    renombrarlo."""
    name = "Nombres de antes de CandidatAI"
    problems = []
    if legacy := legacy_env_names(env_file):
        renamed = ", ".join(f"{n} → CAI_{n.removeprefix(LEGACY_ENV_PREFIX)}" for n in legacy)
        problems.append(f"variables con el prefijo antiguo (se leen igual; renómbralas): {renamed}")
    if settings.uses_legacy_db:
        problems.append(
            f"se usa data/{LEGACY_DB_FILENAME}; para el nombre nuevo, con la app parada, "
            "renómbrala a candidatai.db"
        )
    if problems:
        return CheckResult(name=name, status=CheckStatus.WARN, detail="; ".join(problems))
    return CheckResult(name=name, status=CheckStatus.OK, detail="ninguno")


def check_soffice(configured: Path | None) -> CheckResult:
    name = "LibreOffice"
    path = pdf.find_soffice(configured)
    if path is not None:
        return CheckResult(name=name, status=CheckStatus.OK, detail=str(path))
    if configured is not None:
        detail = f"SOFFICE_PATH apunta a {configured}, que no existe"
    else:
        detail = "no encontrado; instálalo o define SOFFICE_PATH (necesario para los PDF)"
    return CheckResult(name=name, status=CheckStatus.WARN, detail=detail)


def check_cv_templates(builtin_dir: Path, user_dir: Path) -> CheckResult:
    """Plantillas de CV integradas (`templates/`) y del usuario (`data/templates/`). ADR-014."""
    from app.core.policies import get_policies
    from app.services.documents import templates

    name = "Plantillas de CV"
    found, invalid = templates.list_templates(builtin_dir, user_dir)
    builtin = [t.id for t in found if t.path.parent == builtin_dir]
    own = [t.id for t in found if t.path.parent != builtin_dir]
    fallback = get_policies().cv.fallback_template
    parts = [f"integradas: {', '.join(builtin) or 'ninguna'}"]
    if own:
        parts.append(f"tuyas: {', '.join(own)}")
    problems = []
    if invalid:
        problems.append(f"no válidas: {', '.join(i.id for i in invalid)} (cai templates list)")
    if fallback not in [t.id for t in found]:
        problems.append(
            f"falta «{fallback}», la de reserva: regenérala con scripts/build_builtin_templates.py"
        )
    letter_fallback = get_policies().cover_letter.fallback_template
    letters, _ = templates.list_templates(builtin_dir, user_dir, kind="letter")
    if letter_fallback not in [t.id for t in letters]:
        problems.append(
            f"falta «{letter_fallback}», la carta de reserva: regenérala con "
            "scripts/build_builtin_templates.py"
        )
    status = CheckStatus.WARN if problems else CheckStatus.OK
    return CheckResult(name=name, status=status, detail="; ".join(parts + problems))


def check_pdf_conversion() -> CheckResult:
    """Renderiza `ats-simple` con el perfil demo y lo convierte a PDF de verdad (tarda unos s)."""
    from app.core.policies import get_policies
    from app.services.documents import templates
    from app.services.documents.preview import render_preview
    from app.services.profile import EXAMPLE_PATH, load_from_yaml

    name = "Conversión a PDF"
    converter = pdf.converter_name()
    if converter is None:
        return CheckResult(
            name=name,
            status=CheckStatus.WARN,
            detail="sin LibreOffice ni Word: no se pueden generar los PDF de los CVs",
        )
    fallback = get_policies().cv.fallback_template
    try:
        template = templates.get(fallback)
    except templates.TemplateNotFoundError as exc:
        return CheckResult(name=name, status=CheckStatus.WARN, detail=str(exc))
    workdir = Path(tempfile.mkdtemp(prefix="cai-doctor-"))
    start = time.monotonic()
    try:
        output = render_preview(template, load_from_yaml(EXAMPLE_PATH), workdir / "doctor.pdf")
        info = pdf.read_pdf(output)
    except Exception as exc:  # cualquier fallo del conversor se enseña tal cual
        return CheckResult(
            name=name, status=CheckStatus.ERROR, detail=f"{converter}: {exc}".strip()
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    seconds = time.monotonic() - start
    detail = f"{converter}: «{fallback}» → PDF de {info.pages} pág. en {seconds:.0f} s"
    missing = pdf.missing_fonts(template.meta.fonts, info.fonts)
    if missing:
        detail += f"; falta la fuente {', '.join(missing)} y el PDF usa otra"
        return CheckResult(name=name, status=CheckStatus.WARN, detail=detail)
    return CheckResult(name=name, status=CheckStatus.OK, detail=detail)


def check_photo(profile_path: Path, data_dir: Path) -> CheckResult:
    """Avisa si el perfil puede pedir foto (plantilla con foto y política que la deja) y no hay."""
    from app.services import profile as profile_service
    from app.services.documents import photo, templates

    name = "Foto del CV"
    if not profile_path.is_file():
        return CheckResult(name=name, status=CheckStatus.OK, detail="sin perfil: no se comprueba")
    try:
        profile = profile_service.load_from_yaml(profile_path)
    except Exception as exc:  # perfil a medio escribir: lo explica `cai profile validate`
        detail = f"no se puede leer el perfil ({type(exc).__name__}); usa cai profile validate"
        return CheckResult(name=name, status=CheckStatus.WARN, detail=detail)

    found = photo.find_photo(profile, data_dir)
    if found is not None:
        return CheckResult(name=name, status=CheckStatus.OK, detail=str(found))
    prefs = profile.preferences.cv
    policy = prefs.photo_policy
    wanted = [prefs.default_template] if prefs.default_template else []
    wanted += [rule.use for rule in prefs.template_rules]
    with_photo = []
    for template_id in dict.fromkeys(wanted):
        try:
            if templates.get(template_id).meta.photo.supported:
                with_photo.append(template_id)
        except templates.TemplateNotFoundError:
            continue
    if with_photo and (policy.default or any(policy.by_country.values())):
        detail = (
            f"tu perfil usa {', '.join(with_photo)}, con foto, pero no hay "
            f"data/{prefs.photo_file} ni data/photo.*: esos CVs saldrán sin foto"
        )
        return CheckResult(name=name, status=CheckStatus.WARN, detail=detail)
    return CheckResult(name=name, status=CheckStatus.OK, detail="tus plantillas no piden foto")


HTML_CHECK_TEMPLATE = "moderna-2col"
CHROMIUM_INSTALL = "uv run --directory backend playwright install chromium"


def check_html_engine() -> CheckResult:
    """Motor html: Chromium de Playwright imprime `moderna-2col` sin salir a la red."""
    from app.services.documents import preview, templates
    from app.services.documents.engines import html as html_engine

    name = "Motor html (Chromium)"
    try:
        template = templates.get(HTML_CHECK_TEMPLATE)
    except templates.TemplateNotFoundError as exc:
        return CheckResult(name=name, status=CheckStatus.WARN, detail=str(exc))
    requests: list[tuple[str, bool]] = []
    workdir = Path(tempfile.mkdtemp(prefix="cai-doctor-"))
    start = time.monotonic()
    try:
        output = html_engine.render_pdf(
            template,
            preview.demo_context(),
            workdir / "doctor.pdf",
            template.meta.page.size,
            on_request=lambda url, served: requests.append((url, served)),
        )
        info = pdf.read_pdf(output)
    except html_engine.ChromiumUnavailableError:
        return CheckResult(
            name=name,
            status=CheckStatus.WARN,
            detail=f"Chromium no instalado: ejecuta `{CHROMIUM_INSTALL}` (plantillas html)",
        )
    except Exception as exc:  # cualquier fallo de Chromium se enseña tal cual
        return CheckResult(name=name, status=CheckStatus.ERROR, detail=str(exc))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    outside = [url for url, _served in requests if not url.startswith(html_engine.ORIGIN + "/")]
    if outside:
        return CheckResult(
            name=name,
            status=CheckStatus.ERROR,
            detail=f"«{HTML_CHECK_TEMPLATE}» pidió recursos de fuera: {', '.join(outside[:3])}",
        )
    seconds = time.monotonic() - start
    detail = f"«{HTML_CHECK_TEMPLATE}» → PDF de {info.pages} pág. sin red en {seconds:.0f} s"
    missing = pdf.missing_fonts(template.meta.fonts, info.fonts)
    if missing:
        detail += f"; falta la fuente {', '.join(missing)} y el PDF usa otra"
        return CheckResult(name=name, status=CheckStatus.WARN, detail=detail)
    return CheckResult(name=name, status=CheckStatus.OK, detail=detail)


def check_embeddings(settings: Settings) -> CheckResult:
    from app.core.policies import get_policies
    from app.services.matching import embeddings

    name = "Embeddings"
    reason = embeddings.unavailable_reason()
    if reason is not None:
        detail = f"{reason} El score se calcula sin similitud semántica."
        return CheckResult(name=name, status=CheckStatus.WARN, detail=detail)
    model = get_policies().scoring.semantic.model
    return CheckResult(
        name=name, status=CheckStatus.OK, detail=f"{model} (caché en {settings.models_dir})"
    )


def check_connectors(settings: Settings) -> CheckResult:
    """Conectores de ofertas (fase 09): los ATS no necesitan nada; InfoJobs y Adzuna son
    opcionales y van con claves en `.env`. Una clave sin su pareja es un aviso."""
    from app.core.policies import get_policies

    name = "Conectores de ofertas"
    pairs = {
        "InfoJobs": (settings.infojobs_client_id, settings.infojobs_client_secret),
        "Adzuna": (settings.adzuna_app_id, settings.adzuna_app_key),
    }
    configured = [label for label, keys in pairs.items() if all(keys)]
    half = [label for label, keys in pairs.items() if any(keys) and not all(keys)]
    policy = get_policies().connectors
    detail = (
        f"Greenhouse, Lever y Ashby listos; portales con claves: "
        f"{', '.join(configured) or 'ninguno (opcionales)'}; ingesta diaria a las "
        f"{policy.daily_at} ({policy.timezone}) con `cai worker`"
    )
    if half:
        detail += f". Falta una de las dos claves de {', '.join(half)} en `.env`"
        return CheckResult(name=name, status=CheckStatus.WARN, detail=detail)
    return CheckResult(name=name, status=CheckStatus.OK, detail=detail)


def check_email_alerts(
    settings: Settings, imap_factory: "ImapFactory | None" = None
) -> CheckResult:
    """Alertas por correo (fase 09b). Con IMAP configurado, solo login y `EXAMINE` de la carpeta
    (solo lectura): no se lee ni se toca ningún correo."""
    from app.core.policies import get_policies
    from app.services.ingestion.email.mailboxes import MailboxError, connect_imap, has_local_mail

    name = "Alertas por correo"
    minutes = get_policies().email_alerts.poll_minutes
    local = has_local_mail(settings.inbox_dir)
    if not settings.imap_configured:
        partial = settings.imap_host or settings.imap_user or settings.imap_password
        if partial and settings.demo_mode:
            return CheckResult(
                name=name,
                status=CheckStatus.OK,
                detail="demo: el IMAP de `.env` no se usa (tu buzón real queda fuera); "
                "deja correos .eml en la carpeta inbox/ de la demo",
            )
        if partial:
            return CheckResult(
                name=name,
                status=CheckStatus.WARN,
                detail="IMAP a medias: faltan CAI_IMAP_HOST, CAI_IMAP_USER o CAI_IMAP_PASSWORD "
                "en `.env`",
            )
        detail = "sin IMAP (opcional); "
        detail += (
            "hay correos en data/inbox/" if local else "deja correos .eml o .mbox en data/inbox/"
        )
        return CheckResult(name=name, status=CheckStatus.OK, detail=detail)
    try:
        kwargs = {"factory": imap_factory} if imap_factory else {}
        conn = connect_imap(settings, **kwargs)
    except MailboxError as exc:
        status = CheckStatus.WARN if exc.code == "network" else CheckStatus.ERROR
        return CheckResult(name=name, status=status, detail=exc.message)
    with contextlib.suppress(Exception):
        conn.logout()
    return CheckResult(
        name=name,
        status=CheckStatus.OK,
        detail=f"IMAP en solo lectura: {settings.imap_user} en {settings.imap_host}, carpeta "
        f"«{settings.imap_folder}»; cada {minutes} min con `cai worker`",
    )


def check_email_replies(
    settings: Settings, imap_factory: "ImapFactory | None" = None
) -> CheckResult:
    """Respuestas de las empresas (fase 15): como las alertas, solo login y `EXAMINE` de su
    carpeta; no se lee ningún correo."""
    from app.services.ingestion.email.mailboxes import MailboxError, connect_imap

    name = "Respuestas por correo"
    if not settings.imap_configured:
        partial = settings.imap_host or settings.imap_user or settings.imap_password
        if partial and settings.demo_mode:
            return CheckResult(
                name=name,
                status=CheckStatus.OK,
                detail="demo: el IMAP de `.env` no se usa (tu buzón real queda fuera); "
                "deja las respuestas .eml en la carpeta inbox/respuestas/ de la demo",
            )
        return CheckResult(
            name=name,
            status=CheckStatus.OK,
            detail="sin IMAP (opcional); deja las respuestas .eml o .mbox en "
            "data/inbox/respuestas/",
        )
    folder = settings.imap_replies_folder
    try:
        kwargs = {"factory": imap_factory} if imap_factory else {}
        conn = connect_imap(settings, folder=folder, **kwargs)
    except MailboxError as exc:
        status = CheckStatus.WARN if exc.code == "network" else CheckStatus.ERROR
        return CheckResult(name=name, status=status, detail=exc.message)
    with contextlib.suppress(Exception):
        conn.logout()
    return CheckResult(
        name=name,
        status=CheckStatus.OK,
        detail=f"carpeta «{folder}» en solo lectura; solo se descargan los correos de las "
        "empresas de tus candidaturas enviadas",
    )


def check_capture(settings: Settings) -> CheckResult:
    """Botón «Enviar a CandidatAI» (fase 09b): token creado e id de la extensión aceptada."""
    from app.services.capture import token_configured

    name = "Botón de captura"
    if not token_configured(settings):
        return CheckResult(
            name=name,
            status=CheckStatus.OK,
            detail="sin configurar (opcional): carga extension/ en el navegador y ejecuta "
            "`cai capture token`",
        )
    return CheckResult(
        name=name,
        status=CheckStatus.OK,
        detail=f"token creado; acepta la extensión {settings.capture_extension_id}",
    )


def run_doctor(settings: Settings) -> DoctorReport:
    return DoctorReport(
        checks=[
            check_python(),
            check_data_dir(settings.data_dir),
            check_legacy_names(settings),
            check_soffice(settings.soffice_path),
            check_cv_templates(BUILTIN_TEMPLATES_DIR, settings.user_templates_dir),
            check_pdf_conversion(),
            check_html_engine(),
            check_photo(settings.data_dir / "profile.yaml", settings.data_dir),
            check_embeddings(settings),
            check_connectors(settings),
            check_email_alerts(settings),
            check_email_replies(settings),
            check_capture(settings),
        ]
    )
