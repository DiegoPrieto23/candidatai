"""Capturas de la demo para el README. UI en 5181 y API en 8010 (la app real sigue en 5173/8000).

Uso (desde backend/): python screenshots.py OUT_DIR IDIOMA [TEMA] [NOMBRES]
  IDIOMA: en (README.md, demo en inglés) o es (README.es.md, demo en español). La UI se abre en
  ese idioma (`cai-language`). TEMA: light (por defecto) o dark. NOMBRES: lista separada por
  comas para hacer solo esas.

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
LANG = sys.argv[2]
THEME = sys.argv[3] if len(sys.argv) > 3 else "light"
ONLY = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else None
OUT.mkdir(parents=True, exist_ok=True)
assert LANG in ("en", "es"), "IDIOMA: en o es"


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
    # nombre: (ruta, barra plegada)
    pages = {
        "home": ("/", False),
        "inbox": ("/bandeja", False),
        "triage": ("/por-revisar", False),
        "job": (f"/jobs/{cv_job}", False),
        "job-cv": (f"/jobs/{cv_job}#cv", False),
        "job-process": (f"/jobs/{process_job}", False),
        "processes": ("/procesos", False),
        "funnel": ("/embudo", False),
        "skills": ("/skills", False),
        "templates": ("/plantillas", False),
        "sources-companies": ("/fuentes/empresas", False),
        "sources-platforms": ("/fuentes/plataformas", False),
        "agent": ("/agente", False),
        "sidebar-collapsed": ("/por-revisar", True),
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-web-security"])
        ctx = browser.new_context(
            viewport={"width": 1600, "height": 1000},
            device_scale_factor=1.5,
            color_scheme=THEME,
            locale="en-GB" if LANG == "en" else "es-ES",
        )

        def with_origin(route):  # type: ignore[no-untyped-def]
            headers = {**route.request.headers, "origin": "http://127.0.0.1:5173"}
            route.continue_(headers=headers)

        ctx.route(f"{API}/**", with_origin)
        for name, (path, collapsed) in pages.items():
            if ONLY and name not in ONLY:
                continue
            page = ctx.new_page()
            page.add_init_script(
                f"localStorage.setItem('cai-theme', '{THEME}');"
                f"localStorage.setItem('cai-language', '{LANG}');"
                f"localStorage.setItem('cai-sidebar-collapsed', '{1 if collapsed else 0}')"
            )
            page.goto(UI + path)
            page.wait_for_load_state("networkidle")
            # Los iconos de los portales se cargan de sus webs: más margen en Plataformas.
            page.wait_for_timeout(4000 if "plataformas" in path else 1500)
            if path.endswith("#cv"):
                top = page.locator("#cv").evaluate(
                    "e => e.getBoundingClientRect().top + window.scrollY - 150"
                )
                page.evaluate(f"window.scrollTo(0, {top})")
                page.wait_for_timeout(800)
            page.screenshot(path=str(OUT / f"{name}.png"))
            page.close()
            print("ok", name, path)
        browser.close()


run()
