"""Animaciones de la demo para el README y la web (WebP animado) y el tour en vídeo (MP4).

Uso (desde backend/, con ffmpeg): uv run --with imageio-ffmpeg python recordings.py OUT_DIR ESCENA IDIOMA
  ESCENA: tour, triage, discard, mailbox, cv, profile, apply, start, extension o video.
  IDIOMA: en o es.
La API de la demo en 8010, que sirve también la UI compilada (`pnpm build`), en el mismo origen:
sin saltarse CORS ni reescribir cabeceras. La app real sigue en 8000/5173 sin tocarse.

- `tour`: la animación de la sección «Demo» del README y de la web. 25-30 s, 1280×800, en bucle,
  de hasta 1,5 MB y **sin leyendas**: se entiende por lo que dice la app.
- Las cortas (`triage`, `discard`, `mailbox`, `cv`, `profile`, `apply`, `extension`): menos de 20 s,
  con una leyenda abajo (`CAPTIONS`), porque van sueltas en las listas de funcionalidades.
- `video`: el tour en vídeo, fuera de git. 60-90 s, 1920×1080, con subtítulos incrustados
  (`VIDEO_CAPTIONS`) y también en `.srt` y `.vtt`, su transcripción y un clip cuadrado de 15-20 s
  para redes. Todo en `OUT_DIR` (por defecto, `data/tmp/video/<idioma>/`), para subirlo como activo
  de la release.

Graba un `.webm` con Playwright y lo convierte con ffmpeg (`FFMPEG`, el de `imageio-ffmpeg` o el del
PATH). Los textos con los que se busca un botón salen de `frontend/src/locales/<idioma>/`. La
franja «Modo demo» se oculta solo en la grabación: lo dice la nota bajo la animación.

Escenas que cambian la demo: `triage` aprueba una oferta, `discard` descarta una (y la devuelve),
`mailbox` añade un buzón, `cv` renderiza otro CV, y `tour` y `video` aprueban una, descartan otra,
renderizan otro CV, dejan preparada la candidatura de `CV_JOB` (sin enviarla) y mueven una tarjeta
del Tablero. Usa una demo solo para esto.

`apply` necesita un formulario que el worker pueda rellenar sin salir a internet: el de prueba de
Greenhouse de los tests, servido en 127.0.0.1:8030, con la oferta `CV_JOB` apuntando a él y el
worker de la demo con `CAI_APPLIER_ALLOW_LOOPBACK=1` (ver README.md). Se para antes de enviar.

`extension` enseña el botón «Enviar a CandidatAI» con una oferta pública real de LinkedIn
(`LINKEDIN_URL`, sin sesión iniciada): el vídeo de Playwright solo graba la página, así que la
barra del navegador y el cursor se dibujan en un escenario local; la página de la oferta es una
captura suya y el popup es el `popup.html` de verdad de la extensión. La oferta se da de alta en
la demo por la API y la escena acaba en la Bandeja. Deja también `extension-still.webp`, el
fotograma fijo que la UI enseña a quien prefiere menos movimiento. Menos de 10 s y de 1 MB.
Es solo para grabar este material, a mano y de vez en cuando: abre una sola página pública, sin
cuenta ni cookies guardadas, y no forma parte de la app (que nunca descarga LinkedIn).

`start` reproduce en un terminal la salida real de `cai start` (la que lee de START_LOG) y abre
la app que sirve ese `cai start` en START_URL (otro puerto, con la UI compilada).
"""

import base64
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Browser, BrowserContext, Locator, Page, Route, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeout

UI = API = "http://127.0.0.1:8010"
START_URL = os.environ.get("START_URL", "http://127.0.0.1:8020")
START_LOG = os.environ.get("START_LOG", "")
OUT = Path(sys.argv[1])
SCENE = sys.argv[2]
LANG = sys.argv[3]
ROOT = Path(__file__).resolve().parents[2]
LOCALES = ROOT / "frontend" / "src" / "locales" / LANG
EXTENSION = ROOT / "extension"
LINKEDIN_URL = os.environ.get("LINKEDIN_URL", "")
CV_JOB, INTERVIEW_JOB = 1, 55
# Ventana de grabación, la misma que la de las capturas (16:10). El vídeo, a 1080p.
SIZE = {"width": 1440, "height": 900}
VIDEO_SIZE = {"width": 1920, "height": 1080}
# Ancho, fotogramas por segundo y calidad del WebP: unos 300 KB por escena.
WIDTH, FPS, QUALITY = 900, 6, 50
# La animación de la portada, más nítida pero de hasta 1,5 MB (`TOUR_MAX`). La del botón del
# navegador va dentro de la UI, en un aviso estrecho: más pequeña y por debajo de 1 MB.
SHARP = {"tour": (1280, 5, 50), "extension": (900, 8, 55)}
TOUR_MAX = 1.5 * 1024 * 1024
# Cuántas veces más rápido va el WebP que la grabación. El tour se graba a velocidad real (unos
# 40 s, porque el CV tarda en renderizarse) y se acelera para quedar en 25-30 s; lo dice la nota
# bajo la demo en los README y la web.
SPEED = {"tour": 1.5}
# Lo que se recorta al principio de cada grabación: el fotograma en blanco antes de cargar.
TRIM = 1.2
# El clip para redes: cuadrado, de esta duración, desde la revisión de ofertas del vídeo.
CLIP_SIDE, CLIP_SECONDS = 1080, 18
OUT.mkdir(parents=True, exist_ok=True)
assert LANG in ("en", "es"), "IDIOMA: en o es"

CAPTIONS = {
    "es": {
        "triage": [
            "Por revisar: cada oferta con su score explicado",
            "J y K para moverte",
            "A aprueba · D descarta con motivo",
        ],
        "discard": [
            "Por completar: resúmenes de alertas",
            "Descartar, sin abrir la oferta",
            "¿Te equivocaste? Deshacer",
        ],
        "mailbox": [
            "Alertas: añade los buzones donde te llegan",
            "Una guía por proveedor: Gmail, Outlook, Yahoo, iCloud…",
            "O una carpeta de .eml, con cualquier proveedor",
            "Listo: la app solo lee, nunca envía ni borra",
        ],
        "cv": [
            "El contenido del CV ya está verificado",
            "Otra plantilla y otro color, sin gastar tu agente",
            "Renderizado en segundos",
        ],
        "profile": [
            "Mi perfil: lo único que puede afirmar tu CV",
            "Cada empresa, de un vistazo",
            "Despliega para ver y editar sus logros",
        ],
        "apply": [
            "Candidatura asistida: la app rellena el formulario",
            "Te enseña qué rellenó y de dónde sale",
            "Solo se envía si escribes el nombre de la empresa",
        ],
        "start": ["Una orden arranca la app y abre el navegador"],
        "extension": [
            "Abre la oferta en LinkedIn y pulsa el botón de CandidatAI",
            "La oferta se envía a tu CandidatAI",
            "Ya está en tu Bandeja, lista para leer",
        ],
    },
    "en": {
        "triage": [
            "To review: every job with its explained score",
            "J and K to move",
            "A approves · D discards with a reason",
        ],
        "discard": [
            "To complete: summaries from alerts",
            "Discard without opening the job",
            "Changed your mind? Undo",
        ],
        "mailbox": [
            "Alerts: add the mailboxes they arrive in",
            "A guide per provider: Gmail, Outlook, Yahoo, iCloud…",
            "Or a folder of .eml files, with any provider",
            "Done: the app only reads, never sends or deletes",
        ],
        "cv": [
            "The CV content is already verified",
            "Another template and colour, no agent time",
            "Rendered in seconds",
        ],
        "profile": [
            "My profile: the only thing your CV can claim",
            "Every company at a glance",
            "Expand one to see and edit its achievements",
        ],
        "apply": [
            "Assisted application: the app fills the form",
            "It shows what it filled in and where it came from",
            "It only sends once you type the company name",
        ],
        "start": ["One command starts the app and opens the browser"],
        "extension": [
            "Open the job on LinkedIn and click the CandidatAI button",
            "The job is sent to your CandidatAI",
            "It's in your Inbox, ready to read",
        ],
    },
}

# Los subtítulos del vídeo, por pasos (`say`). Se entienden sin sonido y sin conocer la app.
VIDEO_CAPTIONS = {
    "es": {
        "home": "CandidatAI: tu búsqueda de empleo, en tu equipo",
        "new": "Las ofertas entran por URL, por texto, por correo o con la extensión",
        "inbox": "Tu agente de IA las lee y valora el encaje con tu perfil",
        "review": "Revisas cada oferta con su encaje explicado",
        "approve": "A la aprueba",
        "discard": "D la descarta, con su motivo",
        "cv": "Tu agente redacta el CV y la app comprueba cada línea con tu perfil",
        "design": "Otra plantilla y otro color, en segundos y sin gastar tu agente",
        "letter": "También la carta de presentación, con tus indicaciones",
        "apply": "La app rellena el formulario y enseña de dónde sale cada respuesta",
        "send": "Nada se envía hasta que confirmas, escribiendo el nombre de la empresa",
        "board": "El Tablero: cada candidatura, de enviada a oferta",
        "move": "Mueves una tarjeta y queda registrado el paso",
        "replies": "Los correos de las empresas, clasificados para que los aceptes",
        "calendar": "Entrevistas, pruebas y seguimientos en un calendario",
        "interview": "Para cada entrevista, una guía de preparación",
        "results": "Resultados: qué fuentes, puestos y plantillas funcionan",
        "end": "Código abierto y local. Funciona con el agente de IA que ya usas",
    },
    "en": {
        "home": "CandidatAI: your job search, on your own machine",
        "new": "Jobs come in by URL, as text, by email or with the browser extension",
        "inbox": "Your AI agent reads them and assesses the fit with your profile",
        "review": "You review each job with its fit explained",
        "approve": "A approves it",
        "discard": "D discards it, with a reason",
        "cv": "Your agent writes the CV and the app checks every line against your profile",
        "design": "Another template and colour, in seconds and without agent time",
        "letter": "The cover letter too, following your instructions",
        "apply": "The app fills the form and shows where each answer comes from",
        "send": "Nothing is sent until you confirm by typing the company name",
        "board": "The Board: every application, from sent to offer",
        "move": "Move a card and the step is recorded",
        "replies": "Company emails, classified for you to accept",
        "calendar": "Interviews, tests and follow-ups in one calendar",
        "interview": "A preparation guide for every interview",
        "results": "Results: which sources, roles and templates work",
        "end": "Open source and local. Works with the AI agent you already use",
    },
}

CAPTION_JS = """([text, size]) => {
  let bar = document.getElementById('cai-caption');
  if (!bar) {
    bar = document.createElement('div');
    bar.id = 'cai-caption';
    bar.style.cssText = 'position:fixed;left:50%;bottom:28px;transform:translateX(-50%);'
      + 'z-index:2147483647;background:rgba(12,20,22,.88);color:#fff;padding:12px 26px;'
      + 'border-radius:999px;font:600 ' + size + 'px system-ui,sans-serif;'
      + 'box-shadow:0 8px 30px #0005;pointer-events:none;white-space:nowrap';
    document.body.appendChild(bar);
  }
  bar.textContent = text;
}"""

# La franja «Modo demo», fuera de la grabación (nunca de la app).
HIDE_DEMO_JS = """label => document.addEventListener('DOMContentLoaded', () => {
  const s = document.createElement('style');
  s.textContent = `[role=note][aria-label="${label}"]{display:none!important}`;
  document.head.appendChild(s);
})"""

# Un cursor dibujado: el vídeo de Playwright no graba el del sistema, y sin él no se ve quién
# arrastra la tarjeta.
CURSOR_JS = """([x, y, down]) => {
  let c = document.getElementById('cai-cursor');
  if (!c) {
    c = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    c.id = 'cai-cursor';
    c.setAttribute('viewBox', '0 0 24 24');
    c.style.cssText = 'position:fixed;width:26px;z-index:2147483647;pointer-events:none;'
      + 'transition:transform .12s';
    c.innerHTML = '<path d="M3 2l7 19 2.6-7.4L20 11z" fill="#111" stroke="#fff" '
      + 'stroke-width="1.5" stroke-linejoin="round"/>';
    document.body.appendChild(c);
  }
  c.style.left = x + 'px';
  c.style.top = y + 'px';
  c.style.transform = down ? 'scale(.85)' : '';
}"""


def text(ref: str, **values: object) -> str:
    """`zona:clave.anidada` de los locales del idioma, con `{{valores}}` sustituidos."""
    zone, key = ref.split(":")
    value = json.loads((LOCALES / f"{zone}.json").read_text(encoding="utf-8"))
    for part in key.split("."):
        value = value[part]
    result = str(value)
    for name, item in values.items():
        result = result.replace("{{" + name + "}}", str(item))
    return result


def caption(page: Page, n: int) -> None:
    page.evaluate(CAPTION_JS, [CAPTIONS[LANG][SCENE][n], 26])


# Los subtítulos del vídeo: (segundo en que aparece, texto), contados desde que empieza a grabar.
CUES: list[tuple[float, str]] = []
CLOCK: dict[str, float] = {}


def say(page: Page, key: str) -> None:
    """Un subtítulo del vídeo: en la página (incrustado) y en `CUES` (para el `.srt` y el `.vtt`)."""
    line = VIDEO_CAPTIONS[LANG][key]
    page.evaluate(CAPTION_JS, [line, 30])
    CUES.append((time.monotonic() - CLOCK["start"], line))


def pause(page: Page, ms: int) -> None:
    page.wait_for_timeout(ms)


def smooth_scroll(page: Page, to: int, steps: int = 20) -> None:
    start = page.evaluate("window.scrollY")
    for i in range(1, steps + 1):
        page.evaluate(f"window.scrollTo(0, {start + (to - start) * i / steps})")
        pause(page, 40)


def top_of(page: Page, selector: str, offset: int = 120) -> int:
    return int(
        page.locator(selector)
        .first.evaluate(f"e => e.getBoundingClientRect().top + window.scrollY - {offset}")
    )


def idle(page: Page) -> None:
    """La red en reposo, un rato como mucho: la app consulta cosas cada pocos segundos, así que no
    se espera a que quede quieta del todo (lo que se espere queda grabado)."""
    try:
        page.wait_for_load_state("networkidle", timeout=3000)
    except PlaywrightTimeout:
        pass


def goto(page: Page, path: str, wait: int = 1500, base: str = UI) -> None:
    print("…", path, flush=True)
    page.goto(base + path, timeout=90_000)
    idle(page)
    loaded(page)
    pause(page, wait)


def loaded(page: Page) -> None:
    """Tras cambiar de página dentro de la app: hasta que no quede nada cargando."""
    page.wait_for_function("() => !document.querySelector('[data-slot=skeleton]')", timeout=30_000)
    pause(page, 600)


def nav(page: Page, entry: str) -> None:
    """Va a otra página con el menú lateral: sin recargar, y sin un fotograma en blanco."""
    menu = page.get_by_role("navigation")
    menu.get_by_role("link", name=text(f"nav:entries.{entry}")).first.click()
    loaded(page)


def route(page: Page, path: str) -> None:
    """Va a una ruta sin recargar (el router de la UI escucha `popstate`): sin fotograma en blanco."""
    page.evaluate(
        "path => { history.pushState({}, '', path); dispatchEvent(new PopStateEvent('popstate')) }",
        path,
    )
    loaded(page)


def application_tab(job_id: int) -> str:
    """La pestaña «Candidatura» de una ficha: el CV, la carta, el paquete y el formulario."""
    return f"/jobs/{job_id}?tab=application"


def change_design(page: Page) -> int:
    """En el CV: la pestaña «Diseño», otra plantilla y otro color, y espera a que esté. Da el `top`."""
    top = top_of(page, "#cv")
    smooth_scroll(page, top)
    page.locator("#cv").get_by_role("tab", name=text("cv:panel.design"), exact=True).click()
    pause(page, 700)
    form = page.locator("#cv form:has(input[name=template])")
    form.locator("label:has(input[value='moderna-2col'])").click()
    pause(page, 700)
    form.locator("input[name=accent]").nth(1).check(force=True)
    pause(page, 700)
    form.locator("button[type=submit]").click()
    # El del formulario de diseño: en `#cv` hay otros (pedir correcciones) con su propio botón.
    page.wait_for_function(
        "() => !document.querySelector("
        "'#cv form:has(input[name=template]) button[type=submit]').disabled",
        timeout=120_000,
    )
    return top


def triage_ready(page: Page) -> None:
    """La revisión, con una oferta seleccionada: antes, las teclas A, D, J y K no hacen nada."""
    page.locator("[role=option][aria-selected=true]").first.wait_for(timeout=60_000)
    pause(page, 400)


def scene_triage(page: Page) -> None:
    goto(page, "/bandeja/revision")
    triage_ready(page)
    caption(page, 0)
    pause(page, 1800)
    caption(page, 1)
    for key in ("j", "j", "k"):
        page.keyboard.press(key)
        pause(page, 1000)
    caption(page, 2)
    pause(page, 800)
    page.keyboard.press("a")
    pause(page, 2200)


def scene_discard(page: Page) -> None:
    goto(page, "/bandeja/por-completar")
    caption(page, 0)
    pause(page, 2000)
    caption(page, 1)
    page.get_by_role("button", name=text("alerts:discard"), exact=True).first.click()
    # El motivo, en su diálogo: 2 y Enter, como en la revisión.
    page.get_by_role("dialog").wait_for()
    pause(page, 800)
    page.keyboard.press("2")
    pause(page, 500)
    page.keyboard.press("Enter")
    page.get_by_role("button", name=text("alerts:undo"), exact=True).first.wait_for()
    pause(page, 1500)
    caption(page, 2)
    pause(page, 800)
    page.get_by_role("button", name=text("alerts:undo"), exact=True).first.click()
    pause(page, 2200)


def scene_mailbox(page: Page) -> None:
    goto(page, "/fuentes/correo")
    caption(page, 0)
    pause(page, 1500)
    page.get_by_role("button", name=text("mailboxes:add")).first.click()
    pause(page, 1200)
    caption(page, 1)
    dialog = page.get_by_role("dialog")
    for provider in ("gmail", "outlook"):
        dialog.get_by_role("tab", name=text(f"mailboxes:providers.{provider}.name")).click()
        pause(page, 1600)
    caption(page, 2)
    dialog.get_by_role("tab", name=text("mailboxes:providers.folder.name")).click()
    pause(page, 1000)
    label = dialog.get_by_label(text("mailboxes:fields.label"), exact=True)
    label.fill("")
    label.press_sequentially("Outlook", delay=70)
    folder = dialog.get_by_label(text("mailboxes:fields.folderName"), exact=True)
    folder.fill("")
    folder.press_sequentially("outlook", delay=70)
    pause(page, 800)
    dialog.get_by_role("button", name=text("mailboxes:dialog.save")).click()
    pause(page, 1200)
    caption(page, 3)
    pause(page, 2400)


def scene_cv(page: Page) -> None:
    goto(page, application_tab(CV_JOB), 1200)
    smooth_scroll(page, top_of(page, "#cv"))
    caption(page, 0)
    pause(page, 1600)
    caption(page, 1)
    top = change_design(page)
    caption(page, 2)
    pause(page, 800)
    smooth_scroll(page, top + 650)
    pause(page, 2200)


def scene_profile(page: Page) -> None:
    goto(page, "/perfil")
    caption(page, 0)
    pause(page, 1500)
    page.get_by_role("tab", name=text("profileEditor:tabs.career"), exact=True).click()
    pause(page, 900)
    smooth_scroll(page, top_of(page, "[role=tablist]", 30))
    caption(page, 1)
    pause(page, 1800)
    caption(page, 2)
    page.locator("[role=tabpanel] button[aria-expanded=false]:visible").first.click()
    pause(page, 1200)
    smooth_scroll(page, page.evaluate("window.scrollY") + 450)
    pause(page, 2400)


def type_company(dialog: Locator) -> None:
    """Escribe, para confirmar el envío, la empresa que nombra el título del diálogo."""
    prefix = text("apply:submit.title", company="")
    company = dialog.get_by_role("heading").first.inner_text().removeprefix(prefix).strip()
    dialog.get_by_role("textbox").first.press_sequentially(company.split()[0], delay=90)


def scene_apply(page: Page) -> None:
    goto(page, application_tab(CV_JOB), 1200)
    smooth_scroll(page, top_of(page, "#candidatura"))
    caption(page, 0)
    pause(page, 1200)
    section = page.locator("#candidatura")
    prepare = section.get_by_role("button", name=text("apply:prepare.prepare"))
    again = section.get_by_role("button", name=text("apply:prepare.again"))
    prepare.or_(again).first.click()
    send = section.get_by_role("button", name=text("apply:review.send"), exact=True)
    send.wait_for(timeout=180_000)
    pause(page, 800)
    caption(page, 1)
    smooth_scroll(page, top_of(page, "#candidatura") + 380)
    pause(page, 2400)
    caption(page, 2)
    send.scroll_into_view_if_needed()
    send.click()
    pause(page, 1000)
    dialog = page.get_by_role("dialog")
    type_company(dialog)
    pause(page, 2400)


def prepare_application(page: Page) -> None:
    """Rellena antes de grabar el formulario de `CV_JOB`: así la grabación no espera al worker."""
    goto(page, application_tab(CV_JOB), 800)
    section = page.locator("#candidatura")
    send = section.get_by_role("button", name=text("apply:review.send"), exact=True)
    if send.count():
        return
    prepare = section.get_by_role("button", name=text("apply:prepare.prepare"))
    again = section.get_by_role("button", name=text("apply:prepare.again"))
    prepare.or_(again).first.click()
    send.wait_for(timeout=180_000)


def stop_at_confirmation(page: Page, top_ms: int, dialog_ms: int, on_send=None) -> None:  # type: ignore[no-untyped-def]
    """La candidatura ya rellenada: se ve y se pulsa Enviar, y se para en la confirmación."""
    section = page.locator("#candidatura")
    smooth_scroll(page, top_of(page, "#candidatura") + 380)
    pause(page, top_ms)
    if on_send:
        on_send()
    send = section.get_by_role("button", name=text("apply:review.send"), exact=True)
    send.scroll_into_view_if_needed()
    send.click()
    pause(page, 800)
    type_company(page.get_by_role("dialog"))
    pause(page, dialog_ms)
    page.keyboard.press("Escape")
    pause(page, 400)


def move_card(page: Page) -> None:
    """Arrastra una tarjeta de «Enviada» a «En proceso» y registra el paso.

    Las columnas por defecto son Aprobada, CV listo, Enviada, En proceso y Cerradas; de Aprobada a
    CV listo no se pasa a mano (lo da tener un CV), así que se usa la tercera. Con el cursor
    dibujado; si el diálogo no deja registrar (falta un dato), se cierra sin más."""
    columns = page.locator("div.grid > section[aria-label]")
    card = columns.nth(2).locator("li[aria-roledescription]").first
    target = columns.nth(3)
    start, end = card.bounding_box(), target.bounding_box()
    assert start and end, "El Tablero no tiene una tarjeta con una columna a su derecha"
    # Por la esquina de abajo a la derecha: el título es un enlace y desde él no se arrastra.
    x0, y0 = start["x"] + start["width"] - 25, start["y"] + start["height"] - 12
    x1, y1 = end["x"] + end["width"] / 2, end["y"] + 120
    page.evaluate(CURSOR_JS, [x0 - 60, y0 + 80, False])
    for i in range(1, 11):
        page.evaluate(CURSOR_JS, [x0 - 60 + 6 * i, y0 + 80 - 8 * i, False])
        pause(page, 30)
    page.mouse.move(x0, y0)
    page.evaluate(CURSOR_JS, [x0, y0, True])
    page.mouse.down()
    pause(page, 200)
    steps = 30
    for i in range(1, steps + 1):
        x, y = x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps
        page.mouse.move(x, y)
        page.evaluate(CURSOR_JS, [x, y, True])
        pause(page, 25)
    pause(page, 300)
    page.mouse.up()
    page.evaluate(CURSOR_JS, [x1, y1, False])
    dialog = page.get_by_role("dialog")
    dialog.wait_for(timeout=10_000)
    page.evaluate("() => document.getElementById('cai-cursor')?.remove()")
    pause(page, 1100)
    dialog.get_by_role("radio").first.click()
    pause(page, 700)
    register = dialog.get_by_role("button", name=text("move:register"))
    if register.is_enabled():
        register.click()
    else:
        page.keyboard.press("Escape")
    loaded(page)


def mark(label: str) -> None:
    """Cuánto lleva la grabación al acabar un paso: para ajustar la duración."""
    print(f"  {time.monotonic() - CLOCK['start']:5.1f} s · {label}", flush=True)


def scene_tour(page: Page) -> None:
    """La animación de la portada, sin leyendas: Inicio → aprobar → CV en otro diseño →
    candidatura parada en la confirmación → mover una tarjeta en el Tablero → Resultados."""
    goto(page, "/", 800)
    pause(page, 1500)

    mark("inicio")
    route(page, "/bandeja/revision")
    triage_ready(page)
    pause(page, 1000)
    for key in ("j", "j"):
        page.keyboard.press(key)
        pause(page, 600)
    page.keyboard.press("a")
    pause(page, 1300)
    triage_ready(page)
    page.keyboard.press("d")
    page.get_by_role("dialog").wait_for()
    pause(page, 700)
    page.keyboard.press("2")
    pause(page, 600)
    page.keyboard.press("Enter")
    pause(page, 1200)

    mark("revision")
    route(page, application_tab(CV_JOB))
    top = change_design(page)
    smooth_scroll(page, top + 500)
    pause(page, 1300)

    mark("cv")
    stop_at_confirmation(page, 1500, 1500)

    mark("candidatura")
    nav(page, "processes")
    pause(page, 800)
    move_card(page)
    pause(page, 1000)
    mark("tablero")
    nav(page, "funnel")
    page.get_by_role("heading", level=1).first.wait_for(timeout=30_000)
    pause(page, 2500)
    mark("resultados")


def scene_video(page: Page) -> None:
    """El tour en vídeo: de la oferta nueva a la entrevista y los resultados, con subtítulos."""
    goto(page, "/", 800)
    loaded(page)
    say(page, "home")
    pause(page, 3500)

    route(page, "/nueva")
    say(page, "new")
    pause(page, 3500)
    route(page, "/bandeja")
    say(page, "inbox")
    pause(page, 3500)

    route(page, "/bandeja/revision")
    triage_ready(page)
    CLOCK["clip"] = time.monotonic() - CLOCK["start"]
    say(page, "review")
    pause(page, 1600)
    for key in ("j", "j"):
        page.keyboard.press(key)
        pause(page, 900)
    say(page, "approve")
    page.keyboard.press("a")
    pause(page, 2000)
    triage_ready(page)
    say(page, "discard")
    page.keyboard.press("d")
    page.get_by_role("dialog").wait_for()
    pause(page, 900)
    page.keyboard.press("2")
    pause(page, 800)
    page.keyboard.press("Enter")
    pause(page, 1500)

    route(page, application_tab(CV_JOB))
    smooth_scroll(page, top_of(page, "#cv"))
    say(page, "cv")
    pause(page, 3500)
    say(page, "design")
    top = change_design(page)
    smooth_scroll(page, top + 500)
    pause(page, 2500)
    smooth_scroll(page, top_of(page, "#carta"))
    say(page, "letter")
    pause(page, 3000)

    smooth_scroll(page, top_of(page, "#candidatura"))
    say(page, "apply")
    stop_at_confirmation(page, 3000, 2500, on_send=lambda: say(page, "send"))

    nav(page, "processes")
    say(page, "board")
    pause(page, 3000)
    say(page, "move")
    move_card(page)
    pause(page, 1500)

    nav(page, "replies")
    say(page, "replies")
    pause(page, 3500)
    nav(page, "calendar")
    say(page, "calendar")
    pause(page, 3500)

    route(page, f"/jobs/{INTERVIEW_JOB}?tab=process")
    say(page, "interview")
    guide = page.get_by_role("heading", name=text("process:title"), exact=True).first
    smooth_scroll(page, int(guide.evaluate("e => e.getBoundingClientRect().top + window.scrollY - 110")))
    pause(page, 3500)

    nav(page, "funnel")
    page.get_by_role("heading", level=1).first.wait_for(timeout=30_000)
    say(page, "results")
    pause(page, 3500)
    nav(page, "home")
    say(page, "end")
    pause(page, 3500)
    CUES.append((time.monotonic() - CLOCK["start"], ""))


TERMINAL = """<!doctype html><meta charset="utf-8"><style>
body{{margin:0;height:100vh;display:grid;place-items:center;background:#e9eef0;font:16px Consolas,monospace}}
.win{{width:1100px;border-radius:12px;overflow:hidden;box-shadow:0 20px 60px #0003;background:#0c1416}}
.bar{{height:36px;background:#1d2a2d;color:#9fb3b6;display:flex;align-items:center;padding:0 14px;font:13px system-ui}}
pre{{margin:0;padding:22px 26px;min-height:420px;color:#d7f2ee;white-space:pre-wrap}}
.p{{color:#5eead4}}
</style><div class="win"><div class="bar">PowerShell — backend</div><pre id="t"></pre></div>
<script>
const lines = {lines};
const t = document.getElementById('t');
async function run() {{
  const cmd = '{command}';
  t.innerHTML = '<span class="p">PS&gt;</span> ';
  for (const ch of cmd) {{ t.innerHTML += ch; await new Promise(r => setTimeout(r, 55)); }}
  await new Promise(r => setTimeout(r, 600));
  for (const line of lines) {{ t.innerHTML += '\\n' + line; await new Promise(r => setTimeout(r, 700)); }}
  document.title = 'done';
}}
run();
</script>"""


def scene_start(page: Page) -> None:
    log = Path(START_LOG).read_text(encoding="utf-8").splitlines()
    lines = [html.escape(line) for line in log if line]
    page.set_content(TERMINAL.format(lines=lines, command="uv run cai start"))
    caption(page, 0)
    page.wait_for_function("document.title === 'done'", timeout=30_000)
    pause(page, 1200)
    goto(page, "/", 2500, base=START_URL)
    caption(page, 0)
    pause(page, 1500)


# --- El botón del navegador --------------------------------------------------------------------

STAGE = "http://stage.local"
# Lo que `prepare_extension` saca de la oferta de LinkedIn antes de grabar.
POSTING: dict[str, str] = {}
CHROME_H = 88  # alto de las pestañas y la barra de direcciones dibujadas

STAGE_HTML = """<!doctype html><meta charset="utf-8"><style>
*{{box-sizing:border-box}}
body{{margin:0;height:100vh;overflow:hidden;background:#dee3e7;font:14px system-ui,sans-serif}}
.tabs{{height:40px;display:flex;align-items:flex-end;gap:2px;padding:0 10px}}
.tab{{height:32px;width:250px;display:flex;align-items:center;gap:8px;padding:0 12px;
  border-radius:10px 10px 0 0;color:#3c4043;white-space:nowrap;overflow:hidden;font-size:13px}}
.tab.on{{background:#fff}}
.tab img{{width:16px;height:16px}}
.bar{{height:48px;background:#fff;display:flex;align-items:center;gap:12px;padding:0 14px;
  border-bottom:1px solid #d6dadd}}
.url{{flex:1;height:34px;border-radius:17px;background:#f1f3f4;display:flex;align-items:center;
  padding:0 16px;color:#3c4043;overflow:hidden;white-space:nowrap}}
.ext{{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;
  transition:background .2s}}
.ext.hot{{background:#e3e7ea}}
.ext img{{width:20px;height:20px}}
.view{{position:absolute;top:{chrome}px;left:0;right:0;bottom:0;background:#fff;overflow:hidden}}
.view img{{width:100%;display:block}}
.view iframe{{width:100%;height:100%;border:0}}
.popup{{position:absolute;top:{popup_top}px;right:14px;width:340px;height:230px;border:0;
  border-radius:8px;box-shadow:0 10px 30px #0004;background:#fff;display:none}}
.popup.on{{display:block}}
.cursor{{position:absolute;left:900px;top:520px;width:26px;z-index:9;
  transition:left .9s ease,top .9s ease,transform .12s}}
.cursor.down{{transform:scale(.85)}}
</style>
<div class="tabs">
  <div class="tab on" id="tab-job"><img src="{favicon}" alt="">{tab_title}</div>
  <div class="tab" id="tab-app"><img src="{icon}" alt="">CandidatAI</div>
</div>
<div class="bar"><div class="url" id="url">{url}</div>
  <div class="ext" id="ext"><img src="{icon}" alt=""></div></div>
<div class="view" id="view"><img src="{shot}" alt=""></div>
<iframe class="popup" id="popup"></iframe>
<svg class="cursor" id="cursor" viewBox="0 0 24 24"><path d="M3 2l7 19 2.6-7.4L20 11z"
  fill="#111" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/></svg>
"""

# En el popup, el `chrome` que espera `popup.js`: responde con la oferta ya dada de alta.
POPUP_STUB = """(() => {
  if (location.origin !== '%s' || !location.pathname.endsWith('/popup.html')) return;
  const outcome = %s;
  window.chrome = {
    tabs: { query: (_q, cb) => cb([{ id: 1 }]), create: () => {} },
    runtime: {
      sendMessage: (_m, cb) => setTimeout(() => cb(outcome), 700),
      openOptionsPage: () => {},
    },
  };
})()"""


def data_uri(path: Path, kind: str) -> str:
    return f"data:{kind};base64," + base64.b64encode(path.read_bytes()).decode()


def api_post(path: str, body: dict[str, object]) -> dict[str, object]:
    request = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


def prepare_extension(page: Page) -> None:
    """Captura la oferta de LinkedIn (sin sesión ni avisos encima) y la da de alta en la demo."""
    assert LINKEDIN_URL, "LINKEDIN_URL: la URL de una oferta pública de LinkedIn"
    page.set_viewport_size({"width": SIZE["width"], "height": SIZE["height"] - CHROME_H})
    # LinkedIn no deja nunca la red en reposo (`networkidle` no llega): se espera al título.
    page.goto(LINKEDIN_URL, wait_until="domcontentloaded", timeout=45_000)
    page.locator("h1").first.wait_for(timeout=20_000)
    pause(page, 2500)
    # Las cookies (rechazadas) y el aviso de iniciar sesión, fuera de la captura.
    for name in ("Rechazar", "Reject"):
        button = page.get_by_role("button", name=name)
        if button.count():
            button.first.click()
            break
    page.keyboard.press("Escape")
    page.evaluate(
        "() => document.querySelectorAll("
        "'.modal__overlay, .contextual-sign-in-modal, [role=dialog]').forEach(e => e.remove())"
    )
    # Ni fotos ni nombres de personas reales: fuera «Descubre a quién ha contratado…» y cualquier
    # bloque con caras (la animación se publica en el repositorio).
    page.evaluate(
        """() => {
          const faces = document.querySelectorAll('[class*="face-pile"], [class*="facepile"]');
          faces.forEach(e => (e.closest('a, div') || e).remove());
          for (const e of document.querySelectorAll('a, div, p, span')) {
            const text = (e.textContent || '').trim();
            if (/^(Descubre a quién|See who|Discover who)/.test(text) && text.length < 160) {
              (e.closest('a') || e).remove();
            }
          }
        }"""
    )
    pause(page, 600)
    title = page.locator("h1").first.inner_text().strip()
    company = page.locator(".topcard__org-name-link, .topcard__flavor").first.inner_text().strip()
    description = page.locator(".description__text, .show-more-less-html").first.inner_text()
    shot = Path(tempfile.mkdtemp(prefix="cai-li-")) / "posting.png"
    page.screenshot(path=str(shot))
    added = api_post(
        "/jobs/text",
        {"title": title, "company": company, "text": description.strip(), "url": LINKEDIN_URL},
    )
    POSTING.update(
        title=title,
        company=company,
        shot=str(shot),
        job_id=str(added["job_id"]),
        page_title=page.title(),
    )


def move_cursor(page: Page, x: float, y: float, ms: int = 950) -> None:
    page.evaluate(
        "([x, y]) => { const c = document.getElementById('cursor');"
        " c.style.left = x + 'px'; c.style.top = y + 'px' }",
        [x, y],
    )
    pause(page, ms)


def click_cursor(page: Page) -> None:
    page.evaluate("() => document.getElementById('cursor').classList.add('down')")
    pause(page, 140)
    page.evaluate("() => document.getElementById('cursor').classList.remove('down')")


def serve_stage(route: Route) -> None:
    """El escenario y, para el popup, los ficheros de la extensión tal cual."""
    path = route.request.url.removeprefix(STAGE + "/")
    if path != "stage":
        route.fulfill(path=str(EXTENSION / path))
        return
    body = STAGE_HTML.format(
        chrome=CHROME_H,
        popup_top=CHROME_H - 6,
        icon=data_uri(EXTENSION / "icons" / "icon32.png", "image/png"),
        favicon=data_uri(EXTENSION / "icons" / "icon16.png", "image/png"),
        tab_title=html.escape(POSTING["page_title"][:40]),
        url=html.escape(LINKEDIN_URL),
        shot=data_uri(Path(POSTING["shot"]), "image/png"),
    )
    route.fulfill(body=body, content_type="text/html")


def scene_extension(page: Page) -> None:
    outcome = {
        "ok": True,
        "kind": "new",
        "label": "Nueva",
        "title": POSTING["title"],
        "company": POSTING["company"],
        "jobUrl": f"{UI}/jobs/{POSTING['job_id']}",
    }
    page.context.add_init_script(POPUP_STUB % (STAGE, json.dumps(outcome)))
    page.route(f"{STAGE}/**", serve_stage)
    page.goto(f"{STAGE}/stage")
    pause(page, 1300)
    caption(page, 0)
    pause(page, 700)
    ext = page.locator("#ext").bounding_box()
    assert ext is not None
    move_cursor(page, ext["x"] + ext["width"] / 2 - 4, ext["y"] + ext["height"] / 2 - 2)
    page.evaluate("() => document.getElementById('ext').classList.add('hot')")
    click_cursor(page)
    page.evaluate(
        "src => { const p = document.getElementById('popup'); p.src = src; p.classList.add('on') }",
        f"{STAGE}/popup.html",
    )
    caption(page, 1)
    page.frame_locator("#popup").locator(".status").wait_for(timeout=10_000)
    pause(page, 1500)
    page.screenshot(path=str(OUT / "extension-still.png"))
    # A la pestaña de CandidatAI: la Bandeja, con la oferta recién llegada resaltada.
    page.evaluate(
        "url => { document.getElementById('popup').classList.remove('on');"
        " document.getElementById('ext').classList.remove('hot');"
        " document.getElementById('tab-job').classList.remove('on');"
        " document.getElementById('tab-app').classList.add('on');"
        " document.getElementById('url').textContent = url;"
        " document.getElementById('view').innerHTML = `<iframe src='${url}'></iframe>` }",
        f"{UI}/bandeja",
    )
    caption(page, 2)
    row = page.frame_locator("#view iframe").get_by_text(POSTING["title"]).first
    row.wait_for(timeout=15_000)
    row.evaluate(
        "e => { const r = e.closest('li, tr, article') || e;"
        " r.style.outline = '3px solid #0f766e'; r.style.outlineOffset = '3px';"
        " r.style.borderRadius = '10px' }"
    )
    box = row.bounding_box()
    if box:
        move_cursor(page, box["x"] + 40, box["y"] + box["height"] / 2, 700)
    pause(page, 1600)


def still_to_webp(png: Path, target: Path, width: int) -> None:
    """El fotograma fijo para quien prefiere menos movimiento."""
    subprocess.run(
        [
            ffmpeg(), "-y", "-loglevel", "error", "-i", str(png),
            "-vf", f"scale={width}:-1:flags=lanczos", "-c:v", "libwebp", "-q:v", "75", str(target),
        ],
        check=True,
    )
    png.unlink()


def ffmpeg() -> str:
    if os.environ.get("FFMPEG"):
        return os.environ["FFMPEG"]
    try:
        import imageio_ffmpeg  # noqa: PLC0415

        return str(imageio_ffmpeg.get_ffmpeg_exe())
    except ImportError:
        found = shutil.which("ffmpeg")
        assert found, "Hace falta ffmpeg: FFMPEG, `--with imageio-ffmpeg` o en el PATH."
        return found


def to_webp(webm: Path, target: Path, width: int, fps: int, quality: int) -> None:
    """El `.webm` a WebP animado: sin el primer fotograma en blanco, en bucle y, si la escena está
    en `SPEED`, acelerado.

    `mpdecimate` quita los fotogramas repetidos (las pausas), que es lo que más pesa.
    """
    speed = SPEED.get(SCENE, 1)
    faster = f"setpts=PTS/{speed}," if speed != 1 else ""
    subprocess.run(
        [
            ffmpeg(), "-y", "-loglevel", "error", "-ss", str(TRIM), "-i", str(webm),
            "-vf", f"{faster}fps={fps},scale={width}:-1:flags=lanczos,mpdecimate", "-fps_mode", "vfr",
            "-c:v", "libwebp_anim", "-lossless", "0", "-q:v", str(quality),
            "-compression_level", "6", "-loop", "0", str(target),
        ],
        check=True,
    )


def stamp(seconds: float, sep: str) -> str:
    """Un instante de subtítulo: `00:01:02,500` (SRT) o `00:01:02.500` (VTT)."""
    ms = max(0, round(seconds * 1000))
    hours, ms = divmod(ms, 3_600_000)
    minutes, ms = divmod(ms, 60_000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{sep}{ms:03d}"


def subtitles(cues: list[tuple[float, str]], vtt: bool) -> str:
    """Los subtítulos con el tiempo del vídeo ya recortado: cada uno, hasta que sale el siguiente."""
    sep = "." if vtt else ","
    blocks = ["WEBVTT\n"] if vtt else []
    shown = [(start - TRIM, line) for start, line in cues]
    for n, ((start, line), (end, _next)) in enumerate(zip(shown, shown[1:]), 1):
        if not line:
            continue
        timing = f"{stamp(start, sep)} --> {stamp(end, sep)}"
        blocks.append(f"{timing}\n{line}\n" if vtt else f"{n}\n{timing}\n{line}\n")
    return "\n".join(blocks)


TRANSCRIPT_TITLE = {
    "es": "CandidatAI · Recorrido en vídeo (transcripción)",
    "en": "CandidatAI · Video tour (transcript)",
}
TRANSCRIPT_NOTE = {
    "es": "Datos de la demo, inventados. El trabajo del agente de IA ya viene hecho en ella; con un"
    " agente real tarda de segundos a minutos. El vídeo no tiene sonido: todo está en los"
    " subtítulos.",
    "en": "Demo data, made up. The AI agent's work is already done in it; with a real agent it"
    " takes from seconds to minutes. The video has no sound: everything is in the subtitles.",
}


def to_video(webm: Path) -> None:
    """El `.webm` a MP4 (H.264, 1080p), sus subtítulos, la transcripción y el clip cuadrado."""
    name = f"candidatai-tour-{LANG}"
    mp4 = OUT / f"{name}.mp4"
    subprocess.run(
        [
            ffmpeg(), "-y", "-loglevel", "error", "-ss", str(TRIM), "-i", str(webm),
            "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-an", str(mp4),
        ],
        check=True,
    )
    (OUT / f"{name}.srt").write_text(subtitles(CUES, vtt=False), encoding="utf-8")
    (OUT / f"{name}.vtt").write_text(subtitles(CUES, vtt=True), encoding="utf-8")
    lines = [line for _start, line in CUES if line]
    notes = [TRANSCRIPT_TITLE[LANG], "", TRANSCRIPT_NOTE[LANG], ""]
    transcript = [*notes, *(f"- {line}" for line in lines)]
    (OUT / f"{name}.txt").write_text("\n".join(transcript) + "\n", encoding="utf-8")
    # El clip para redes: la revisión de ofertas y el CV, en cuadrado sobre el color de la marca.
    clip = OUT / f"candidatai-clip-{LANG}.mp4"
    subprocess.run(
        [
            ffmpeg(), "-y", "-loglevel", "error", "-ss", f"{CLOCK['clip'] - TRIM:.2f}",
            "-t", str(CLIP_SECONDS), "-i", str(mp4),
            "-vf", f"scale={CLIP_SIDE}:-2:flags=lanczos,"
            f"pad={CLIP_SIDE}:{CLIP_SIDE}:0:(oh-ih)/2:color=0x0F766E",
            "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", "-an", str(clip),
        ],
        check=True,
    )
    duration = CUES[-1][0] - TRIM
    for path in (mp4, clip):
        print("ok", path, f"{path.stat().st_size // 1024} KB")
    print(f"duración del vídeo: {duration:.0f} s (60-90 s)")
    if not 60 <= duration <= 90:
        print("AVISO: el vídeo no dura entre 60 y 90 s; ajusta las pausas de `scene_video`.")


SCENES = {
    "triage": scene_triage,
    "discard": scene_discard,
    "mailbox": scene_mailbox,
    "cv": scene_cv,
    "profile": scene_profile,
    "apply": scene_apply,
    "start": scene_start,
    "tour": scene_tour,
    "extension": scene_extension,
    "video": scene_video,
}
# Lo que se prepara antes de grabar, sin vídeo.
def warm_up(page: Page) -> None:
    """Antes de grabar el tour o el vídeo: la candidatura rellenada y la revisión ya abierta una vez
    (la primera vez carga el modelo de similitud y tarda casi un minuto)."""
    prepare_application(page)
    warm_triage(page)


def warm_triage(page: Page) -> None:
    """La revisión abierta una vez sin grabar: la primera carga el modelo de similitud."""
    page.goto(UI + "/bandeja/revision", timeout=90_000)
    page.locator("[role=option][aria-selected=true]").first.wait_for(timeout=180_000)


SETUP = {
    "tour": warm_up,
    "video": warm_up,
    "triage": warm_triage,
    "extension": prepare_extension,
}


def new_context(browser: Browser, video_dir: Path | None) -> BrowserContext:
    size = VIDEO_SIZE if SCENE == "video" else SIZE
    ctx = browser.new_context(
        viewport=size,
        locale="en-GB" if LANG == "en" else "es-ES",
        record_video_dir=str(video_dir) if video_dir else None,
        record_video_size=size if video_dir else None,
    )
    ctx.add_init_script(
        f"try {{ localStorage.setItem('cai-language', '{LANG}');"
        " localStorage.setItem('cai-theme', 'light') } catch {}"
    )
    ctx.add_init_script(f"({HIDE_DEMO_JS})({json.dumps(text('nav:demo.label'))})")
    return ctx


def main() -> None:
    raw = Path(tempfile.mkdtemp(prefix="cai-rec-"))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        if SCENE in SETUP:
            ctx = new_context(browser, None)
            SETUP[SCENE](ctx.new_page())
            ctx.close()
        ctx = new_context(browser, raw)
        page = ctx.new_page()
        CLOCK["start"] = time.monotonic()
        SCENES[SCENE](page)
        video = page.video
        ctx.close()
        assert video is not None
        webm = raw / f"{SCENE}.webm"
        shutil.move(video.path(), webm)
        browser.close()
    if SCENE == "video":
        to_video(webm)
        return
    target = OUT / f"{SCENE}.webp"
    to_webp(webm, target, *SHARP.get(SCENE, (WIDTH, FPS, QUALITY)))
    print("ok", target, f"{target.stat().st_size // 1024} KB", "· webm:", webm)
    if SCENE == "tour" and target.stat().st_size > TOUR_MAX:
        print("AVISO: tour.webp pasa de 1,5 MB; baja la calidad o los fotogramas en `SHARP`.")
    still = OUT / f"{SCENE}-still.png"
    if still.exists():
        width = SHARP.get(SCENE, (WIDTH, FPS, QUALITY))[0]
        still_to_webp(still, OUT / f"{SCENE}-still.webp", width)


main()
