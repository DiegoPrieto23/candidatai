"""Autoría de plantillas (fases 08.3 y 08b): lo que usan `jh templates …` y la página Plantillas.

`inspect`, `build_docx`, `scaffold_html` y `compare` trabajan con ficheros dentro de `data/`
(`importer/paths.py`). Word va al motor docx; PDF, imagen y HTML, al html. Las
previews con el perfil demo de una plantilla del usuario van a su carpeta (son su miniatura); las
de las integradas y las del perfil real, a `data/cache/previews/`, para no escribir datos
personales fuera de `data/` ni tocar `templates/`.
"""

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services import profile as profile_service
from app.services.documents import pdf, photo, preview, templates
from app.services.documents.importer import build, compare, inspect, paths, scaffold, visual

ProfileChoice = Literal["demo", "real"]


class ValidationResult(BaseModel):
    ok: bool
    template_id: str
    engine: str
    path: str
    sections: list[str]


class PreviewResult(BaseModel):
    template_id: str
    profile: ProfileChoice
    pdf_path: str  # relativas a data/ (o a la raíz del repo en una integrada con perfil demo)
    png_path: str
    pages: int
    max_pages: int
    fits: bool
    warnings: list[str]


def inspect_file(path: Path) -> inspect.DocxInspection | visual.VisualInspection:
    source = paths.source_file(path)
    if visual.is_visual(source):
        return visual.inspect_visual(source)
    return inspect.inspect_docx(source)


def scaffold_html(
    source: Path,
    template_id: str,
    name: str | None = None,
    sections: list[str] | None = None,
    side: list[str] | None = None,
    force: bool = False,
) -> scaffold.ScaffoldResult:
    return scaffold.scaffold_html(
        paths.source_file(source), template_id, name=name, sections=sections, side=side,
        force=force,
    )  # fmt: skip


def compare_template(template_id: str, source: Path) -> compare.CompareResult:
    templates.validate(template_id)
    return compare.compare(template_id, paths.source_file(source))


def build_docx(
    source: Path, mapping: Path, template_id: str, name: str | None = None, force: bool = False
) -> build.BuildResult:
    source_path = paths.source_file(source)
    mapping_path = paths.mapping_file(mapping)
    try:
        data = json.loads(mapping_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"El mapeo no es JSON válido: {exc}") from exc
    result = build.build_docx(source_path, data, template_id, name=name, force=force)
    mapping_path.unlink(missing_ok=True)  # como `--file`: se borra tras procesarse bien
    return result


def validate(template_id: str) -> ValidationResult:
    """`template.yaml`, variables del contrato y que renderiza con todo el perfil demo."""
    template = templates.validate(template_id)
    preview.check_renders(template)
    return ValidationResult(
        ok=True,
        template_id=template.id,
        engine=template.meta.engine,
        path=str(template.path),
        sections=list(template.meta.sections),
    )


def _relative(path: Path) -> str:
    data_dir = get_settings().data_dir
    if path.resolve().is_relative_to(data_dir.resolve()):
        return path.resolve().relative_to(data_dir.resolve()).as_posix()
    return str(path)


def previews_dir() -> Path:
    return get_settings().data_dir / "cache" / "previews"


def _output_paths(template: templates.Template, which: ProfileChoice) -> tuple[Path, Path]:
    user_dir = get_settings().user_templates_dir.resolve()
    if which == "demo" and template.path.resolve().is_relative_to(user_dir):
        return template.path / "preview.pdf", template.path / "preview.png"
    stem = f"{template.id}-{which}-{template.file_hash()[:12]}"
    return previews_dir() / f"{stem}.pdf", previews_dir() / f"{stem}.png"


def preview_template(
    session: Session | None, template_id: str, which: ProfileChoice = "demo"
) -> PreviewResult:
    """PDF y PNG de la plantilla con el perfil demo o con el real (la última versión importada)."""
    template = templates.validate(template_id)
    if which == "real":
        if session is None:
            raise ValueError("La preview con el perfil real necesita la base de datos.")
        candidate = profile_service.current(session).profile
        photo_source = photo.find_photo(candidate)
    else:
        candidate = profile_service.load_from_yaml(profile_service.EXAMPLE_PATH)
        photo_source = preview.DEMO_PHOTO
    pdf_path, png_path = _output_paths(template, which)
    preview.render_preview(
        template, candidate, pdf_path, photo_source=photo_source, output_png=png_path
    )
    info = pdf.read_pdf(pdf_path)
    max_pages = template.meta.page.max_pages
    warnings = []
    if info.pages > max_pages:
        warnings.append(
            f"Con el perfil {which} ocupa {info.pages} páginas y la plantilla admite {max_pages}: "
            "ajusta `capacity` o sube `page.max_pages` si el diseño lo pide."
        )
    missing = pdf.missing_fonts(template.meta.fonts, info.fonts)
    if missing:
        warnings.append(f"Falta la fuente {', '.join(missing)}: el PDF usa otra.")
    return PreviewResult(
        template_id=template.id,
        profile=which,
        pdf_path=_relative(pdf_path),
        png_path=_relative(png_path),
        pages=info.pages,
        max_pages=max_pages,
        fits=info.pages <= max_pages,
        warnings=warnings,
    )


def real_preview_png(session: Session, template_id: str) -> Path:
    """PNG con el perfil real, desde la caché si la plantilla y el perfil no han cambiado."""
    template = templates.get(template_id)
    version = profile_service.current(session).profile_version_id
    png = previews_dir() / f"{template.id}-real-{template.file_hash()[:12]}-v{version}.png"
    if not png.is_file():
        result = preview_template(session, template_id, "real")
        generated = get_settings().data_dir / result.png_path
        png.parent.mkdir(parents=True, exist_ok=True)
        generated.replace(png)
        (get_settings().data_dir / result.pdf_path).unlink(missing_ok=True)
    return png


def source_png(template_id: str) -> Path | None:
    """Primera página del original (`source.png`, la crea `build-docx`), si la hay."""
    template = templates.get(template_id)
    png = template.path / build.SOURCE_PNG
    return png if png.is_file() else None
