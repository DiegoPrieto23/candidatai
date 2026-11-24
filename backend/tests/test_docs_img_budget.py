"""Los medios de `docs/img/` caben en su presupuesto: el repositorio se clona entero.

Todo `docs/img/` hasta 15 MB y la animación de la sección «Demo» (`tour.webp`) hasta 1,5 MB por
idioma. Se regeneran con `scripts/readme_media/`; si no caben, primero se quita lo que no enlaza
nadie y después se baja la calidad de lo que no está en el README."""

from __future__ import annotations

import pytest

from app.core.config import REPO_ROOT

IMG = REPO_ROOT / "docs" / "img"
BUDGET = 15 * 1024 * 1024
TOUR_MAX = int(1.5 * 1024 * 1024)


def _mb(size: int) -> str:
    return f"{size / 1024 / 1024:.2f} MB"


def test_docs_img_fits_its_budget() -> None:
    files = [path for path in IMG.rglob("*") if path.is_file()]
    total = sum(path.stat().st_size for path in files)
    biggest = sorted(files, key=lambda path: path.stat().st_size, reverse=True)[:5]
    detail = ", ".join(f"{p.relative_to(IMG).as_posix()} {_mb(p.stat().st_size)}" for p in biggest)
    assert total <= BUDGET, f"docs/img: {_mb(total)} (máximo {_mb(BUDGET)}). Lo que más: {detail}"


@pytest.mark.parametrize("lang", ["en", "es"])
def test_the_demo_animation_is_light(lang: str) -> None:
    tour = IMG / lang / "anim" / "tour.webp"
    assert tour.is_file()
    size = tour.stat().st_size
    assert size <= TOUR_MAX, f"{lang}/anim/tour.webp ocupa {_mb(size)} (máximo {_mb(TOUR_MAX)})"
