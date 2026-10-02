"""`jh templates compare`: el original y la recreación lado a lado, con una métrica de parecido.

La preview usa el perfil demo y el original tiene el texto de su dueño: la SSIM (similitud
estructural, 0-1, sobre la página en grises, desenfocada y a baja resolución, donde pesan la
disposición, los bloques de color y los márgenes más que las letras) es solo una orientación para
iterar: sirve para ver si un cambio acerca o aleja, no como nota absoluta. Con diseños distintos
da 0,4-0,65; una buena recreación, por encima.
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
from pydantic import BaseModel

from app.core.config import REPO_ROOT, get_settings
from app.services.documents.importer import TemplateImportError, visual

SSIM_WIDTH = 300  # px: a esta escala cuenta la maqueta, no la letra
SIDE_HEIGHT = 1100  # px de cada mitad del PNG lado a lado
GAP = 24
LABEL_HEIGHT = 36


class CompareResult(BaseModel):
    template_id: str
    source: str
    image_path: str  # relativa a data/
    preview_path: str
    ssim: float
    note: str


def _box_mean(values: np.ndarray, size: int) -> np.ndarray:
    """Media en ventanas `size`×`size` (imagen integral), sin bordes."""
    integral = np.pad(values, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    total = (
        integral[size:, size:]
        - integral[:-size, size:]
        - integral[size:, :-size]
        + integral[:-size, :-size]
    )
    return total / (size * size)


def ssim(a: Image.Image, b: Image.Image, width: int = SSIM_WIDTH, window: int = 7) -> float:
    """SSIM media entre dos imágenes, en grises y al tamaño de `a` reducido a `width` px."""
    height = max(round(width * a.height / a.width), window)

    def prepare(image: Image.Image) -> np.ndarray:
        # Un desenfoque ligero antes de reducir: cuentan los bloques, no cada letra.
        gray = ImageOps.grayscale(image).filter(ImageFilter.GaussianBlur(2 * image.width / width))
        return np.asarray(gray.resize((width, height)), dtype=np.float64)

    x, y = prepare(a), prepare(b)
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    mx, my = _box_mean(x, window), _box_mean(y, window)
    sxx = _box_mean(x * x, window) - mx * mx
    syy = _box_mean(y * y, window) - my * my
    sxy = _box_mean(x * y, window) - mx * my
    index = ((2 * mx * my + c1) * (2 * sxy + c2)) / ((mx * mx + my * my + c1) * (sxx + syy + c2))
    return float(np.clip(index.mean(), -1.0, 1.0))


def _fit(image: Image.Image, height: int) -> Image.Image:
    width = round(image.width * height / image.height)
    return image.convert("RGB").resize((width, height))


LABEL_FONT = REPO_ROOT / "templates" / "moderna-2col" / "fonts" / "Lato-Bold-latin.woff2"


def _label_font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Lato de `moderna-2col` (la de Pillow por defecto no tiene tildes)."""
    try:
        return ImageFont.truetype(str(LABEL_FONT), 18)
    except OSError:
        return ImageFont.load_default(size=18)


def side_by_side(original: Image.Image, recreation: Image.Image, output: Path) -> Path:
    left, right = _fit(original, SIDE_HEIGHT), _fit(recreation, SIDE_HEIGHT)
    canvas = Image.new(
        "RGB", (left.width + right.width + GAP * 3, SIDE_HEIGHT + LABEL_HEIGHT + GAP), "#E5E7EB"
    )
    canvas.paste(left, (GAP, LABEL_HEIGHT))
    canvas.paste(right, (GAP * 2 + left.width, LABEL_HEIGHT))
    draw = ImageDraw.Draw(canvas)
    font = _label_font()
    draw.text((GAP, 8), "Original", fill="#111827", font=font)
    draw.text((GAP * 2 + left.width, 8), "Recreación (perfil demo)", fill="#111827", font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, format="PNG", optimize=True)
    return output


def compare(template_id: str, source: Path) -> CompareResult:
    from app.services.documents import authoring

    if not visual.is_visual(source):
        raise TemplateImportError(
            f"`compare` es para plantillas recreadas desde PDF, imagen o HTML; {source.name} es "
            "Word (la plantilla docx conserva el diseño original)."
        )
    settings = get_settings()
    out_dir = settings.tmp_dir / "compare" / template_id
    out_dir.mkdir(parents=True, exist_ok=True)
    _kind, pages, _pdf = visual.source_pages_png(source, out_dir)
    preview = authoring.preview_template(None, template_id, "demo")
    with Image.open(pages[0]) as original, Image.open(settings.data_dir / preview.png_path) as rec:
        score = ssim(original, rec)
        image = side_by_side(original, rec, out_dir / "comparacion.png")
    return CompareResult(
        template_id=template_id,
        source=str(source),
        image_path=image.relative_to(settings.data_dir).as_posix(),
        preview_path=preview.png_path,
        ssim=round(score, 3),
        note=(
            "Orientativa: la recreación usa el perfil demo y el original su propio texto. Mira "
            "la imagen y compara disposición, colores, márgenes y jerarquía, no el texto."
        ),
    )
