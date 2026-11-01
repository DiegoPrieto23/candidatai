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
