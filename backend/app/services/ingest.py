"""Alta manual de ofertas: por URL (descarga y extracción) o por texto pegado.

Las dos vías normalizan, calculan la huella, detectan duplicados exactos y difusos (devuelven la
oferta existente sin crear eventos; el difuso, con `duplicate_of`), evalúan el riesgo del
contenido (`services/untrusted.py`) y registran el evento `found`.

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
from app.models import Application, Company, Event, Job, Source
from app.models.base import utcnow
from app.services import platforms, reposts
from app.services.events import record
from app.services.normalize import fingerprint, normalize_company, normalize_title
from app.services.pipeline import Actor, EventType, Stage
from app.services.signals import RepublishedSignal, set_signal
from app.services.signals import read as read_signals
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
_SUGGEST_TEXT = (
    "Copia el texto de la oferta y dalo de alta como texto (`add_job_from_text`, "
    "`cai jobs add-text` o «Pegar texto» en la UI)."
)
# LinkedIn: además de pegar el texto, el botón del navegador «Enviar a CandidatAI» la manda desde la
# propia página de la oferta, ya abierta en el navegador de la persona.
_LINKEDIN_HELP = (
    "Las ofertas de LinkedIn no se descargan. Pide a la persona que abra la oferta en su navegador "
    "y pulse el botón «Enviar a CandidatAI», o copia el texto de la oferta y dalo de alta como "
    "texto (`add_job_from_text` o `cai jobs add-text`)."
)

DetailLevel = Literal["summary", "full"]

SOURCE_NAMES = {"manual_url": "Alta manual por URL", "manual_text": "Alta manual por texto"}


class IngestError(ValueError):
    """La oferta no se puede dar de alta; el mensaje dice por qué y qué hacer."""


class LinkedInUrlError(IngestError):
    """La URL es de LinkedIn, que nunca se descarga (POLICIES §8).

    Error `linkedin_url`. La UI lo traduce a un aviso con los dos caminos: el botón del navegador
    desde la página de la oferta o pegar su texto."""


class PageUnavailableError(IngestError):
    """No se pudo abrir la página de la oferta (sin red, login, bloqueo, JavaScript).

    Error `page_unavailable`. La solución es siempre la misma, pegar su texto, y la UI la ofrece
    con su propio aviso."""


class AddJobResult(BaseModel):
    job_id: int
    created: bool
    duplicate_of: int | None
    risk_flags: list[str]
    # Fase 45: una vacante cerrada por la empresa que vuelve entra nueva y enlazada a la antigua;
    # la misma publicación caducada que reaparece reabre la existente; una que cerraste tú y vuelve
    # no se crea, pero queda avisada en la Bandeja.
    reopening_of: int | None = None
    reopened: bool = False
    republished_after_close: bool = False


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
    """Rechaza LinkedIn y destinos locales o de red privada (la URL puede venir de
    contenido no confiable). Solo se comprueban IPs literales y `localhost`; no se resuelve DNS."""
    host = host.lower().rstrip(".")
    if any(host == blocked or host.endswith(f".{blocked}") for blocked in _BLOCKED_HOSTS):
        raise LinkedInUrlError(_LINKEDIN_HELP)
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


def _check_resolved(request: httpx.Request) -> None:
    """Un dominio que apunta a la red local (`127.0.0.1.nip.io`, uno de tu router) tampoco: la URL
    puede llegar de un correo de alertas. Lo resuelve `liveness`, que importa este módulo."""
    from app.services import liveness

    liveness.check_resolved(request)


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
        event_hooks={"request": [check_request, _check_resolved]},
    )
    try:
        with client, client.stream("GET", url) as response:
            status, final_url = response.status_code, response.url
            content = b""
            if status < 400:
                for chunk in response.iter_bytes():
                    content += chunk
                    if len(content) > MAX_DOWNLOAD_BYTES:
                        raise PageUnavailableError(
                            f"La página ocupa más de {MAX_DOWNLOAD_BYTES // 1_000_000} MB. "
                            f"{_SUGGEST_TEXT}"
                        )
            encoding = response.encoding or "utf-8"
    except httpx.HTTPError as exc:
        raise PageUnavailableError(f"No se pudo descargar {url}: {exc}. {_SUGGEST_TEXT}") from exc
    if status in {401, 403}:
        raise PageUnavailableError(
            f"La página exige iniciar sesión o bloquea el acceso (HTTP {status}). {_SUGGEST_TEXT}"
        )
    if status >= 400:
        raise PageUnavailableError(f"La página respondió con HTTP {status}. {_SUGGEST_TEXT}")
    html = content.decode(encoding, errors="replace")
    if looks_like_login(final_url, html):
        raise PageUnavailableError(
            f"La página pide iniciar sesión para ver la oferta. {_SUGGEST_TEXT}"
        )
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


def _existing(job: Job, **flags: bool) -> AddJobResult:
    return AddJobResult(
        job_id=job.id,
        created=False,
        duplicate_of=job.duplicate_of,
        risk_flags=job.risk_flags,
        **flags,
    )


# --- Reaperturas (fase 45) ---------------------------------------------------------------------

Republication = Literal["reopening", "reactivate", "notice"]
# Quién cerró la oferta: la empresa (o caducó) o tú. Los demás cierres (el filtro previo) no se
# reconsideran: si vuelve, se anota la publicación como siempre.
COMPANY_CLOSES = frozenset({EventType.EXPIRED, EventType.REJECTED})
USER_CLOSES = frozenset({EventType.WITHDRAWN, EventType.ACCEPTED})


def discard_reason(session: Session, job_id: int) -> str | None:
    payload = session.scalars(
        select(Event.payload)
        .where(Event.job_id == job_id, Event.type == EventType.DISCARDED)
        .order_by(Event.occurred_at.desc(), Event.id.desc())
        .limit(1)
    ).first()
    reason = (payload or {}).get("reason")
    return reason if isinstance(reason, str) else None


def closed_by_company(session: Session, job_id: int, closed_by: str | None) -> bool | None:
    """`True` si la cerró la empresa o caducó, `False` si la cerraste tú, `None` si ninguna (el
    filtro previo). Descartada con el motivo `closed` («la han cerrado») cuenta como la empresa."""
    if closed_by in COMPANY_CLOSES:
        return True
    if closed_by in USER_CLOSES:
        return False
    if closed_by == EventType.DISCARDED:
        return discard_reason(session, job_id) == "closed"
    return None


def republication(
    session: Session, job: Job, *, same_id: bool, now: datetime | None = None
) -> Republication | None:
    """Qué hacer cuando `job`, ya guardada, vuelve a aparecer. Solo lee.

    Nada si sigue viva o se cerró hace menos de `dedup.reopen_after_days`. Si no:
    - la misma publicación (`same_id`: mismo id o URL) que caducó: `reactivate`, se reabre esa;
    - otra publicación (misma huella) de una que cerró la empresa o caducó: `reopening`, oferta
      nueva enlazada;
    - otra publicación de una que cerraste tú: `notice`, solo el aviso."""
    app = session.get(Application, job.id)
    if app is None or app.stage != Stage.CLOSED or app.closed_at is None:
        return None
    limit = (now or utcnow()) - timedelta(days=get_policies().dedup.reopen_after_days)
    if app.closed_at >= limit:
        return None
    if same_id:
        return "reactivate" if app.closed_by == EventType.EXPIRED else None
    company = closed_by_company(session, job.id, app.closed_by)
    if company is None:
        return None
    return "reopening" if company else "notice"


def latest_by_fingerprint(session: Session, fp: str) -> Job | None:
    """La oferta más reciente con esa huella (con reaperturas puede haber varias)."""
    return session.scalars(
        select(Job).where(Job.fingerprint == fp).order_by(Job.id.desc()).limit(1)
    ).first()


def note_known(
    session: Session,
    job: Job,
    *,
    same_id: bool,
    url: str | None,
    platform: str | None,
    external_id: str | None,
) -> AddJobResult:
    """Una oferta ya guardada vuelve a aparecer: reactiva, avisa o solo anota la publicación.
    `reopening` no se trata aquí: la oferta nueva la crea `store_job`."""
    now = utcnow()
    action = republication(session, job, same_id=same_id, now=now)
    reposts.note_sighting(session, job, url=url, platform=platform, external_id=external_id)
    if action == "reactivate":
        record(session, job.id, EventType.REOPENED, Actor.SYSTEM, {"reason": "republished"})
        return _existing(job, reopened=True)
    if action == "notice":
        previous = read_signals(job).republished_after_close
        quiet = timedelta(days=get_policies().dedup.reopen_after_days)
        dismissed = (
            previous.dismissed_at
            if previous and previous.dismissed_at and now - previous.dismissed_at < quiet
            else None
        )
        set_signal(
            job,
            "republished_after_close",
            RepublishedSignal(seen_at=now, url=url or None, dismissed_at=dismissed),
        )
        return _existing(job, republished_after_close=True)
    return _existing(job)


def needs_store(session: Session, job: Job) -> bool:
    """La misma publicación ya guardada que hay que pasar por `store_job` (para reactivarla)
    aunque quien la lee la salte por conocida."""
    return republication(session, job, same_id=True) is not None


def fuzzy_original(
    session: Session,
    company_id: int,
    title: str,
    now: datetime,
    *,
    skip_source_id: int | None = None,
    skip_platform: str | None = None,
) -> Job | None:
    """La misma vacante con un título casi igual («Data Engineer» y «Data Engineer (m/f/d)»): la
    oferta de la misma empresa vista en `dedup.fuzzy_window_days` cuyo título se parece al menos
    `dedup.fuzzy_title_threshold`. Con empates, la que sigue viva y, después, la más reciente (tras
    una reapertura, la reapertura). Siempre la original, nunca una duplicada guardada antes de que
    dejaran de crearse.

    Para una oferta con id propio se pasan su fuente (`skip_source_id`) o su plataforma
    (`skip_platform`): las de esa misma fuente o plataforma que también tienen id no cuentan,
    porque el portal ya dice que son publicaciones distintas (p. ej. «Senior Data Engineer» en
    remoto y «Data Engineer» en Vigo). Solo lee."""
    policy = get_policies().dedup
    since = now - timedelta(days=policy.fuzzy_window_days)
    candidates = session.scalars(
        select(Job)
        .where(Job.company_id == company_id, Job.first_seen_at >= since)
        .order_by(Job.first_seen_at, Job.id)
    ).all()
    target = normalize_title(title)
    best: tuple[tuple[float, bool, int], Job] | None = None
    for order, candidate in enumerate(candidates):
        if candidate.external_id and (
            (skip_source_id is not None and candidate.source_id == skip_source_id)
            or (skip_platform is not None and candidate.platform == skip_platform)
        ):
            continue
        score = fuzz.token_set_ratio(target, normalize_title(candidate.title))
        if score < policy.fuzzy_title_threshold:
            continue
        job = original_of(session, candidate)
        app = session.get(Application, job.id)
        key = (score, app is None or app.stage != Stage.CLOSED, order)
        if best is None or key > best[0]:
            best = (key, job)
    return best[1] if best else None


def original_of(session: Session, job: Job) -> Job:
    """La original de una duplicada guardada antes de que dejaran de crearse; si no, la misma."""
    if job.duplicate_of is None:
        return job
    return session.get(Job, job.duplicate_of) or job


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
    sin registrar eventos (sí la publicación, si trae otro id o URL: `services/reposts.py`), salvo
    las reaperturas de la fase 45 (`republication`).

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
    same: Job | None = None
    if platform is not None and external_id:
        same = find_by_platform(session, platform, external_id)
    elif external_id and source.kind not in SOURCE_NAMES:
        # Un conector sin plataforma reconocible: su id vale dentro de esa fuente.
        same = session.scalars(
            select(Job)
            .where(Job.source_id == source.id, Job.external_id == external_id)
            .order_by(Job.id.desc())
            .limit(1)
        ).first()
    if same is not None:
        return note_known(
            session, same, same_id=True, url=url, platform=platform, external_id=external_id
        )

    now = utcnow()
    company_row = get_or_create_company(session, company)
    fp = fingerprint(company, title, location)
    existing = latest_by_fingerprint(session, fp)
    # Una duplicada de antes lleva a su original, que es la que sigue la vacante.
    fuzzy = existing is not None and existing.duplicate_of is not None
    if existing is not None:
        existing = original_of(session, existing)
    else:
        # La misma vacante con un título casi igual tampoco es una oferta nueva.
        existing = fuzzy_original(
            session,
            company_row.id,
            title,
            now,
            skip_source_id=source.id if external_id else None,
            skip_platform=platform if external_id else None,
        )
        fuzzy = existing is not None
    reopening_of: int | None = None
    if existing is not None:
        if republication(session, existing, same_id=False) == "reopening":
            reopening_of = existing.id
        else:
            # La misma oferta con otro id, URL o título: puede ser una republicación (fase 16).
            known = note_known(
                session,
                existing,
                same_id=False,
                url=url,
                platform=platform,
                external_id=external_id,
            )
            if fuzzy:
                known.duplicate_of = existing.id
            return known

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
        reopening_of=reopening_of,
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
    if reopening_of is not None:
        found["reopening_of"] = reopening_of
    record(session, job.id, EventType.FOUND, Actor.SYSTEM, found, occurred_at=now)
    if risk.risky:
        record(
            session,
            job.id,
            EventType.INJECTION_SUSPECTED,
            Actor.SYSTEM,
            {"flags": job.risk_flags, "excerpt": risk.excerpt},
        )
    return AddJobResult(
        job_id=job.id,
        created=True,
        duplicate_of=job.duplicate_of,
        risk_flags=job.risk_flags,
        reopening_of=reopening_of,
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
        raise PageUnavailableError(
            f"La página apenas tiene texto ({len(page.text)} caracteres): puede que se cargue "
            f"con JavaScript o que pida iniciar sesión. {_SUGGEST_TEXT}"
        )
    if not page.title or not page.company:
        missing = "el título" if not page.title else "la empresa"
        raise PageUnavailableError(
            f"No se encontró {missing} en la página. Da de alta su texto indicando el puesto y la "
            "empresa (`add_job_from_text`, `cai jobs add-text --title … --company …` o «Pegar "
            "texto» en la UI)."
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
