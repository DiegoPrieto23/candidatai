"""«Buscar ofertas» en la app real: el botón de tu agente no se mueve al avisar de que se abrió."""

import json
import sqlite3
from datetime import UTC, datetime

import pytest
from playwright.sync_api import Page, Route, expect

from tests.e2e.harness import AppServer, run_cai, t

pytestmark = pytest.mark.e2e


def test_the_agent_button_stays_put_when_it_shows_its_notice(
    page: Page, demo_app: AppServer
) -> None:
    # Sin abrir una terminal de verdad: lo que importa es la respuesta y lo que hace la página.
    launches: list[dict[str, object]] = []

    def launched(route: Route) -> None:
        launches.append(route.request.post_data_json)
        route.fulfill(
            status=202,
            content_type="application/json",
            body=json.dumps({"label": "x", "prompt": "x", "agent": "Claude Code", "job_id": None}),
        )

    page.route("**/agent/launch", launched)
    page.goto("/buscar")
    button = page.get_by_role("button", name=t("search.searchNow"), exact=False).first
    expect(button).to_be_enabled()
    before = button.bounding_box()
    button.click()
    expect(page.get_by_role("status").filter(has_text="Claude Code")).to_be_visible()
    assert button.bounding_box() == before
    assert launches[0]["action"] == "search-jobs"


def test_search_jobs_is_one_page_with_an_index(page: Page, demo_app: AppServer) -> None:
    # Una ruta de antes abre la página en su sección, ya a la vista.
    page.goto("/fuentes/correo")
    expect(page.get_by_role("heading", level=1, name=t("search.title"))).to_be_attached()
    expect(page.get_by_role("heading", level=2, name=t("search.nav.where"))).to_be_in_viewport()
    expect(page.get_by_role("heading", level=3, name=t("alerts.email.title"))).to_be_attached()

    # El índice lleva a cada sección sin salir de la página, y la URL dice dónde estás.
    index = page.get_by_role("navigation", name=t("search.nav.label"))
    index.get_by_role("link", name=t("search.nav.settings")).click()
    expect(page).to_have_url(f"{demo_app.url}/buscar/ajustes")
    expect(page.get_by_role("heading", level=2, name=t("search.nav.settings"))).to_be_in_viewport()
    index.get_by_role("link", name=t("search.nav.search"), exact=True).click()
    expect(page).to_have_url(f"{demo_app.url}/buscar")
    expect(
        page.get_by_role("button", name=t("search.searchNow"), exact=False).first
    ).to_be_in_viewport()
    # «Dónde buscar» vuelve a la vista que tenías abierta.
    index.get_by_role("link", name=t("search.nav.where")).click()
    expect(page).to_have_url(f"{demo_app.url}/fuentes/correo")


def test_more_filters_takes_you_to_your_roles_even_from_the_same_address(
    page: Page, demo_app: AppServer
) -> None:
    # Con la URL ya en `/buscar/ajustes` (entraste por el índice y subiste), el enlace no cambia
    # de ruta: aun así tiene que bajar y dejar el cursor en tus puestos.
    page.goto("/buscar/ajustes")
    roles = page.get_by_role("textbox", name=t("profileEditor.fields.roles"))
    expect(roles).to_be_in_viewport()
    page.evaluate("window.scrollTo(0, 0)")
    expect(roles).not_to_be_in_viewport()
    page.get_by_role("link", name=t("search.strip.moreFilters"), exact=True).click()
    expect(roles).to_be_focused()
    expect(roles).to_be_in_viewport()
    expect(page).to_have_url(f"{demo_app.url}/buscar/ajustes")
    # Atrás y Adelante vuelven a esa entrada del historial, pero no te ponen el cursor otra vez.
    roles.blur()
    page.go_back()
    page.go_forward()
    expect(page.get_by_role("heading", level=2, name=t("search.nav.settings"))).to_be_in_viewport()
    expect(roles).not_to_be_focused()
    # Y desde `/buscar`, igual.
    page.goto("/buscar")
    page.get_by_role("link", name=t("search.strip.moreFilters"), exact=True).click()
    expect(roles).to_be_focused()
    expect(roles).to_be_in_viewport()


def test_a_role_added_in_the_strip_is_saved_to_your_profile(
    page: Page, demo_app: AppServer
) -> None:
    # La franja guarda en tu perfil de verdad: el puesto aparece en la configuración, y se deshace.
    page.goto("/buscar")
    strip = page.get_by_role("region", name=t("search.strip.label"))
    roles = strip.get_by_role("group", name=t("search.strip.roles"))
    roles.get_by_role("button", name=t("search.strip.addRole")).click()
    roles.get_by_role("combobox", name=t("search.strip.addRole")).fill("Data Platform Engineer")
    page.keyboard.press("Enter")
    expect(roles.get_by_text("Data Platform Engineer", exact=True)).to_be_visible()
    expect(strip.get_by_role("button", name=t("search.strip.undo"))).to_be_enabled()
    settings = page.get_by_role("region", name=t("profileEditor.blocks.searchRole.title"))
    expect(settings.get_by_text("Data Platform Engineer", exact=True)).to_be_attached()

    strip.get_by_role("button", name=t("search.strip.undo")).click()
    expect(strip.get_by_text(t("search.strip.undone"))).to_be_visible()
    expect(roles.get_by_text("Data Platform Engineer", exact=True)).to_have_count(0)
    expect(settings.get_by_text("Data Platform Engineer", exact=True)).to_have_count(0)


def test_what_you_are_after_lives_in_search_jobs(page: Page, demo_app: AppServer) -> None:
    page.goto("/buscar/ajustes")
    expect(page.get_by_role("heading", level=2, name=t("search.nav.settings"))).to_be_visible()
    expect(
        page.get_by_role("region", name=t("profileEditor.blocks.searchRole.title"))
    ).to_be_visible()
    page.goto("/perfil")
    expect(page.get_by_role("tab", name=t("profileEditor.tabs.about"))).to_be_visible()
    expect(page.get_by_role("tab")).to_have_count(4)


def test_the_notice_says_searching_until_the_agent_finishes(
    page: Page, demo_app: AppServer
) -> None:
    # La ventana del agente no se abre aquí: la búsqueda se apunta a mano, como al lanzarla, y el
    # final llega por el comando de verdad que usa el agente.
    db = sqlite3.connect(demo_app.data_dir / "candidatai.db")
    with db:
        ids = [row[0] for row in db.execute("SELECT id FROM sources WHERE kind = 'agent_browse'")]
        last = db.execute("SELECT COALESCE(MAX(id), 0) FROM source_runs").fetchone()[0]
        db.execute(
            "INSERT INTO search_runs (source_ids, after_source_run_id, started_at) "
            "VALUES (?, ?, ?)",
            (json.dumps(ids), last, datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")),
        )
    db.close()

    page.goto("/calendario")
    notice = page.get_by_role("status").filter(has_text=t("nav.searchRun.running.title"))
    expect(notice).to_be_visible()
    page.goto("/buscar")
    expect(
        page.get_by_role("button", name=t("search.searching"), exact=False).first
    ).to_be_disabled()

    done = run_cai(demo_app.data_dir, "sources", "finish-search", "--outcome", "no_browser")
    assert done.returncode == 0, done.stderr
    expect(page.get_by_text(t("nav.searchRun.no_browser.title"))).to_be_visible(timeout=10_000)
    expect(notice).to_have_count(0)
    expect(
        page.get_by_role("button", name=t("search.searchNow"), exact=False).first
    ).to_be_enabled()

    page.get_by_role("button", name=t("nav.searchRun.close")).click()
    expect(page.get_by_text(t("nav.searchRun.no_browser.title"))).to_have_count(0)
    page.reload()
    expect(page.get_by_role("heading", level=1, name=t("search.title"))).to_be_visible()
    expect(page.get_by_text(t("nav.searchRun.no_browser.title"))).to_have_count(0)
