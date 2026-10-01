"""Foto del CV (fase 08.2): búsqueda en `data/`, recorte por forma y caché."""

from pathlib import Path

import pytest
from PIL import Image

from app.core.config import REPO_ROOT, get_settings
from app.services.documents import photo
from tests.matching_support import demo_profile

DEMO_PHOTO = REPO_ROOT / "demo" / "photo.png"
RED, BLUE = (220, 20, 20), (20, 20, 220)


def two_colors(
    path: Path, size: tuple[int, int] = (200, 100), orientation: int | None = None
) -> Path:
    """Imagen con la mitad izquierda roja y la derecha azul (y orientación EXIF opcional)."""
    image = Image.new("RGB", size, BLUE)
    image.paste(RED, (0, 0, size[0] // 2, size[1]))
    exif = Image.Exif()
    if orientation is not None:
        exif[0x0112] = orientation
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, exif=exif)
    return path


def near(pixel: tuple[int, ...], color: tuple[int, int, int]) -> bool:
    return all(abs(a - b) < 40 for a, b in zip(pixel[:3], color, strict=True))


# --- Recorte --------------------------------------------------------------------------------


def test_circle_is_transparent_outside() -> None:
    image = photo.crop(DEMO_PHOTO, "circle", 120)
    assert image.size == (120, 120) and image.mode == "RGBA"
    alpha = image.getchannel("A")
    assert alpha.getpixel((0, 0)) == 0 and alpha.getpixel((119, 119)) == 0
    assert alpha.getpixel((60, 60)) == 255
    assert alpha.getpixel((60, 1)) > 128  # el borde superior, en el centro, es del círculo


def test_rounded_only_cuts_the_corners() -> None:
    image = photo.crop(DEMO_PHOTO, "rounded", 120)
    alpha = image.getchannel("A")
    assert image.size == (120, 120) and image.mode == "RGBA"
    assert alpha.getpixel((0, 0)) == 0
    assert alpha.getpixel((60, 0)) == 255 and alpha.getpixel((0, 60)) == 255
    # Un círculo sí habría cortado aquí.
    assert alpha.getpixel((12, 12)) == 255


def test_square_has_no_transparency(tmp_path: Path) -> None:
    image = photo.crop(two_colors(tmp_path / "p.png"), "square", 90)
    assert image.size == (90, 90) and image.mode == "RGB"
    # Recorte centrado de 200x100: la mitad izquierda roja, la derecha azul.
    assert near(image.getpixel((10, 45)), RED) and near(image.getpixel((80, 45)), BLUE)


def test_exif_orientation_is_respected(tmp_path: Path) -> None:
    # Orientación 6: hay que girarla 90° a la derecha; lo que era la izquierda queda arriba.
    source = two_colors(tmp_path / "p.jpg", orientation=6)
    image = photo.crop(source, "square", 100)
    assert near(image.getpixel((50, 15)), RED) and near(image.getpixel((50, 85)), BLUE)


def test_unreadable_photo_is_a_clear_error(tmp_path: Path) -> None:
    broken = tmp_path / "photo.jpg"
    broken.write_bytes(b"no es una imagen")
    with pytest.raises(photo.PhotoError, match="photo.jpg"):
        photo.crop(broken, "circle", 50)


def test_prepared_photo_is_cached(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cache = tmp_path / "cache"
    first = photo.prepared_photo(DEMO_PHOTO, "circle", 30, cache)
    assert first.parent == cache and first.suffix == ".png"
    assert Image.open(first).size == (photo.size_px(30),) * 2

    def fail(*_args: object) -> None:
        raise AssertionError("no debería recortar otra vez")

    monkeypatch.setattr(photo, "crop", fail)
    assert photo.prepared_photo(DEMO_PHOTO, "circle", 30, cache) == first
    monkeypatch.undo()
    # Otra forma u otro tamaño, otra entrada.
    assert photo.prepared_photo(DEMO_PHOTO, "square", 30, cache) != first
    assert photo.prepared_photo(DEMO_PHOTO, "circle", 25, cache) != first


def test_prepared_photo_uses_data_cache_by_default() -> None:
    out = photo.prepared_photo(DEMO_PHOTO, "rounded", 20)
    assert out.parent == get_settings().data_dir / "cache" / "photo"


# --- Dónde está la foto ---------------------------------------------------------------------


def test_photo_file_of_the_profile_comes_first(tmp_path: Path) -> None:
    profile = demo_profile()
    profile.preferences.cv.photo_file = "fotos/yo.png"
    two_colors(tmp_path / "photo.jpg")
    assert photo.find_photo(profile, tmp_path) == tmp_path / "photo.jpg"
    two_colors(tmp_path / "fotos" / "yo.png")
    assert photo.find_photo(profile, tmp_path) == tmp_path / "fotos" / "yo.png"


def test_falls_back_to_any_photo_extension(tmp_path: Path) -> None:
    profile = demo_profile()  # pide `photo.jpg`, que no existe
    assert photo.find_photo(profile, tmp_path) is None
    two_colors(tmp_path / "Photo.WEBP")
    two_colors(tmp_path / "photo.png")
    assert photo.find_photo(profile, tmp_path) == tmp_path / "photo.png"  # png antes que webp


def test_unopenable_photos_are_skipped(tmp_path: Path) -> None:
    profile = demo_profile()
    (tmp_path / "photo.jpg").write_bytes(b"roto")
    (tmp_path / "photo.heic").write_bytes(b"sin soporte heic en Pillow")
    assert photo.find_photo(profile, tmp_path) is None
    two_colors(tmp_path / "photo.webp")
    assert photo.find_photo(profile, tmp_path) == tmp_path / "photo.webp"
