"""Botón «Enviar a CandidatAI» (fase 09b, `docs/FUENTES_OFERTAS.md` §Botón).

La extensión manda lo que el usuario está viendo (URL, título, descripción o el texto que haya
seleccionado) a `POST /capture`. Aquí:

1. se identifica la oferta (`platforms.detect`);
2. si era un resumen de una alerta (`pending_detail`), se completa con el texto y pasa a
   `pending_extraction` (`detail_captured`), sin crear otra oferta;
3. si ya estaba completa (por identidad, URL o huella), se dice y no se toca;
4. si no, se da de alta con una fuente `browser_capture`.

Todo lo capturado es contenido no confiable: pasa por la detección de riesgo, también el HTML del
bloque de la descripción (texto oculto).

El token se genera con `cai capture token` y solo se guarda su sha256 en `data/capture_token`.
"""

import hashlib
import hmac
import secrets
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import Application, Company, Job, Source
from app.services import ingest, platforms
from app.services.events import record
from app.services.pipeline import Actor, EventType, Stage
from app.services.untrusted import assess

SOURCE_KIND = "browser_capture"
SOURCE_NAME = "Botón «Enviar a CandidatAI»"
MIN_CAPTURE_CHARS = 200  # una selección corta vale, pero no un título suelto
MAX_TEXT_CHARS = 100_000
MAX_HTML_CHARS = 1_000_000
MAX_STORED_URL = 2000

CaptureStatus = Literal["new", "completed", "existing"]


class CaptureNotConfiguredError(Exception):
    """No hay token creado: falta `cai capture token`."""


class CaptureInput(BaseModel):
    """Lo que manda la extensión. Todo es contenido no confiable."""

    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1, max_length=4000)
    title: str = Field(default="", max_length=500)
    text: str = Field(default="", max_length=MAX_TEXT_CHARS)
    selection: str | None = Field(default=None, max_length=MAX_TEXT_CHARS)
    company: str | None = Field(default=None, max_length=300)
    location: str | None = Field(default=None, max_length=300)
    html: str | None = Field(default=None, max_length=MAX_HTML_CHARS)  # bloque de la descripción
    site: str | None = Field(default=None, max_length=40)  # extractor usado, para depurar

    @field_validator("url")
    @classmethod
    def _http_url(cls, value: str) -> str:
        value = value.strip()
        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise ValueError("La URL debe empezar por http:// o https://.")
        return value


class CaptureResult(BaseModel):
    status: CaptureStatus
    job_id: int
    stage: Stage
    title: str
    company: str
    platform: str | None
    risk_flags: list[str]
    duplicate_of: int | None
    message: str


# --- Token -----------------------------------------------------------------------------------


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def rotate_token(settings: Settings) -> str:
    """Genera un token nuevo (el anterior deja de valer). Devuelve el token: no se vuelve a ver."""
    token = secrets.token_urlsafe(32)
    path: Path = settings.capture_token_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_digest(token) + "\n", encoding="utf-8", newline="\n")
    return token


def token_configured(settings: Settings) -> bool:
    path = settings.capture_token_path
    return path.is_file() and bool(path.read_text(encoding="utf-8").strip())


def check_token(settings: Settings, token: str | None) -> bool:
    """`True` si el token es el vigente. Lanza `CaptureNotConfiguredError` si no hay ninguno."""
    if not token_configured(settings):
        raise CaptureNotConfiguredError(
            "La captura no está configurada: ejecuta `cai capture token` y pega el token en las "
            "opciones de la extensión."
        )
    stored = settings.capture_token_path.read_text(encoding="utf-8").strip()
    return bool(token) and hmac.compare_digest(_digest(token or ""), stored)


# --- Captura ---------------------------------------------------------------------------------


def _source(session: Session) -> Source:
    source = session.scalars(select(Source).where(Source.kind == SOURCE_KIND).limit(1)).first()
    if source is None:
        source = Source(kind=SOURCE_KIND, name=SOURCE_NAME, config={}, active=True)
        session.add(source)
        session.flush()
    return source


def _clean_url(url: str, pid: platforms.PlatformId | None) -> str:
    canonical = platforms.canonical_url(pid) if pid else None
    if canonical:
        return canonical
    parts = urlsplit(url)
    clean = urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
    if len(clean) > MAX_STORED_URL:  # la columna `jobs.url` es de 2000
        clean = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))[:MAX_STORED_URL]
    return clean


def _find(session: Session, pid: platforms.PlatformId | None, urls: list[str]) -> Job | None:
    if pid is not None:
        job = ingest.find_by_platform(session, pid.platform, pid.external_id)
        if job is not None:
            return job
    for url in urls:
        job = session.scalars(select(Job).where(Job.url == url).limit(1)).first()
        if job is not None:
            return job
    return None


def _stage(session: Session, job_id: int) -> Stage:
    app = session.get(Application, job_id)
    return Stage(app.stage) if app else Stage.PENDING_EXTRACTION


def _company(session: Session, job: Job) -> str:
    company = session.get(Company, job.company_id)
    return company.name if company else ""


def _result(session: Session, job: Job, status: CaptureStatus, message: str) -> CaptureResult:
    return CaptureResult(
        status=status,
        job_id=job.id,
        stage=_stage(session, job.id),
        title=job.title,
        company=_company(session, job),
        platform=job.platform,
        risk_flags=list(job.risk_flags or []),
        duplicate_of=job.duplicate_of,
        message=message,
    )


def _complete(session: Session, job: Job, text: str, data: CaptureInput) -> CaptureResult:
    """Completa un resumen de una alerta con el texto capturado."""
    risk = assess(text, data.html)
    job.raw_text = text
    job.detail_level = "full"
    job.risk_flags = [flag.value for flag in risk.flags]
    if not job.location_raw and data.location and data.location.strip():
        job.location_raw = " ".join(data.location.split())
    session.flush()
    record(
        session,
        job.id,
        EventType.DETAIL_CAPTURED,
        Actor.USER,
        {"source": SOURCE_KIND, "chars": len(text)},
    )
    if risk.risky:
        record(
            session,
            job.id,
            EventType.INJECTION_SUSPECTED,
            Actor.SYSTEM,
            {"flags": job.risk_flags, "excerpt": risk.excerpt},
        )
    return _result(
        session,
        job,
        "completed",
        "Completada: tenía el resumen de una alerta y ya está lista para extraer.",
    )


def _existing(session: Session, job: Job) -> CaptureResult:
    stage = _stage(session, job.id)
    if stage == Stage.CLOSED:
        message = "Ya estaba, pero cerrada (descartada, caducada o duplicada). Puedes reabrirla."
    else:
        message = "Ya estaba en CandidatAI."
    return _result(session, job, "existing", message)


def _require_text(text: str) -> None:
    if len(text) < MIN_CAPTURE_CHARS:
        raise ValueError(
            "No se encontró la descripción de la oferta en la página. Selecciona su texto con el "
            "ratón y vuelve a pulsar el botón."
        )


def _require_offer_text(data: CaptureInput, selection: str) -> None:
    """Para completar un resumen no vale el texto de la página entera (`main`): podría ser una
    lista de resultados y el agente extraería de ahí. Hace falta el extractor o una selección."""
    if data.site == "main" and not selection:
        raise ValueError(
            "No se reconoce la descripción en esta página. Selecciona el texto de la oferta con el "
            "ratón y vuelve a pulsar el botón."
        )


def capture(session: Session, data: CaptureInput) -> CaptureResult:
    selection = (data.selection or "").strip()
    text = ingest.clean_text(selection or data.text)
    pid = platforms.detect(data.url)
    url = _clean_url(data.url, pid)

    # Primero se busca: una oferta que ya estaba se reconoce aunque esta vez no haya descripción.
    found = _find(session, pid, list(dict.fromkeys([url, data.url])))
    if found is not None and _stage(session, found.id) != Stage.PENDING_DETAIL:
        return _existing(session, found)
    _require_text(text)
    if found is not None:
        _require_offer_text(data, selection)
        return _complete(session, found, text, data)

    title = " ".join(data.title.split())
    company = " ".join((data.company or "").split())
    if not title:
        raise ValueError("No se encontró el título de la oferta en la página.")
    if not company:
        raise ValueError(
            "No se encontró la empresa en la página. Selecciona el texto de la oferta incluyendo "
            "el nombre de la empresa y vuelve a pulsar, o dala de alta en «Nueva oferta»."
        )
    stored = ingest.store_job(
        session,
        source=_source(session),
        title=title,
        company=company,
        text=text,
        url=url,
        location=data.location,
        posted_at=None,
        html=data.html,
        external_id=pid.external_id if pid else None,
        platform=pid.platform if pid else None,
    )
    job = session.get(Job, stored.job_id)
    assert job is not None
    if not stored.created:
        # Misma huella (empresa, título y ubicación) que una oferta ya guardada.
        if _stage(session, job.id) == Stage.PENDING_DETAIL:
            _require_offer_text(data, selection)
            return _complete(session, job, text, data)
        return _existing(session, job)
    message = "Nueva: lista para extraer."
    if job.duplicate_of is not None:
        message = (
            f"Nueva, pero parece un duplicado de la oferta {job.duplicate_of} y queda cerrada."
        )
    return _result(session, job, "new", message)
