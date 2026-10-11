"""Motor html (fase 08b): saneado, render de `moderna-2col` y sin red."""

from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from app.core.config import get_settings
from app.services.documents import authoring, pdf, photo, preview, sanitize, templates
from app.services.documents.engines import html as html_engine
from tests.cv_support import requires_chromium, write_template

ACCENTS = ["#1F4E79", "#2E5E4E", "#7A2E39", "#3F3F46"]


def _rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _context(accent: str = ACCENTS[0]) -> dict[str, Any]:
    ctx = preview.demo_context()  # todo el perfil demo, con sus secciones extra
    ctx["accent_color"] = accent
    return ctx


def _photo(tmp_path: Path) -> Path:
    meta = templates.get("moderna-2col").meta.photo
    return photo.prepared_photo(preview.DEMO_PHOTO, meta.shape, meta.size_mm, tmp_path)


def html_template(root: Path, template_id: str, html: str, css: str = "") -> Path:
    folder = write_template(root, template_id, engine="html")
    (folder / "template.docx").unlink()
    (folder / "template.html").write_text(html, encoding="utf-8")
    (folder / "style.css").write_text(css, encoding="utf-8")
    return folder


# --- Saneado --------------------------------------------------------------------------------


def test_clean_html_removes_scripts_handlers_and_remote_urls() -> None:
    dirty = (
        '<html><head><link rel="stylesheet" href="https://cdn.example.com/a.css">'
        "<style>@import url(http://e.example/b.css); body{background:url('https://t.example/p.png')}"
        ".x{background:url(fonts/ok.png)}</style></head>"
        '<body onload="steal()"><script>alert(1)</script><iframe src="x.html"></iframe>'
        '<img src="http://evil.example/pixel.png"><img src="jh-photo.png">'
        '<a href="javascript:alert(1)">j</a><a href="mailto:a@example.com">m</a>'
        '<p style="background:url(//e.example/x)">t</p></body></html>'
    )
    clean = sanitize.clean_html(dirty)
    for gone in (
        "<script",
        "alert(1)",
        "onload",
        "<iframe",
        "evil.example",
        "cdn.example.com",
        "@import",
        "t.example",
        "javascript:",
        "//e.example",
    ):
        assert gone not in clean
    for kept in ('src="jh-photo.png"', "url(fonts/ok.png)", "mailto:a@example.com"):
        assert kept in clean


def test_sanitize_covers_every_srcset_and_image_set_entry() -> None:
    srcset = '<img srcset="a.png 1x, http://x.example/b.png 2x">'
    assert [f.what for f in sanitize.scan(srcset, "t.html")] == [
        "URL externa en srcset: http://x.example/b.png"
    ]
    assert "x.example" not in sanitize.clean_html(srcset)
    css = '.a { background: image-set("b.png" 1x, "https://e.example/a.png" 2x); }'
    assert sanitize.scan(css, "style.css")[0].what.startswith("URL externa en image-set()")
    assert "e.example" not in sanitize.clean_css(css)


def test_clean_html_accepts_empty_documents_and_xml_declarations() -> None:
    assert "<body></body>" in sanitize.clean_html("  ")
    clean = sanitize.clean_html('<?xml version="1.0" encoding="utf-8"?><p>{x}</p>')
    assert "<p>{x}</p>" in clean and "<?xml" not in clean


def test_validate_reports_an_unreadable_stylesheet() -> None:
    folder = html_template(get_settings().user_templates_dir, "latin1", "<p>{{ name }}</p>")
    (folder / "style.css").write_bytes("/* café */".encode("latin-1"))
    with pytest.raises(templates.TemplateInvalidError, match="No se puede leer"):
        templates.validate("latin1")


def test_scan_reports_what_and_where() -> None:
    text = '<p>{{ name }}</p>\n<script src="x.js"></script>\n<img src="https://a.example/x.png">\n'
    found = sanitize.scan(text, "template.html")
    assert [(f.line, f.what) for f in found] == [
        (2, "etiqueta <script>"),
        (3, "URL externa en src: https://a.example/x.png"),
    ]
    assert sanitize.scan("a { background: url('//cdn.example/x.png') }", "style.css")[0].line == 1
    assert sanitize.scan(".a { color: red; background: url(img/x.png) }", "style.css") == []


def test_validate_fails_with_script_and_remote_url() -> None:
    root = get_settings().user_templates_dir
    html_template(
        root,
        "insegura",
        "<p>{{ name }}</p>\n<script>alert(1)</script>",
        "body { background: url(https://cdn.example/bg.png); }",
    )
    with pytest.raises(templates.TemplateInvalidError) as exc:
        templates.validate("insegura")
    fields = [i.field for i in exc.value.issues]
    assert fields == ["template.html:2", "style.css:1"]
    assert "script" in str(exc.value) and "cdn.example" in str(exc.value)


def test_validate_checks_contract_variables_in_html() -> None:
    root = get_settings().user_templates_dir
    html_template(root, "fuera", "<p>{{ name }} {{ salario }}</p>")
    with pytest.raises(templates.TemplateInvalidError, match="salario"):
        templates.validate("fuera")


def test_validate_detects_missing_attributes_by_rendering() -> None:
    root = get_settings().user_templates_dir
    html_template(root, "rota", "{% for e in experience %}{{ e.rol }}{% endfor %}")
    with pytest.raises(templates.TemplateInvalidError, match="No renderiza"):
        authoring.validate("rota")


def test_render_string_escapes_profile_text() -> None:
    template = templates.get("moderna-2col")
    ctx = _context()
    ctx["summary"] = '<script>alert("x")</script> & más'
    html = html_engine.render_string(template, ctx, None)
    assert "<script" not in html
    assert "&lt;script&gt;" in html and "&amp; más" in html
    assert "jh-photo.png" not in html  # sin foto, no hay <img>


def test_resolver_serves_only_local_files(tmp_path: Path) -> None:
    template = templates.get("moderna-2col")
    fonts = get_settings().data_dir / "fonts"
    fonts.mkdir(parents=True)
    (fonts / "Mia.woff2").write_bytes(b"x")
    resolve = html_engine.resource_resolver(template.path, tmp_path / "foto.png")
    assert resolve("style.css") == (template.path / "style.css").resolve()
    assert resolve("fonts/Lato-Bold-latin.woff2") is not None
    assert resolve("fonts/Mia.woff2") == (fonts / "Mia.woff2").resolve()
    assert resolve(html_engine.PHOTO_URL) == tmp_path / "foto.png"
    assert resolve("../ats-simple/template.yaml") is None
    assert resolve("fonts/../../../backend/pyproject.toml") is None
    assert resolve("no-existe.png") is None


def test_add_links_only_wraps_profile_links_in_the_body() -> None:
    html = (
        "<html><head><title>github.com/x</title></head><body>"
        "<p>Repo: github.com/x/repo · <b>github.com/x</b></p>"
        '<a href="#top">github.com/x</a></body></html>'
    )
    targets = {t: f"https://{t}" for t in ("github.com/x", "github.com/x/repo")}
    out = html_engine.add_links(html, targets)
    assert "<title>github.com/x</title>" in out
    assert 'Repo: <a href="https://github.com/x/repo">github.com/x/repo</a> · ' in out
    assert '<b><a href="https://github.com/x">github.com/x</a></b>' in out
    assert '<a href="#top">github.com/x</a>' in out  # sin enlaces anidados
    assert html_engine.add_links(html, {}) == html


def test_template_still_cannot_add_external_links() -> None:
    html = '<html><body><a href="https://phishing.example">github.com/x</a></body></html>'
    cleaned = sanitize.clean_html(html)
    assert "phishing" not in cleaned
    # El `<a>` de la plantilla queda sin destino y su texto no se enlaza (nada de enlaces anidados).
    assert "href" not in html_engine.add_links(cleaned, {"github.com/x": "https://github.com/x"})


# --- Render con Chromium --------------------------------------------------------------------


@requires_chromium
def test_moderna_2col_pdf_has_profile_links(tmp_path: Path) -> None:
    from pypdf import PdfReader

    template = templates.get("moderna-2col")
    out = html_engine.render_pdf(template, _context(), tmp_path / "cv.pdf", "A4")
    uris = {
        annot.get_object()["/A"]["/URI"]
        for page in PdfReader(out).pages
        for annot in page.get("/Annots") or []
    }
    assert uris == {
        "https://linkedin.com/in/lucia-varela-demo",
        "https://github.com/lucia-varela-demo",
        "https://github.com/lucia-varela-demo/tfg-anomalias",
    }


@requires_chromium
@pytest.mark.parametrize("accent", ACCENTS)
def test_moderna_2col_renders_each_accent_color(tmp_path: Path, accent: str) -> None:
    template = templates.get("moderna-2col")
    out = html_engine.render_pdf(template, _context(accent), tmp_path / "cv.pdf", "A4")
    info = pdf.read_pdf(out)
    assert info.pages == 1
    assert pdf.missing_fonts(template.meta.fonts, info.fonts) == []
    # La barra lateral (abajo a la izquierda, sin texto) es del color elegido.
    png = preview.pdf_to_png(out, tmp_path / "cv.png")
    with Image.open(png) as image:
        pixel = image.convert("RGB").getpixel((15, image.height - 15))
    assert all(abs(a - b) <= 3 for a, b in zip(pixel, _rgb(accent), strict=True))


@requires_chromium
def test_moderna_2col_with_and_without_photo(tmp_path: Path) -> None:
    template = templates.get("moderna-2col")
    requests: list[tuple[str, bool]] = []
    log = lambda url, served: requests.append((url, served))  # noqa: E731

    html_engine.render_pdf(
        template, _context(), tmp_path / "con.pdf", "A4", _photo(tmp_path), on_request=log
    )
    served = {url.removeprefix(html_engine.ORIGIN + "/") for url, ok in requests if ok}
    assert html_engine.PHOTO_URL in served
    assert "style.css" in served and any(s.startswith("fonts/Lato") for s in served)

    requests.clear()
    html_engine.render_pdf(template, _context(), tmp_path / "sin.pdf", "A4", on_request=log)
    assert not any(html_engine.PHOTO_URL in url for url, _ok in requests)
    # Con foto, la primera página lleva una imagen más que sin ella.
    assert (tmp_path / "con.pdf").stat().st_size > (tmp_path / "sin.pdf").stat().st_size


@requires_chromium
def test_moderna_2col_shows_extra_sections_and_hides_empty(tmp_path: Path) -> None:
    template = templates.get("moderna-2col")
    ctx = _context()
    out = html_engine.render_pdf(template, ctx, tmp_path / "cv.pdf", "A4")

    # Los títulos llevan `letter-spacing`: pypdf los extrae con espacios entre letras.
    def squeezed(path: Path) -> str:
        return "".join(pdf.read_pdf(path).text.split()).upper()

    assert ctx["extra_sections"], "el perfil demo trae secciones extra"
    assert ctx["extra_sections"][0].title.upper() in squeezed(out)

    ctx["show"] = {**ctx["show"], "extra_sections": False, "projects": False}
    out = html_engine.render_pdf(template, ctx, tmp_path / "sin.pdf", "A4")
    assert ctx["extra_sections"][0].title.upper() not in squeezed(out)
    project = "".join(ctx["projects"][0]["name"].split()).upper()
    assert project not in squeezed(out)


@requires_chromium
def test_page_size_comes_from_render_options(tmp_path: Path) -> None:
    from pypdf import PdfReader

    template = templates.get("moderna-2col")
    out = html_engine.render_pdf(template, _context(), tmp_path / "cv.pdf", "Letter")
    box = PdfReader(out).pages[0].mediabox
    assert round(float(box.width) / 72 * 25.4) == 216
    assert round(float(box.height) / 72 * 25.4) == 279


@requires_chromium
def test_no_render_reaches_the_network(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Aunque el saneado fallase, Chromium no sale de `jh.local` ni sirve nada de fuera."""
    monkeypatch.setattr(html_engine.sanitize, "clean_html", lambda html: html)
    root = get_settings().user_templates_dir
    folder = html_template(
        root,
        "espia",
        '<html><head><link rel="stylesheet" href="style.css">'
        '<link rel="stylesheet" href="https://cdn.example.com/x.css"></head>'
        '<body><img src="http://tracker.example/p.png"><img src="//cdn.example.com/q.png">'
        '<img src="../../profile.yaml"><p>{{ name }}</p></body></html>',
        "body { background: url(http://bg.example/x.png); }",
    )
    (get_settings().data_dir / "profile.yaml").write_text("secreto: 1", encoding="utf-8")
    template = templates.Template(meta=templates.load_meta(folder), path=folder)
    requests: list[tuple[str, bool]] = []
    out = html_engine.render_pdf(
        template,
        _context(),
        tmp_path / "cv.pdf",
        "A4",
        on_request=lambda url, ok: requests.append((url, ok)),
    )
    assert out.is_file()
    served = [url for url, ok in requests if ok]
    assert served and all(url.startswith(html_engine.ORIGIN + "/") for url in served)
    assert not any("profile.yaml" in url for url in served)
    blocked = [url for url, ok in requests if not ok]
    assert any("tracker.example" in url for url in blocked)
    assert not any("bg.example" in url for url, _ok in requests)  # el CSS servido va saneado


@requires_chromium
def test_css_in_another_encoding_does_not_break_the_render(tmp_path: Path) -> None:
    folder = html_template(
        get_settings().user_templates_dir,
        "latin1",
        '<html><head><link rel="stylesheet" href="extra.css"></head><body>{{ name }}</body></html>',
    )
    (folder / "extra.css").write_bytes("/* café */ body { color: red; }".encode("latin-1"))
    template = templates.Template(meta=templates.load_meta(folder), path=folder)
    out = html_engine.render_pdf(template, _context(), tmp_path / "cv.pdf", "A4")
    assert pdf.read_pdf(out).pages == 1


@requires_chromium
def test_preview_and_validate_of_moderna_2col() -> None:
    assert authoring.validate("moderna-2col").engine == "html"
    result = authoring.preview_template(None, "moderna-2col", "demo")
    assert result.fits and result.warnings == []
    assert (get_settings().data_dir / result.png_path).is_file()
