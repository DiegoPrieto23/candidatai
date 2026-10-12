"""Grabaciones de la demo para el README (webm de Playwright; luego ffmpeg a MP4 y GIF).

Uso: python record.py OUT_DIR escena   (escenas: tour, cv, triage, shots)
UI en 5181 y API en 8010; la app real sigue en 5173/8000 sin tocarse.
"""

import shutil
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

UI = "http://127.0.0.1:5181"
API = "http://127.0.0.1:8010"
OUT = Path(sys.argv[1])
SCENE = sys.argv[2]
THEME = sys.argv[3] if len(sys.argv) > 3 else "light"
CV_JOB = 1
SIZE = {"width": 1600, "height": 1000}
OUT.mkdir(parents=True, exist_ok=True)


def pause(page: Page, ms: int) -> None:
    page.wait_for_timeout(ms)


def smooth_scroll(page: Page, to: int, steps: int = 25) -> None:
    start = page.evaluate("window.scrollY")
    for i in range(1, steps + 1):
        page.evaluate(f"window.scrollTo(0, {start + (to - start) * i / steps})")
        pause(page, 40)


def goto(page: Page, path: str, wait: int = 1800) -> None:
    page.goto(UI + path)
    page.wait_for_load_state("networkidle")
    pause(page, wait)


def scene_cv(page: Page) -> None:
    goto(page, f"/jobs/{CV_JOB}", 1200)
    section = page.locator("#cv")
    top = section.evaluate("e => e.getBoundingClientRect().top + window.scrollY - 150")
    smooth_scroll(page, int(top))
    pause(page, 1500)
    form = page.get_by_role("form", name="Renderizar el CV")
    form.get_by_text("Moderna a dos columnas").click()
    pause(page, 900)
    form.locator("input[name=accent]").nth(1).check(force=True)
    pause(page, 900)
    form.get_by_role("button", name="Renderizar").click()
    page.get_by_role("button", name="Renderizar").wait_for(timeout=120_000)
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
    goto(page, "/plataformas", 2500)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-web-security"])
        ctx = browser.new_context(
            viewport=SIZE,
            color_scheme=THEME,
            locale="es-ES",
            record_video_dir=str(OUT / "raw"),
            record_video_size=SIZE,
        )
        ctx.route(
            f"{API}/**",
            lambda route: route.continue_(
                headers={**route.request.headers, "origin": "http://127.0.0.1:5173"}
            ),
        )
        page = ctx.new_page()
        {"tour": scene_tour, "cv": scene_cv, "triage": scene_triage}[SCENE](page)
        video = page.video
        ctx.close()
        browser.close()
        assert video is not None
        shutil.move(video.path(), OUT / f"{SCENE}.webm")
        print("ok", OUT / f"{SCENE}.webm")


main()
