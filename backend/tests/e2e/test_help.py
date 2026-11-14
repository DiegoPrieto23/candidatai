"""La ayuda del portal: el botón de abajo a la derecha busca en las preguntas frecuentes y en la
guía de uso, lleva a la pantalla donde se hace cada cosa y se maneja con el teclado."""

import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.harness import AppServer, t

pytestmark = pytest.mark.e2e


def test_help_answers_and_takes_you_to_the_screen(page: Page, demo_app: AppServer) -> None:
    page.goto("/bandeja")
    expect(page.get_by_role("main").get_by_role("row").nth(1)).to_be_visible()

    # Con el teclado: «?» abre la ayuda con el foco en el buscador.
    page.keyboard.press("?")
    panel = page.get_by_role("dialog", name=t("help.title"))
    search = panel.get_by_role("searchbox", name=t("help.searchLabel"))
    expect(search).to_be_focused()
    expect(panel.get_by_role("heading", name=t("help.groups.start"))).to_be_visible()

    # El panel cabe en la ventana, sin salirse por arriba.
    box = panel.bounding_box()
    assert box is not None and box["y"] >= 0, box

    search.fill("plantilla propia")
    faq = panel.get_by_role("region", name=t("help.faqHeading"))
    question = faq.get_by_role("button", name=t("help.faq.ownTemplate.q"))
    expect(question).to_be_visible()
    # La guía se descarga al abrir la ayuda y también se busca en ella.
    expect(panel.get_by_role("region", name=t("help.guideHeading"))).to_be_visible()
    question.click()
    expect(faq.get_by_text(t("help.faq.ownTemplate.a"))).to_be_visible()

    faq.get_by_role("link", name=t("help.goTo", screen=t("help.screens.templates"))).click()
    expect(page).to_have_url(re.compile(r"/perfil/plantillas$"))
    expect(panel).to_be_hidden()

    # Esc la cierra y devuelve el foco al botón.
    button = page.get_by_role("button", name=t("help.button"), exact=True)
    button.click()
    expect(panel).to_be_visible()
    page.keyboard.press("Escape")
    expect(panel).to_be_hidden()
    expect(button).to_be_focused()


@pytest.mark.parametrize("lang", ["en"], indirect=True)
def test_help_in_english_searches_the_english_guide(page: Page, demo_app: AppServer) -> None:
    page.goto("/")
    page.get_by_role("button", name=t("help.button", "en"), exact=True).click()
    panel = page.get_by_role("dialog", name=t("help.title", "en"))
    panel.get_by_role("searchbox").fill("updating")
    guide = panel.get_by_role("region", name=t("help.guideHeading", "en"))
    expect(guide.get_by_role("button").first).to_have_text(re.compile(r"^Updating"))
