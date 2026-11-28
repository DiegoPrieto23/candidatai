"""En qué web se abre una oferta (fase 48.4): un portal (LinkedIn, InfoJobs…), el ATS con el que
publica la empresa (Greenhouse, Lever…) o otra web, para que el botón de la ficha diga adónde lleva.

Solo se mira el dominio de la URL guardada: no se visita nada. Aquí vive también la lista de los
dominios de ATS que usan la ingesta y la resolución de la web de una empresa.
"""

import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel

from app.services import platforms

# Dominio del ATS → su nombre. Una oferta en uno de ellos no dice cuál es la web de la empresa.
ATS_NAMES: dict[str, str] = {
    "greenhouse.io": "Greenhouse",
    "lever.co": "Lever",
    "ashbyhq.com": "Ashby",
    "personio.de": "Personio",
    "personio.com": "Personio",
    "teamtailor.com": "Teamtailor",
    "workable.com": "Workable",
    "smartrecruiters.com": "SmartRecruiters",
    "recruitee.com": "Recruitee",
}
ATS_HOSTS: tuple[str, ...] = tuple(ATS_NAMES)
# Otros ATS que solo se nombran (la ingesta no los trata aparte).
_MORE_ATS: dict[str, str] = {
    "myworkdayjobs.com": "Workday",
    "bamboohr.com": "BambooHR",
    "breezy.hr": "Breezy HR",
    "jobvite.com": "Jobvite",
    "factorialhr.com": "Factorial",
    "join.com": "JOIN",
}

# Portales de empleo, aparte de los que reconoce `platforms` por su dominio.
PLATFORM_NAMES: dict[str, str] = {
    "linkedin": "LinkedIn",
    "infojobs": "InfoJobs",
    "indeed": "Indeed",
    "tecnoempleo": "Tecnoempleo",
}
_MORE_PORTALS: dict[str, str] = {
    "adzuna.es": "Adzuna",
    "adzuna.com": "Adzuna",
    "adzuna.co.uk": "Adzuna",
    "getmanfred.com": "Manfred",
    "freehire.me": "freehire",
    "glassdoor.com": "Glassdoor",
    "glassdoor.es": "Glassdoor",
    "welcometothejungle.com": "Welcome to the Jungle",
    "talent.com": "Talent.com",
    "jobfluent.com": "JobFluent",
    "domestika.org": "Domestika",
    "remoteok.com": "Remote OK",
    "weworkremotely.com": "We Work Remotely",
    "wellfound.com": "Wellfound",
}

SiteKind = Literal["portal", "ats", "web"]


class JobSite(BaseModel):
    kind: SiteKind
    name: str | None  # «LinkedIn», «Greenhouse»; `None` en otra web
    host: str  # el dominio, sin `www.`


_HOST_CHARS = re.compile(r"^[a-z0-9.:\[\]-]{1,253}$")


def _ascii_host(host: str) -> str | None:
    """El dominio en ASCII (un dominio con letras de otros alfabetos, en punycode: `xn--…`, para
    que no se vea como el de otra web), o `None` si no es un nombre de servidor."""
    try:
        host = host.encode("idna").decode("ascii") if not host.isascii() else host
    except UnicodeError:
        return None
    return host if _HOST_CHARS.match(host) else None


def host_is(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def _named(host: str, names: dict[str, str]) -> str | None:
    for domain, name in names.items():
        if host_is(host, domain):
            return name
    return None


def site_of(url: str | None) -> JobSite | None:
    """La web de una oferta, o `None` si la URL no es `http(s)` con dominio."""
    if not url:
        return None
    try:
        parts = urlsplit(url.strip())
        host = _ascii_host((parts.hostname or "").lower().rstrip("."))
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"} or not host:
        return None
    shown = host.removeprefix("www.")
    platform = platforms.platform_of_host(host)
    if platform is not None:
        return JobSite(kind="portal", name=PLATFORM_NAMES.get(platform, platform), host=shown)
    if (portal := _named(host, _MORE_PORTALS)) is not None:
        return JobSite(kind="portal", name=portal, host=shown)
    ats = _named(host, ATS_NAMES) or _named(host, _MORE_ATS)
    if ats is not None:
        return JobSite(kind="ats", name=ats, host=shown)
    return JobSite(kind="web", name=None, host=shown)
