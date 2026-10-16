"""Grabaciones de la demo para el README (webm de Playwright; luego ffmpeg a MP4 y GIF).

Uso (desde backend/): python recordings.py OUT_DIR ESCENA IDIOMA [TEMA]
  ESCENA: tour, cv, triage o start. IDIOMA: en o es (la UI se abre en ese idioma).
UI en 5181 y API en 8010; la app real sigue en 5173/8000 sin tocarse.

`start` es distinto: reproduce en un terminal la salida real de `cai start` (la que el script
lee de START_LOG) y después abre la app que sirve ese mismo `cai start` en START_URL (otro
puerto, con la UI compilada). Los selectores no dependen del idioma de la UI.
"""

import html
import os
import shutil
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

UI = "http://127.0.0.1:5181"
API = "http://127.0.0.1:8010"
START_URL = os.environ.get("START_URL", "http://127.0.0.1:8020")
START_LOG = os.environ.get("START_LOG", "")
OUT = Path(sys.argv[1])
SCENE = sys.argv[2]
LANG = sys.argv[3]
THEME = sys.argv[4] if len(sys.argv) > 4 else "light"
CV_JOB = 1
SIZE = {"width": 1600, "height": 1000}
OUT.mkdir(parents=True, exist_ok=True)
assert LANG in ("en", "es"), "IDIOMA: en o es"


def pause(page: Page, ms: int) -> None:
    page.wait_for_timeout(ms)


def smooth_scroll(page: Page, to: int, steps: int = 25) -> None:
    start = page.evaluate("window.scrollY")
    for i in range(1, steps + 1):
        page.evaluate(f"window.scrollTo(0, {start + (to - start) * i / steps})")
        pause(page, 40)


def goto(page: Page, path: str, wait: int = 1800, base: str = UI) -> None:
    page.goto(base + path)
    page.wait_for_load_state("networkidle")
    pause(page, wait)


def scene_cv(page: Page) -> None:
    goto(page, f"/jobs/{CV_JOB}", 1200)
    section = page.locator("#cv")
    top = section.evaluate("e => e.getBoundingClientRect().top + window.scrollY - 150")
    smooth_scroll(page, int(top))
    pause(page, 1500)
    form = section.locator("form:has(input[name=template])")
    form.locator("label:has(input[value='moderna-2col'])").click()
    pause(page, 900)
    form.locator("input[name=accent]").nth(1).check(force=True)
    pause(page, 900)
    submit = form.locator("button[type=submit]")
    submit.click()
    page.wait_for_function(
        "() => !document.querySelector('#cv form button[type=submit]').disabled", timeout=120_000
    )
    pause(page, 1500)
    smooth_scroll(page, int(top) + 650)
    pause(page, 2500)


def scene_triage(page: Page) -> None:
    goto(page, "/por-revisar", 2000)
    for key in ("j", "j", "k"):
        page.keyboard.press(key)
        pause(page, 1300)
    page.keyboard.press("a")
    pause(page, 2200)
    page.keyboard.press("j")
    pause(page, 1500)


def scene_tour(page: Page) -> None:
    goto(page, "/", 2500)
    smooth_scroll(page, 700)
    pause(page, 1200)
    goto(page, "/bandeja", 2200)
    goto(page, "/por-revisar", 1800)
    for key in ("j", "j", "k"):
        page.keyboard.press(key)
        pause(page, 1100)
    goto(page, f"/jobs/{CV_JOB}", 1500)
    smooth_scroll(page, 900)
    pause(page, 800)
    top = page.locator("#cv").evaluate("e => e.getBoundingClientRect().top + window.scrollY - 150")
    smooth_scroll(page, int(top))
    pause(page, 2500)
    goto(page, "/procesos", 2500)
    goto(page, "/embudo", 1800)
    smooth_scroll(page, 900)
    pause(page, 1200)
    smooth_scroll(page, 1800)
    pause(page, 1500)
    goto(page, "/plantillas", 2500)
    goto(page, "/fuentes/plataformas", 2500)


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
  for (const line of lines) {{ t.innerHTML += '\\n' + line; await new Promise(r => setTimeout(r, 900)); }}
  document.title = 'done';
}}
run();
</script>"""


def scene_start(page: Page) -> None:
    lines = [html.escape(line) for line in Path(START_LOG).read_text(encoding="utf-8").splitlines() if line]
    page.set_content(TERMINAL.format(lines=lines, command="uv run cai start"))
    page.wait_for_function("document.title === 'done'", timeout=30_000)
    pause(page, 1500)
    goto(page, "/", 3000, base=START_URL)
    smooth_scroll(page, 500)
    pause(page, 1500)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-web-security"])
        ctx = browser.new_context(
            viewport=SIZE,
            color_scheme=THEME,
            locale="en-GB" if LANG == "en" else "es-ES",
            record_video_dir=str(OUT / "raw"),
            record_video_size=SIZE,
        )
        ctx.add_init_script(f"try {{ localStorage.setItem('cai-language', '{LANG}') }} catch {{}}")
        ctx.route(
            f"{API}/**",
            lambda route: route.continue_(
                headers={**route.request.headers, "origin": "http://127.0.0.1:5173"}
            ),
        )
        page = ctx.new_page()
        {"tour": scene_tour, "cv": scene_cv, "triage": scene_triage, "start": scene_start}[SCENE](page)
        video = page.video
        ctx.close()
        browser.close()
        assert video is not None
        target = OUT / f"{SCENE}-{LANG}.webm"
        shutil.move(video.path(), target)
        print("ok", target)


main()
