"""Iconos de CandidatAI a partir de `docs/brand/mark.svg` (fase 23.5a).

Genera los PNG de la extensión (16, 32, 48 y 128 px), el favicon SVG y el `apple-touch-icon` de la
UI, y los iconos de los accesos directos de los instaladores: el de Windows
(`frontend/public/candidatai.ico`) y, desde la fase 26.2, el PNG del `.desktop` de Linux
(`candidatai.png`) y el `.icns` de la `.app` de macOS (`candidatai.icns`, con Pillow, sin
herramientas de Apple).
El SVG se rasteriza con el Chromium de Playwright, que el backend ya trae.

Uso (desde backend/): uv run python ../scripts/build_icons.py
"""

import io
import shutil
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
MARK = ROOT / "docs" / "brand" / "mark.svg"
PUBLIC = ROOT / "frontend" / "public"
EXTENSION_SIZES = (16, 32, 48, 128)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
PNG_SIZE = 512  # el del `.desktop` de Linux
ICNS_SIZE = 1024  # Pillow saca del grande los tamaños del `.icns`


def render(svg: str, size: int, page) -> Image.Image:  # type: ignore[no-untyped-def]
    """El SVG a `size` px, con fondo transparente (se dibuja a 4x y se reduce: bordes suaves)."""
    big = size * 4
    page.set_viewport_size({"width": big, "height": big})
    page.set_content(
        f'<html><body style="margin:0;background:transparent">'
        f'<div style="width:{big}px;height:{big}px">{svg}</div></body></html>'
    )
    page.locator("svg").evaluate("e => { e.style.width = '100%'; e.style.height = '100%' }")
    png = page.screenshot(omit_background=True, clip={"x": 0, "y": 0, "width": big, "height": big})
    return Image.open(io.BytesIO(png)).convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    svg = MARK.read_text(encoding="utf-8")
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for size in EXTENSION_SIZES:
            render(svg, size, page).save(ROOT / "extension" / "icons" / f"icon{size}.png")
        render(svg, 180, page).save(PUBLIC / "apple-touch-icon.png")
        ico = [render(svg, n, page) for n in ICO_SIZES]
        render(svg, PNG_SIZE, page).save(PUBLIC / "candidatai.png")
        render(svg, ICNS_SIZE, page).save(PUBLIC / "candidatai.icns")
        browser.close()
    ico[-1].save(PUBLIC / "candidatai.ico", sizes=[(n, n) for n in ICO_SIZES], append_images=ico[:-1])
    shutil.copyfile(MARK, PUBLIC / "favicon.svg")
    print("ok")


if __name__ == "__main__":
    main()
