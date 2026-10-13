"""Plataforma de un formulario de candidatura y la URL donde está el formulario.

Por la URL se reconocen Greenhouse, Lever, Ashby, LinkedIn y los portales de empleo (InfoJobs,
Tecnoempleo, Indeed, Glassdoor, Manfred). Cualquier otra web se mira en la página (`inspect`): un
iframe de un ATS conocido lleva a su URL; un formulario de candidatura (adjunto, o correo y nombre)
es `generic`; si no, `unknown`.

LinkedIn, los portales y `unknown` solo se abren (ADR-009, ADR-021): en un portal la ficha de la
oferta no es el formulario. Desde ahí llegas tú al formulario de la empresa y la app rellena esa
pestaña («Rellenar esta página»), nunca una página del propio portal.
"""

import contextlib
import ipaddress
import re
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from playwright.sync_api import Page

from app.core.config import get_settings
from app.services import platforms as job_platforms

Platform = Literal["greenhouse", "lever", "ashby", "generic", "linkedin", "board", "unknown"]
PLATFORMS: tuple[Platform, ...] = (
    "greenhouse", "lever", "ashby", "generic", "linkedin", "board", "unknown",
)  # fmt: skip
# Las que se rellenan solas; el resto, «abrir y preparar».
AUTOMATED: frozenset[str] = frozenset({"greenhouse", "lever", "ashby", "generic"})

_HOSTS: dict[str, tuple[str, ...]] = {
    "greenhouse": ("greenhouse.io",),
    "lever": ("lever.co",),
    "ashby": ("ashbyhq.com",),
    "linkedin": ("linkedin.com",),
}

# Portales de empleo: candidatar es iniciar sesión y pulsar su botón, que a menudo lleva a la web
# de la empresa. Nunca se rellena una página suya.
BOARD_LABELS: dict[str, str] = {
    "infojobs": "InfoJobs",
    "tecnoempleo": "Tecnoempleo",
    "indeed": "Indeed",
    "glassdoor": "Glassdoor",
    "manfred": "Manfred",
}
# Para iniciar sesión desde la página de inicio del navegador de CandidatAI.
LOGIN_LINKS: tuple[tuple[str, str], ...] = (
    ("InfoJobs", "https://www.infojobs.net/"),
    ("Tecnoempleo", "https://www.tecnoempleo.com/"),
    ("Indeed", "https://es.indeed.com/"),
    ("Glassdoor", "https://www.glassdoor.es/"),
    ("Manfred", "https://www.getmanfred.com/"),
    ("LinkedIn", "https://www.linkedin.com/login"),
)
_GLASSDOOR_HOST = re.compile(r"(?:^|\.)glassdoor\.(?:com|[a-z]{2}|co\.[a-z]{2}|com\.[a-z]{2})$")

_LEVER_JOB = re.compile(r"^/[^/]+/[0-9a-f-]{36}/?$", re.I)
_ASHBY_JOB = re.compile(r"^/[^/]+/[0-9a-f-]{36}/?$", re.I)


def _host_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def job_board(url: str) -> str | None:
    """El portal de empleo de la URL (`infojobs`, `glassdoor`…), o `None` si no es de uno."""
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    found = job_platforms.platform_of_host(host)
    if found in BOARD_LABELS:
        return found
    if _GLASSDOOR_HOST.search(host):
        return "glassdoor"
    if _host_matches(host, "getmanfred.com"):
        return "manfred"
    return None


def detect(url: str) -> Platform | None:
    """La plataforma por la URL, o `None` si no se reconoce (hay que mirar la página)."""
    host = (urlsplit(url).hostname or "").lower()
    for platform, domains in _HOSTS.items():
        if any(_host_matches(host, domain) for domain in domains):
            return platform  # type: ignore[return-value]
    if job_board(url) is not None:
        return "board"
    return None


def fill_problem(url: str) -> str | None:
    """Por qué no se rellena la página de esta URL, o `None`: nunca LinkedIn ni un portal."""
    return portal_problem(url) or url_problem(url)


def portal_problem(url: str) -> str | None:
    """Si la URL es de LinkedIn o de un portal de empleo, por qué no se rellena; si no, `None`."""
    platform = detect(url)
    if platform == "linkedin":
        return "Esta pestaña es de LinkedIn: ahí no se rellena nada automáticamente (ADR-009)."
    if platform == "board":
        label = BOARD_LABELS[job_board(url) or ""]
        return (
            f"Esta pestaña es de {label}, no del formulario de la empresa: pulsa allí «Solicitar» "
            "o «Inscribirme» y, cuando llegues al formulario, vuelve a pulsar «Rellenar esta "
            "página». Si se completa dentro del portal, termínala tú."
        )
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


# Un formulario de candidatura: con adjunto, o con correo y un campo de nombre. Un buscador
# («Qué / Dónde»), un login o una suscripción por correo no lo son.
_INSPECT_JS = """() => {
  const frames = [...document.querySelectorAll('iframe[src]')].map(f => f.src);
  const nameRe = /(^|[^a-z])(name|nombre|first|last|apellido|surname)/i;
  const describe = (el) => [
    el.name, el.id, el.getAttribute('autocomplete'), el.getAttribute('placeholder'),
    el.getAttribute('aria-label'), ...[...(el.labels || [])].map(l => l.textContent),
  ].join(' ');
  // Un buscador marcado como tal. Un campo de búsqueda suelto dentro de un formulario (p. ej. el
  // selector de país del teléfono) no lo convierte en buscador.
  const isSearch = (el) => el.type === 'search' || el.closest('[role=search], search') !== null;
  const looksLikeApplication = (root, outsideForms) => {
    const pick = (selector) => [...root.querySelectorAll(selector)]
      .filter(el => !isSearch(el) && (!outsideForms || el.form === null));
    if (pick('input[type=file]').length > 0) return true;
    const email = pick('input[type=email], input[autocomplete=email]');
    if (email.length === 0) return false;
    if (pick('input[type=password]').length > 0) return false;
    return pick('input:not([type]), input[type=text]').some(el => nameRe.test(describe(el)));
  };
  const form = [...document.forms].some(f => looksLikeApplication(f, false)) ||
    looksLikeApplication(document, true);
  return {frames, form};
}"""


# Botones que abren el formulario en las webs de empleo que lo cargan al pulsar (Teamtailor y
# otras): «Enviar solicitud», «Solicitar», «Apply now»… Sin formulario en la página no envían nada.
APPLY_BUTTON = (
    r"^((enviar|env[ií]a|presentar|iniciar) (mi |tu |la )?(solicitud|candidatura)"
    r"|solicitar( empleo| ahora| el puesto)?|aplicar( ahora| a la oferta| al puesto)?"
    r"|inscribirme|inscr[ií]bete|postularme|postular|quiero aplicar|me interesa"
    r"|apply( now| here| for this (job|position|role))?|submit (your |an )?application"
    r"|start (your |an )?application|i'?m interested)$"
)

# Marca el primer botón o enlace visible, fuera de cualquier formulario, cuyo texto es el de abrir
# la candidatura. Devuelve su texto, su `href` y si se abre en otra pestaña.
_APPLY_BUTTON_JS = """(pattern) => {
  const rx = new RegExp(pattern, 'i');
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const st = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
  };
  const text = (el) => (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
  const el = [...document.querySelectorAll('a, button, [role=button]')]
    .find(e => !e.closest('form') && visible(e) && rx.test(text(e)));
  if (!el) return null;
  el.setAttribute('data-cai-apply', '1');
  const href = el.tagName === 'A' ? el.href : null;
  return {label: text(el), href, blank: el.tagName === 'A' && el.target === '_blank'};
}"""


def find_apply_button(page: Page) -> dict | None:
    """El botón que abre el formulario (marcado con `data-cai-apply`), o `None`."""
    return page.evaluate(_APPLY_BUTTON_JS, APPLY_BUTTON)


def inspect(page: Page) -> tuple[Platform, str | None]:
    """Para una URL no reconocida: la plataforma según la página y, si el formulario está en un
    iframe de un ATS conocido, la URL de ese iframe (para abrirla directamente)."""
    found = page.evaluate(_INSPECT_JS)
    for src in found["frames"]:
        platform = detect(src)
        if platform in AUTOMATED:
            return platform, src  # type: ignore[return-value]
    return ("generic" if found["form"] else "unknown"), None
