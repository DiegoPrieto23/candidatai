"""Importar un CV en PDF, imagen o HTML como plantilla html (fase 08b): `inspect`,
`scaffold-html` y `compare`.

El original es el CV FICTICIO de `tests/fixtures/cv-ficticio.html` y su PDF (generado con el
motor html). La imagen se saca del PDF en cada test.
"""

import json
import shutil
from pathlib import Path

import pytest
import yaml
from PIL import Image
from typer.testing import CliRunner

from app import cli
from app.core.config import get_settings
from app.services.documents import authoring, preview, templates, uploads
from app.services.documents.importer import TemplateImportError, compare, paths, scaffold, visual
from app.services.documents.importer.build import TemplateExistsError
from app.services.documents.importer.inspect import DocxInspection
from tests.cv_support import requires_chromium

FIXTURES = Path(__file__).parent / "fixtures"
CV_PDF = FIXTURES / "cv-ficticio.pdf"
CV_HTML = FIXTURES / "cv-ficticio.html"
ORDER = ["summary", "experience", "education", "extra", "contact", "skills", "languages"]
runner = CliRunner()


@pytest.fixture
def uploads_dir(isolated_env: Path) -> Path:
    folder = paths.uploads_dir()
    folder.mkdir(parents=True)
    return folder


@pytest.fixture
def cv_pdf(uploads_dir: Path) -> Path:
    return Path(shutil.copyfile(CV_PDF, uploads_dir / "cv.pdf"))


@pytest.fixture
def cv_png(uploads_dir: Path) -> Path:
    return preview.pdf_to_png(CV_PDF, uploads_dir / "cv.png", 900)


# --- inspect --------------------------------------------------------------------------------


def test_inspect_pdf_reads_design_sections_and_capacity(cv_pdf: Path) -> None:
    report = authoring.inspect_file(cv_pdf)
    assert isinstance(report, visual.VisualInspection)
    assert report.format == "pdf" and report.pages == 1 and report.page.size == "A4"
    assert (get_settings().data_dir / report.page_images[0]).is_file()
    assert report.fonts[:2] == ["Georgia", "Arial"]

    lay = report.layout
    assert lay.columns == 2 and lay.sidebar is None
    assert lay.header_band_color == "#0E6E6E"
    assert 130 < lay.column_edges_mm[0] < 140  # la calle entre la columna principal y la lateral
    assert lay.margins_mm["left"] == pytest.approx(15, abs=1.5)
    assert report.colors[0].color == "#FFFFFF" and report.colors[1].color == "#0E6E6E"

    assert [s.section for s in report.sections] == ORDER
    assert [s.column for s in report.sections] == [0, 0, 0, 0, 1, 1, 1]
    assert report.capacity.bullets_per_experience == [3, 2]
    assert report.capacity.skill_groups == 3
    assert 140 <= (report.capacity.summary_chars or 0) <= 170

    name = report.text_blocks[0]
    assert name.text == "Marta Ríos Ferreiro" and name.bold and name.size_pt == pytest.approx(26)
    assert not report.ats.ats_friendly and report.ats.reasons


def test_inspect_image_estimates_layout_and_leaves_sections_to_the_agent(cv_png: Path) -> None:
    report = authoring.inspect_file(cv_png)
    assert isinstance(report, visual.VisualInspection)
    assert report.format == "image" and report.page.size == "A4"
    assert report.text_blocks == [] and report.sections == []
    assert report.capacity_note and "--sections" in report.capacity_note
    assert report.layout.columns == 2 and report.layout.header_band_color == "#0E6E6E"
    assert any("No tiene texto" in r for r in report.ats.reasons)


@requires_chromium
def test_inspect_html_prints_it_first(uploads_dir: Path) -> None:
    source = Path(shutil.copyfile(CV_HTML, uploads_dir / "cv.html"))
    report = authoring.inspect_file(source)
    assert isinstance(report, visual.VisualInspection)
    assert report.format == "html"
    assert [s.section for s in report.sections] == ORDER
    assert any("sin red" in n for n in report.notes)


def test_inspect_html_serves_no_other_file(
    uploads_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un HTML ajeno no puede incrustar los otros CVs de `data/uploads/` en su PDF."""
    from app.services.documents.engines import html as html_engine

    (uploads_dir / "otro-cv.png").write_bytes(b"\x89PNG")
    source = uploads_dir / "ajeno.html"
    source.write_text('<img src="otro-cv.png"><p>x</p>', encoding="utf-8")
    seen: dict[str, object] = {}

    def capture(html: str, resolve: object, output: Path, *_args: object) -> Path:
        seen["resolve"] = resolve
        raise RuntimeError("basta")

    monkeypatch.setattr(html_engine, "html_to_pdf", capture)
    with pytest.raises(RuntimeError):
        visual.print_html(source, uploads_dir / "out.pdf")
    resolve = seen["resolve"]
    assert callable(resolve)
    assert resolve("otro-cv.png") is None and resolve("ajeno.html") is None


def test_scaffold_escapes_font_names_from_the_pdf() -> None:
    stack = scaffold._font_stack('Evil"; } body { background: url(http://x.example) } "')
    name = stack.removeprefix('"').removesuffix('", sans-serif')
    assert name.startswith("Evil") and not set(name) & set("\"';{}():/")
    assert scaffold._font_stack("Georgia") == '"Georgia", serif'
    assert scaffold._font_stack(None) == "sans-serif"


def test_inspect_keeps_docx_on_its_engine_and_rejects_files_outside_data(
    uploads_dir: Path, tmp_path: Path
) -> None:
    from tests.template_support import make_cv

    assert isinstance(authoring.inspect_file(make_cv(uploads_dir / "cv.docx")), DocxInspection)
    outside = Path(shutil.copyfile(CV_PDF, tmp_path / "fuera.pdf"))
    with pytest.raises(paths.OutsideDataError):
        authoring.inspect_file(outside)


def test_inspect_rejects_a_broken_pdf(uploads_dir: Path) -> None:
    broken = uploads_dir / "roto.pdf"
    broken.write_bytes(b"%PDF-1.4 esto no es un PDF")
    with pytest.raises(TemplateImportError, match="PDF"):
        authoring.inspect_file(broken)


# --- scaffold-html --------------------------------------------------------------------------


def test_scaffold_html_from_pdf_creates_a_valid_template(cv_pdf: Path) -> None:
    result = authoring.scaffold_html(cv_pdf, "marta", name="Marta")
    folder = get_settings().user_templates_dir / "marta"
    assert result.path == "templates/marta"
    assert {"template.html", "style.css", "template.yaml", "source.pdf", "source.png"} <= set(
        result.files
    )
    # Columna principal en su orden y después la lateral; el contacto, en la lateral.
    assert result.sections == [
        "summary", "experience", "education", "extra_sections", "skills", "languages"
    ]  # fmt: skip
    assert result.side_sections == ["skills", "languages"]
    assert result.accent_color == "#0E6E6E" and result.fonts == ["Georgia", "Arial"]

    meta = yaml.safe_load((folder / "template.yaml").read_text(encoding="utf-8"))
    assert meta["engine"] == "html" and meta["source_file"] == "source.pdf"
    assert meta["ats_friendly"] is False and meta["layout"]["columns"] == 2
    assert meta["capacity"]["experience_bullets"] == 5
    assert meta["options"]["accent_color"]["default"] == "#0E6E6E"

    html = (folder / "template.html").read_text(encoding="utf-8")
    assert html.index('class="main"') < html.index('class="side"')  # lateral a la derecha
    assert "labels.contact" in html
    assert templates.unsafe_content(templates.get("marta")) == []
    assert authoring.validate("marta").engine == "html"

    # La subida queda como importada (mismo sha256 que el `source.*`) y tiene su original.
    info = next(u for u in uploads.list_uploads() if u.name == "cv.pdf")
    assert info.template_id == "marta" and info.supported
    assert authoring.source_png("marta") is not None


def test_scaffold_html_from_image_with_sections_given_by_the_agent(cv_png: Path) -> None:
    result = authoring.scaffold_html(
        cv_png, "desde-imagen", sections=["summary", "experience", "skills"], side=["skills"]
    )
    assert result.sections == ["summary", "experience", "skills"]
    assert result.side_sections == ["skills"]
    # El original .png es también su vista: se conserva tal cual y la subida sale importada.
    assert (get_settings().user_templates_dir / "desde-imagen" / "source.png").read_bytes() == (
        cv_png.read_bytes()
    )
    info = next(u for u in uploads.list_uploads() if u.name == "cv.png")
    assert info.template_id == "desde-imagen"
    assert authoring.validate("desde-imagen").sections == ["summary", "experience", "skills"]


def test_scaffold_html_errors(cv_pdf: Path, uploads_dir: Path) -> None:
    from tests.template_support import make_cv

    with pytest.raises(TemplateImportError, match="fuera del contrato"):
        authoring.scaffold_html(cv_pdf, "mala", sections=["summary", "hobbies"])
    with pytest.raises(TemplateImportError, match="build-docx"):
        authoring.scaffold_html(make_cv(uploads_dir / "cv.docx"), "word")
    authoring.scaffold_html(cv_pdf, "doble")
    with pytest.raises(TemplateExistsError):
        authoring.scaffold_html(cv_pdf, "doble")
    authoring.scaffold_html(cv_pdf, "doble", force=True)
    assert not list(get_settings().tmp_dir.glob("cai-scaffold-*"))  # sin restos del staging


@requires_chromium
def test_scaffolded_template_renders_with_the_demo_profile(cv_pdf: Path) -> None:
    authoring.scaffold_html(cv_pdf, "marta")
    result = authoring.preview_template(None, "marta", "demo")
    assert result.pages == 1 and result.fits


# --- compare --------------------------------------------------------------------------------


def test_ssim_is_one_for_the_same_image_and_lower_for_another() -> None:
    with Image.open(preview.DEMO_PHOTO) as photo:
        same = compare.ssim(photo, photo.copy())
    page = Image.open(templates.get("ats-simple").path / "preview.png")
    other = Image.open(templates.get("moderna-2col").path / "preview.png")
    assert same == pytest.approx(1.0)
    assert compare.ssim(page, other) < 0.9


@requires_chromium
def test_compare_puts_original_and_recreation_side_by_side(cv_pdf: Path) -> None:
    authoring.scaffold_html(cv_pdf, "marta")
    result = authoring.compare_template("marta", cv_pdf)
    image = get_settings().data_dir / result.image_path
    assert image.is_file() and 0 < result.ssim <= 1
    with Image.open(image) as png:
        assert png.width > png.height  # dos páginas en vertical, una al lado de la otra
    # Un diseño distinto (barra lateral azul a la izquierda) se parece menos que la recreación.
    assert authoring.compare_template("moderna-2col", cv_pdf).ssim < result.ssim


def test_compare_needs_a_visual_original(uploads_dir: Path) -> None:
    from tests.template_support import make_cv

    with pytest.raises(TemplateImportError, match="Word"):
        authoring.compare_template("moderna-2col", make_cv(uploads_dir / "cv.docx"))


# --- CLI ------------------------------------------------------------------------------------


def test_cli_inspect_scaffold_and_validate_json(cv_pdf: Path) -> None:
    result = runner.invoke(cli.app, ["templates", "inspect", str(cv_pdf), "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["format"] == "pdf"

    args = ["templates", "scaffold-html", "--source", str(cv_pdf), "--id", "cli", "--json"]
    result = runner.invoke(cli.app, [*args, "--sections", "summary, experience,skills"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["sections"] == ["summary", "experience", "skills"]

    result = runner.invoke(cli.app, args)
    assert result.exit_code == 1
    assert json.loads(result.output)["error"]["type"] == "exists"

    result = runner.invoke(cli.app, ["templates", "validate", "cli", "--json"])
    assert result.exit_code == 0 and json.loads(result.output)["engine"] == "html"


def test_cli_scaffold_text_output(cv_png: Path) -> None:
    result = runner.invoke(
        cli.app, ["templates", "scaffold-html", "--source", str(cv_png), "--id", "texto"]
    )
    assert result.exit_code == 0, result.output
    assert "Plantilla html creada" in result.output and "Siguientes pasos" in result.output
