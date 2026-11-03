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


def test_what_you_are_after_lives_in_search_jobs(page: Page, demo_app: AppServer) -> None:
    page.goto("/buscar/ajustes")
    expect(page.get_by_role("heading", level=1, name=t("search.settings.title"))).to_be_visible()
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
