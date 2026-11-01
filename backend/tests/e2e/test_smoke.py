"""Humo: cada página de la UI abre con la demo, pinta su encabezado y no da errores invisibles; una
ficha de oferta aguanta F5 y el idioma cambia y vuelve.

Las rutas van en `ROUTES`, no se adivinan: `tests/test_e2e_harness.py` comprueba que cubre todas
las de `frontend/src/App.tsx`, para que una página nueva no se quede sin humo.
"""

import re
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.e2e.harness import AppServer, t

pytestmark = [pytest.mark.e2e, pytest.mark.smoke]


@dataclass(frozen=True)
class Route:
    path: str  # la de `App.tsx`; `:id`, una oferta de la demo
    heading: str | None  # la clave del `h1`; sin ella, solo se exige que haya uno con texto
    lands_on: str | None = None  # a dónde redirige, si redirige


ROUTES = [
    Route("/", None),  # «Hoy»: el `h1` es una frase con lo que tienes pendiente
    Route("/como-funciona", "howItWorks.title"),
    Route("/bandeja", "inbox.title"),
    Route("/bandeja/revision", "triage.title"),
    Route("/bandeja/por-completar", "alerts.title"),
    Route("/jobs/:id", None),  # el título de la oferta: lo prueba `test_job_page_survives_reload`
    Route("/nueva", "newJob.title"),
    Route("/procesos", "processes.title"),
    Route("/procesos/calendario", "calendar.title"),
    Route("/embudo", "funnel.title"),
    Route("/perfil", "profile.title"),
    Route("/perfil/skills", "skills.title"),
    Route("/perfil/plantillas", "templates.title"),
    # Antes tenían entrada propia en la barra.
    Route("/por-revisar", "triage.title", "/bandeja/revision"),
    Route("/triaje", "triage.title", "/bandeja/revision"),
    Route("/alertas", "alerts.title", "/bandeja/por-completar"),
    Route("/calendario", "calendar.title", "/procesos/calendario"),
    Route("/respuestas", "processes.title", "/procesos"),
    Route("/skills", "skills.title", "/perfil/skills"),
    Route("/plantillas", "templates.title", "/perfil/plantillas"),
    Route("/fuentes", "platforms.title", "/fuentes/plataformas"),
    Route("/fuentes/empresas", "sources.title"),
    Route("/fuentes/plataformas", "platforms.title"),
    Route("/fuentes/correo", "alerts.email.title"),
    Route("/fuentes/extension", "extension.title"),
    Route("/empresas", "sources.title", "/fuentes/empresas"),
    Route("/plataformas", "platforms.title", "/fuentes/plataformas"),
    Route("/agente", "agent.title"),
]


def _first_job(server: AppServer) -> dict[str, Any]:
    response = httpx.get(f"{server.url}/jobs", params={"limit": 1}, timeout=10, trust_env=False)
    response.raise_for_status()
    body = response.json()
    items: list[dict[str, Any]] = body["items"] if isinstance(body, dict) else body
    assert items, "la demo no tiene ofertas"
    return items[0]


def _heading(page: Page) -> Any:
    return page.get_by_role("heading", level=1)


@pytest.mark.parametrize("route", [r for r in ROUTES if ":id" not in r.path], ids=lambda r: r.path)
def test_page_opens(page: Page, demo_app: AppServer, route: Route) -> None:
    page.goto(route.path)
    heading = _heading(page)
    if route.heading is None:
        expect(heading).to_have_text(re.compile(r"\S"))
    else:
        expect(heading).to_have_text(t(route.heading))
    expect(page).to_have_url(f"{demo_app.url}{route.lands_on or route.path}")
    page.wait_for_load_state("networkidle")  # que lleguen los errores de lo que pide al cargar


def test_job_page_survives_reload(page: Page, demo_app: AppServer) -> None:
    job = _first_job(demo_app)
    page.goto(f"/jobs/{job['id']}")
    expect(_heading(page)).to_have_text(job["title"])
    page.reload()
    expect(_heading(page)).to_have_text(job["title"])
    page.wait_for_load_state("networkidle")


def test_language_switches_and_back(page: Page, demo_app: AppServer) -> None:
    page.goto("/bandeja")
    expect(_heading(page)).to_have_text(t("inbox.title"))
    for current, target in (("es", "en"), ("en", "es")):
        name = t("common.language.name", current)
        page.get_by_role("button", name=t("nav.language.button", current, name=name)).click()
        page.get_by_role("menuitemradio", name=t("common.language.name", target)).click()
        expect(_heading(page)).to_have_text(t("inbox.title", target))
        expect(page.locator("html")).to_have_attribute("lang", target)


@pytest.mark.parametrize("lang", ["en"], indirect=True)
def test_the_ui_opens_in_english(page: Page, demo_app: AppServer, lang: str) -> None:
    page.goto("/bandeja")
    expect(_heading(page)).to_have_text(t("inbox.title", lang))
    expect(page.locator("html")).to_have_attribute("lang", lang)


def test_the_browser_cannot_reach_the_internet(page: Page, demo_app: AppServer) -> None:
    """Lo que la UI pidiera a internet se corta: las E2E no usan la red externa."""
    page.goto("/bandeja")
    outcome = page.evaluate(
        "fetch('https://example.com/').then(() => 'salió', (e) => 'cortado: ' + e.name)"
    )
    assert outcome.startswith("cortado"), outcome


@pytest.mark.parametrize("path", ["/fuentes/plataformas", "/fuentes/empresas"])
def test_where_to_search_asks_nothing_outside_the_app(
    page: Page, demo_app: AppServer, path: str
) -> None:
    """Los iconos de portales y empresas los sirve la app: abrir «Dónde buscar» no hace que tu
    navegador visite cada web (y cada empresa no ve una visita tuya)."""
    requested: list[str] = []
    page.on("request", lambda request: requested.append(request.url))
    page.goto(path)
    expect(_heading(page)).to_have_text(re.compile(r"\S"))
    page.wait_for_load_state("networkidle")
    outside = [url for url in requested if not url.startswith((demo_app.url, "data:", "blob:"))]
    assert outside == []
    assert any("/sources/" in url and "/icon" in url for url in requested)
