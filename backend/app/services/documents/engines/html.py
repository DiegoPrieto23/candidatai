"""Motor html: contexto del contrato → Jinja2 → HTML saneado → PDF con Chromium.

- Jinja2 en un `SandboxedEnvironment` con autoescape: el texto del perfil y del agente no puede
  inyectar etiquetas, y la plantilla (que puede venir de un CV ajeno) no llega a atributos
  internos de Python.
- El HTML generado pasa por `sanitize.clean_html` antes de imprimirse. Después, y solo entonces,
  los enlaces del perfil (`context.links`) pasan a ser `<a href>`: la plantilla no puede
  poner enlaces externos, el código sí.
- Chromium (Playwright) imprime sin JavaScript y sin red: la página se carga desde un origen
  virtual (`http://cai.local/`) y cada petición se sirve solo desde la carpeta de la plantilla, sus
  `fonts/` (o `data/fonts/`) y la foto ya recortada. Cualquier otra se aborta.
- El tamaño de página y los márgenes los pone el CSS (`@page`); el tamaño se fuerza con el de las
  opciones de render.
"""

import asyncio
import concurrent.futures
import mimetypes
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import lxml.html
from jinja2 import FileSystemLoader, StrictUndefined, select_autoescape
from jinja2.sandbox import SandboxedEnvironment

from app.core.config import get_settings
from app.schemas.cv import PageSize
from app.services.documents import sanitize
from app.services.documents.context import links, split_links
from app.services.documents.pdf import PdfConversionError, PdfConverterUnavailableError
from app.services.documents.templates import Template

ORIGIN = "http://cai.local"
PAGE_URL = f"{ORIGIN}/index.html"
# Nombre con el que la plantilla ve la foto: `<img src="{{ photo }}">`.
PHOTO_URL = "cai-photo.png"
RENDER_TIMEOUT_MS = 60_000
# Tipos fijos: `mimetypes` en Windows depende del registro.
MIME_TYPES = {
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".svg": "image/svg+xml",
}

RequestLog = Callable[[str, bool], None]  # (url, servida)


class HtmlRenderError(PdfConversionError):
    """Chromium no pudo imprimir: `pdf_failed`, como un fallo de LibreOffice."""


class ChromiumUnavailableError(PdfConverterUnavailableError):
    """Falta Chromium: `pdf_unavailable` (`cai doctor` dice cómo instalarlo)."""


def environment(folder: Path) -> SandboxedEnvironment:
    return SandboxedEnvironment(
        loader=FileSystemLoader(folder),
        autoescape=select_autoescape(default=True, default_for_string=True),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_string(
    template: Template, context: dict[str, Any], photo_path: Path | None, file: str | None = None
) -> str:
    """El HTML de la plantilla con el contexto, ya saneado."""
    values = dict(context)
    values["photo"] = PHOTO_URL if photo_path is not None else ""
    name = file or template.engine_file.name
    html = environment(template.path).get_template(name).render(values)
    return sanitize.clean_html(html)


# Donde un texto nunca se convierte en enlace.
_NO_LINK_TAGS = frozenset({"a", "head", "title", "style", "script", "textarea"})


def add_links(html: str, targets: dict[str, str]) -> str:
    """Envuelve en `<a href>` los textos de `targets` que aparecen en el documento ya saneado."""
    if not targets or not any(text in html for text in targets):
        return html

    def pieces(text: str | None) -> list[tuple[str, str | None]] | None:
        """Los trozos de `text`, o `None` si no tiene ningún enlace."""
        parts = split_links(text or "", targets)
        return parts if any(url for _, url in parts) else None

    def anchor(text: str, url: str) -> lxml.html.HtmlElement:
        element = lxml.html.Element("a", href=url)
        element.text = text
        return element

    root = lxml.html.document_fromstring(html)
    for element in list(root.iter()):
        if not isinstance(element.tag, str) or any(
            str(e.tag).lower() in _NO_LINK_TAGS for e in (element, *element.iterancestors())
        ):
            continue
        children = list(element)
        parts = pieces(element.text)
        if parts:
            element.text = None
            previous: lxml.html.HtmlElement | None = None
            index = 0
            for text, url in parts:
                if url is not None:
                    previous = anchor(text, url)
                    element.insert(index, previous)
                    index += 1
                elif previous is None:
                    element.text = (element.text or "") + text
                else:
                    previous.tail = (previous.tail or "") + text
        for child in children:
            parts = pieces(child.tail)
            if parts:
                child.tail = None
                previous = child
                for text, url in parts:
                    if url is None:
                        previous.tail = (previous.tail or "") + text
                    else:
                        link = anchor(text, url)
                        previous.addnext(link)
                        previous = link
    return lxml.html.tostring(root, doctype="<!DOCTYPE html>", encoding="unicode")


def _inside(root: Path, relative: str) -> Path | None:
    candidate = (root / relative).resolve()
    if candidate.is_relative_to(root.resolve()) and candidate.is_file():
        return candidate
    return None


def resource_resolver(folder: Path, photo_path: Path | None) -> Callable[[str], Path | None]:
    """Qué fichero local sirve cada ruta pedida (`None`: no se sirve)."""
    fonts_dir = get_settings().data_dir / "fonts"

    def resolve(path: str) -> Path | None:
        if path == PHOTO_URL:
            return photo_path
        found = _inside(folder, path)
        if found is None and path.startswith("fonts/"):
            found = _inside(fonts_dir, path.removeprefix("fonts/"))
        return found

    return resolve


def _page_size_css(page_size: PageSize | None) -> str:
    return f"<style>@page {{ size: {page_size}; }}</style>" if page_size else ""


def _with_page_size(html: str, page_size: PageSize | None) -> str:
    extra = _page_size_css(page_size)
    if not extra:
        return html
    lower = html.lower()
    at = lower.rfind("</head>")
    return html[:at] + extra + html[at:] if at >= 0 else extra + html


def _print(
    html: str,
    resolve: Callable[[str], Path | None],
    output: Path,
    on_request: RequestLog | None,
) -> None:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import Route, sync_playwright
    except ImportError as exc:  # pragma: no cover - dependencia del proyecto
        raise ChromiumUnavailableError("Falta Playwright: `uv sync`.") from exc

    page_bytes = html.encode("utf-8")

    def handle(route: Route) -> None:
        url = route.request.url
        parts = urlsplit(url)
        local = f"{parts.scheme}://{parts.netloc}" == ORIGIN
        relative = unquote(parts.path.lstrip("/"))
        if local and relative == "index.html":
            if on_request:
                on_request(url, True)
            route.fulfill(status=200, content_type="text/html; charset=utf-8", body=page_bytes)
            return
        file = resolve(relative) if local else None
        if on_request:
            on_request(url, file is not None)
        if file is None:
            route.abort("blockedbyclient")
            return
        try:
            suffix = file.suffix.lower()
            if suffix == ".css":
                css = file.read_text(encoding="utf-8", errors="replace")
                body = sanitize.clean_css(css).encode("utf-8")
                mime = "text/css; charset=utf-8"
            else:
                body = file.read_bytes()
                mime = MIME_TYPES.get(suffix) or mimetypes.guess_type(file.name)[0] or ""
            route.fulfill(status=200, content_type=mime or "application/octet-stream", body=body)
        except OSError:
            route.abort("failed")  # un fichero ilegible no debe dejar la página esperando

    try:
        with sync_playwright() as pw:
            try:
                # Sin resolución de nombres: si algo escapase a `route`, tampoco saldría a la red.
                browser = pw.chromium.launch(
                    args=["--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE cai.local"]
                )
            except PlaywrightError as exc:
                raise ChromiumUnavailableError(
                    "Playwright no encuentra Chromium: ejecuta "
                    "`uv run --directory backend playwright install chromium`. "
                    f"({str(exc).splitlines()[0]})"
                ) from exc
            try:
                ctx = browser.new_context(
                    java_script_enabled=False,
                    service_workers="block",
                    accept_downloads=False,
                )
                ctx.set_default_timeout(RENDER_TIMEOUT_MS)  # también para `page.pdf`
                ctx.route("**/*", handle)
                page = ctx.new_page()
                page.goto(PAGE_URL, wait_until="load")
                output.parent.mkdir(parents=True, exist_ok=True)
                page.pdf(path=str(output), prefer_css_page_size=True, print_background=True)
            finally:
                browser.close()
    except (ChromiumUnavailableError, HtmlRenderError):
        raise
    except PlaywrightError as exc:
        raise HtmlRenderError(f"Chromium no pudo imprimir el PDF: {exc}") from exc


def html_to_pdf(
    html: str,
    resolve: Callable[[str], Path | None],
    output: Path,
    page_size: PageSize | None = None,
    on_request: RequestLog | None = None,
    targets: dict[str, str] | None = None,
) -> Path:
    """Imprime `html` a PDF sin red ni JavaScript. `resolve` decide qué ficheros se sirven.

    `targets`: textos que pasan a ser enlaces (`context.links`), después del último saneado.
    """
    document = _with_page_size(add_links(sanitize.clean_html(html), targets or {}), page_size)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        _print(document, resolve, output, on_request)
    else:
        # La API síncrona de Playwright no funciona dentro de un bucle asyncio: otro hilo.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(_print, document, resolve, output, on_request).result()
    return output


def render_pdf(
    template: Template,
    context: dict[str, Any],
    output: Path,
    page_size: PageSize,
    photo_path: Path | None = None,
    on_request: RequestLog | None = None,
    file: Path | None = None,
) -> Path:
    """Renderiza la plantilla html (o `file`, p. ej. su carta) y escribe el PDF en `output`."""
    html = render_string(template, context, photo_path, file.name if file else None)
    resolve = resource_resolver(template.path, photo_path)
    return html_to_pdf(html, resolve, output, page_size, on_request, links(context))
