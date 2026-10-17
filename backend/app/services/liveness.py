"""¿Sigue abierta? (fase 16): comprobación ligera de la URL de una oferta.

- **ATS** (Greenhouse, Lever, Ashby), cuando la URL o la fuente dan el tablero y el id: su API
  pública. Greenhouse y Lever responden 404 a una oferta retirada; en Ashby, la oferta deja de
  aparecer en el tablero.
- **Resto**: un GET sin cookies ni JavaScript, con las mismas defensas que el alta por URL (nada
  local ni de red privada, también tras redirecciones) y leyendo como mucho `liveness.max_bytes`.
  Cuenta como posible cierre: HTTP 404/410, una redirección que pierde la oferta (vuelve a una
  lista o a la portada), una frase de `liveness.closed_phrases` o un `validThrough` ya pasado.
- 401/403/429/5xx, fallos de red o una página de login dan `unknown`: no avisan.
- **LinkedIn nunca** (ADR-016): `skipped`.

El resultado va a `jobs.signals` (`services/signals.py`). Nunca cierra la oferta: la primera vez
que la detecta registra `closure_suspected` (no cambia la etapa) y la UI propone descartarla. Si el
usuario dice «Sigue abierta», ese mismo motivo ya no vuelve a avisar.
"""

import ipaddress
import re
import socket
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import lxml.html
from lxml.etree import ParserError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.models import Application, Job, Source
from app.models.base import utcnow
from app.schemas.sources import KIND_LABELS
from app.services import ingest, platforms
from app.services.events import JobNotFoundError, record
from app.services.ingestion.base import make_client
from app.services.normalize import fold, normalize_title
from app.services.pipeline import Actor, EventType, Stage
from app.services.signals import (
    ClosedSignal,
    LivenessCheck,
    LivenessStatus,
    OpenConfirmed,
    read,
    set_signal,
)

# ATS con comprobación por API; el resto de ATS (fase 25.1) se comprueban por su página.
_API_KINDS = frozenset({"greenhouse", "lever", "ashby"})
# Etapas que el worker revisa cada día (las que van camino de un CV o de enviarse).
DAILY_STAGES = (Stage.APPROVED, Stage.CV_READY)

_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_GREENHOUSE_HOSTS = frozenset({"boards.greenhouse.io", "job-boards.greenhouse.io"})
_GREENHOUSE_PATH = re.compile(r"^/([^/]+)/jobs/(\d{1,20})(?:/|$)")
_LEVER_HOSTS = {"jobs.lever.co": "global", "jobs.eu.lever.co": "eu"}
_ASHBY_HOST = "jobs.ashbyhq.com"
_UUID_PATH = re.compile(rf"^/([^/]+)/({_UUID})(?:/|$)")
_NUMERIC_ID = re.compile(r"^\d{1,20}$")
_UUID_ID = re.compile(rf"^{_UUID}$")

GREENHOUSE_JOB = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs/{job_id}"
LEVER_JOB = {
    "global": "https://api.lever.co/v0/postings/{slug}/{job_id}",
    "eu": "https://api.eu.lever.co/v0/postings/{slug}/{job_id}",
}
ASHBY_BOARD = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


class LivenessResult(BaseModel):
    status: LivenessStatus
    reason: str | None = None  # en `possibly_closed`, un `ClosedReason`
    detail: str = ""
    http_status: int | None = None


class LivenessView(BaseModel):
    job_id: int
    status: LivenessStatus
    reason: str | None
    detail: str
    checked_at: datetime | None
    cached: bool  # resultado de una comprobación reciente: no se ha vuelto a consultar
    possibly_closed: ClosedSignal | None  # el aviso vigente, si lo hay
    suppressed: bool  # el usuario dijo «Sigue abierta» por este mismo motivo
    message: str


def _open(detail: str, status: int | None = None) -> LivenessResult:
    return LivenessResult(status="open", detail=detail, http_status=status)


def _closed(reason: str, detail: str, status: int | None = None) -> LivenessResult:
    return LivenessResult(
        status="possibly_closed", reason=reason, detail=detail, http_status=status
    )


def _unknown(detail: str, status: int | None = None) -> LivenessResult:
    return LivenessResult(status="unknown", detail=detail, http_status=status)


# --- ATS ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class AtsTarget:
    kind: str  # greenhouse | lever | ashby
    slug: str
    job_id: str
    region: str = "global"


def _valid_target(kind: str, slug: str, job_id: str, region: str = "global") -> AtsTarget | None:
    id_pattern = _NUMERIC_ID if kind == "greenhouse" else _UUID_ID
    if kind == "ashby":  # Ashby no garantiza que el id sea un UUID (ver `ingestion/ashby.py`)
        id_pattern = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
    if not _SLUG.match(slug) or ".." in slug or not id_pattern.match(job_id):
        return None
    return AtsTarget(kind, slug, job_id, region)


def ats_target(
    url: str | None,
    source_kind: str | None = None,
    source_config: dict[str, Any] | None = None,
    external_id: str | None = None,
) -> AtsTarget | None:
    """Tablero e id de ATS de una oferta: por su URL o, si viene de un conector de ATS, por la
    fuente (el `absolute_url` de Greenhouse puede ser la web de la empresa)."""
    parts = urlsplit(url or "")
    host = (parts.hostname or "").lower()
    if host in _GREENHOUSE_HOSTS and (m := _GREENHOUSE_PATH.match(parts.path)):
        return _valid_target("greenhouse", m.group(1), m.group(2))
    if host in _LEVER_HOSTS and (m := _UUID_PATH.match(parts.path)):
        return _valid_target("lever", m.group(1), m.group(2).lower(), _LEVER_HOSTS[host])
    if host == _ASHBY_HOST and (m := _UUID_PATH.match(parts.path)):
        return _valid_target("ashby", m.group(1), m.group(2).lower())
    config = source_config or {}
    slug = config.get("slug")
    if source_kind in _API_KINDS and isinstance(slug, str) and external_id:
        region = str(config.get("region") or "global")
        return _valid_target(source_kind, slug, external_id, region if region == "eu" else "global")
    return None


def _ashby_ids(item: dict[str, Any]) -> set[str]:
    ids = {str(item["id"]).lower()} if item.get("id") else set()
    job_url = item.get("jobUrl")
    if isinstance(job_url, str):
        ids.add(urlsplit(job_url).path.rstrip("/").rsplit("/", 1)[-1].lower())
    return ids


def check_ats(target: AtsTarget, client: httpx.Client) -> LivenessResult:
    label = KIND_LABELS.get(target.kind, target.kind)
    if target.kind == "greenhouse":
        url = GREENHOUSE_JOB.format(slug=target.slug, job_id=target.job_id)
    elif target.kind == "lever":
        url = LEVER_JOB[target.region].format(slug=target.slug, job_id=target.job_id)
    else:
        url = ASHBY_BOARD.format(slug=target.slug)
    try:
        response = client.get(url)
    except httpx.HTTPError as exc:
        return _unknown(f"no se pudo consultar la API de {label} ({type(exc).__name__})")
    status = response.status_code
    if status == 404:
        what = "el tablero ya no existe" if target.kind == "ashby" else "la oferta ya no está"
        return _closed("ats_missing", f"{label} dice que {what} (HTTP 404)", status)
    if status != 200:
        return _unknown(f"la API de {label} respondió HTTP {status}", status)
    if target.kind != "ashby":
        return _open(f"{label} la sigue publicando", status)
    try:
        data = response.json()
        jobs = data["jobs"]
        listed = [j for j in jobs if isinstance(j, dict) and j.get("isListed") is not False]
    except (ValueError, KeyError, TypeError):
        return _unknown("la API de Ashby devolvió un formato inesperado", status)
    if any(target.job_id.lower() in _ashby_ids(j) for j in listed):
        return _open("Ashby la sigue publicando", status)
    return _closed("ats_missing", "ya no aparece en su tablero de Ashby", status)


# --- Página ------------------------------------------------------------------------------------


def _lost_identity(original: str, final: str) -> bool:
    """La redirección ha perdido la oferta: otra id de plataforma, la portada, una lista (un tramo
    superior de la ruta) o una página de error (`?error=true`, como hace Greenhouse)."""
    pid = platforms.detect(original)
    if pid is not None:
        new = platforms.detect(final)
        return new is None or new.external_id != pid.external_id
    before, after = urlsplit(original), urlsplit(final)
    if "error" in parse_qs(after.query):
        return True
    old_path, new_path = before.path.rstrip("/"), after.path.rstrip("/")
    if old_path == new_path:
        return False  # solo cambia el esquema, el dominio o los parámetros
    return new_path == "" or old_path.startswith(new_path + "/")


def _visible_text(doc: Any) -> str:
    for node in doc.xpath("//script|//style|//noscript|//template"):
        node.drop_tree()  # conserva el texto que va detrás
    # Con espacios entre nodos: «<h1>Oferta</h1><p>La oferta…» no debe quedar «OfertaLa oferta».
    return fold(" ".join(doc.itertext()))


def _phrase_in(text: str, phrases: list[str]) -> str | None:
    padded = f" {text} "
    for phrase in phrases:
        folded = fold(phrase)
        if folded and f" {folded} " in padded:
            return phrase
    return None


def closed_phrase(text: str, platform: str | None) -> str | None:
    """La frase de «oferta cerrada» que aparece en el texto (ya plegado), si hay alguna."""
    phrases = get_policies().liveness.closed_phrases
    return _phrase_in(text, [*phrases.get("any", []), *phrases.get(platform or "", [])])


def _shows_title(text: str, title: str) -> bool:
    """Todas las palabras del título normalizado aparecen en el texto (ya plegado)."""
    words = fold(normalize_title(title)).split()
    return bool(words) and set(words) <= set(text.split())


def _expired(doc: Any, now: datetime) -> datetime | None:
    posting = ingest.find_job_posting(doc)
    valid = ingest.parse_date(posting.get("validThrough")) if posting else None
    # Un día de margen: muchas webs ponen solo la fecha (medianoche).
    return valid if valid is not None and valid < now - timedelta(days=1) else None


def _resolve(host: str) -> list[str]:
    """IPs de un dominio. Aparte para poder simularlo en los tests (sin red)."""
    return [str(info[4][0]) for info in socket.getaddrinfo(host, None)]


def check_resolved(request: httpx.Request) -> None:
    """Además de `ingest.check_request` (IPs literales y `localhost`), resuelve el dominio y
    rechaza los que apuntan a la red local o privada: estas URLs vienen de alertas, correos y
    conectores (no confiables) y el worker las abre solo. Se aplica también en cada redirección.
    Queda el margen de que el DNS cambie entre esta consulta y la conexión."""
    host = request.url.host
    try:
        ipaddress.ip_address(host.strip("[]"))
        return  # IP literal: ya la ha comprobado `ingest.check_request`
    except ValueError:
        pass
    try:
        addresses = _resolve(host)
    except (OSError, UnicodeError):
        return  # sin resolución, la conexión fallará igual (y dará `unknown`)
    for address in addresses:
        try:
            ip = ipaddress.ip_address(address.split("%", 1)[0])
        except ValueError:
            continue
        if not ip.is_global:
            raise ingest.IngestError("El dominio apunta a una dirección local o de red privada.")


def check_page(url: str, now: datetime | None = None, title: str | None = None) -> LivenessResult:
    """Con `title`, «abierta» exige ver la oferta: su título en la página o un JSON-LD
    `JobPosting`. Si no, puede ser un control anti-bot o una página genérica: `unknown`."""
    now = now or utcnow()
    policy = get_policies().liveness
    headers = {
        "User-Agent": ingest.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }
    client = httpx.Client(
        timeout=httpx.Timeout(policy.timeout_seconds, connect=min(policy.timeout_seconds, 10.0)),
        headers=headers,
        follow_redirects=True,
        event_hooks={"request": [ingest.check_request, check_resolved]},
    )
    try:
        with client, client.stream("GET", url) as response:
            status, final_url = response.status_code, response.url
            redirected = bool(response.history)
            content = b""
            if status < 400:
                for chunk in response.iter_bytes():
                    content += chunk
                    if len(content) >= policy.max_bytes:
                        content = content[: policy.max_bytes]
                        break
            encoding = response.encoding or "utf-8"
    except ingest.IngestError as exc:  # LinkedIn o una dirección local, también tras redirigir
        return _unknown(f"la página lleva a un sitio que no se comprueba ({exc})")
    except (httpx.InvalidURL, UnicodeError):
        return _unknown("la URL no es válida")
    except httpx.HTTPError as exc:
        return _unknown(f"no se pudo abrir la página ({type(exc).__name__})")

    if status in (404, 410):
        return _closed(f"http_{status}", f"la página responde HTTP {status}", status)
    if status in (401, 403):
        return _unknown(f"la página bloquea el acceso (HTTP {status})", status)
    if status >= 400:
        return _unknown(f"la página respondió HTTP {status}", status)
    if redirected and _lost_identity(url, str(final_url)):
        # Solo el dominio: la URL final la elige el servidor (no confiable) y este texto llega al
        # agente y al historial.
        return _closed("redirected", f"la URL redirige a otra página de {final_url.host}", status)
    html = content.decode(encoding, errors="replace")
    if ingest.looks_like_login(final_url, html):
        return _unknown("la página pide iniciar sesión", status)
    try:
        doc = lxml.html.document_fromstring(html)
    except (ParserError, ValueError):
        return _unknown("la página no se pudo leer", status)
    # Antes de `_visible_text`, que quita los `<script>` (y con ellos el JSON-LD).
    has_posting = ingest.find_job_posting(doc) is not None
    expired = _expired(doc, now)
    text = _visible_text(doc)
    if (block := _phrase_in(text, policy.blocked_phrases)) is not None:
        return _unknown(f"la página muestra un control anti-bot («{block}»)", status)
    platform = platforms.platform_of_host(final_url.host)
    if (phrase := closed_phrase(text, platform)) is not None:
        return _closed("closed_text", f"la página dice «{phrase}»", status)
    if expired is not None:
        return _closed("expired_date", f"la oferta caducaba el {expired:%d/%m/%Y}", status)
    if title and not has_posting and not _shows_title(text, title):
        return _unknown(
            "la página no muestra la oferta (¿control anti-bot o página genérica?)", status
        )
    return _open("la página sigue publicada", status)


# --- Oferta ------------------------------------------------------------------------------------


def check_target(job: Job, source: Source | None, now: datetime | None = None) -> LivenessResult:
    """Comprueba la oferta sin tocar la BD (solo red)."""
    url = (job.url or "").strip()
    host = (urlsplit(url).hostname or "") if url else ""
    if job.platform == "linkedin" or platforms.platform_of_host(host) == "linkedin":
        return LivenessResult(
            status="skipped", detail="LinkedIn no se comprueba desde la app (ADR-016)"
        )
    target = ats_target(
        url, source.kind if source else None, source.config if source else None, job.external_id
    )
    if target is not None:
        with make_client(get_policies().liveness.timeout_seconds) as client:
            return check_ats(target, client)
    if not url:
        return LivenessResult(status="skipped", detail="la oferta no tiene URL")
    try:
        ingest.check_request(httpx.Request("GET", url))
    except ingest.IngestError as exc:
        return LivenessResult(status="skipped", detail=str(exc))
    except (httpx.InvalidURL, UnicodeError):
        return LivenessResult(status="skipped", detail="la URL de la oferta no es válida")
    return check_page(url, now, job.title)


def _stage(session: Session, job_id: int) -> Stage | None:
    app = session.get(Application, job_id)
    return Stage(app.stage) if app else None


def _message(view_status: str, detail: str, suppressed: bool, cached: bool) -> str:
    when = " (comprobación reciente)" if cached else ""
    if view_status == "open":
        return f"Sigue abierta: {detail}{when}."
    if view_status == "possibly_closed":
        if suppressed:
            return (
                f"La comprobación dice que puede estar cerrada ({detail}), pero dijiste que sigue "
                f"abierta: no se avisa{when}."
            )
        return (
            f"Puede que esté cerrada: {detail}{when}. No se ha cerrado en CandidatAI: "
            "descártala tú si lo confirmas."
        )
    if view_status == "unknown":
        return f"No se pudo comprobar: {detail}{when}."
    return f"No se comprueba: {detail}."


def _view(job: Job, cached: bool) -> LivenessView:
    signals = read(job)
    check = signals.liveness
    status: LivenessStatus = check.status if check else "unknown"
    reason = check.reason if check else None
    detail = check.detail if check else "aún no se ha comprobado"
    confirmed = signals.open_confirmed
    suppressed = (
        status == "possibly_closed"
        and signals.possibly_closed is None
        and confirmed is not None
        and confirmed.reason == reason
    )
    return LivenessView(
        job_id=job.id,
        status=status,
        reason=reason,
        detail=detail,
        checked_at=check.checked_at if check else None,
        cached=cached,
        possibly_closed=signals.possibly_closed,
        suppressed=suppressed,
        message=_message(status, detail, suppressed, cached),
    )


def apply_result(
    session: Session, job: Job, result: LivenessResult, now: datetime | None = None
) -> None:
    """Guarda el resultado en `jobs.signals` y, si es un aviso nuevo, registra
    `closure_suspected`. Nunca cierra la oferta."""
    now = now or utcnow()
    signals = read(job)
    set_signal(
        job,
        "liveness",
        LivenessCheck(
            checked_at=now,
            status=result.status,
            reason=result.reason,
            detail=result.detail,
            http_status=result.http_status,
        ),
    )
    if result.status == "open":
        # Abierta de verdad: si vuelve a cerrarse más adelante, aunque sea por el mismo motivo
        # que el usuario descartó, hay que avisar.
        set_signal(job, "possibly_closed", None)
        set_signal(job, "open_confirmed", None)
    elif result.status == "possibly_closed" and result.reason is not None:
        confirmed = signals.open_confirmed
        if confirmed is None or confirmed.reason != result.reason:
            current = signals.possibly_closed
            set_signal(
                job,
                "possibly_closed",
                ClosedSignal(
                    since=current.since if current else now,
                    checked_at=now,
                    reason=result.reason,  # type: ignore[arg-type]
                    detail=result.detail,
                    http_status=result.http_status,
                ),
            )
            stage = _stage(session, job.id)
            if current is None and stage is not None and stage != Stage.CLOSED:
                record(
                    session,
                    job.id,
                    EventType.CLOSURE_SUSPECTED,
                    Actor.SYSTEM,
                    {"reason": result.reason, "detail": result.detail},
                    occurred_at=now,
                )
    session.flush()


def check_job(
    session: Session, job_id: int, *, force: bool = False, now: datetime | None = None
) -> LivenessView:
    """Comprueba si la oferta sigue abierta. Sin `force`, si hay una comprobación de hace menos
    de `liveness.fresh_hours`, devuelve esa sin volver a consultar."""
    now = now or utcnow()
    job = session.get(Job, job_id)
    if job is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    if _stage(session, job_id) == Stage.CLOSED:
        detail = "la oferta ya está cerrada en CandidatAI"
        return LivenessView(
            job_id=job_id,
            status="skipped",
            reason=None,
            detail=detail,
            checked_at=None,
            cached=False,
            possibly_closed=read(job).possibly_closed,
            suppressed=False,
            message=_message("skipped", detail, False, False),
        )
    last = read(job).liveness
    fresh = timedelta(hours=get_policies().liveness.fresh_hours)
    if not force and last is not None and last.checked_at > now - fresh:
        return _view(job, cached=True)
    result = check_target(job, session.get(Source, job.source_id), now)
    apply_result(session, job, result, now)
    return _view(job, cached=False)


def confirm_open(session: Session, job_id: int, now: datetime | None = None) -> LivenessView:
    """«Sigue abierta» (solo desde la UI): quita el aviso y ese motivo ya no vuelve a avisar."""
    job = session.get(Job, job_id)
    if job is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    signals = read(job)
    if signals.possibly_closed is None and signals.open_confirmed is not None:
        return _view(job, cached=True)  # nada que confirmar: se conserva la confirmación anterior
    if signals.possibly_closed is not None:
        reason: str | None = signals.possibly_closed.reason
    else:
        reason = signals.liveness.reason if signals.liveness else None
    set_signal(job, "open_confirmed", OpenConfirmed(at=now or utcnow(), reason=reason))
    set_signal(job, "possibly_closed", None)
    session.flush()
    return _view(job, cached=True)


def due_for_check(session: Session, now: datetime | None = None) -> list[int]:
    """Ofertas aprobadas o con CV listo, con URL comprobable y sin comprobación reciente."""
    now = now or utcnow()
    fresh = timedelta(hours=get_policies().liveness.fresh_hours)
    rows = session.scalars(
        select(Job)
        .join(Application, Application.job_id == Job.id)
        .where(Application.stage.in_([s.value for s in DAILY_STAGES]), Job.url != "")
        .order_by(Job.id)
    )
    due = []
    for job in rows:
        host = urlsplit(job.url).hostname or ""
        if job.platform == "linkedin" or platforms.platform_of_host(host) == "linkedin":
            continue
        last = read(job).liveness
        if last is None or last.checked_at <= now - fresh:
            due.append(job.id)
    return due
