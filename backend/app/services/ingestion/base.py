"""Interfaz común de los conectores de ofertas (fase 09).

Un conector descarga las ofertas publicadas de una fuente (`fetch`) y, si su listado no trae la
descripción, la completa oferta a oferta (`complete`), solo para las que pasan el filtro previo y
aún no están en la BD. Nunca guarda nada: eso lo hace `ingestion/service.py`.

Solo usan endpoints públicos documentados, sin scraping. Un fallo de toda la fuente es una
`ConnectorError`; una oferta mal formada se salta y se anota como `Issue`, y el resto sigue.
"""

import html
import logging
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlsplit

import httpx
import lxml.html
from lxml import etree
from lxml.etree import ParserError

from app.schemas.sources import Issue, SourceConfig
from app.services.ingest import MAX_TEXT_CHARS, clean_text

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
USER_AGENT = "CandidatAI/0.1 (local job search app)"  # solo ASCII en cabeceras
_BLOCK_TAGS = frozenset(
    {"p", "div", "br", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section"}
)


class ConnectorError(Exception):
    """La fuente entera ha fallado (HTTP, red o formato). El mensaje dice qué revisar."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class MissingKeysError(ConnectorError):
    """Portal opcional sin claves en `.env`: la fuente se omite con un aviso."""

    def __init__(self, message: str) -> None:
        super().__init__("missing_keys", message)


@dataclass
class RawJob:
    """Una oferta tal como la da la fuente, ya en texto. `text` y `html` no son confiables."""

    external_id: str
    title: str
    company: str
    url: str
    location: str | None = None
    text: str = ""
    html: str | None = None  # para detectar texto oculto (`services/untrusted.py`)
    posted_at: datetime | None = None
    remote: bool | None = None  # la fuente dice que es remota (None: no lo dice)
    needs_detail: bool = False  # el listado no trae la descripción: hay que llamar a `complete`
    detail_url: str | None = None  # dónde pide `complete` el detalle, si no sale del id


@dataclass
class FetchResult:
    jobs: list[RawJob] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)


class Connector(Protocol):
    kind: str
    label: str

    def fetch(self, name: str, config: SourceConfig, client: httpx.Client) -> FetchResult: ...

    def complete(self, job: RawJob, client: httpx.Client) -> RawJob: ...


# --- HTTP ------------------------------------------------------------------------------------


def make_client(timeout: float, transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """Sin redirecciones: los endpoints no redirigen, y una redirección se llevaría a otro sitio
    las claves que algunos portales (Adzuna) piden en la URL."""
    # httpx registra cada petición en INFO con su URL completa, claves incluidas.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return httpx.Client(
        timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        follow_redirects=False,
        transport=transport,
    )


def _get(
    client: httpx.Client,
    url: str,
    *,
    label: str,
    params: dict[str, Any] | None = None,
    auth: httpx.Auth | tuple[str, str] | None = None,
    headers: dict[str, str] | None = None,
    not_found: str | None = None,
) -> httpx.Response:
    """GET con los errores traducidos a `ConnectorError` con un mensaje para el usuario."""
    try:
        response = client.get(url, params=params, auth=auth, headers=headers)
    except httpx.TimeoutException as exc:
        raise ConnectorError("timeout", f"{label} no respondió a tiempo.") from exc
    except httpx.HTTPError as exc:
        raise ConnectorError(
            "network", f"No se pudo conectar con {label}: {type(exc).__name__}."
        ) from exc
    status = response.status_code
    if status == 404 and not_found:
        raise ConnectorError("not_found", not_found)
    if status in (401, 403):
        raise ConnectorError(
            "unauthorized", f"{label} rechazó la petición (HTTP {status}): revisa las claves."
        )
    if response.is_redirect:
        raise ConnectorError(
            "http_error", f"{label} respondió con una redirección (HTTP {status}): no se sigue."
        )
    if status == 429:
        raise ConnectorError("rate_limited", f"{label} pide esperar (HTTP 429).")
    if status >= 400:
        raise ConnectorError("http_error", f"{label} respondió con un error HTTP {status}.")
    return response


def get_json(
    client: httpx.Client,
    url: str,
    *,
    label: str,
    params: dict[str, Any] | None = None,
    auth: httpx.Auth | tuple[str, str] | None = None,
    not_found: str | None = None,
) -> Any:
    """GET que devuelve el JSON o lanza `ConnectorError` con un mensaje para el usuario."""
    response = _get(client, url, label=label, params=params, auth=auth, not_found=not_found)
    try:
        return response.json()
    except ValueError as exc:
        raise ConnectorError("unexpected_format", f"{label} no devolvió JSON.") from exc


def get_xml(
    client: httpx.Client,
    url: str,
    *,
    label: str,
    params: dict[str, Any] | None = None,
    not_found: str | None = None,
) -> etree._Element:
    """GET de un feed XML o RSS (Personio, Teamtailor). Sin entidades externas ni red: el feed
    no es confiable."""
    response = _get(
        client,
        url,
        label=label,
        params=params,
        headers={"Accept": "application/xml, application/rss+xml, text/xml"},
        not_found=not_found,
    )
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
    try:
        root = etree.fromstring(response.content, parser)
    except etree.XMLSyntaxError as exc:
        raise ConnectorError("unexpected_format", f"{label} no devolvió XML válido.") from exc
    if root is None:
        raise ConnectorError("unexpected_format", f"{label} devolvió un XML vacío.")
    return root


def xml_text(node: etree._Element | None, path: str) -> str | None:
    """Texto de un hijo del XML (`path` admite prefijos de espacio de nombres)."""
    if node is None:
        return None
    namespaces = {k: v for k, v in node.nsmap.items() if k}
    found = node.find(path, namespaces=namespaces or None)
    if found is None:
        return None
    return optional_str("".join(found.itertext()))


def unexpected(label: str, what: str) -> ConnectorError:
    return ConnectorError(
        "unexpected_format",
        f"Formato inesperado en la respuesta de {label}: {what}. Puede que la API haya cambiado.",
    )


def parse_items(
    items: list[Any], label: str, parse: Callable[[dict[str, Any]], RawJob | None]
) -> FetchResult:
    """Convierte cada oferta con `parse`; las que fallan se anotan y se saltan. `parse` devuelve
    `None` para las que la fuente marca como no publicadas."""
    result = FetchResult()
    for index, item in enumerate(items):
        ref = str(item.get("id", index)) if isinstance(item, dict) else str(index)
        try:
            if not isinstance(item, dict):
                raise TypeError("no es un objeto")
            job = parse(item)
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            reason = f"falta {exc}" if isinstance(exc, KeyError) else str(exc)
            result.issues.append(
                Issue(
                    code="invalid_item", message=f"Oferta de {label} ignorada: {reason}.", item=ref
                )
            )
            continue
        if job is not None:
            result.jobs.append(job)
    return result


# --- Texto -----------------------------------------------------------------------------------


def require_str(item: dict[str, Any], key: str) -> str:
    value = item[key]
    if not isinstance(value, str | int) or not str(value).strip():
        raise ValueError(f"`{key}` vacío o no es texto")
    return str(value).strip()


def require_url(item: dict[str, Any], key: str) -> str:
    """URL de la oferta: solo http(s) con dominio. Es contenido no confiable y la UI la enlaza."""
    url = require_str(item, key)
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError(f"`{key}` no es una URL http(s)")
    return url


def safe_id(value: str) -> str:
    """Id de la fuente que va en la ruta de una URL (InfoJobs): sin `/`, `?`, `#` ni `..`."""
    if not _SAFE_ID.match(value):
        raise ValueError("`id` con caracteres no válidos")
    return value


def optional_str(value: Any) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def _walk(node: Any) -> Iterator[str]:
    tag = node.tag if isinstance(node.tag, str) else ""
    if tag in ("script", "style"):
        if node.tail:
            yield node.tail
        return
    if tag == "li":
        yield "\n- "
    if node.text:
        yield node.text
    for child in node:
        yield from _walk(child)
    if tag in _BLOCK_TAGS:
        yield "\n"
    if node.tail:
        yield node.tail


def html_fragment_to_text(fragment: str) -> str:
    """Texto legible de una descripción en HTML: un salto por bloque y `- ` en las listas."""
    if not fragment.strip():
        return ""
    try:
        root = lxml.html.fragment_fromstring(fragment, create_parent="div")
    except (ParserError, ValueError):
        return clean_text(fragment)
    return clean_text("".join(_walk(root)))


def unescape_html(value: str) -> str:
    """Greenhouse devuelve el HTML de la descripción escapado como entidades (`&lt;p&gt;`)."""
    return html.unescape(value)


def join_text(*parts: str | None) -> str:
    return clean_text("\n\n".join(p for p in parts if p and p.strip()))[:MAX_TEXT_CHARS]


def parse_datetime(value: Any) -> datetime | None:
    """ISO 8601 (con o sin zona, que se toma como UTC) o milisegundos desde 1970 (Lever)."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(value / 1000, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def looks_remote(*values: str | None) -> bool | None:
    text = " ".join(v.lower() for v in values if v)
    if not text:
        return None
    return True if any(w in text for w in ("remote", "remoto", "teletrabajo")) else None
