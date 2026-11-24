"""Capturas de la demo para el README, la web y las listas de funcionalidades (WebP).

Uso (desde backend/): python screenshots.py OUT_DIR IDIOMA [TEMA] [NOMBRES]
  IDIOMA: en (README.md, demo en inglés) o es (README.es.md, demo en español). La UI se abre en
  ese idioma (`cai-language`). TEMA: light (por defecto) o dark; en oscuro solo se hacen las de
  `DARK`. NOMBRES: lista separada por comas para hacer solo esas.
La API de la demo en 8010, que sirve también la UI compilada (`pnpm build`): la app real sigue en
8000/5173 sin tocarse.

Ventana de 1440×900 en todas. Las de `README` (las 9 de los README y la web) salen a ×2
(2880×1800); el resto, a ×1. La franja «Modo demo» se oculta solo aquí: lo dice la nota bajo
cada bloque del README y de la web.

Los textos con los que se busca un botón, una pestaña o un título salen de
`frontend/src/locales/<idioma>/`, así que el script sirve para los dos idiomas.

La UI y la API están en el mismo origen, como con `cai start`: no hace falta saltarse CORS ni
reescribir cabeceras (la API rechaza cualquier escritura que no venga de su UI).
"""

import io
import json
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

UI = "http://127.0.0.1:8010"
OUT = Path(sys.argv[1])
LANG = sys.argv[2]
THEME = sys.argv[3] if len(sys.argv) > 3 else "light"
ONLY = set(sys.argv[4].split(",")) if len(sys.argv) > 4 else None
LOCALES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "locales" / LANG
OUT.mkdir(parents=True, exist_ok=True)
assert LANG in ("en", "es"), "IDIOMA: en o es"

VIEWPORT = {"width": 1440, "height": 900}
# Ofertas de la demo (`cai demo seed`, la misma en los dos idiomas): la primera con CV (CV, carta,
# paquete y dosier), la que tiene una entrevista con su plan y la que tiene una oferta recibida.
CV_JOB, INTERVIEW_JOB, OFFER_JOB = 1, 55, 60
# Las 9 de los README y de la web: a ×2.
README = {
    "home", "triage", "job-cv", "processes", "funnel", "replies", "calendar", "search",
    "profile-experience",
}
# Las que también se hacen en oscuro.
DARK = {"home", "triage", "job-cv", "processes", "profile-experience"}
# Calidad del WebP: a ×2 pesan cuatro veces más píxeles, así que algo menos de calidad.
QUALITY, QUALITY_2X = 80, 72


def text(ref: str) -> str:
    """`zona:clave.anidada` de los locales del idioma (p. ej. `process:title`)."""
    zone, key = ref.split(":")
    value = json.loads((LOCALES / f"{zone}.json").read_text(encoding="utf-8"))
    for part in key.split("."):
        value = value[part]
    return str(value)


# La franja «Modo demo», fuera de la captura (nunca de la app).
HIDE_DEMO = (
    "document.addEventListener('DOMContentLoaded', () => {"
    " const s = document.createElement('style');"
    f" s.textContent = '[role=note][aria-label=\"{text('nav:demo.label')}\"]{{display:none!important}}';"
    " document.head.appendChild(s) })"
)


# Las rutas de este equipo (la carpeta de la extensión, por ejemplo) llevan el nombre de quien
# genera las capturas: en la imagen salen cambiadas por unas inventadas, y si queda alguna, falla.
REPO = str(Path(__file__).resolve().parents[2])
HOME = str(Path.home())
FAKE_HOME = "C:\\Users\\olivia" if "\\" in HOME else "/home/olivia"
FAKE_REPO = FAKE_HOME + ("\\CandidatAI" if "\\" in HOME else "/CandidatAI")
MASK_PATHS = """([pairs]) => {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode())
    for (const [real, fake] of pairs)
      if (node.nodeValue.includes(real)) node.nodeValue = node.nodeValue.split(real).join(fake);
}"""


# Lo que se ve en la página: el texto y lo que llevan los campos y los atributos que se leen.
VISIBLE_TEXT = """() => [document.body.innerText,
  ...[...document.querySelectorAll('input, textarea')].map(e => e.value),
  ...[...document.querySelectorAll('[title], [placeholder], [aria-label]')].map(e =>
    [e.title, e.placeholder, e.getAttribute('aria-label')].join(' '))].join('\\n')"""


def mask_paths(page: Page) -> None:
    page.evaluate(MASK_PATHS, [[[REPO, FAKE_REPO], [HOME, FAKE_HOME]]])
    # El nombre de usuario suelto cubre también la ruta con «/», con «%20» o en otras mayúsculas.
    seen = page.evaluate(VISIBLE_TEXT).lower().replace("%20", " ")
    if Path(HOME).name.lower() in seen:
        sys.exit(f"La captura de {page.url} enseña una ruta de este equipo.")


def settle(page: Page) -> None:
    """Espera a que la página esté lista sin depender de que la red quede quieta del todo.

    La app consulta cosas cada pocos segundos y el servidor puede tardar en traer un icono: la red
    en reposo se espera un rato y, si no llega, basta con que no quede ningún «cargando»."""
    try:
        page.wait_for_load_state("networkidle", timeout=10_000)
    except PlaywrightTimeout:
        print("  (la red no queda en reposo; sigo cuando no haya nada cargando)")
    try:
        page.wait_for_function(
            "() => !document.querySelector('[data-slot=skeleton]')", timeout=20_000
        )
    except PlaywrightTimeout:
        print("  (aún hay algo cargando; capturo igualmente)")


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
        page.get_by_role("tab", name=text(ref), exact=True).first.click()
        page.wait_for_timeout(900)

    return step


def open_details(page: Page) -> None:
    """Despliega los `<details>` (p. ej. el plan de preparación de una entrevista)."""
    page.evaluate("document.querySelectorAll('details').forEach(d => { d.open = true })")
    page.wait_for_timeout(500)


def open_help(page: Page) -> None:
    """El panel de ayuda, con su atajo `?`."""
    page.keyboard.press("?")
    page.get_by_role("tablist", name=text("help:tabs.label")).wait_for(timeout=10_000)
    page.wait_for_timeout(900)


def job(job_id: int, tab_name: str) -> str:
    """La ficha de una oferta en una pestaña (`?tab=`: overview, application, process, company)."""
    return f"/jobs/{job_id}?tab={tab_name}"


# nombre: (ruta, barra plegada, pasos antes de capturar)
SHOTS = {
    "home": ("/", False, []),
    "how-it-works": ("/como-funciona", False, []),
    "inbox": ("/bandeja", False, []),
    "triage": ("/bandeja/revision", False, []),
    "alerts": ("/bandeja/por-completar", False, []),
    "processes": ("/procesos", False, []),
    "search": ("/buscar", False, []),
    "search-settings": ("/buscar/ajustes", False, []),
    "calendar": ("/calendario", False, []),
    "replies": ("/respuestas", False, []),
    "funnel": ("/resultados", False, []),
    "skills": ("/perfil/skills", False, []),
    "templates": ("/perfil/plantillas", False, []),
    "profile-experience": ("/perfil", False, [tab("profileEditor:tabs.career"), anchor("[role=tablist]", 30)]),
    "profile-history": ("/perfil", False, [tab("profileEditor:tabs.history")]),
    "sources-companies": ("/fuentes/empresas", False, []),
    "sources-platforms": ("/fuentes/plataformas", False, []),
    "sources-email": ("/fuentes/correo", False, []),
    # Sin la extensión instalada en este Chromium: la guía en el paso 1.
    "sources-extension": ("/fuentes/extension", False, []),
    "agent": ("/agente", False, []),
    "new-job": ("/nueva", False, []),
    "job": (job(CV_JOB, "overview"), False, []),
    # Desde las pestañas de la ficha, sin una línea cortada por arriba.
    "job-cv": (job(CV_JOB, "application"), False, [anchor("[role=tablist]", 24)]),
    "job-letter": (job(CV_JOB, "application"), False, [anchor("#carta")]),
    "job-package": (job(CV_JOB, "application"), False, [anchor("#paquete")]),
    "job-research": (job(CV_JOB, "company"), False, [heading("research:title")]),
    "job-interview": (job(INTERVIEW_JOB, "process"), False, [open_details, heading("process:title")]),
    "job-offer": (job(OFFER_JOB, "process"), False, [heading("offers:received.title")]),
    "help": ("/", False, [open_help]),
    "assistant": ("/", False, [open_help, tab("help:tabs.assistant")]),
    "sidebar-collapsed": ("/bandeja/revision", True, []),
}


def save_webp(png: bytes, target: Path, quality: int) -> None:
    Image.open(io.BytesIO(png)).convert("RGB").save(target, "WEBP", quality=quality, method=6)


def new_context(browser: Browser, scale: int) -> BrowserContext:
    ctx = browser.new_context(
        viewport=VIEWPORT,
        device_scale_factor=scale,
        color_scheme=THEME,
        locale="en-GB" if LANG == "en" else "es-ES",
    )
    ctx.add_init_script(HIDE_DEMO)
    return ctx


def run() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        contexts: dict[int, BrowserContext] = {}
        for name, (path, collapsed, steps) in SHOTS.items():
            if (ONLY and name not in ONLY) or (THEME == "dark" and name not in DARK):
                continue
            scale = 2 if name in README else 1
            if scale not in contexts:
                contexts[scale] = new_context(browser, scale)
            page = contexts[scale].new_page()
            page.add_init_script(
                f"localStorage.setItem('cai-theme', '{THEME}');"
                f"localStorage.setItem('cai-language', '{LANG}');"
                f"localStorage.setItem('cai-sidebar-collapsed', '{1 if collapsed else 0}')"
            )
            print("…", name, path, flush=True)
            page.goto(UI + path, timeout=90_000)
            settle(page)
            # Los iconos de los portales se cargan de sus webs: más margen en Plataformas.
            page.wait_for_timeout(4000 if "plataformas" in path else 1500)
            for step in steps:
                step(page)
            mask_paths(page)
            target = OUT / f"{name}.webp"
            save_webp(page.screenshot(), target, QUALITY_2X if scale == 2 else QUALITY)
            page.close()
            print("ok", name, path, f"×{scale}", f"{target.stat().st_size // 1024} KB")
        browser.close()


run()
