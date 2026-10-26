"""Capturas de la demo para el README y las listas de funcionalidades (WebP, fase 28.3b).

Uso (desde backend/): python screenshots.py OUT_DIR IDIOMA [TEMA] [NOMBRES]
  IDIOMA: en (README.md, demo en inglés) o es (README.es.md, demo en español). La UI se abre en
  ese idioma (`cai-language`). TEMA: light (por defecto) o dark; en oscuro solo se hacen las de
  `DARK`. NOMBRES: lista separada por comas para hacer solo esas.
UI en 5181 y API en 8010 (la app real sigue en 5173/8000).

Los textos con los que se busca un botón, una pestaña o un título salen de
`frontend/src/locales/<idioma>/`, así que el script sirve para los dos idiomas.

La API solo acepta el origen 127.0.0.1:5173: este Chromium ignora CORS y cada petición a la API
sale con ese `Origin`. Solo para capturas, en local.
"""

import io
import json
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import Page, sync_playwright

UI = "http://127.0.0.1:5181"
API = "http://127.0.0.1:8010"
OUT = Path(sys.argv[1])
LANG = sys.argv[2]
THEME = sys.argv[3] if len(sys.argv) > 3 else "light"
ONLY = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else None
LOCALES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "locales" / LANG
OUT.mkdir(parents=True, exist_ok=True)
assert LANG in ("en", "es"), "IDIOMA: en o es"

# Ofertas de la demo (`cai demo seed`, la misma en los dos idiomas): la primera con CV (CV, carta,
# paquete y dosier), la que tiene una entrevista con su plan y la que tiene una oferta recibida.
CV_JOB, INTERVIEW_JOB, OFFER_JOB = 1, 55, 60
# Las que también se hacen en oscuro.
DARK = {"home", "triage", "job-cv", "processes", "profile-experience"}
QUALITY = 80


def text(ref: str) -> str:
    """`zona:clave.anidada` de los locales del idioma (p. ej. `process:title`)."""
    zone, key = ref.split(":")
    value = json.loads((LOCALES / f"{zone}.json").read_text(encoding="utf-8"))
    for part in key.split("."):
        value = value[part]
    return str(value)


def scroll_to(page: Page, locator_top: float, offset: int = 110) -> None:
    page.evaluate(f"window.scrollTo(0, {locator_top} + window.scrollY - {offset})")
    page.wait_for_timeout(700)


def heading(ref: str):  # type: ignore[no-untyped-def]
    def step(page: Page) -> None:
        target = page.get_by_role("heading", name=text(ref), exact=True).first
        scroll_to(page, target.evaluate("e => e.getBoundingClientRect().top"))

    return step


def anchor(selector: str, offset: int = 110):  # type: ignore[no-untyped-def]
    def step(page: Page) -> None:
        top = page.locator(selector).first.evaluate("e => e.getBoundingClientRect().top")
        scroll_to(page, top, offset)

    return step


def tab(ref: str):  # type: ignore[no-untyped-def]
    def step(page: Page) -> None:
        page.get_by_role("tab", name=text(ref), exact=True).click()
        page.wait_for_timeout(900)

    return step


def button(ref: str):  # type: ignore[no-untyped-def]
    def step(page: Page) -> None:
        page.get_by_role("button", name=text(ref)).first.click()
        page.wait_for_timeout(900)

    return step


def open_details(page: Page) -> None:
    """Despliega los `<details>` (p. ej. el plan de preparación de una entrevista)."""
    page.evaluate("document.querySelectorAll('details').forEach(d => { d.open = true })")
    page.wait_for_timeout(500)


# nombre: (ruta, barra plegada, pasos antes de capturar)
SHOTS = {
    "home": ("/", False, []),
    "inbox": ("/bandeja", False, []),
    "triage": ("/por-revisar", False, []),
    "alerts": ("/alertas", False, [button("mailboxes:panel.title")]),
    "processes": ("/procesos", False, []),
    "calendar": ("/calendario", False, []),
    "replies": ("/respuestas", False, []),
    "funnel": ("/embudo", False, []),
    "skills": ("/skills", False, []),
    "templates": ("/plantillas", False, []),
    "profile-experience": ("/perfil", False, [tab("profileEditor:tabs.career"), anchor("[role=tablist]", 30)]),
    "profile-search": ("/perfil", False, [tab("profileEditor:tabs.search"), anchor("[role=tablist]", 30)]),
    "sources-companies": ("/fuentes/empresas", False, []),
    "sources-platforms": ("/fuentes/plataformas", False, []),
    "agent": ("/agente", False, []),
    "new-job": ("/nueva", False, []),
    "job": (f"/jobs/{CV_JOB}", False, []),
    "job-cv": (f"/jobs/{CV_JOB}", False, [anchor("#cv")]),
    "job-letter": (f"/jobs/{CV_JOB}", False, [anchor("#carta")]),
    "job-package": (f"/jobs/{CV_JOB}", False, [anchor("#paquete")]),
    "job-research": (f"/jobs/{CV_JOB}", False, [heading("research:title")]),
    "job-interview": (f"/jobs/{INTERVIEW_JOB}", False, [open_details, heading("process:title")]),
    "job-offer": (f"/jobs/{OFFER_JOB}", False, [heading("offers:received.title")]),
    "sidebar-collapsed": ("/por-revisar", True, []),
}


def save_webp(png: bytes, target: Path) -> None:
    Image.open(io.BytesIO(png)).convert("RGB").save(target, "WEBP", quality=QUALITY, method=6)


def run() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-web-security"])
        ctx = browser.new_context(
            viewport={"width": 1600, "height": 1000},
            device_scale_factor=1,
            color_scheme=THEME,
            locale="en-GB" if LANG == "en" else "es-ES",
        )

        def with_origin(route):  # type: ignore[no-untyped-def]
            headers = {**route.request.headers, "origin": "http://127.0.0.1:5173"}
            route.continue_(headers=headers)

        ctx.route(f"{API}/**", with_origin)
        for name, (path, collapsed, steps) in SHOTS.items():
            if (ONLY and name not in ONLY) or (THEME == "dark" and name not in DARK):
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
            for step in steps:
                step(page)
            save_webp(page.screenshot(), OUT / f"{name}.webp")
            page.close()
            print("ok", name, path)
        browser.close()


run()
