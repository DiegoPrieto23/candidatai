"""Extracción de ofertas de un correo de alertas, común a todos los parsers.

Una alerta es una lista de «tarjetas»: un enlace a la oferta con el título y, cerca, la empresa y
la ubicación (en LinkedIn, «Empresa · Ubicación»). Se localiza cada enlace con identidad de
plataforma (`services/platforms.py`), se sube por el HTML hasta el bloque más grande que solo
habla de esa oferta y se leen sus líneas de texto. Los parsers de cada plataforma ajustan qué
líneas son ruido («Solicitud sencilla», «Hace 2 días»…).

Sin HTML, se lee el texto plano: las líneas anteriores a cada enlace son título, empresa y
ubicación, en ese orden.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import lxml.html
from lxml.etree import ParserError

from app.services.ingestion.email.message import AlertMessage
from app.services.platforms import PlatformId, canonical_url, detect

MAX_ITEMS = 200  # por correo; una alerta normal trae entre 5 y 30
MAX_FIELD_CHARS = 300
MAX_ANCHORS = 1_000  # enlaces de oferta que se miran por correo (uno hostil puede traer miles)
MAX_CARD_LINES = 8  # líneas de una tarjeta: título, empresa, ubicación y algo de ruido
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_URL_IN_TEXT = re.compile(r"https?://[^\s<>\"')\]]+")
_SEPARATORS = re.compile(r"\s+[·•|]\s+")
# Ruido común a cualquier plataforma (sobre la línea plegada a minúsculas).
COMMON_NOISE = (
    r"^(?:ver|view|see|apply|solicitar|aplicar|inscribirme)\b",
    r"^(?:hace|posted|publicad[oa]|actualizad[oa])\b",
    r"\b(?:ago|d[ií]as?|horas?|semanas?|days?|hours?|weeks?)$",
    r"^(?:nuevo|nueva|new|promocionad[oa]|promoted|destacad[oa]|urgente)$",
    r"^\d+\s",
    r"^[\W\d_]+$",
)


@dataclass(frozen=True)
class AlertItem:
    """Una oferta anunciada en un correo. Todo es texto no confiable."""

    platform: str
    external_id: str
    url: str
    title: str
    company: str | None
    location: str | None


@dataclass
class ParseOptions:
    platform: str | None = None  # solo enlaces de esta plataforma (None: cualquiera conocida)
    noise: tuple[str, ...] = ()  # patrones extra de líneas que no son título, empresa ni lugar
    _compiled: list[re.Pattern[str]] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self._compiled = [re.compile(p, re.IGNORECASE) for p in (*COMMON_NOISE, *self.noise)]

    def is_noise(self, line: str) -> bool:
        lowered = line.lower()
        return any(p.search(lowered) for p in self._compiled)


def _clip(value: str | None) -> str | None:
    # Sin caracteres de control: el texto acaba en la consola (secuencias ANSI) y en la UI.
    value = " ".join(_CONTROL.sub(" ", value or "").split())
    return value[:MAX_FIELD_CHARS] or None


def resolve_link(href: str) -> PlatformId | None:
    """Identidad de la oferta de un enlace, mirando también la URL de destino de un redirector de
    seguimiento (`?url=https%3A…`). Nunca se sigue el enlace."""
    pid = detect(href)
    if pid is not None:
        return pid
    try:
        query = parse_qsl(urlsplit(href).query)
    except ValueError:
        return None
    for _key, value in query:
        if value.startswith(("http://", "https://")):
            pid = detect(value)
            if pid is not None:
                return pid
    return None


def clean_url(href: str, pid: PlatformId) -> str:
    """URL de la oferta sin parámetros de seguimiento."""
    canonical = canonical_url(pid)
    if canonical:
        return canonical
    target = (
        href
        if detect(href) == pid
        else next((v for _k, v in parse_qsl(urlsplit(href).query) if detect(v) == pid), href)
    )
    parts = urlsplit(target)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _fields(lines: list[str], title: str, options: ParseOptions) -> tuple[str | None, str | None]:
    """Empresa y ubicación a partir de las líneas de la tarjeta, sin el título."""
    rest = [line for line in lines if line != title and not options.is_noise(line)]
    for line in rest:
        parts = _SEPARATORS.split(line)
        if len(parts) >= 2:  # «Empresa · Ubicación» (· Modalidad…)
            return _clip(parts[0]), _clip(parts[1])
    company = rest[0] if rest else None
    location = rest[1] if len(rest) > 1 else None
    return _clip(company), _clip(location)


def _block_lines(element: lxml.html.HtmlElement) -> list[str]:
    lines: list[str] = []
    for text in element.itertext():
        line = _clip(text)
        if line and (not lines or lines[-1] != line):
            lines.append(line)
            if len(lines) >= MAX_CARD_LINES:
                break
    return lines


def _from_html(html: str, options: ParseOptions) -> list[AlertItem]:
    try:
        doc = lxml.html.document_fromstring(html)
    except (ParserError, ValueError):
        return []
    for bad in doc.xpath("//script|//style|//head"):
        bad.drop_tree()

    anchors: dict[PlatformId, list[tuple[lxml.html.HtmlElement, str]]] = {}
    # Ofertas enlazadas dentro de cada elemento, calculado una vez subiendo desde cada enlace.
    inside: dict[lxml.html.HtmlElement, set[PlatformId]] = {}
    seen = 0
    for anchor in doc.iter("a"):
        href = (anchor.get("href") or "").strip()
        pid = resolve_link(href)
        if pid is None or (options.platform and pid.platform != options.platform):
            continue
        anchors.setdefault(pid, []).append((anchor, href))
        node: lxml.html.HtmlElement | None = anchor
        while node is not None:
            ids = inside.setdefault(node, set())
            if pid in ids and node is not anchor:
                break  # los antepasados ya la tienen
            ids.add(pid)
            node = node.getparent()
        seen += 1
        if seen >= MAX_ANCHORS:
            break

    items: list[AlertItem] = []
    for pid, links in anchors.items():
        first, href = links[0]
        card = first
        # La tarjeta: el bloque más grande que solo habla de esta oferta, sin llegar a `body`.
        while (
            (parent := card.getparent()) is not None
            and parent.tag not in ("body", "html")
            and inside.get(parent) == {pid}
        ):
            card = parent
        texts = [_clip(a.text_content()) for a, _ in links]
        titles = [t for t in texts if t and not options.is_noise(t)]
        lines = _block_lines(card)
        if titles:
            title = max(titles, key=len)
        else:
            candidates = [line for line in lines if not options.is_noise(line)]
            if not candidates:
                continue
            title = candidates[0]
        company, location = _fields(lines, title, options)
        if company is None:
            alts = [_clip(img.get("alt")) for img in card.iter("img")]
            company = next((a for a in alts if a and not options.is_noise(a)), None)
        items.append(
            AlertItem(
                platform=pid.platform,
                external_id=pid.external_id,
                url=clean_url(href, pid),
                title=_clip(title) or title,
                company=company,
                location=location,
            )
        )
        if len(items) >= MAX_ITEMS:
            break
    return items


def _from_text(text: str, options: ParseOptions) -> list[AlertItem]:
    items: dict[PlatformId, AlertItem] = {}
    block: list[str] = []
    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        urls = _URL_IN_TEXT.findall(line)
        pids = [(u, resolve_link(u)) for u in urls]
        found = [(u, p) for u, p in pids if p and options.platform in (None, p.platform)]
        if not found:
            if not line:
                continue
            if not urls and not options.is_noise(line):
                block.append(line)
            continue
        href, pid = found[0]
        assert pid is not None
        # Lo que queda en la línea antes del enlace («Ver empleo: https://…») es ruido o título.
        head = line.split(href)[0].strip(" :-")
        if head and not options.is_noise(head):
            block.append(head)
        if block and pid not in items:
            fields = (block[-3:] if len(block) >= 3 else block) + [None, None]
            items[pid] = AlertItem(
                platform=pid.platform,
                external_id=pid.external_id,
                url=clean_url(href, pid),
                title=_clip(fields[0]) or "",
                company=_clip(fields[1]),
                location=_clip(fields[2]),
            )
        block = []
        if len(items) >= MAX_ITEMS:
            break
    return [item for item in items.values() if item.title]


def extract_items(message: AlertMessage, options: ParseOptions) -> list[AlertItem]:
    """Ofertas del correo: del HTML si lo hay y da resultados; si no, del texto plano."""
    if message.html:
        items = _from_html(message.html, options)
        if items:
            return items
    return _from_text(message.text or "", options) if message.text else []


def dedupe(items: Iterable[AlertItem]) -> list[AlertItem]:
    seen: set[tuple[str, str]] = set()
    result = []
    for item in items:
        key = (item.platform, item.external_id)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
