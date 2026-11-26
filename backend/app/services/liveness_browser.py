"""«¿Sigue abierta?» con un navegador de verdad, cuando la página bloquea la petición ligera.

Algunos portales (Indeed, p. ej.) responden 401 o 403 a cualquier cliente que no sea un navegador.
Aquí se abre la página una vez en Chrome (o en el de `BROWSER_CHANNEL`) con la ventana fuera de la
pantalla y un perfil temporal: sin cookies, sin sesión y sin nada del perfil de las candidaturas.
No se hace clic en nada ni se intenta pasar un captcha o un control anti-bot: si aparece, quien
llama lo ve en el texto y da `unknown`.

El modo sin ventana (`headless`) no sirve: esos mismos portales lo detectan y lo bloquean.

Se ejecuta en un hilo propio: la API sync de Playwright no puede ir en un hilo con un bucle de
asyncio en marcha, y así tampoco choca con el navegador de las candidaturas.
"""

import logging
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Fuera de cualquier monitor: Windows no la enseña, aunque asome en la barra de tareas.
OFFSCREEN_ARGS = ["--window-position=-32000,-32000", "--window-size=1280,900"]
# Lo que no hace falta para leer el texto de la página.
SKIPPED_RESOURCES = frozenset({"image", "media", "font"})


@dataclass(frozen=True)
class RenderedPage:
    status: int | None
    final_url: str
    html: str
    redirected: bool


class BrowserUnavailableError(Exception):
    """No hay navegador que abrir (Playwright o Chrome sin instalar)."""


def _fetch(
    url: str,
    timeout_seconds: float,
    wait_seconds: float,
    allow: Callable[[str], bool],
) -> RenderedPage:
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import Request, Route, sync_playwright
    except ImportError as exc:  # pragma: no cover - Playwright va en las dependencias
        raise BrowserUnavailableError("Playwright no está instalado") from exc

    settings = get_settings()
    channels: list[str | None] = [settings.browser_channel or "chrome"]
    if channels[0] is not None:
        channels.append(None)  # el Chromium de Playwright, si está instalado
    with (
        sync_playwright() as playwright,
        tempfile.TemporaryDirectory(prefix="cai-liveness-", ignore_cleanup_errors=True) as profile,
    ):
        context = None
        for channel in channels:
            try:
                context = playwright.chromium.launch_persistent_context(
                    profile,
                    headless=False,
                    channel=channel,
                    locale="es-ES",
                    args=OFFSCREEN_ARGS,
                )
                break
            except PlaywrightError as exc:
                logger.info("No se pudo abrir el navegador %s: %s", channel or "chromium", exc)
        if context is None:
            raise BrowserUnavailableError("no hay Chrome ni Chromium que abrir")
        try:
            page = context.pages[0] if context.pages else context.new_page()

            def route(route_: Route, request: Request) -> None:
                # Solo se navega a direcciones que pasarían la comprobación de la petición
                # ligera (nada local, de red privada ni de LinkedIn), también tras redirigir.
                skipped = request.resource_type in SKIPPED_RESOURCES
                if skipped or (request.is_navigation_request() and not allow(request.url)):
                    route_.abort()
                else:
                    route_.continue_()

            page.route("**/*", route)
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_seconds * 1000)
            if wait_seconds:
                page.wait_for_timeout(wait_seconds * 1000)
            redirected = bool(response and response.request.redirected_from) or (
                page.url.rstrip("/") != url.rstrip("/")
            )
            return RenderedPage(
                status=response.status if response else None,
                final_url=page.url,
                html=page.content(),
                redirected=redirected,
            )
        finally:
            context.close()


def fetch_rendered(
    url: str,
    timeout_seconds: float,
    wait_seconds: float,
    allow: Callable[[str], bool],
) -> RenderedPage:
    """Abre `url` en el navegador fuera de la pantalla y devuelve el HTML ya pintado.

    `allow(url)` decide a qué direcciones se puede navegar. Lanza `BrowserUnavailableError` si no
    hay navegador y deja pasar los errores de Playwright (red, tiempo agotado) como `Exception`.
    """
    outcome: dict[str, object] = {}

    def run() -> None:
        try:
            outcome["page"] = _fetch(url, timeout_seconds, wait_seconds, allow)
        except Exception as exc:  # se relanza en el hilo de quien llama
            outcome["error"] = exc

    thread = threading.Thread(target=run, name="cai-liveness-browser", daemon=True)
    thread.start()
    thread.join(timeout_seconds * 2 + wait_seconds + 60)
    if thread.is_alive():
        raise TimeoutError("el navegador no respondió a tiempo")
    if isinstance(outcome.get("error"), BaseException):
        raise outcome["error"]  # type: ignore[misc]
    page = outcome.get("page")
    assert isinstance(page, RenderedPage)
    return page
