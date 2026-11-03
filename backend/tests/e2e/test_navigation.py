"""La barra lateral: sus entradas, y lo que salió de ella se alcanza desde su sección nueva."""

import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.harness import AppServer, t

pytestmark = pytest.mark.e2e


def test_the_entries_and_each_section_opens_its_tabs(page: Page, demo_app: AppServer) -> None:
    page.goto("/")
    nav = page.get_by_role("navigation", name=t("nav.mainNav"))
    expected = [
        "home",
        "profile",
        "inbox",
        "search",
        "sources",
        "processes",
        "calendar",
        "replies",
        "funnel",
        "agent",
    ]
    links = nav.get_by_role("link")
    expect(links).to_have_count(len(expected))
    for index, entry in enumerate(expected):
        expect(links.nth(index)).to_contain_text(t(f"nav.entries.{entry}"))

    # Mi perfil: Skills y Plantillas.
    nav.get_by_role("link", name=re.compile(t("nav.entries.profile"))).click()
    tabs = page.get_by_role("navigation", name=t("nav.tabs.profileLabel"))
    tabs.get_by_role("link", name=t("nav.tabs.skills")).click()
    expect(page).to_have_url(re.compile(r"/perfil/skills$"))
    expect(page.get_by_role("heading", level=1, name=t("skills.title"))).to_be_visible()
    tabs.get_by_role("link", name=t("nav.tabs.templates")).click()
    expect(page.get_by_role("heading", level=1, name=t("templates.title"))).to_be_visible()

    # La Bandeja: la revisión rápida, con sus atajos, y «Por completar», con los suyos.
    nav.get_by_role("link", name=re.compile(t("nav.entries.inbox"))).click()
    tabs = page.get_by_role("navigation", name=t("nav.tabs.inboxLabel"))
    tabs.get_by_role("link", name=re.compile(t("nav.tabs.review"))).click()
    selected = page.get_by_role("article", name=t("triage.selected"))
    expect(selected).to_be_visible()
    first = selected.get_by_role("heading").first.inner_text()
    page.keyboard.press("j")
    expect(selected.get_by_role("heading").first).not_to_have_text(first)
    tabs.get_by_role("link", name=re.compile(t("nav.tabs.complete"))).click()
    expect(page.get_by_role("heading", level=1, name=t("alerts.title"))).to_be_visible()
    # Las teclas actúan sobre la oferta elegida: primero, que la lista haya cargado.
    expect(page.get_by_role("listbox", name=t("alerts.passing"))).to_be_visible()
    page.keyboard.press("d")
    expect(page.get_by_role("dialog")).to_be_visible()
    page.keyboard.press("Escape")

    # Dónde buscar: los buzones.
    nav.get_by_role("link", name=t("nav.entries.sources")).click()
    page.get_by_role("link", name=t("nav.tabs.email")).click()
    expect(page.get_by_role("heading", level=1, name=t("alerts.email.title"))).to_be_visible()
    expect(page.get_by_role("button", name=t("alerts.addMailbox")).first).to_be_visible()

    # Procesos: el tablero y, en su propia entrada, el calendario, sin pestañas.
    nav.get_by_role("link", name=re.compile(t("nav.entries.processes"))).first.click()
    expect(page.get_by_role("heading", level=1, name=t("processes.title"))).to_be_visible()
    nav.get_by_role("link", name=t("nav.entries.calendar")).click()
    expect(page.get_by_role("heading", level=1, name=t("calendar.title"))).to_be_visible()

    # Buscar ofertas.
    nav.get_by_role("link", name=t("nav.entries.search")).click()
    expect(page.get_by_role("heading", level=1, name=t("search.title"))).to_be_visible()

    # Y la ayuda, al pie.
    page.get_by_role("complementary", name=t("nav.sidebar")).get_by_role(
        "link", name=t("nav.entries.howItWorks")
    ).click()
    expect(page.get_by_role("heading", level=1, name=t("howItWorks.title"))).to_be_visible()
