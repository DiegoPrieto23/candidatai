"""Plataforma de un formulario de candidatura y la URL donde está el formulario.

Por la URL se reconocen Greenhouse, Lever, Ashby y LinkedIn. Cualquier otra web se mira en la
página (`inspect`): un iframe de un ATS conocido lleva a su URL; un formulario con correo o
adjunto es `generic`; si no, `unknown`. LinkedIn y `unknown` solo se abren (ADR-009).
"""

import contextlib
import ipaddress
import re
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from playwright.sync_api import Page

from app.core.config import get_settings

Platform = Literal["greenhouse", "lever", "ashby", "generic", "linkedin", "unknown"]
PLATFORMS: tuple[Platform, ...] = ("greenhouse", "lever", "ashby", "generic", "linkedin", "unknown")
# Las que se rellenan solas; el resto, «abrir y preparar».
AUTOMATED: frozenset[str] = frozenset({"greenhouse", "lever", "ashby", "generic"})

_HOSTS: dict[str, tuple[str, ...]] = {
    "greenhouse": ("greenhouse.io",),
    "lever": ("lever.co",),
    "ashby": ("ashbyhq.com",),
    "linkedin": ("linkedin.com",),
}

_LEVER_JOB = re.compile(r"^/[^/]+/[0-9a-f-]{36}/?$", re.I)
_ASHBY_JOB = re.compile(r"^/[^/]+/[0-9a-f-]{36}/?$", re.I)


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def detect(url: str) -> Platform | None:
    """La plataforma por la URL, o `None` si no se reconoce (hay que mirar la página)."""
    host = (urlsplit(url).hostname or "").lower()
    for platform, domains in _HOSTS.items():
        if any(_host_matches(host, domain) for domain in domains):
            return platform  # type: ignore[return-value]
    return None


def url_problem(url: str) -> str | None:
    """Por qué no se abre esta URL en el navegador de las candidaturas (con tus sesiones), o
    `None`. Solo `http`/`https` y nunca la propia máquina (la API de la app), salvo en tests."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return f"La URL de la oferta no es una web («{parts.scheme or '?'}:»): no se abre."
    host = parts.hostname.lower()
    loopback = host == "localhost" or host.endswith(".localhost") or host == "0.0.0.0"
    with contextlib.suppress(ValueError):
        loopback = loopback or ipaddress.ip_address(host).is_loopback
    if loopback and not get_settings().applier_allow_loopback:
        return "La URL de la oferta apunta a este mismo equipo: no se abre."
    return None


def application_url(platform: str, url: str) -> str:
    """La URL del formulario: en Lever, `…/apply`; en Ashby, `…/application`. El resto, igual."""
    parts = urlsplit(url)
    path = parts.path
    if platform == "lever" and _LEVER_JOB.match(path):
        path = path.rstrip("/") + "/apply"
    elif platform == "ashby" and _ASHBY_JOB.match(path):
        path = path.rstrip("/") + "/application"
    return urlunsplit((parts.scheme, parts.netloc, path, parts.query, ""))


_INSPECT_JS = """() => {
  const frames = [...document.querySelectorAll('iframe[src]')].map(f => f.src);
  const fields = document.querySelectorAll(
    'form input[type=email], form input[type=file], form textarea, ' +
    'input[type=email], input[type=file]');
  return {frames, form: fields.length > 0};
}"""


def inspect(page: Page) -> tuple[Platform, str | None]:
    """Para una URL no reconocida: la plataforma según la página y, si el formulario está en un
    iframe de un ATS conocido, la URL de ese iframe (para abrirla directamente)."""
    found = page.evaluate(_INSPECT_JS)
    for src in found["frames"]:
        platform = detect(src)
        if platform in AUTOMATED:
            return platform, src  # type: ignore[return-value]
    return ("generic" if found["form"] else "unknown"), None
