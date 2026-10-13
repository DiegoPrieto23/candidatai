"""Iconos de CandidatAI: monograma «CA» blanco sobre un cuadrado redondeado oscuro, con el punto
verde azulado de la marca. Genera los PNG de la extensión, el favicon SVG de la UI y el icono de
Windows (`frontend/public/candidatai.ico`, el del acceso directo del instalador; fase 23.4).

Provisional: la fase 23.5 lo sustituye por el logo de `docs/brand/`.

Uso (desde backend/, que trae Pillow): uv run python ../scripts/build_icons.py
La fuente es Segoe UI Bold (Windows); en otro sistema, pasa otra con --font.
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BG = (24, 24, 27, 255)  # zinc-900, como el monograma de la UI
FG = (255, 255, 255, 255)
DOT = (45, 212, 191, 255)  # verde azulado de la marca
SCALE = 8  # se dibuja a 8x y se reduce: bordes suaves también a 16 px


def icon(size: int, font_path: str) -> Image.Image:
    big = size * SCALE
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=int(big * 0.22), fill=BG)
    font = ImageFont.truetype(font_path, int(big * 0.44))
    box = draw.textbbox((0, 0), "CA", font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    draw.text(((big - w) / 2 - box[0], (big - h) / 2 - box[1] - big * 0.02), "CA", font=font, fill=FG)
    r = big * 0.11
    cx, cy = big * 0.80, big * 0.80
    if size >= 32:  # a 16 px el punto ensucia más que aporta
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=DOT)
    return img.resize((size, size), Image.Resampling.LANCZOS)


FAVICON = """<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#18181B"/>
  <text x="31" y="41.5" text-anchor="middle" font-family="'Segoe UI', 'Helvetica Neue', Arial, sans-serif"
    font-size="27" font-weight="800" fill="#FFFFFF" letter-spacing="-0.5">CA</text>
  <circle cx="51" cy="51" r="7" fill="#2DD4BF"/>
</svg>
"""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--font", default=r"C:\Windows\Fonts\segoeuib.ttf")
    args = parser.parse_args()
    for size in (16, 32, 48, 128):
        icon(size, args.font).save(ROOT / "extension" / "icons" / f"icon{size}.png")
    (ROOT / "frontend" / "public" / "favicon.svg").write_text(FAVICON, encoding="utf-8")
    sizes = [16, 24, 32, 48, 64, 128, 256]
    big = icon(256, args.font)
    big.save(
        ROOT / "frontend" / "public" / "candidatai.ico",
        sizes=[(n, n) for n in sizes],
        append_images=[icon(n, args.font) for n in sizes[:-1]],
    )
    print("ok")


if __name__ == "__main__":
    main()
