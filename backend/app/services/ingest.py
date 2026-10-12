"""Alta manual de ofertas: por URL (descarga y extracción) o por texto pegado.

Las dos vías normalizan, calculan la huella, detectan duplicados exactos (devuelven la oferta
existente sin crear eventos) y difusos (`duplicate_of` + evento `duplicate_detected`), evalúan el
riesgo del contenido (`services/untrusted.py`) y registran el evento `found`.

No se ejecuta JavaScript ni se sortean logins: si la página no da el texto, se pide pegarlo.
"""

import ipaddress
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
import lxml.html
from lxml.etree import ParserError
from pydantic import BaseModel
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.models import Company, Job, Source
from app.models.base import utcnow
from app.services import platforms, reposts
from app.services.events import record
from app.services.normalize import fingerprint, normalize_company, normalize_title
from app.services.pipeline import Actor, EventType
from app.services.untrusted import assess

MIN_TEXT_CHARS = 400
MAX_TEXT_CHARS = 20_000
MAX_DOWNLOAD_BYTES = 5_000_000
FETCH_TIMEOUT = httpx.Timeout(20.0, connect=10.0)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
_BLOCKED_HOSTS = ("linkedin.com", "lnkd.in")
_LOGIN_PATH_WORDS = ("login", "signin", "sign-in", "sign_in", "auth", "sso", "iniciar-sesion")
_SUGGEST_TEXT = "Copia el texto de la oferta y usa `jh jobs add-text`."

DetailLevel = Literal["summary", "full"]

SOURCE_NAMES = {"manual_url": "Alta manual por URL", "manual_text": "Alta manual por texto"}


class IngestError(ValueError):
    """La oferta no se puede dar de alta; el mensaje dice por qué y qué hacer."""


class AddJobResult(BaseModel):
    job_id: int
    created: bool
    duplicate_of: int | None
    risk_flags: list[str]


@dataclass(frozen=True)
class ParsedPage:
    title: str | None
    company: str | None
    location: str | None
    posted_at: datetime | None
    text: str


# --- Texto ----------------------------------------------------------------------------------


def clean_text(text: str) -> str:
    """Espacios simples por línea, como mucho una línea en blanco seguida y 20 000 caracteres."""
    lines = [" ".join(line.split()) for line in text.replace("\r\n", "\n").split("\n")]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()[:MAX_TEXT_CHARS].rstrip()


def _main_text(html: str) -> str:
    import trafilatura  # pesado (~1 s): solo al descargar una URL, no al arrancar

    text = trafilatura.extract(
        html,
        output_format="txt",
        include_comments=False,
        include_tables=True,
        include_links=False,
        include_images=False,
    )
    return clean_text(text or "")


def _html_to_text(fragment: str) -> str:
    try:
        return clean_text(lxml.html.fromstring(fragment).text_content())
    except (ParserError, ValueError):
        return clean_text(fragment)


# --- Metadatos ------------------------------------------------------------------------------


def _iter_nodes(data: Any) -> Any:
    """Recorre un JSON-LD (listas, `@graph`, objetos anidados) nodo a nodo."""
    if isinstance(data, list):
        for item in data:
            yield from _iter_nodes(item)
    elif isinstance(data, dict):
        yield data
        for key in ("@graph", "mainEntity"):
            if key in data:
                yield from _iter_nodes(data[key])


def _is_job_posting(node: dict[str, Any]) -> bool:
    kind = node.get("@type")
    kinds = kind if isinstance(kind, list) else [kind]
    return "JobPosting" in kinds


def find_job_posting(doc: Any) -> dict[str, Any] | None:
    for script in doc.xpath('//script[@type="application/ld+json"]'):
        try:
            data = json.loads(script.text_content(), strict=False)
        except ValueError:
            continue
        for node in _iter_nodes(data):
            if _is_job_posting(node):
                return node
    return None


def _name(value: Any) -> str | None:
    if isinstance(value, dict):
        value = value.get("name")
    if isinstance(value, str) and value.strip():
        return " ".join(value.split())
    return None


def _location(posting: dict[str, Any]) -> str | None:
    places = posting.get("jobLocation")
    places = places if isinstance(places, list) else [places]
    labels: list[str] = []
    for place in places:
        address = place.get("address") if isinstance(place, dict) else None
        if isinstance(address, str):
            parts = [address]
        elif isinstance(address, dict):
            parts = [
                _name(address.get(key)) or ""
                for key in ("addressLocality", "addressRegion", "addressCountry")
            ]
        else:
            parts = []
        label = ", ".join(p for p in parts if p)
        if label and label not in labels:
            labels.append(label)
    if not labels and posting.get("jobLocationType") == "TELECOMMUTE":
        return "Remote"
    return " / ".join(labels) or None


def parse_date(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _meta(doc: Any, prop: str) -> str | None:
    values = doc.xpath(f'//meta[@property="{prop}" or @name="{prop}"]/@content')
    return _name(values[0]) if values else None


def parse_page(html: str) -> ParsedPage:
    """Texto principal y metadatos: JSON-LD `JobPosting` si existe; si no, etiquetas `og:`."""
    try:
        doc = lxml.html.document_fromstring(html)
    except (ParserError, ValueError):
        return ParsedPage(None, None, None, None, "")
    text = _main_text(html)
    posting = find_job_posting(doc)
    if posting is not None:
        # Algunas webs pintan la oferta con JavaScript pero la incluyen entera en el JSON-LD.
        description = posting.get("description")
        if len(text) < MIN_TEXT_CHARS and isinstance(description, str):
            text = max(text, _html_to_text(description), key=len)
        return ParsedPage(
            title=_name(posting.get("title")) or _meta(doc, "og:title"),
            company=_name(posting.get("hiringOrganization")) or _meta(doc, "og:site_name"),
            location=_location(posting),
            posted_at=parse_date(posting.get("datePosted")),
            text=text,
        )
    return ParsedPage(
        title=_meta(doc, "og:title"),
        company=_meta(doc, "og:site_name"),
        location=None,
        posted_at=None,
        text=text,
    )


# --- Descarga -------------------------------------------------------------------------------


def _check_host(host: str) -> None:
    """Rechaza LinkedIn (ADR-009) y destinos locales o de red privada (la URL puede venir de
    contenido no confiable). Solo se comprueban IPs literales y `localhost`; no se resuelve DNS."""
    host = host.lower().rstrip(".")
    if any(host == blocked or host.endswith(f".{blocked}") for blocked in _BLOCKED_HOSTS):
        raise IngestError(f"Las ofertas de LinkedIn no se descargan (ADR-009). {_SUGGEST_TEXT}")
    if host == "localhost" or host.endswith(".localhost"):
        raise IngestError("No se descargan direcciones locales.")
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return
    if not ip.is_global:
        raise IngestError("No se descargan direcciones locales ni de red privada.")


def _check_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise IngestError(f"URL no válida: «{url}». Debe empezar por http:// o https://.")
    _check_host(parts.hostname)


def check_request(request: httpx.Request) -> None:
    """Se ejecuta en cada petición, también en las redirecciones."""
    _check_url(str(request.url))


def looks_like_login(final_url: httpx.URL, html: str) -> bool:
    path = final_url.path.lower()
    if any(word in path for word in _LOGIN_PATH_WORDS):
        return True
    try:
        doc = lxml.html.document_fromstring(html)
    except (ParserError, ValueError):
        return False
    return bool(doc.xpath('//input[translate(@type, "PASSWORD", "password")="password"]'))


def fetch_page(url: str) -> str:
    """Descarga la página (sin cookies previas ni JavaScript) y devuelve su HTML."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    }
    # Un cliente nuevo por descarga: no arrastra cookies de otras peticiones.
    client = httpx.Client(
        timeout=FETCH_TIMEOUT,
        headers=headers,
        follow_redirects=True,
        event_hooks={"request": [check_request]},
    )
    try:
        with client, client.stream("GET", url) as response:
            status, final_url = response.status_code, response.url
            content = b""
            if status < 400:
                for chunk in response.iter_bytes():
                    content += chunk
                    if len(content) > MAX_DOWNLOAD_BYTES:
                        raise IngestError(
                            f"La página ocupa más de {MAX_DOWNLOAD_BYTES // 1_000_000} MB. "
                            f"{_SUGGEST_TEXT}"
                        )
            encoding = response.encoding or "utf-8"
    except httpx.HTTPError as exc:
        raise IngestError(f"No se pudo descargar {url}: {exc}. {_SUGGEST_TEXT}") from exc
    if status in {401, 403}:
        raise IngestError(
            f"La página exige iniciar sesión o bloquea el acceso (HTTP {status}). {_SUGGEST_TEXT}"
        )
    if status >= 400:
        raise IngestError(f"La página respondió con HTTP {status}. {_SUGGEST_TEXT}")
    html = content.decode(encoding, errors="replace")
    if looks_like_login(final_url, html):
        raise IngestError(f"La página pide iniciar sesión para ver la oferta. {_SUGGEST_TEXT}")
    return html


# --- Alta -----------------------------------------------------------------------------------


def _get_or_create_source(session: Session, kind: str) -> Source:
    source = session.scalars(select(Source).where(Source.kind == kind).limit(1)).first()
    if source is None:
        source = Source(kind=kind, name=SOURCE_NAMES[kind])
        session.add(source)
        session.flush()
    return source


def get_or_create_company(session: Session, name: str) -> Company:
    normalized = normalize_company(name)
    company = session.scalars(select(Company).where(Company.normalized_name == normalized)).first()
    if company is None:
        company = Company(name=name, normalized_name=normalized)
        session.add(company)
        session.flush()
    return company


def find_by_platform(session: Session, platform: str, external_id: str) -> Job | None:
    return session.scalars(
        select(Job).where(Job.platform == platform, Job.external_id == external_id).limit(1)
    ).first()


def _existing(job: Job) -> AddJobResult:
    return AddJobResult(
        job_id=job.id, created=False, duplicate_of=job.duplicate_of, risk_flags=job.risk_flags
    )


def _fuzzy_duplicate(
    session: Session,
    company_id: int,
    title: str,
    now: datetime,
    source_id: int | None = None,
) -> tuple[int, float] | None:
    """Oferta original más parecida de la misma empresa en la ventana, y su puntuación.

    Con `source_id` (oferta de un conector con id propio), las ofertas de esa misma fuente que
    también tienen id no cuentan: el ATS ya dice que son publicaciones distintas (p. ej. «Senior
    Data Engineer» en remoto y «Data Engineer» en Vigo)."""
    policy = get_policies().dedup
    since = now - timedelta(days=policy.fuzzy_window_days)
    candidates = session.scalars(
        select(Job)
        .where(Job.company_id == company_id, Job.first_seen_at >= since)
        .order_by(Job.first_seen_at, Job.id)
    ).all()
    target = normalize_title(title)
    best: tuple[int, float] | None = None
    for candidate in candidates:
        if source_id is not None and candidate.source_id == source_id and candidate.external_id:
            continue
        score = fuzz.token_set_ratio(target, normalize_title(candidate.title))
        if score >= policy.fuzzy_title_threshold and (best is None or score > best[1]):
            # Siempre se apunta a la original, no a otro duplicado.
            best = (candidate.duplicate_of or candidate.id, score)
    return best


def store_job(
    session: Session,
    *,
    source: Source,
    title: str,
    company: str,
    text: str,
    url: str,
    location: str | None,
    posted_at: datetime | None,
    html: str | None,
    external_id: str | None = None,
    platform: str | None = None,
    detail_level: DetailLevel = "full",
) -> AddJobResult:
    """Guarda una oferta: huella, duplicados, riesgo y eventos. Lo usan el alta manual, los
    conectores (fase 09) y las alertas por correo (09b). Un duplicado exacto devuelve la existente
    sin registrar eventos (sí la publicación, si trae otro id o URL: `services/reposts.py`).

    Sin `platform`, se deduce de la URL (`services/platforms.py`) cuando su id coincide con
    `external_id` o no hay `external_id`. Una oferta `summary` entra en `pending_detail`."""
    title, company = " ".join(title.split()), " ".join(company.split())
    location = " ".join(location.split()) if location else None
    if not title or not company:
        raise IngestError("Faltan el título o la empresa de la oferta.")
    if not normalize_company(company):
        raise IngestError(f"Nombre de empresa no válido: «{company}».")
    if not text:
        raise IngestError("El texto de la oferta está vacío.")

    if platform is None:
        pid = platforms.detect(url)
        if pid is not None and external_id in (None, pid.external_id):
            platform, external_id = pid.platform, pid.external_id
    if platform is not None and external_id:
        same = find_by_platform(session, platform, external_id)
        if same is not None:
            return _existing(same)

    fp = fingerprint(company, title, location)
    existing = session.scalars(select(Job).where(Job.fingerprint == fp)).first()
    if existing is not None:
        # La misma oferta con otro id o URL: puede ser una republicación (fase 16).
        reposts.note_sighting(
            session, existing, url=url, platform=platform, external_id=external_id
        )
        return _existing(existing)

    now = utcnow()
    company_row = get_or_create_company(session, company)
    duplicate = _fuzzy_duplicate(
        session, company_row.id, title, now, source.id if external_id else None
    )
    risk = assess(text, html)
    job = Job(
        source_id=source.id,
        company_id=company_row.id,
        external_id=external_id,
        platform=platform if external_id else None,
        detail_level=detail_level,
        url=url,
        title=title,
        location_raw=location,
        raw_text=text,
        risk_flags=[flag.value for flag in risk.flags],
        fingerprint=fp,
        duplicate_of=duplicate[0] if duplicate else None,
        posted_at=posted_at,
        first_seen_at=now,
    )
    session.add(job)
    session.flush()
    reposts.note_sighting(
        session, job, url=url, platform=job.platform, external_id=external_id, seen_at=now
    )

    manual = source.kind in SOURCE_NAMES
    found: dict[str, object] = {"source": source.kind}
    if not manual:
        found["source_id"] = source.id
    if detail_level == "summary":
        found["detail_level"] = "summary"
    record(session, job.id, EventType.FOUND, Actor.SYSTEM, found, occurred_at=now)
    if risk.risky:
        record(
            session,
            job.id,
            EventType.INJECTION_SUSPECTED,
            Actor.SYSTEM,
            {"flags": job.risk_flags, "excerpt": risk.excerpt},
        )
    if duplicate:
        record(
            session,
            job.id,
            EventType.DUPLICATE_DETECTED,
            Actor.SYSTEM,
            {"duplicate_of": duplicate[0], "score": round(duplicate[1], 1)},
        )
    return AddJobResult(
        job_id=job.id, created=True, duplicate_of=job.duplicate_of, risk_flags=job.risk_flags
    )


def add_from_url(session: Session, url: str) -> AddJobResult:
    """Descarga la oferta de `url` y la da de alta. Si esa URL ya existe, devuelve la existente."""
    url = url.strip()
    _check_url(url)
    existing = session.scalars(select(Job).where(Job.url == url).limit(1)).first()
    if existing is not None:
        return _existing(existing)

    html = fetch_page(url)
    page = parse_page(html)
    if len(page.text) < MIN_TEXT_CHARS:
        raise IngestError(
            f"La página apenas tiene texto ({len(page.text)} caracteres): puede que se cargue "
            f"con JavaScript o que pida iniciar sesión. {_SUGGEST_TEXT}"
        )
    if not page.title or not page.company:
        missing = "el título" if not page.title else "la empresa"
        raise IngestError(
            f"No se encontró {missing} en la página. Usa `jh jobs add-text` indicando "
            "--title y --company."
        )
    return store_job(
        session,
        source=_get_or_create_source(session, "manual_url"),
        title=page.title,
        company=page.company,
        text=page.text,
        url=url,
        location=page.location,
        posted_at=page.posted_at,
        html=html,
    )


def _text_identity(
    url: str, platform: str | None, external_id: str | None, source: Source | None
) -> tuple[str | None, str | None]:
    """`platform` y `external_id` de una oferta pegada: los dados o, si faltan, los de la URL."""
    pid = platforms.detect(url)
    if external_id is None:
        if pid is not None and platform in (None, pid.platform):
            return pid.platform, pid.external_id
        return platform, None
    if platform is None:
        host_platform = platforms.platform_of_host(urlsplit(url).hostname) if url else None
        source_platform = (source.config or {}).get("platform") if source is not None else None
        platform = host_platform or source_platform
    return platform, external_id


def add_from_text(
    session: Session,
    title: str,
    company: str,
    text: str,
    url: str | None = None,
    location: str | None = None,
    *,
    source: Source | None = None,
    platform: str | None = None,
    external_id: str | None = None,
) -> AddJobResult:
    """Da de alta una oferta a partir de su texto pegado (p. ej. de LinkedIn).

    Con `source` (una plataforma `agent_browse`), la oferta queda ligada a ella en vez de al alta
    manual. Sin `external_id`, se intenta deducir de la URL (`platforms.detect`)."""
    url = (url or "").strip()
    if url:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.hostname:
            raise IngestError(f"URL no válida: «{url}». Debe empezar por http:// o https://.")
    platform, external_id = _text_identity(url, platform, external_id, source)
    return store_job(
        session,
        source=source or _get_or_create_source(session, "manual_text"),
        title=title,
        company=company,
        text=clean_text(text),
        url=url,
        location=location,
        posted_at=None,
        html=None,
        external_id=external_id,
        platform=platform,
    )
