"""La web del proyecto (`site/`): mismas secciones en los dos idiomas, nada de otros dominios y
`scripts/build_site.py` arma `_site/` con todo lo que referencia.

Los casos de error montan un repositorio pequeño en una carpeta temporal."""

from __future__ import annotations

import importlib.util
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from types import ModuleType

import pytest

from app.core.config import REPO_ROOT

SITE = REPO_ROOT / "site"
PAGES = {"es": SITE / "index.html", "en": SITE / "en" / "index.html"}
BASE_URL = "https://diegoprieto23.github.io/candidatai/"


def _load(name: str) -> ModuleType:
    scripts = str(REPO_ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "scripts" / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


build_site = _load("build_site")
check_links = _load("check_links")


class _Page(HTMLParser):
    """Lo que interesa de una página: idioma, secciones, ids, anclas y lo que carga."""

    def __init__(self) -> None:
        super().__init__()
        self.lang = ""
        self.sections: list[str] = []
        self.ids: list[str] = []
        self.anchors: list[str] = []
        self.loads: list[tuple[str, str]] = []  # (etiqueta, url) que el navegador pide solo
        self.hreflang: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if tag == "html":
            self.lang = a.get("lang", "")
        if "id" in a:
            self.ids.append(a["id"])
            if tag == "section":
                self.sections.append(a["id"])
        if tag == "a" and a.get("href", "").startswith("#"):
            self.anchors.append(a["href"])
        if tag in ("img", "script", "source", "iframe", "video", "audio") and a.get("src"):
            self.loads.append((tag, a["src"]))
        for part in a.get("srcset", "").split(","):
            if part.strip():
                self.loads.append((tag, part.strip().split()[0]))
        if tag == "link":
            rel = a.get("rel", "")
            if rel == "alternate" and a.get("hreflang"):
                self.hreflang[a["hreflang"]] = a.get("href", "")
            elif rel not in ("canonical", "alternate"):
                self.loads.append((f"link {rel}", a.get("href", "")))


def _parse(path: Path) -> _Page:
    page = _Page()
    page.feed(path.read_text(encoding="utf-8"))
    return page


def test_both_languages_have_the_same_sections_and_anchors() -> None:
    es, en = _parse(PAGES["es"]), _parse(PAGES["en"])
    assert es.sections == en.sections
    assert {"how", "honest", "features", "privacy", "tour", "install", "limits"} <= set(es.sections)
    assert sorted(es.ids) == sorted(en.ids)
    assert es.anchors == en.anchors
    for page in (es, en):
        assert len(page.ids) == len(set(page.ids)), "ids repetidos"
        for anchor in page.anchors:
            assert anchor[1:] in page.ids, anchor


def test_language_attributes_and_alternates() -> None:
    es, en = _parse(PAGES["es"]), _parse(PAGES["en"])
    assert es.lang == "es"
    assert en.lang == "en"
    expected = {"es": BASE_URL, "en": f"{BASE_URL}en/", "x-default": BASE_URL}
    assert es.hreflang == expected
    assert en.hreflang == expected


def test_site_loads_nothing_from_other_domains() -> None:
    external = re.compile(r"^(?:[a-z][a-z0-9+.-]*:)?//", re.I)
    for path in PAGES.values():
        page = _parse(path)
        assert page.loads, path
        for tag, url in page.loads:
            assert not external.match(url), f"{path.name}: {tag} carga {url}"
        assert "Content-Security-Policy" in path.read_text(encoding="utf-8")
    for css in SITE.rglob("*.css"):
        text = css.read_text(encoding="utf-8")
        assert "@import" not in text
        for url in re.findall(r"url\(\s*['\"]?([^'\")]+)", text):
            assert not external.match(url), f"{css.name}: {url}"
    for js in SITE.rglob("*.js"):
        text = js.read_text(encoding="utf-8")
        assert not re.search(r"\b(?:fetch|XMLHttpRequest|import\s*\(|sendBeacon)\b", text), js.name
        assert "document.cookie" not in text


def test_build_produces_every_referenced_file(tmp_path: Path) -> None:
    out, errors = build_site.build(REPO_ROOT, tmp_path / "_site")
    assert errors == []
    assert (out / "index.html").is_file()
    assert (out / "en" / "index.html").is_file()
    assert not list(out.rglob("*.md"))
    version = build_site.version(REPO_ROOT)
    copied_images: set[str] = set()
    for page in out.rglob("*.html"):
        rel = page.relative_to(out).as_posix()
        text = page.read_text(encoding="utf-8")
        assert "{{" not in text, rel
        assert f"v{version}" in text, rel
        for ref in build_site.references(text):
            target = build_site.local_target(ref, rel)
            if target is not None:
                assert (out / target).is_file(), f"{rel}: {ref}"
                if target.startswith("img/"):
                    copied_images.add(target)
    # Solo las imágenes que se usan: docs/img/ no se duplica entera.
    assert {p.relative_to(out).as_posix() for p in (out / "img").rglob("*") if p.is_file()} == (
        copied_images
    )


def _mini_repo(root: Path, page: str) -> Path:
    (root / "backend").mkdir(parents=True)
    (root / "backend" / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "9.8.7"\n', encoding="utf-8"
    )
    (root / "docs" / "img" / "es").mkdir(parents=True)
    (root / "docs" / "img" / "es" / "home.webp").write_bytes(b"RIFF")
    (root / "site").mkdir()
    (root / "site" / "index.html").write_text(page, encoding="utf-8")
    (root / "site" / "README.md").write_text("notas", encoding="utf-8")
    return root


def test_build_fills_the_version_and_mounts_images(tmp_path: Path) -> None:
    root = _mini_repo(
        tmp_path / "repo",
        '<p id="a">v{{version}}</p><a href="#a">x</a><img src="img/es/home.webp" alt="">',
    )
    out, errors = build_site.build(root, tmp_path / "out")
    assert errors == []
    assert "v9.8.7" in (out / "index.html").read_text(encoding="utf-8")
    assert (out / "img" / "es" / "home.webp").read_bytes() == b"RIFF"
    assert not (out / "README.md").exists()
    assert check_links.site_missing(root)[1] == []


@pytest.mark.parametrize(
    ("page", "error"),
    [
        ('<img src="img/es/nope.webp" alt="">', "nope.webp"),
        ("<p>{{missing}}</p>", "{{missing}}"),
        ('<link rel="stylesheet" href="assets/none.css">', "assets/none.css"),
    ],
)
def test_build_fails_on_what_is_missing(tmp_path: Path, page: str, error: str) -> None:
    root = _mini_repo(tmp_path / "repo", page)
    _, errors = build_site.build(root, tmp_path / "out")
    assert any(error in line for line in errors), errors


def test_check_links_catches_broken_images_and_anchors(tmp_path: Path) -> None:
    root = _mini_repo(
        tmp_path / "repo",
        '<a href="#nowhere">x</a><img src="img/es/gone.webp" alt=""><a href="en/">en</a>',
    )
    _, missing = check_links.site_missing(root)
    assert any("#nowhere" in line for line in missing)
    assert any("gone.webp" in line for line in missing)
    assert any("en/" in line for line in missing)


def test_every_image_from_docs_carries_its_provisional_marker_or_none() -> None:
    """Hasta los medios definitivos, cada imagen de docs/img/ lleva el marcador justo antes."""
    marker = "<!-- media:provisional -->"
    for path in PAGES.values():
        lines = path.read_text(encoding="utf-8").splitlines()
        media = re.compile(r'(?:src|srcset|content)="[^"]*img/')
        uses = [i for i, line in enumerate(lines) if media.search(line)]
        marked = [i for i in uses if lines[i - 1].strip() == marker]
        unmarked = [lines[i].strip() for i in uses if i not in marked]
        # O todas marcadas (medios provisionales) o ninguna (definitivos): nunca a medias.
        assert marked in (uses, []), f"{path.name}: {unmarked}"


def test_social_metadata_points_to_an_existing_image() -> None:
    for lang, path in PAGES.items():
        text = path.read_text(encoding="utf-8")
        canonical = re.search(r'rel="canonical" href="([^"]+)"', text)
        og_url = re.search(r'property="og:url" content="([^"]+)"', text)
        assert canonical and og_url and canonical.group(1) == og_url.group(1)
        assert 'name="twitter:card" content="summary_large_image"' in text
        locale = {"es": "es_ES", "en": "en_US"}[lang]
        assert f'property="og:locale" content="{locale}"' in text
        for prop in ('property="og:image"', 'name="twitter:image"'):
            found = re.search(prop + r' content="([^"]+)"', text)
            assert found and found.group(1).startswith(f"{BASE_URL}img/")
            assert (REPO_ROOT / "docs" / found.group(1)[len(BASE_URL) :]).is_file()


def test_accessibility_basics() -> None:
    css = (SITE / "assets" / "site.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css
    assert ":focus-visible" in css
    for path in PAGES.values():
        text = path.read_text(encoding="utf-8")
        assert re.search(r'<a class="skip" href="#main">', text)
        assert 'id="main"' in text
        assert "data-label-dark=" in text and "data-label-light=" in text
        tab = r'role="tab" id="([^"]+)" aria-controls="([^"]+)" aria-selected="(\w+)"'
        tabs = re.findall(tab, text)
        assert tabs
        for tab, panel in ((t, p) for t, p, _ in tabs):
            assert f'id="{panel}" aria-labelledby="{tab}"' in text, panel
        for group in text.split('role="tablist"')[1:]:
            head = group.split("</div>")[0]
            group_tabs = re.findall(r'role="tab"[^>]*aria-selected="(\w+)"', head)
            assert group_tabs.count("true") == 1


def test_nothing_inline_that_the_content_policy_would_block() -> None:
    for path in PAGES.values():
        text = path.read_text(encoding="utf-8")
        assert 'style="' not in text
        assert "<style" not in text
        assert not re.search(r"<script(?![^>]*\bsrc=)", text)
        assert not re.search(r"\bon[a-z]+=\"", text)  # onclick=…


def test_build_mounts_images_referenced_from_css_and_fills_js(tmp_path: Path) -> None:
    root = _mini_repo(tmp_path / "repo", '<link rel="stylesheet" href="assets/a.css">')
    (root / "site" / "assets").mkdir()
    (root / "site" / "assets" / "a.css").write_text(
        'body { background: url("../img/es/home.webp?v=1#x"); }', encoding="utf-8"
    )
    (root / "site" / "assets" / "a.js").write_text('const v = "{{version}}";', encoding="utf-8")
    out, errors = build_site.build(root, tmp_path / "out")
    assert errors == []
    assert (out / "img" / "es" / "home.webp").is_file()
    assert '"9.8.7"' in (out / "assets" / "a.js").read_text(encoding="utf-8")


def test_build_refuses_to_wipe_a_folder_it_did_not_create(tmp_path: Path) -> None:
    root = _mini_repo(tmp_path / "repo", "<p>x</p>")
    precious = tmp_path / "precious"
    precious.mkdir()
    (precious / "keep.txt").write_text("no me borres", encoding="utf-8")
    _, errors = build_site.build(root, precious)
    assert errors and (precious / "keep.txt").is_file()
    # Una web armada antes sí se vuelve a armar.
    again = tmp_path / "web"
    assert build_site.build(root, again)[1] == []
    assert build_site.build(root, again)[1] == []


def test_main_exit_codes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert build_site.main(["--out", str(tmp_path / "ok")]) == 0
    root = _mini_repo(tmp_path / "repo", '<img src="img/es/nope.webp" alt="">')
    monkeypatch.setattr(build_site, "ROOT", root)
    assert build_site.main(["--out", str(tmp_path / "bad")]) == 1
    monkeypatch.setattr(check_links, "ROOT", REPO_ROOT)
    monkeypatch.setattr(sys, "argv", ["check_links.py", "--site"])
    assert check_links.main() == 0
