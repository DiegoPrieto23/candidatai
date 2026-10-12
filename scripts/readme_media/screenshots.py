"""Capturas de la demo para el README. UI en 5181 y API en 8010 (la app real sigue en 5173/8000).

La API solo acepta el origen 127.0.0.1:5173: este Chromium ignora CORS y cada petición a la API
sale con ese `Origin`. Solo para capturas, en local.
"""

import json
import sys
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

UI = "http://127.0.0.1:5181"
API = "http://127.0.0.1:8010"
OUT = Path(sys.argv[1])
THEME = sys.argv[2] if len(sys.argv) > 2 else "light"
ONLY = set(sys.argv[3].split(",")) if len(sys.argv) > 3 else None
OUT.mkdir(parents=True, exist_ok=True)


def api(path: str) -> object:
    with urllib.request.urlopen(API + path) as r:
        return json.load(r)


def first_job(stage: str) -> int:
    data = api(f"/jobs?stage={stage}&limit=5")
    items = data.get("items") or data.get("jobs") or []
    return items[0]["id"]


def run() -> None:
    cv_job = first_job("cv_ready")
    process_job = first_job("in_process")
    pages = {
        "bandeja": "/bandeja",
        "por-revisar": "/por-revisar",
        "ficha": f"/jobs/{cv_job}",
        "ficha-cv": f"/jobs/{cv_job}#cv",
        "ficha-proceso": f"/jobs/{process_job}",
        "procesos": "/procesos",
        "embudo": "/embudo",
        "skills": "/skills",
        "plantillas": "/plantillas",
        "plataformas": "/plataformas",
        "empresas": "/empresas",
        "agente": "/agente",
        "inicio": "/",
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-web-security"])
        ctx = browser.new_context(
            viewport={"width": 1600, "height": 1000},
            device_scale_factor=1.5,
            color_scheme=THEME,
            locale="es-ES",
        )

        def with_origin(route):  # type: ignore[no-untyped-def]
            headers = {**route.request.headers, "origin": "http://127.0.0.1:5173"}
            route.continue_(headers=headers)

        ctx.route(f"{API}/**", with_origin)
        page = ctx.new_page()
        page.add_init_script(f"localStorage.setItem('jh-theme', '{THEME}')")
        for name, path in pages.items():
            if ONLY and name not in ONLY:
                continue
            page.goto(UI + path)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(1500)
            if path.endswith("#cv"):
                top = page.locator("#cv").evaluate(
                    "e => e.getBoundingClientRect().top + window.scrollY - 150"
                )
                page.evaluate(f"window.scrollTo(0, {top})")
                page.wait_for_timeout(800)
            page.screenshot(path=str(OUT / f"{name}.png"))
            print("ok", name, path)
        browser.close()


run()
