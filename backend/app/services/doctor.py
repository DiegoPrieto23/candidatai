"""Comprobaciones del entorno local para `cai doctor`."""

import contextlib
import os
import shutil
import sys
import tempfile
import time
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel

from app.core.config import LEGACY_DB_FILENAME, LEGACY_ENV_PREFIX, REPO_ROOT, Settings
from app.services.documents import pdf

if TYPE_CHECKING:
    from app.services.agent_prefs import Resolution
    from app.services.agent_registry import AgentSpec
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
    if reason is not None and settings.in_docker:
        reason = "La imagen de Docker no la incluye (traería torch)."
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
    from app.services.ingestion.email.mailboxes import (
        MailboxError,
        connect_imap,
        has_local_mail,
        settings_account,
    )

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
        account = settings_account(settings)
        assert account is not None
        conn = connect_imap(account, **kwargs)
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
    from app.services.ingestion.email.mailboxes import MailboxError, connect_imap, settings_account

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
        account = settings_account(settings, folder)
        assert account is not None
        conn = connect_imap(account, **kwargs)
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


def check_mail_sources(imap_factory: "ImapFactory | None" = None) -> CheckResult:
    """Buzones añadidos desde la UI (fase 27.4): login y `EXAMINE` de cada uno activo, sin leer
    correos. La cuenta de `.env` ya la prueban «Alertas por correo» y «Respuestas por correo»."""
    from sqlalchemy.exc import SQLAlchemyError

    from app.core.db import session_scope
    from app.services import mail_sources

    name = "Buzones"
    try:
        with session_scope() as session:
            rows = [r for r in mail_sources.active_sources(session) if not r.from_env]
            results = [
                (row.label, mail_sources.probe_mail_source(session, row.id, imap_factory))
                for row in rows
            ]
    except SQLAlchemyError:
        return CheckResult(
            name=name, status=CheckStatus.OK, detail="sin base de datos aún: ninguno añadido"
        )
    if not results:
        return CheckResult(
            name=name,
            status=CheckStatus.OK,
            detail="ninguno añadido desde la UI (opcional: Alertas → Añadir buzón)",
        )
    failed = [f"{label}: {r.message}" for label, r in results if not r.ok]
    if failed:
        network = all(r.code == "network" for _, r in results if not r.ok)
        return CheckResult(
            name=name,
            status=CheckStatus.WARN if network else CheckStatus.ERROR,
            detail="; ".join(failed),
        )
    labels = ", ".join(label for label, _ in results)
    return CheckResult(name=name, status=CheckStatus.OK, detail=f"en solo lectura: {labels}")


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


# --- Agentes (fase 24.1) -----------------------------------------------------------------------


class AgentStatusLine(BaseModel):
    """Un agente en `cai agents doctor`: si lo tienes y qué le falta."""

    name: str
    display_name: str
    enabled: bool
    installed: bool
    version: str | None
    open_source: bool
    isolation_level: Literal["A", "B", "C"]
    missing: list[str]  # qué falta para usarlo con la app (vacío: nada)


class AgentsOverview(BaseModel):
    """Qué agentes tienes, cuál se usaría hoy y por qué, y qué falta para los demás."""

    error: str | None = None  # el manifiesto no es válido
    selected: str | None = None
    selected_reason: str = ""
    background: str | None = None  # con qué agente iría «En segundo plano»
    background_reason: str | None = None  # o por qué no hay
    agents: list[AgentStatusLine] = []


def _missing(spec: "AgentSpec", installed: bool, platform: str) -> list[str]:
    missing = []
    if spec.info.note:
        missing.append(f"no se recomienda: {spec.info.note}")
    if not installed:
        how = getattr(spec.info.install, platform) or spec.info.homepage
        missing.append(f"falta instalarlo: {how}")
    if spec.config == "none" and not spec.info.note:
        missing.append(
            "sin configuración generada: solo compatible vía AGENTS.md, pidiéndole los skills en "
            f"lenguaje natural y con el nivel {spec.capabilities.isolation_level} de aislamiento"
        )
    elif not spec.launchable:
        missing.append("sin `launch` en el manifiesto: los botones de la UI copian la orden")
    if spec.config == "generated" and not spec.capabilities.headless:
        missing.append(
            "sin «En segundo plano»: no tiene un `launch.headless` completo en el manifiesto"
        )
    return missing


def _effective_agents() -> tuple["Resolution", "Resolution"]:
    """El agente general en terminal y en segundo plano, con las preferencias de la UI (fase 24.4)
    si la base de datos ya existe."""
    from sqlalchemy.exc import SQLAlchemyError

    from app.core.db import session_scope
    from app.services import agent_launch

    try:
        with session_scope() as session:
            return agent_launch.choose(session)[1], agent_launch.choose(session, mode="background")[
                1
            ]
    except SQLAlchemyError:
        return agent_launch.choose(None)[1], agent_launch.choose(None, mode="background")[1]


def agents_overview(settings: Settings, refresh: bool = False) -> AgentsOverview:
    from app.services import agent_launch, agent_registry

    try:
        specs = agent_registry.load()
        listed = agent_registry.list_agents(refresh=refresh).agents
    except agent_registry.ManifestError as exc:
        return AgentsOverview(error=str(exc))
    platform = agent_registry.current_platform()
    lines = [
        AgentStatusLine(
            name=entry.name,
            display_name=entry.info.display_name,
            enabled=entry.enabled,
            installed=entry.installed,
            version=entry.version,
            open_source=entry.info.open_source,
            isolation_level=entry.capabilities.isolation_level,
            missing=_missing(specs[entry.name], entry.installed, platform),
        )
        for entry in listed
    ]
    picked, background = _effective_agents()
    if picked.agent and not picked.blocked:
        reason = {
            "env": f"porque CAI_AGENT={settings.agent}",
            "first_installed": "el primero del manifiesto que está habilitado e instalado",
        }.get(picked.reason, picked.reason_text)
        if model := agent_launch.model_label(picked.model, picked.preset):
            reason += f", con {model}"
    else:
        reason = picked.blocked or ""
    return AgentsOverview(
        selected=picked.agent if not picked.blocked else None,
        selected_reason=reason,
        background=background.agent if not background.blocked else None,
        background_reason=background.blocked,
        agents=lines,
    )


def check_agents(settings: Settings) -> CheckResult:
    """Agentes de IA (fase 24.1): cuál usarían los botones y cuáles más tienes."""
    name = "Agentes"
    overview = agents_overview(settings)
    if overview.error:
        return CheckResult(name=name, status=CheckStatus.ERROR, detail=overview.error)
    by_name = {line.name: line for line in overview.agents}
    others = [
        line.display_name
        for line in overview.agents
        if line.installed and line.name != overview.selected
    ]
    also = f"; también instalados: {', '.join(others)}" if others else ""
    more = "; detalle con `cai agents doctor`"
    if overview.selected is None:
        detail = f"ninguno disponible ({overview.selected_reason}){also}{more}"
        return CheckResult(name=name, status=CheckStatus.WARN, detail=detail)
    line = by_name[overview.selected]
    version = f" {line.version}" if line.version else ""
    background = "con «En segundo plano»" if overview.background else "sin «En segundo plano»"
    detail = f"se usa {line.display_name}{version}, {background}{also}{more}"
    return CheckResult(name=name, status=CheckStatus.OK, detail=detail)


def check_docker(
    settings: Settings, is_mount: Callable[[Path], bool] = os.path.ismount
) -> list[CheckResult]:
    """Sección «Docker» (fase 26.3, ADR-042): solo con `CAI_IN_DOCKER=1`. Dónde escucha la API,
    dónde quedan tus datos, cómo llega tu agente y qué no funciona dentro."""
    from app.services import container

    if not settings.in_docker:
        return []
    if container.in_container():
        api = CheckResult(
            name="Docker · API",
            status=CheckStatus.OK,
            detail="escucha en el contenedor; el compose la publica solo en 127.0.0.1 de tu equipo",
        )
    else:
        api = CheckResult(
            name="Docker · API",
            status=CheckStatus.WARN,
            detail="CAI_IN_DOCKER=1 fuera de un contenedor: la API sigue solo en 127.0.0.1. "
            "Quítalo de tu .env si no usas Docker",
        )
    mounts = (container.DATA_MOUNT, container.DEMO_MOUNT)
    if settings.data_dir in mounts and is_mount(settings.data_dir):
        data = CheckResult(
            name="Docker · datos",
            status=CheckStatus.OK,
            detail=f"en el volumen montado en {settings.data_dir.as_posix()}: sobreviven al "
            "contenedor (copia de seguridad: ver «Con Docker» en la guía)",
        )
    else:
        data = CheckResult(
            name="Docker · datos",
            status=CheckStatus.WARN,
            detail=f"{settings.data_dir} no es un volumen: se pierden al borrar el contenedor. "
            "Monta uno en /data (lo hace docker-compose.yml)",
        )
    agent = CheckResult(
        name="Docker · tu agente",
        status=CheckStatus.OK,
        detail=f"fuera del contenedor. Por MCP: `{container.MCP_COMMAND}`; sin MCP: "
        f"`{container.CLI_COMMAND} … --json`",
    )
    limits = CheckResult(
        name="Docker · límites",
        status=CheckStatus.OK,  # esperados: no se arreglan dentro (ver la guía)
        detail="los botones «en tu agente» copian la orden; sin «En segundo plano»; candidatura "
        "asistida: abre la oferta en tu navegador y envíala tú; sin LibreOffice (motor html)",
    )
    return [api, data, agent, limits]


DOCKER_NO_SOFFICE = CheckResult(
    name="LibreOffice",
    status=CheckStatus.OK,
    detail="no viene en la imagen de Docker: los PDF salen con las plantillas html (motor html)",
)


def run_doctor(settings: Settings) -> DoctorReport:
    docker = settings.in_docker
    # En Docker no hay LibreOffice a propósito, ni agentes (están fuera del contenedor): lo
    # explica la sección «Docker» en vez de dar avisos que no se pueden arreglar dentro.
    soffice = [] if docker else [check_soffice(settings.soffice_path)]
    conversion = [DOCKER_NO_SOFFICE] if docker else [check_pdf_conversion()]
    agents = [] if docker else [check_agents(settings)]
    return DoctorReport(
        checks=[
            check_python(),
            check_data_dir(settings.data_dir),
            check_legacy_names(settings),
            *soffice,
            check_cv_templates(BUILTIN_TEMPLATES_DIR, settings.user_templates_dir),
            *conversion,
            check_html_engine(),
            check_photo(settings.data_dir / "profile.yaml", settings.data_dir),
            check_embeddings(settings),
            check_connectors(settings),
            check_email_alerts(settings),
            check_email_replies(settings),
            check_mail_sources(),
            check_capture(settings),
            *agents,
            *check_docker(settings),
        ]
    )
