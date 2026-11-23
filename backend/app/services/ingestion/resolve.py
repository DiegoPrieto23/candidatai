"""De la dirección de la web de empleo de una empresa a su fuente: qué ATS usa, con qué slug y
qué filtros de ubicación trae la propia dirección. Sin agente ni modelos.

Tres pasos, en orden:

1. **La URL es de un ATS** (`boards.greenhouse.io/acme`, `acme.teamtailor.com`…): el tipo y el
   slug salen de ella, sin descargar nada.
2. **Es la web de la empresa:** se descarga esa única página (con los controles de
   `ingest.fetch_page`: nada local ni privado, también tras redirecciones; tamaño y tiempo
   acotados) y se buscan en su HTML las huellas de un ATS conocido (enlaces a ofertas, `iframe` o
   script de *embed*, `for=<slug>`). Si hay varias, la que más aparece. El HTML es contenido no
   confiable: solo se buscan direcciones, nunca se interpreta nada más.
3. **Sin huella:** se prueban las APIs públicas con slugs sacados del nombre y del dominio
   (`discover`), y solo vale un tablero que case con ellos.

Si nada funciona, `kind` queda vacío (`how="none"`): el alta la guarda como plataforma que el
agente recorre con el navegador.

Los filtros de ubicación salen de los parámetros (`office=Madrid`, `location=`…), que se toman
tal cual, y de los segmentos de la ruta (`/madrid/`), que son solo candidatos: los confirma el
servicio si casan con la ubicación de alguna oferta del tablero o con los lugares del perfil.
"""

import logging
import re
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from html import unescape
from typing import Literal
from urllib.parse import parse_qs, unquote, urlsplit

import httpx

from app.core.policies import get_policies
from app.schemas.sources import KIND_LABELS
from app.services import ingest, liveness
from app.services.ingestion import discover
from app.services.normalize import fold, normalize_company

logger = logging.getLogger(__name__)

MAX_PAGE_BYTES = 2_000_000
Method = Literal["url", "page", "search", "none"]

# Subdominios que no son el slug de una empresa en los ATS que lo ponen en el subdominio.
_NOT_SLUGS = frozenset(
    {"www", "app", "api", "apply", "jobs", "careers", "career", "assets", "static", "cdn",
     "scripts", "help", "support", "status", "blog", "embed", "boards", "job-boards", "docs"}
)  # fmt: skip
# Primer segmento de la ruta que no es el slug en los ATS que lo ponen en la ruta.
_NOT_PATH_SLUGS = frozenset({"embed", "v1", "v0", "api", "jobs", "j", "o", "static", "assets"})
_ATS_HOSTS = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "personio.de",
    "personio.com",
    "teamtailor.com",
    "workable.com",
    "smartrecruiters.com",
    "recruitee.com",
)
# Direcciones de ATS dentro del HTML: con o sin esquema, y con `\/` en el JSON de un script.
_ATS_URL = re.compile(
    r"(?:https?:)?//(?:[a-z0-9-]+\.)*(?:"
    + "|".join(re.escape(h) for h in _ATS_HOSTS)
    + r")(?::\d+)?(?:/[^\s\"'<>()\\]*)?",
    re.IGNORECASE,
)
_SLUG = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,99}$")
# Parámetros de una web de empleo que dicen dónde («office=Madrid»).
_LOCATION_PARAMS = frozenset(
    {"office", "offices", "location", "locations", "city", "cities", "ciudad", "ubicacion",
     "ubicación", "oficina", "loc", "place", "sede"}
)  # fmt: skip
# Segmentos de ruta que nunca son un lugar.
_NOT_PLACES = frozenset(
    {"jobs", "job", "careers", "career", "empleo", "empleos", "trabajo", "trabaja-con-nosotros",
     "join", "join-us", "work-with-us", "positions", "openings", "vacantes", "ofertas", "search",
     "buscar", "all", "index", "en", "es", "fr", "de", "it", "pt", "ca", "eu", "gl", "home",
     "team", "teams", "departments", "department", "about"}
)  # fmt: skip
_PLACE_SEGMENT = re.compile(r"^[a-zà-ÿ]+(?:[-_][a-zà-ÿ]+){0,3}$")
# Primera etiqueta de un dominio de empleo que no forma parte del de la empresa.
_CAREER_LABELS = frozenset(
    {"careers", "career", "jobs", "job", "empleo", "trabajo", "work", "talent", "join", "apply"}
)


class ResolveError(ValueError):
    """La dirección no se puede usar (no es http/https, es local o de red privada)."""


@dataclass
class Board:
    kind: str
    slug: str
    region: str = "global"


@dataclass
class Resolution:
    """Lo que sale de una dirección. `kind` vacío: no se reconoce ningún ATS."""

    url: str
    how: Method
    board: Board | None
    locations: list[str] = field(default_factory=list)  # de los parámetros: firmes
    place_candidates: list[str] = field(default_factory=list)  # de la ruta: por confirmar
    website: str | None = None  # web de la empresa, para su logo (si no es la del ATS)
    issues: list[str] = field(default_factory=list)  # lo que no se pudo hacer (sin abrir la web…)

    @property
    def kind_label(self) -> str | None:
        return KIND_LABELS[self.board.kind] if self.board else None


# --- Lectura de direcciones ------------------------------------------------------------------


def _host_is(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def _valid(slug: str | None) -> str | None:
    slug = (slug or "").strip().lower()
    return slug if _SLUG.match(slug) and ".." not in slug else None


def _subdomain(host: str, domain: str) -> str | None:
    """`acme` en `acme.teamtailor.com`; `None` si es otro nivel o un subdominio del propio ATS."""
    prefix = host.removesuffix(f".{domain}")
    if prefix == host or "." in prefix or prefix in _NOT_SLUGS:
        return None
    return _valid(prefix)


def board_from_url(url: str) -> Board | None:
    """El tablero de una dirección de ATS, o `None` si no es de ninguno conocido."""
    try:
        parts = urlsplit(url if "://" in url else f"https:{url}" if url.startswith("//") else url)
    except ValueError:
        return None
    host = (parts.hostname or "").lower().rstrip(".")
    segments = [unquote(s) for s in parts.path.split("/") if s]
    first = segments[0] if segments else None
    query = parse_qs(parts.query)

    if _host_is(host, "greenhouse.io"):
        if host.startswith("boards-api.") and segments[:2] == ["v1", "boards"]:
            return _board("greenhouse", segments[2] if len(segments) > 2 else None)
        if host.split(".")[0] in {"boards", "job-boards"}:
            if first == "embed":  # `embed/job_board?for=acme` y su script
                return _board("greenhouse", (query.get("for") or [None])[0])
            if first not in _NOT_PATH_SLUGS:
                return _board("greenhouse", first)
        return None
    if _host_is(host, "lever.co"):
        if host in {"jobs.lever.co", "jobs.eu.lever.co"} and first not in _NOT_PATH_SLUGS:
            return _board("lever", first, "eu" if ".eu." in host else "global")
        if host in {"api.lever.co", "api.eu.lever.co"} and segments[:2] == ["v0", "postings"]:
            slug = segments[2] if len(segments) > 2 else None
            return _board("lever", slug, "eu" if ".eu." in host else "global")
        return None
    if _host_is(host, "ashbyhq.com"):
        if host == "jobs.ashbyhq.com" and first not in _NOT_PATH_SLUGS:
            return _board("ashby", first)
        if host == "api.ashbyhq.com" and segments[:2] == ["posting-api", "job-board"]:
            return _board("ashby", segments[2] if len(segments) > 2 else None)
        return None
    for domain in ("jobs.personio.de", "jobs.personio.com"):
        if _host_is(host, domain):
            return _board("personio", _subdomain(host, domain))
    if _host_is(host, "teamtailor.com"):
        return _board("teamtailor", _subdomain(host, "teamtailor.com"))
    if _host_is(host, "recruitee.com"):
        return _board("recruitee", _subdomain(host, "recruitee.com"))
    if _host_is(host, "workable.com"):
        if host == "apply.workable.com":
            if first == "api" and len(segments) >= 5 and segments[2:4] == ["widget", "accounts"]:
                return _board("workable", segments[4])
            if first not in _NOT_PATH_SLUGS:
                return _board("workable", first)
            return None
        return _board("workable", _subdomain(host, "workable.com"))
    if _host_is(host, "smartrecruiters.com"):
        if host in {"careers.smartrecruiters.com", "jobs.smartrecruiters.com"}:
            return _board("smartrecruiters", first) if first not in _NOT_PATH_SLUGS else None
        if host == "api.smartrecruiters.com" and segments[:2] == ["v1", "companies"]:
            return _board("smartrecruiters", segments[2] if len(segments) > 2 else None)
    return None


def _board(kind: str, slug: str | None, region: str = "global") -> Board | None:
    valid = _valid(slug)
    if valid is None:
        return None
    # SmartRecruiters distingue mayúsculas en el slug (`AcmeDatos`); el resto, no.
    return Board(kind, (slug or "").strip() if kind == "smartrecruiters" else valid, region)


def boards_in_html(html: str) -> list[tuple[Board, int]]:
    """Tableros enlazados desde una página, del más citado al menos (empate: el primero)."""
    text = unescape(html).replace("\\/", "/")
    counts: Counter[tuple[str, str, str]] = Counter()
    for match in _ATS_URL.finditer(text):
        board = board_from_url(match.group(0))
        if board is not None:
            counts[(board.kind, board.slug, board.region)] += 1
    return [(Board(*key), count) for key, count in counts.most_common()]


def url_filters(url: str) -> tuple[list[str], list[str]]:
    """Ubicaciones de los parámetros (firmes) y candidatas de la ruta (`/madrid/`)."""
    parts = urlsplit(url)
    locations: list[str] = []
    for key, values in parse_qs(parts.query).items():
        if fold(key).replace(" ", "") not in {fold(k) for k in _LOCATION_PARAMS}:
            continue
        for value in values:
            for piece in value.split(","):
                piece = " ".join(piece.split())
                # Un id (`locationId=8f3a…`) no es un lugar: solo letras, espacios y guiones.
                if 1 < len(piece) <= 80 and re.fullmatch(r"[^\W\d_]+(?:[\s'.-][^\W\d_]+)*", piece):
                    locations.append(piece)
    candidates = []
    for segment in parts.path.split("/"):
        segment = unquote(segment).strip().lower()
        if segment in _NOT_PLACES or len(segment) < 3 or not _PLACE_SEGMENT.match(segment):
            continue
        candidates.append(re.sub(r"[-_]", " ", segment))
    return _unique(locations), _unique(candidates)


def _unique(values: list[str]) -> list[str]:
    seen: dict[str, str] = {}
    for value in values:
        seen.setdefault(fold(value), value)
    return list(seen.values())


def company_website(url: str) -> str | None:
    """Web de la empresa para su logo: el origen de su web de empleo, sin `careers.` delante; nada
    si está en el dominio de un ATS."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().rstrip(".")
    if not host or "." not in host or any(_host_is(host, d) for d in _ATS_HOSTS):
        return None
    labels = host.split(".")
    if len(labels) > 2 and labels[0] in _CAREER_LABELS | {"www"}:
        host = ".".join(labels[1:])
    return f"https://{host}"


def _domain_label(url: str) -> str | None:
    """`datadoghq` en `careers.datadoghq.com`; `cabify` en `cabify.careers`."""
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    labels = [label for label in host.split(".") if label and label not in {"www"}]
    if len(labels) < 2:
        return None
    if labels[0] in _CAREER_LABELS and len(labels) > 2:
        labels = labels[1:]
    candidate = labels[0] if labels[-1] in _CAREER_LABELS else labels[-2]
    return _valid(candidate)


def platform_id(url: str) -> str:
    """Id de plataforma para una web de empleo sin ATS: `cabify` para `cabify.careers`."""
    label = _domain_label(url) or "web"
    return re.sub(r"[^a-z0-9_-]", "-", label.lower())[:40].strip("-") or "web"


# --- Red -------------------------------------------------------------------------------------


def check_url(url: str) -> str:
    """La dirección limpia o `ResolveError`. Mismas reglas que el alta de ofertas por URL."""
    url = url.strip()
    if "://" not in url:
        url = f"https://{url}"
    try:
        ingest.check_request(httpx.Request("GET", url))
    except ingest.LinkedInUrlError as exc:
        raise ResolveError(
            "LinkedIn no sirve como web de empleo de una empresa: hace falta la de su propia web."
        ) from exc
    except (ingest.IngestError, httpx.InvalidURL, ValueError) as exc:
        raise ResolveError(str(exc)) from exc
    return url


def fetch_html(url: str, timeout: float) -> tuple[str, str]:
    """HTML de la página y la URL final tras las redirecciones. Lanza `ResolveError`."""
    client = httpx.Client(
        timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
        headers={
            "User-Agent": ingest.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
        follow_redirects=True,
        event_hooks={"request": [ingest.check_request, liveness.check_resolved]},
    )
    try:
        with client, client.stream("GET", url) as response:
            if response.status_code >= 400:
                raise ResolveError(f"La web respondió con HTTP {response.status_code}.")
            chunks: list[bytes] = []
            size = 0
            deadline = time.monotonic() + timeout * 2  # el de httpx es por operación, no total
            for chunk in response.iter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_PAGE_BYTES or time.monotonic() > deadline:
                    break  # basta el principio: las huellas suelen estar ahí
            content = b"".join(chunks)[:MAX_PAGE_BYTES]
            final = str(response.url)
            encoding = response.encoding or "utf-8"
    except ingest.IngestError as exc:  # redirección a un sitio local o a LinkedIn
        raise ResolveError(str(exc)) from exc
    except httpx.HTTPError as exc:
        raise ResolveError(f"No se pudo abrir la web ({type(exc).__name__}).") from exc
    return content.decode(encoding, errors="replace"), final


def _search(
    name: str,
    url: str,
    kinds: tuple[str, ...],
    sleep: Callable[[float], None],
    transport: httpx.BaseTransport | None,
) -> Board | None:
    """Prueba las APIs con slugs del nombre y del dominio. Vale un tablero con ofertas cuyo slug
    sea el del dominio de la web o que `discover` no dé por dudoso (el nombre casa o el slug sale
    del nombre completo)."""
    slugs = discover.candidate_slugs(name)
    label = _domain_label(url)
    if label and label not in {s for s, _ in slugs}:
        slugs.append((label, True))
    if not slugs:
        return None
    found = discover.find_boards(name, slugs, kinds, sleep=sleep, transport=transport)
    hits = [
        h
        for h in found
        if h.jobs_count > 0 and (h.confidence != "doubtful" or h.slug.lower() == label)
    ]
    if not hits:
        return None
    best = max(hits, key=lambda h: (h.confidence == "confirmed", h.jobs_count))
    return Board(best.kind, best.slug, best.region)


def resolve(
    name: str,
    url: str,
    *,
    sleep: Callable[[float], None] | None = None,
    transport: httpx.BaseTransport | None = None,
) -> Resolution:
    """Qué ATS hay detrás de una web de empleo. Lanza `ResolveError` si la dirección no vale."""
    url = check_url(url)
    locations, candidates = url_filters(url)
    result = Resolution(url=url, how="none", board=None, locations=locations)
    result.place_candidates = candidates
    result.website = company_website(url)

    if (board := board_from_url(url)) is not None:
        result.how, result.board = "url", board
        # En la dirección del ATS, el slug no es un lugar.
        result.place_candidates = [c for c in candidates if fold(c) != fold(board.slug)]
        return result

    gh_jid = "gh_jid" in parse_qs(urlsplit(url).query)
    try:
        html, final = fetch_html(url, get_policies().connectors.timeout_seconds)
    except ResolveError as exc:
        result.issues.append(str(exc))
    else:
        if (board := board_from_url(final)) is not None:  # la web redirige a su ATS
            result.how, result.board = "page", board
            return result
        boards = boards_in_html(html)
        if boards:
            result.how, result.board = "page", boards[0][0]
            return result
        gh_jid = gh_jid or "gh_jid=" in html

    if not normalize_company(name):
        return result
    # Una oferta de Greenhouse enlazada sin su tablero (`?gh_jid=`): basta con probar ese ATS.
    kinds = ("greenhouse",) if gh_jid else discover.DISCOVER_KINDS
    try:
        board = _search(name, url, kinds, sleep or time.sleep, transport)
    except (httpx.HTTPError, ValueError) as exc:
        logger.info("Búsqueda del tablero de %s fallida: %s", name, exc)
        result.issues.append("No se pudieron consultar las webs de empleo conocidas.")
        board = None
    if board is not None:
        result.how, result.board = "search", board
    return result
