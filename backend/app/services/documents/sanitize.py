"""Saneado de plantillas html (fase 08b, `CV_TEMPLATES.md` §Motor html).

Una plantilla html puede venir de un CV ajeno recreado por un agente: es contenido no confiable.
Dos capas:

- `scan`: al validar, busca en `template.html` y `style.css` lo que no se admite (`<script>`,
  atributos `on*`, `<iframe>`, `<object>`, `<embed>`, `javascript:` y URLs remotas en `src`,
  `href` y `url()`) y dice qué y en qué línea. `validate` falla si hay algo.
- `clean_html`: al renderizar, quita lo mismo del HTML ya generado, por si se coló algo después de
  validar. Además Chromium imprime sin JavaScript y sin red (`engines/html.py`).
"""

import re
from dataclasses import dataclass

import lxml.html

# Etiquetas que no se admiten en ninguna parte del documento.
FORBIDDEN_TAGS = ("script", "iframe", "frame", "frameset", "object", "embed", "applet", "base")
_URL_ATTRIBUTES = ("src", "href", "srcset", "action", "formaction", "poster", "data", "xlink:href")

# Una URL que sale del equipo o ejecuta código: esquema remoto, `//host` o `javascript:`. Las
# relativas, `data:`, `mailto:` y `tel:` se admiten (no piden nada a la red al imprimir).
_REMOTE_URL = re.compile(r"^\s*(?:https?:|ftps?:|wss?:|file:|javascript:|//)", re.IGNORECASE)
_BAD_SCHEME = re.compile(r"^\s*(?!data:|mailto:|tel:)[a-z][a-z0-9+.-]*:", re.IGNORECASE)

_SCAN_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"<\s*(" + "|".join(FORBIDDEN_TAGS) + r")\b", re.IGNORECASE),
        "etiqueta <{0}>",
    ),
    (re.compile(r"<[^>]*\s(on[a-z]+)\s*=", re.IGNORECASE), "atributo {0}"),
    (
        re.compile(
            r"\b(" + "|".join(_URL_ATTRIBUTES) + r")\s*=\s*[\"']?\s*"
            r"((?:https?:|ftps?:|wss?:|file:|javascript:|//)[^\s\"'>]*)",
            re.IGNORECASE,
        ),
        "URL externa en {0}: {1}",
    ),
    (
        re.compile(
            r"url\(\s*[\"']?\s*((?:https?:|ftps?:|wss?:|file:|javascript:|//)[^)\"']*)",
            re.IGNORECASE,
        ),
        "URL externa en url(): {0}",
    ),
    (
        re.compile(
            r"@import\s+(?:url\()?\s*[\"']?\s*((?:https?:|ftps?:|file:|//)[^)\"';]*)",
            re.IGNORECASE,
        ),
        "@import externo: {0}",
    ),
)


@dataclass(frozen=True)
class Finding:
    file: str
    line: int
    what: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.what}"


_SRCSET = re.compile(r"\bsrcset\s*=\s*([\"'])(.*?)\1", re.IGNORECASE | re.DOTALL)
_IMAGE_SET = re.compile(r"image-set\(([^)]*)\)", re.IGNORECASE)
_QUOTED = re.compile(r"([\"'])(.*?)\1")


def scan(text: str, filename: str) -> list[Finding]:
    """Lo que no se admite en `text` (HTML o CSS), con su línea. Lista vacía si está limpio."""
    findings: list[Finding] = []
    seen: set[tuple[int, str]] = set()

    def add(position: int, what: str) -> None:
        line = text.count("\n", 0, position) + 1
        if (line, what) not in seen:
            seen.add((line, what))
            findings.append(Finding(file=filename, line=line, what=what))

    for pattern, message in _SCAN_RULES:
        for match in pattern.finditer(text):
            add(match.start(), message.format(*(g.strip() for g in match.groups())))
    # Todas las entradas de `srcset` y de `image-set()`, no solo la primera.
    for match in _SRCSET.finditer(text):
        for entry in match.group(2).split(","):
            url = entry.strip().split(" ")[0]
            if url and is_remote_url(url):
                add(match.start(), f"URL externa en srcset: {url}")
    for match in _IMAGE_SET.finditer(text):
        for quoted in _QUOTED.finditer(match.group(1)):
            if is_remote_url(quoted.group(2)):
                add(match.start(), f"URL externa en image-set(): {quoted.group(2)}")
    return sorted(findings, key=lambda f: (f.line, f.what))


def is_remote_url(value: str) -> bool:
    """`True` si la URL sale del equipo o ejecuta código (sí admite rutas relativas y `data:`)."""
    return bool(_REMOTE_URL.match(value) or _BAD_SCHEME.match(value))


_CSS_URL = re.compile(r"url\(\s*([\"']?)([^)\"']*)\1\s*\)", re.IGNORECASE)
_CSS_IMPORT = re.compile(r"@import[^;]*;?", re.IGNORECASE)


def clean_css(css: str) -> str:
    """Quita `@import`, las `url()` remotas y los `image-set()` con alguna URL remota."""

    def replace(match: re.Match[str]) -> str:
        return "none" if is_remote_url(match.group(2)) else match.group(0)

    def replace_set(match: re.Match[str]) -> str:
        remote = any(is_remote_url(q.group(2)) for q in _QUOTED.finditer(match.group(1)))
        return "none" if remote else match.group(0)

    without_imports = _CSS_IMPORT.sub("", css)
    return _IMAGE_SET.sub(replace_set, _CSS_URL.sub(replace, without_imports))


_XML_DECLARATION = re.compile(r"^\s*<\?xml[^>]*\?>", re.IGNORECASE)
EMPTY_DOCUMENT = "<!DOCTYPE html>\n<html><head></head><body></body></html>"


def clean_html(html: str) -> str:
    """Devuelve el documento sin etiquetas prohibidas, atributos `on*` ni URLs remotas."""
    # lxml no admite un documento vacío ni una declaración XML con codificación en un str.
    html = _XML_DECLARATION.sub("", html)
    if not html.strip():
        return EMPTY_DOCUMENT
    root = lxml.html.document_fromstring(html)
    for element in list(root.iter()):
        if not isinstance(element.tag, str):
            # Comentarios e instrucciones de proceso: fuera (pueden llevar condicionales de IE).
            if element.getparent() is not None:
                element.drop_tree()
            continue
        tag = element.tag.lower()
        if tag in FORBIDDEN_TAGS:
            element.drop_tree()
            continue
        if tag == "meta" and (element.get("http-equiv") or "").lower() == "refresh":
            element.drop_tree()
            continue
        if tag == "link" and is_remote_url(element.get("href", "")):
            element.drop_tree()
            continue
        if tag == "style" and element.text:
            element.text = clean_css(element.text)
        for name in list(element.attrib):
            value = element.attrib[name]
            lower = name.lower()
            if (
                lower.startswith("on")
                or (lower in _URL_ATTRIBUTES and is_remote_url(value))
                or (lower == "srcset" and any(is_remote_url(p) for p in value.split(",")))
            ):
                del element.attrib[name]
            elif lower == "style":
                element.attrib[name] = clean_css(value)
    return lxml.html.tostring(root, doctype="<!DOCTYPE html>", encoding="unicode")
