"""Primer arranque, con la carpeta de datos vacía: «Primeros pasos» en Inicio, el perfil creado a
mano y guardado desde «Mi perfil» y lo que dice cada página principal cuando aún no hay nada.

Sin agente, el perfil se empieza a mano en «Mi perfil» («Empezar a mano»): lo justo para que valide
y, después, bloque a bloque en el editor. Con agente, lo crea a partir de tu CV (no se prueba aquí).
"""

import json
import re

import pytest
import yaml
from playwright.sync_api import Page, expect

from tests.e2e.harness import AppServer, run_cai, t
from tests.e2e.sites import FIXTURES
from tests.e2e.test_smoke import ROUTES, Route

pytestmark = pytest.mark.e2e

CV = FIXTURES.parent / "cv-ficticio.pdf"


def _start_by_hand(page: Page) -> None:
    """En «Mi perfil» sin perfil: «Empezar a mano», lo mínimo y «Crear mi perfil» abre el editor."""
    page.get_by_role("button", name=t("profileEditor.noProfile.byHand.open")).click()
    form = page.get_by_role("region", name=t("profileEditor.noProfile.byHand.title"))
    form.get_by_label(t("profileEditor.fields.name"), exact=True).fill("Candidata Prueba E2E")
    form.get_by_label(t("profileEditor.fields.headline"), exact=True).fill("Analista de datos")
    form.get_by_label(t("profileEditor.noProfile.byHand.role"), exact=True).fill("Data Analyst")
    form.get_by_role("checkbox", name=t("profileEditor.seniority.mid")).check()
    form.get_by_role("button", name=t("profileEditor.noProfile.byHand.create")).click()
    expect(page.get_by_role("tab", name=t("profileEditor.tabs.about"))).to_be_visible()


def _first_steps(page: Page):  # noqa: ANN202 - Locator
    return page.get_by_role("region", name=t("home.firstSteps.title"), exact=True)


def test_first_steps_lead_where_they_say_and_tick_off(page: Page, empty_app: AppServer) -> None:
    page.goto("/")
    steps = _first_steps(page)
    expect(steps).to_be_visible()
    # En su orden: primero tu perfil, luego dónde buscar.
    expect(steps.get_by_role("heading", level=3)).to_have_text(
        [t("home.firstSteps.profile.title"), t("home.firstSteps.search.title")]
    )

    # Paso 1: el CV se sube para tu agente; sin agente, el perfil se empieza a mano.
    steps.get_by_label(t("profileEditor.noProfile.start.fileLabel")).set_input_files(CV)
    uploaded = t("profileEditor.noProfile.start.uploaded", name=CV.name)
    expect(steps.get_by_text(uploaded)).to_be_visible()
    steps.get_by_role("link", name=t("home.firstSteps.profile.byHand")).click()
    expect(page).to_have_url(f"{empty_app.url}/perfil")
    _start_by_hand(page)
    page.goto("/")
    done = steps.get_by_role("link", name=t("home.firstSteps.profile.done"))
    expect(done).to_be_visible()
    done.click()
    expect(page).to_have_url(f"{empty_app.url}/perfil")
    expect(page.get_by_role("heading", level=1)).to_have_text(t("profile.title"))

    # Paso 2: «o añade un portal tú» lleva a los portales, vacíos.
    page.goto("/")
    expect(steps.get_by_role("link", name=t("home.firstSteps.profile.done"))).to_be_visible()
    steps.get_by_role("link", name=t("home.firstSteps.search.manual")).click()
    expect(page).to_have_url(f"{empty_app.url}/fuentes/plataformas")
    expect(page.get_by_text(t("platforms.empty.title"))).to_be_visible()
    page.get_by_role("button", name=t("platforms.add.button")).first.click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_label(t("platforms.add.portal")).select_option("infojobs")
    # Las búsquedas salen solas de los puestos del perfil.
    expect(dialog.get_by_label(t("platforms.add.urls"))).to_have_value(re.compile(r"infojobs"))
    dialog.get_by_role("button", name=t("platforms.add.submit")).click()
    expect(dialog).to_be_hidden()

    # Con los dos hechos, la tarjeta desaparece.
    page.goto("/")
    expect(page.get_by_role("heading", level=1)).to_be_visible()
    page.wait_for_load_state("networkidle")
    expect(_first_steps(page)).to_have_count(0)


def test_the_profile_saved_from_the_ui_stays_and_is_valid(page: Page, empty_app: AppServer) -> None:
    page.goto("/perfil")
    _start_by_hand(page)
    block = page.get_by_role("region", name=t("profileEditor.blocks.personal.title"))
    name = block.get_by_label(t("profileEditor.fields.name"), exact=True)
    headline = block.get_by_label(t("profileEditor.fields.headline"), exact=True)
    expect(name).to_have_value("Candidata Prueba E2E")
    expect(headline).to_have_value("Analista de datos")
    name.fill("Candidata Prueba E2E Editada")
    headline.fill("Data Engineer · Python · SQL")
    expect(block.get_by_text(t("profileEditor.unsaved.badge"))).to_be_visible()
    block.get_by_role("button", name=t("profileEditor.actions.save"), exact=True).click()
    expect(block.get_by_role("status")).to_have_text(t("profileEditor.actions.saved"))

    page.reload()
    expect(name).to_have_value("Candidata Prueba E2E Editada")
    expect(headline).to_have_value("Data Engineer · Python · SQL")

    profile_file = empty_app.data_dir / "profile.yaml"
    data = yaml.safe_load(profile_file.read_text(encoding="utf-8"))
    assert data["personal"]["name"] == "Candidata Prueba E2E Editada"
    result = run_cai(empty_app.data_dir, "profile", "validate", "--json")
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ok"] is True


# Las páginas principales con la carpeta vacía: cada una dice qué hacer.
EMPTY_STATES = {
    "/": "home.firstSteps.title",
    "/bandeja": "inbox.empty.title",
    "/bandeja/revision": "triage.empty.title",
    "/procesos": "processes.none.title",
    "/embudo": "funnel.empty.title",
    "/fuentes/plataformas": "platforms.empty.title",
    "/fuentes/empresas": "sources.empty.title",
    "/bandeja/por-completar": "alerts.empty.title",
    "/fuentes/correo": "alerts.email.emptyTitle",
}


# Lo que hoy falla (`xfail` estricto: al arreglarlo, el test lo avisa y hay que quitarlo de aquí).
KNOWN_FAILURES: dict[str, str] = {}


def _route_param(route: Route) -> object:
    reason = KNOWN_FAILURES.get(route.path)
    marks = [pytest.mark.xfail(reason=reason, strict=True)] if reason else []
    return pytest.param(route, id=route.path, marks=marks)


@pytest.mark.parametrize("route", [_route_param(r) for r in ROUTES if ":id" not in r.path])
def test_every_page_opens_empty_and_says_what_to_do(
    page: Page, empty_shared_app: AppServer, route: Route
) -> None:
    page.goto(route.path)
    page.wait_for_load_state("networkidle")  # con lo que pide al cargar ya respondido
    heading = page.get_by_role("heading", level=1)
    if route.heading is None:
        expect(heading).to_have_text(re.compile(r"\S"))
    else:
        expect(heading).to_have_text(t(route.heading))
    if (key := EMPTY_STATES.get(route.lands_on or route.path)) is not None:
        expect(page.get_by_text(t(key), exact=True).first).to_be_visible()
