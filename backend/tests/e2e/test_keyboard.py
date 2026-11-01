"""Con teclado: el primer Tab enseña «Saltar al contenido» y, tras activarlo, el siguiente Tab ya
cae dentro de la página, sin recorrer el menú."""

import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.harness import AppServer, t

pytestmark = pytest.mark.e2e


def test_skip_to_content_from_home(page: Page, demo_app: AppServer) -> None:
    page.goto("/")
    expect(page.get_by_role("heading", level=1)).to_have_text(re.compile(r"\S"))

    page.keyboard.press("Tab")
    skip = page.get_by_role("link", name=t("nav.skipToContent"))
    expect(skip).to_be_focused()
    # Oculto hasta recibir el foco: con él, se ve entero y no como el píxel de `sr-only`.
    box = skip.bounding_box()
    assert box is not None and box["width"] > 40, box

    page.keyboard.press("Enter")
    expect(page.locator("main")).to_be_focused()
    page.keyboard.press("Tab")
    assert page.evaluate("document.querySelector('main').contains(document.activeElement)")
    expect(page).to_have_url(f"{demo_app.url}/")


def test_inbox_stage_filters_are_one_tab_stop_with_arrows(page: Page, demo_app: AppServer) -> None:
    """Los nueve filtros de etapa de la Bandeja: un Tab entra (en el elegido), las flechas eligen
    otro y el siguiente Tab sale al buscador."""
    page.goto("/bandeja")
    stages = page.get_by_role("radiogroup", name=t("inbox.filterStage"))
    all_stages = stages.get_by_role("radio", name=t("inbox.allStages"))
    expect(all_stages).to_have_attribute("aria-checked", "true")
    expect(page.get_by_role("main").get_by_role("row").nth(1)).to_be_visible()

    all_stages.focus()
    page.keyboard.press("ArrowRight")
    first = stages.get_by_role("radio").nth(1)
    expect(first).to_be_focused()
    expect(first).to_have_attribute("aria-checked", "true")
    expect(page).to_have_url(re.compile(r"[?&]stage=pending_detail"))
    page.keyboard.press("End")
    expect(stages.get_by_role("radio").last).to_have_attribute("aria-checked", "true")
    page.keyboard.press("Home")
    expect(all_stages).to_be_focused()
    expect(all_stages).to_have_attribute("aria-checked", "true")

    page.keyboard.press("Tab")
    expect(page.get_by_role("searchbox", name=t("inbox.search"))).to_be_focused()
