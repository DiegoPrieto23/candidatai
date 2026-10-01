"""Foto del CV: busca la foto del candidato y la recorta a la forma y tamaño de la plantilla.

- Fuente: `preferences.cv.photo_file` (relativa a `data/`); si ese fichero no existe, el primer
  `data/photo.*` (jpg, jpeg, png, webp; heic solo si Pillow lo abre).
- Recorte centrado a un cuadrado, respetando la orientación EXIF, y máscara según `photo.shape`:
  círculo y esquinas redondeadas con fondo transparente (PNG con alfa), cuadrado sin alfa.
- Caché en `data/cache/photo/`, por hash de la foto, forma y tamaño: renderizar diez veces el
  mismo CV no recorta la foto diez veces.
"""

import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

from app.core.config import get_settings
from app.schemas.cv import PhotoShape
from app.schemas.profile import CandidateProfile

PHOTO_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".heic")
DPI = 300
# Supermuestreo de la máscara para que el borde del círculo no salga dentado.
_MASK_SCALE = 4
# Radio de las esquinas redondeadas, en proporción al lado.
ROUNDED_RADIUS = 0.12


class PhotoError(ValueError):
    pass


def _inside(path: Path, root: Path) -> bool:
    return path.resolve().is_relative_to(root.resolve())


def _opens(path: Path) -> bool:
    try:
        with Image.open(path) as img:
            img.verify()
    except (OSError, UnidentifiedImageError):
        return False
    return True


def find_photo(profile: CandidateProfile, data_dir: Path | None = None) -> Path | None:
    """La foto del candidato dentro de `data/`, o `None` si no hay ninguna que se pueda abrir."""
    data_dir = data_dir or get_settings().data_dir
    configured = data_dir / profile.preferences.cv.photo_file
    if configured.is_file() and _inside(configured, data_dir) and _opens(configured):
        return configured
    if not data_dir.is_dir():
        return None
    candidates = sorted(
        p
        for p in data_dir.iterdir()
        if p.is_file() and p.stem.lower() == "photo" and p.suffix.lower() in PHOTO_EXTENSIONS
    )
    # Por orden de extensión preferida (jpg antes que heic), no alfabético.
    candidates.sort(key=lambda p: PHOTO_EXTENSIONS.index(p.suffix.lower()))
    return next((p for p in candidates if _opens(p)), None)


def size_px(size_mm: float) -> int:
    return round(size_mm / 25.4 * DPI)


def crop(source: Path, shape: PhotoShape, side: int) -> Image.Image:
    """Recorte cuadrado centrado de `side` px con la forma pedida."""
    try:
        with Image.open(source) as original:
            img = ImageOps.exif_transpose(original)
            img = ImageOps.fit(img.convert("RGB"), (side, side), Image.Resampling.LANCZOS)
    except (OSError, UnidentifiedImageError) as exc:
        raise PhotoError(f"No se puede abrir la foto {source.name}: {exc}") from exc
    if shape == "square":
        return img

    big = side * _MASK_SCALE
    mask = Image.new("L", (big, big), 0)
    draw = ImageDraw.Draw(mask)
    if shape == "circle":
        draw.ellipse((0, 0, big - 1, big - 1), fill=255)
    else:
        draw.rounded_rectangle((0, 0, big - 1, big - 1), radius=big * ROUNDED_RADIUS, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask.resize((side, side), Image.Resampling.LANCZOS))
    return out


def prepared_photo(
    source: Path, shape: PhotoShape, size_mm: float, cache_dir: Path | None = None
) -> Path:
    """PNG recortado de la foto para una plantilla, desde la caché si ya existe."""
    cache_dir = cache_dir or get_settings().data_dir / "cache" / "photo"
    side = size_px(size_mm)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:16]
    target = cache_dir / f"{digest}-{shape}-{side}.png"
    if target.is_file():
        return target
    image = crop(source, shape, side)
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".tmp")
    image.save(tmp, format="PNG", dpi=(DPI, DPI))
    tmp.replace(target)
    return target
