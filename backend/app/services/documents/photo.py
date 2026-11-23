"""Foto del CV: busca la foto del candidato y la recorta a la forma y tamaño de la plantilla.

- Fuente: `preferences.cv.photo_file` (relativa a `data/`); si ese fichero no existe, el primer
  `data/photo.*` (jpg, jpeg, png, webp; heic solo si Pillow lo abre).
- Recorte centrado a un cuadrado, respetando la orientación EXIF, y máscara según `photo.shape`:
  círculo y esquinas redondeadas con fondo transparente (PNG con alfa), cuadrado sin alfa.
- Caché en `data/cache/photo/`, por hash de la foto, forma y tamaño: renderizar diez veces el
  mismo CV no recorta la foto diez veces.
- Encuadre (desde «Mi perfil»): el navegador recorta la foto y sube el recorte como `data/photo.*`;
  junto a él se guardan la original (`data/photo-original.*`) y dónde estaba el recuadro
  (`data/photo-crop.json`), para volver a encuadrar sin perder calidad.
"""

import hashlib
import json
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, ValidationError

from app.core.config import get_settings
from app.schemas.cv import PhotoShape
from app.schemas.profile import CandidateProfile

if TYPE_CHECKING:
    from PIL import Image

# Pillow se importa al usarlo, como lo demás pesado de documentos: la API arranca sin cargarlo.

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
    from PIL import Image, UnidentifiedImageError

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


def crop(source: Path, shape: PhotoShape, side: int) -> "Image.Image":
    """Recorte cuadrado centrado de `side` px con la forma pedida."""
    from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

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


# --- Subir la foto desde «Mi perfil» -----------------------------------------------------------

MAX_PHOTO_BYTES = 10 * 1024 * 1024
# Se mira el contenido, no la extensión: nada de SVG ni de un `.jpg` que no lo es.
_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


ORIGINAL_STEM = "photo-original"
CROP_FILE = "photo-crop.json"


class PhotoCrop(BaseModel):
    """El recuadro elegido, en porcentaje de la original (como lo da el editor del navegador)."""

    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)
    width: float = Field(gt=0, le=100)
    height: float = Field(gt=0, le=100)


class PhotoInfo(BaseModel):
    exists: bool
    filename: str | None = None
    size_bytes: int | None = None
    version: str | None = None  # cambia con la foto: para que el navegador no enseñe la anterior
    has_original: bool = False  # se guardó la original: se puede volver a encuadrar desde ella
    crop: PhotoCrop | None = None  # el último encuadre, para empezar desde él


def _named_photo(data_dir: Path) -> list[Path]:
    if not data_dir.is_dir():
        return []
    return [
        p
        for p in data_dir.iterdir()
        if p.is_file() and p.stem.lower() == "photo" and p.suffix.lower() in PHOTO_EXTENSIONS
    ]


def current_photo(profile: CandidateProfile | None, data_dir: Path | None = None) -> Path | None:
    """Como `find_photo`, también sin perfil todavía (entonces, solo `data/photo.*`)."""
    data_dir = data_dir or get_settings().data_dir
    if profile is not None:
        return find_photo(profile, data_dir)
    return next((p for p in sorted(_named_photo(data_dir)) if _opens(p)), None)


def _originals(data_dir: Path) -> list[Path]:
    if not data_dir.is_dir():
        return []
    return [
        p
        for p in data_dir.iterdir()
        if p.is_file() and p.stem.lower() == ORIGINAL_STEM and p.suffix.lower() in PHOTO_EXTENSIONS
    ]


def original_photo(data_dir: Path | None = None) -> Path | None:
    """La foto original del último encuadre, si se guardó y se puede abrir."""
    data_dir = data_dir or get_settings().data_dir
    return next((p for p in sorted(_originals(data_dir)) if _opens(p)), None)


def _read_crop(data_dir: Path) -> PhotoCrop | None:
    try:
        return PhotoCrop.model_validate(
            json.loads((data_dir / CROP_FILE).read_text(encoding="utf-8"))
        )
    except (OSError, ValueError, ValidationError):
        return None


def _clear_original(data_dir: Path) -> None:
    for old in _originals(data_dir):
        old.unlink(missing_ok=True)
    (data_dir / CROP_FILE).unlink(missing_ok=True)


def photo_info(path: Path | None, data_dir: Path | None = None) -> PhotoInfo:
    if path is None:
        return PhotoInfo(exists=False)
    data_dir = data_dir or get_settings().data_dir
    stat = path.stat()
    has_original = original_photo(data_dir) is not None
    return PhotoInfo(
        exists=True,
        filename=path.name,
        size_bytes=stat.st_size,
        version=f"{stat.st_mtime_ns:x}",
        has_original=has_original,
        crop=_read_crop(data_dir) if has_original else None,
    )


def _image_suffix(content: bytes) -> str:
    """La extensión según el contenido. `PhotoError` si no es un JPEG, PNG o WebP de hasta 10 MB."""
    from PIL import Image, UnidentifiedImageError

    if len(content) > MAX_PHOTO_BYTES:
        raise PhotoError("La foto pasa de 10 MB: conviene probar con una más pequeña.")
    try:
        with Image.open(BytesIO(content)) as img:
            suffix = _FORMATS.get(img.format or "")
            img.verify()
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError) as exc:
        raise PhotoError("No parece una imagen válida: se aceptan JPG, PNG y WebP.") from exc
    except Image.DecompressionBombError as exc:
        raise PhotoError(
            "La imagen es demasiado grande: conviene probar con una más pequeña."
        ) from exc
    if suffix is None:
        raise PhotoError("Formato no admitido: se aceptan JPG, PNG y WebP.")
    return suffix


def _write(target: Path, content: bytes) -> None:
    tmp = target.with_name(f"{target.name}.tmp")
    tmp.write_bytes(content)
    tmp.replace(target)


def save_photo(
    content: bytes,
    profile: CandidateProfile | None,
    data_dir: Path | None = None,
    original: bytes | None = None,
    crop_area: PhotoCrop | None = None,
) -> PhotoInfo:
    """Guarda la foto como `data/photo.<ext>` y quita la anterior. Con `original` (la foto antes
    de encuadrarla) y `crop_area`, los guarda para volver a encuadrar; sin ellos, se olvida la
    original anterior, que ya no corresponde. `PhotoError` si alguna no es un JPEG, PNG o WebP de
    hasta 10 MB, o si el perfil apunta a otro fichero (seguiría mandando ese)."""
    data_dir = data_dir or get_settings().data_dir
    suffix = _image_suffix(content)
    original_suffix = _image_suffix(original) if original is not None else None
    if profile is not None:
        configured = data_dir / profile.preferences.cv.photo_file
        if configured.is_file() and configured not in _named_photo(data_dir):
            raise PhotoError(
                f"El perfil usa otra foto (`{profile.preferences.cv.photo_file}`): "
                "hay que quitarla antes de subir una nueva."
            )
    data_dir.mkdir(parents=True, exist_ok=True)
    target = data_dir / f"photo{suffix}"
    _write(target, content)
    for old in _named_photo(data_dir):
        if old != target:
            old.unlink(missing_ok=True)
    if original is None or original_suffix is None:
        _clear_original(data_dir)
    else:
        kept = data_dir / f"{ORIGINAL_STEM}{original_suffix}"
        _write(kept, original)
        for old in _originals(data_dir):
            if old != kept:
                old.unlink(missing_ok=True)
        if crop_area is None:
            (data_dir / CROP_FILE).unlink(missing_ok=True)
        else:
            _write(data_dir / CROP_FILE, crop_area.model_dump_json().encode("utf-8"))
    return photo_info(target, data_dir)


def delete_photo(profile: CandidateProfile | None, data_dir: Path | None = None) -> PhotoInfo:
    """Quita la foto (también la que indique el perfil, dentro de `data/`) y sus recortes."""
    data_dir = data_dir or get_settings().data_dir
    found = current_photo(profile, data_dir)
    if found is not None:
        found.unlink(missing_ok=True)
    for old in _named_photo(data_dir):
        old.unlink(missing_ok=True)
    _clear_original(data_dir)
    cache = data_dir / "cache" / "photo"
    if cache.is_dir():
        for cached in cache.iterdir():
            if cached.is_file():
                cached.unlink(missing_ok=True)
    return PhotoInfo(exists=False)
