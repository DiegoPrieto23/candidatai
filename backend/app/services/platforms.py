"""Identidad de una oferta por plataforma (fase 09b): `platform` + `external_id` a partir de la URL.

Así una alerta por correo, una captura con el botón y una búsqueda posterior reconocen que son la
misma oferta. Patrones comprobados con URLs públicas reales (octubre de 2026):

- LinkedIn: `/jobs/view/<id>`, `/jobs/view/<slug>-<id>`, `/comm/jobs/view/<id>` (correos) y el
  parámetro `currentJobId` (búsqueda y colecciones).
- InfoJobs: `/<ciudad>/<slug>/of-i<30 hex>`; el mismo id que da su API.
- Indeed: parámetros `jk` o `vjk` (16 hex), en cualquier dominio de país.
- Tecnoempleo: `/<slug>/<tecnologías>/rf-<20 hex>`.
"""

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

PLATFORM_LABELS: dict[str, str] = {
    "linkedin": "LinkedIn",
    "infojobs": "InfoJobs",
    "indeed": "Indeed",
    "tecnoempleo": "Tecnoempleo",
}

# Plataformas cuya página de oferta no se descarga nunca desde el código (ADR-016): sus ofertas
# entran como resumen y se completan con el botón de captura.
_NO_FETCH = frozenset({"linkedin"})

_LINKEDIN_VIEW = re.compile(r"/jobs/view/(?:[^/]*?-)?(\d{6,20})(?:/|$)")
_INFOJOBS = re.compile(r"/of-i([0-9a-f]{20,40})(?:/|$)", re.IGNORECASE)
_TECNOEMPLEO = re.compile(r"/rf-([0-9a-f]{10,40})(?:/|$)", re.IGNORECASE)
_DIGITS = re.compile(r"^\d{6,20}$")
_INDEED_HOST = re.compile(r"(?:^|\.)indeed\.(?:com|[a-z]{2}|co\.[a-z]{2}|com\.[a-z]{2})$")
_HEX16 = re.compile(r"^[0-9a-f]{16}$", re.IGNORECASE)


@dataclass(frozen=True)
class PlatformId:
    platform: str
    external_id: str


def _host_is(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def _host_is_indeed(host: str) -> bool:
    # indeed.com, es.indeed.com, indeed.es, uk.indeed.co.uk, br.indeed.com.br…
    return _INDEED_HOST.search(host) is not None


def platform_of_host(host: str | None) -> str | None:
    """Plataforma de un dominio, sin mirar la ruta."""
    host = (host or "").lower().rstrip(".")
    if _host_is(host, "linkedin.com"):
        return "linkedin"
    if _host_is(host, "infojobs.net"):
        return "infojobs"
    if _host_is(host, "tecnoempleo.com"):
        return "tecnoempleo"
    if _host_is_indeed(host):
        return "indeed"
    return None


def detect(url: str | None) -> PlatformId | None:
    """`PlatformId` de la URL de una oferta, o `None` si no es de una plataforma conocida o no
    trae el id (p. ej. una página de búsqueda sin oferta seleccionada)."""
    if not url:
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"}:
        return None
    platform = platform_of_host(parts.hostname)
    if platform is None:
        return None
    path = parts.path
    query = parse_qs(parts.query)

    if platform == "linkedin":
        match = _LINKEDIN_VIEW.search(path)
        if match:
            return PlatformId("linkedin", match.group(1))
        current = query.get("currentJobId", [""])[0]
        return PlatformId("linkedin", current) if _DIGITS.match(current) else None
    if platform == "infojobs":
        match = _INFOJOBS.search(path)
        return PlatformId("infojobs", match.group(1).lower()) if match else None
    if platform == "tecnoempleo":
        match = _TECNOEMPLEO.search(path)
        return PlatformId("tecnoempleo", match.group(1).lower()) if match else None
    for key in ("jk", "vjk"):
        value = query.get(key, [""])[0]
        if _HEX16.match(value):
            return PlatformId("indeed", value.lower())
    return None


def can_fetch(platform: str | None) -> bool:
    """Si la página de una oferta de esa plataforma se puede descargar con el alta por URL."""
    return platform not in _NO_FETCH


def canonical_url(pid: PlatformId) -> str | None:
    """URL limpia de la oferta (sin parámetros de seguimiento), si la plataforma tiene una."""
    if pid.platform == "linkedin":
        return f"https://www.linkedin.com/jobs/view/{pid.external_id}/"
    if pid.platform == "indeed":
        return f"https://www.indeed.com/viewjob?jk={pid.external_id}"
    return None
