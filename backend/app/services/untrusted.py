"""Detección de riesgo en el contenido no confiable de una oferta, al guardarla (ADR-012).

Dos señales, ambas deterministas y sin red:

- `hidden_text`: texto del HTML original que un humano no ve (estilos en línea, `hidden`,
  `aria-hidden`), típico de instrucciones dirigidas a una IA.
- `injection_phrase`: frases de `config/injection_patterns.yaml` en el texto limpio o en el texto
  oculto, comparadas sin mayúsculas, tildes, signos ni espacios repetidos.

Es una red de seguridad: se avisa, no se censura. La oferta se guarda igualmente.
"""

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum

import lxml.html
from lxml.etree import ParserError, _Element

from app.core.policies import get_injection_patterns

EXCERPT_MAX_CHARS = 200

# Elementos cuyo contenido no es texto visible por diseño: no cuentan como texto oculto.
_NON_TEXT_TAGS = frozenset({"script", "style", "template", "noscript", "head", "title", "meta"})
# Zonas donde ocultar texto es habitual y legítimo (submenús, banners de cookies, desplegables).
# El texto oculto ahí no activa `hidden_text`, pero sí se revisa en busca de frases de inyección.
_BENIGN_TAGS = frozenset({"nav", "header", "footer", "aside", "dialog", "form", "select", "menu"})
_BENIGN_ROLES = frozenset({"navigation", "dialog", "alertdialog", "menu", "menubar", "tooltip"})
_LINK_DENSITY = 0.8  # un bloque oculto que es casi todo enlaces es un menú
_OFFSCREEN_PX = 1000
_ZERO_SIZE = re.compile(r"^0(?:\.0+)?(?:px|pt|em|rem|%|vh|vw)?$")
_LENGTH_PX = re.compile(r"^(-?\d+(?:\.\d+)?)(px)?$")
_NAMED_COLORS = {
    "white": "#ffffff",
    "black": "#000000",
    "transparent": "transparent",
}


class RiskFlag(StrEnum):
    HIDDEN_TEXT = "hidden_text"
    INJECTION_PHRASE = "injection_phrase"


@dataclass(frozen=True)
class HiddenText:
    reason: str
    text: str
    benign: bool = False  # en una zona donde ocultar texto es habitual (menú, diálogo…)


@dataclass(frozen=True)
class PhraseMatch:
    phrase: str
    excerpt: str


@dataclass(frozen=True)
class RiskReport:
    flags: list[RiskFlag]
    excerpt: str | None

    @property
    def risky(self) -> bool:
        return bool(self.flags)


# --- Texto oculto ---------------------------------------------------------------------------


def _parse_style(value: str | None) -> dict[str, str]:
    if not value:
        return {}
    style: dict[str, str] = {}
    for declaration in value.split(";"):
        prop, sep, raw = declaration.partition(":")
        if sep:
            clean = raw.lower().replace("!important", "").strip()
            style[prop.strip().lower()] = clean
    return style


def _px(value: str | None) -> float | None:
    if value is None:
        return None
    match = _LENGTH_PX.match(value.replace(" ", ""))
    return float(match.group(1)) if match else None


def _normalize_color(value: str | None) -> str | None:
    if not value:
        return None
    color = value.replace(" ", "").lower()
    color = _NAMED_COLORS.get(color, color)
    if re.fullmatch(r"#[0-9a-f]{3}", color):
        color = "#" + "".join(ch * 2 for ch in color[1:])
    return color


def _background(element: _Element) -> str | None:
    """Color de fondo en línea del elemento o del ancestro más cercano que lo declare."""
    node: _Element | None = element
    while node is not None:
        style = _parse_style(node.get("style"))
        for prop in ("background-color", "background"):
            if prop in style:
                color = _normalize_color(style[prop].split()[0] if style[prop] else None)
                if color and color != "transparent":
                    return color
        node = node.getparent()
    return None


def _hidden_reason(element: _Element) -> str | None:
    """Por qué el propio elemento oculta su contenido, o `None` si no lo oculta."""
    if element.get("hidden") is not None:
        return "hidden"
    if (element.get("aria-hidden") or "").strip().lower() == "true":
        return "aria-hidden"
    style = _parse_style(element.get("style"))
    if not style:
        return None
    if style.get("display") == "none":
        return "display:none"
    if style.get("visibility") in {"hidden", "collapse"}:
        return "visibility:hidden"
    if _ZERO_SIZE.match(style.get("font-size", "").replace(" ", "")):
        return "font-size:0"
    opacity = style.get("opacity")
    if opacity is not None:
        try:
            if float(opacity) < 0.05:
                return "opacity:0"
        except ValueError:
            pass
    if style.get("position") in {"absolute", "fixed"}:
        for prop in ("left", "top", "right", "bottom"):
            offset = _px(style.get(prop))
            if offset is not None and offset <= -_OFFSCREEN_PX:
                return "offscreen"
    indent = _px(style.get("text-indent"))
    if indent is not None and indent <= -_OFFSCREEN_PX:
        return "offscreen"
    color = _normalize_color(style.get("color"))
    if color and color == _background(element):
        return "color=background"
    return None


def _visible_text(element: _Element) -> str:
    return " ".join(element.text_content().split())


def _is_benign_zone(element: _Element) -> bool:
    return (
        element.tag in _BENIGN_TAGS
        or (element.get("role") or "").strip().lower() in _BENIGN_ROLES
        or (element.get("aria-modal") or "").strip().lower() == "true"
    )


def _is_link_list(element: _Element, text: str) -> bool:
    link_chars = sum(len(_visible_text(a)) for a in element.iter("a"))
    return link_chars >= _LINK_DENSITY * len(text)


def find_hidden_text(html: str, min_chars: int | None = None) -> list[HiddenText]:
    """Bloques de texto oculto en el HTML, del más externo (no se repiten los anidados).

    Los que están en una zona benigna o son listas de enlaces se devuelven con `benign=True`.
    """
    if min_chars is None:
        min_chars = get_injection_patterns().hidden_text_min_chars
    try:
        root = lxml.html.document_fromstring(html)
    except (ParserError, ValueError):
        return []
    found: list[HiddenText] = []

    def walk(element: _Element, benign: bool) -> None:
        for child in element:
            if not isinstance(child.tag, str) or child.tag in _NON_TEXT_TAGS:
                continue
            child_benign = benign or _is_benign_zone(child)
            reason = _hidden_reason(child)
            if reason is None:
                walk(child, child_benign)
                continue
            text = _visible_text(child)
            if len(text) >= min_chars:
                child_benign = child_benign or _is_link_list(child, text)
                found.append(HiddenText(reason=reason, text=text, benign=child_benign))

    walk(root, benign=False)
    return found


# --- Frases de inyección --------------------------------------------------------------------


def _normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Minúsculas, sin tildes, signos como espacio y espacios simples.

    Devuelve también, para cada carácter del resultado, su posición en el texto original, para
    poder citar un extracto literal.
    """
    chars: list[str] = []
    positions: list[int] = []
    for index, original in enumerate(text):
        for ch in unicodedata.normalize("NFKD", original):
            if unicodedata.combining(ch):
                continue
            ch = ch.lower() if ch.isalnum() else " "
            if ch == " " and (not chars or chars[-1] == " "):
                continue
            chars.append(ch)
            positions.append(index)
    return "".join(chars).rstrip(), positions


def _normalize(text: str) -> str:
    return _normalize_with_map(text)[0]


def _excerpt(text: str, start: int, end: int) -> str:
    """Hasta `EXCERPT_MAX_CHARS` caracteres del original alrededor de [start, end)."""
    budget = max(EXCERPT_MAX_CHARS - (end - start), 0)
    lo = max(start - budget // 3, 0)
    hi = min(end + budget - (start - lo), len(text))
    # No cortar palabras por la mitad en los bordes del extracto.
    while 0 < lo < start and not text[lo - 1].isspace():
        lo += 1
    while end < hi < len(text) and not text[hi].isspace():
        hi -= 1
    excerpt = " ".join(text[lo:hi].split())
    return excerpt[:EXCERPT_MAX_CHARS]


def find_injection_phrases(text: str, phrases: list[str] | None = None) -> list[PhraseMatch]:
    """Frases de inyección presentes en `text`, con un extracto literal de cada una."""
    if phrases is None:
        phrases = get_injection_patterns().phrases
    normalized, positions = _normalize_with_map(text)
    haystack = f" {normalized} "
    matches: list[PhraseMatch] = []
    for phrase in phrases:
        needle = _normalize(phrase)
        if not needle:
            continue
        # Espacios alrededor para casar palabras completas («ia» no casa dentro de «media»).
        at = haystack.find(f" {needle} ")
        if at < 0:
            continue
        start = positions[at]  # `at` apunta al espacio previo en `haystack` = índice en normalized
        end = positions[at + len(needle) - 1] + 1
        matches.append(PhraseMatch(phrase=phrase, excerpt=_excerpt(text, start, end)))
    return matches


# --- Evaluación conjunta --------------------------------------------------------------------


def assess(text: str, html: str | None = None) -> RiskReport:
    """Señales de riesgo de una oferta: su texto limpio y, si lo hay, el HTML original."""
    hidden = find_hidden_text(html) if html else []
    phrase_matches = find_injection_phrases(text)
    for block in hidden:
        phrase_matches.extend(find_injection_phrases(block.text))

    suspicious = [block for block in hidden if not block.benign]
    flags: list[RiskFlag] = []
    if suspicious:
        flags.append(RiskFlag.HIDDEN_TEXT)
    if phrase_matches:
        flags.append(RiskFlag.INJECTION_PHRASE)

    excerpt: str | None = None
    if phrase_matches:
        excerpt = phrase_matches[0].excerpt
    elif suspicious:
        excerpt = suspicious[0].text[:EXCERPT_MAX_CHARS]
    return RiskReport(flags=flags, excerpt=excerpt)
