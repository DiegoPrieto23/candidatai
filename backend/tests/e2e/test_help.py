"""La ayuda del portal: el botón de abajo a la derecha busca en las preguntas frecuentes y en la
guía de uso, lleva a la pantalla donde se hace cada cosa y se maneja con el teclado."""

import re

import pytest
from playwright.sync_api import Page, Route, expect

from tests.e2e.agent import api, cai
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


def test_ask_your_agent_and_read_the_answer(page: Page, fresh_demo_app: AppServer) -> None:
    """«Pídeselo a tu agente»: la petición queda para la próxima sesión, el agente (simulado, con
    los mismos comandos `cai … --json`) la lee y contesta, y el panel enseña la respuesta con un
    enlace a la oferta. Aquí no hay agente instalado: se simula que hay uno sin segundo plano."""
    server = fresh_demo_app

    def with_agent(route: Route) -> None:
        body = route.fetch().json()
        body["no_agent_installed"] = False
        for action in body["actions"]:
            if action["id"] == "assistant":
                action["background_agent"] = {"available": False, "agent": None, "reason": "x"}
        route.fulfill(json=body)

    page.route(re.compile(r"/agent$"), with_agent)
    page.goto(f"{server.url}/bandeja")
    page.get_by_role("button", name=t("help.button"), exact=True).click()
    panel = page.get_by_role("dialog", name=t("help.title"))
    panel.get_by_role("tab", name=t("help.tabs.assistant")).click()
    field = panel.get_by_role("textbox", name=t("help.assistant.label"))
    expect(field).to_be_focused()
    expect(panel.get_by_role("button", name=t("help.assistant.sendNow"))).to_be_disabled()

    field.fill("¿Qué oferta miro primero?")
    panel.get_by_role("button", name=t("help.assistant.sendLater")).click()
    expect(panel.get_by_text(t("help.assistant.status.waiting"))).to_be_visible()
    expect(field).to_have_value("")

    # El agente, en su próxima sesión: ve el encargo, lee la petición y contesta.
    listed = cai(server, "requests", "list")["requests"]
    pending = [r for r in listed if r["action"] == "assistant"]  # la demo trae otro encargo
    assert len(pending) == 1
    asked = api(server, "/agent/assistant")["requests"][0]
    assert pending[0]["prompt"].endswith(f"la petición {asked['id']}.")
    assert "oferta miro" not in pending[0]["prompt"]  # el texto no va en la orden
    shown = cai(server, "assistant", "show", str(asked["id"]))
    assert shown["text"] == "¿Qué oferta miro primero?" and shown["open"] is True
    job = api(server, "/jobs", limit=1)["items"][0]
    answer = {"answer": "Empieza por esta.", "links": [{"job_id": job["id"]}, {"screen": "review"}]}
    cai(server, "assistant", "answer", str(asked["id"]), payload=answer)
    cai(server, "requests", "complete", str(pending[0]["id"]), "--summary", "Contestada.")

    # Al volver a la pestaña, la respuesta y sus enlaces.
    panel.get_by_role("tab", name=t("help.tabs.help")).click()
    panel.get_by_role("tab", name=t("help.tabs.assistant")).click()
    history = panel.get_by_role("region", name=t("help.assistant.history"))
    expect(history.get_by_text("Empieza por esta.")).to_be_visible()
    review = t("help.goTo", screen=t("help.screens.review"))
    expect(history.get_by_role("link", name=review)).to_be_visible()
    history.get_by_role("link").first.click()
    expect(page).to_have_url(re.compile(rf"/jobs/{job['id']}$"))
    expect(panel).to_be_hidden()
