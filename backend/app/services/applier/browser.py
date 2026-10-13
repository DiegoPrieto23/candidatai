"""El navegador de las candidaturas: contexto persistente de Playwright en `data/browser-profile/`.

- Visible (salvo `CAI_BROWSER_HEADLESS`, para los tests): ahí inicias tú las sesiones que quieras,
  resuelves un captcha o terminas una candidatura.
- Lo abre y lo usa solo el worker: el perfil solo admite un proceso a la vez y la página rellenada
  tiene que seguir viva hasta que confirmes el envío.
- La API síncrona de Playwright queda atada al hilo que la arranca, así que todas las llamadas
  pasan por un hilo propio (`BrowserHost.call`), sea cual sea el hilo del worker que las pide.
- Si cierras la ventana, el siguiente uso lo vuelve a abrir (las pestañas preparadas se pierden).
- `CAI_BROWSER_CHANNEL` (`chrome`, `msedge`) usa el navegador instalado en vez de Chromium.

Sin trucos anti-detección: si una web pide demostrar que eres humano, se te pasa la pestaña.
"""

import atexit
import contextlib
import queue
import threading
from collections.abc import Callable
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright

from app.core.config import get_settings
from app.core.policies import get_policies

T = TypeVar("T")


class BrowserUnavailableError(RuntimeError):
    pass


@dataclass
class PreparedPage:
    job_id: int
    page: Page


@dataclass
class BrowserState:
    """Lo que vive en el hilo del navegador. Solo se toca desde `BrowserHost.call`."""

    playwright: Playwright
    profile_dir: Path
    headless: bool
    channel: str | None
    step_timeout_ms: float
    context: BrowserContext | None = None
    pages: dict[int, PreparedPage] = field(default_factory=dict)  # intento -> pestaña

    def ensure_context(self) -> BrowserContext:
        if self.context is not None:
            try:  # si cerraste la ventana, el aviso de cierre puede no haber llegado aún: una
                # llamada que va hasta el navegador falla si ya no está
                self.context.cookies("about:blank")
            except Exception:
                with contextlib.suppress(Exception):
                    self.context.close()
                self._closed()
        if self.context is None:
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            try:
                context = self.playwright.chromium.launch_persistent_context(
                    str(self.profile_dir),
                    headless=self.headless,
                    channel=self.channel,
                    no_viewport=not self.headless,
                    accept_downloads=False,
                )
            except Exception as exc:
                raise BrowserUnavailableError(
                    "No se pudo abrir el navegador: "
                    f"{str(exc).splitlines()[0]}. Si falta Chromium: "
                    "`uv run --directory backend playwright install chromium`. Si ya hay otro "
                    "navegador con el perfil de CandidatAI abierto, ciérralo."
                ) from exc
            context.set_default_timeout(self.step_timeout_ms)
            context.set_default_navigation_timeout(self.step_timeout_ms)
            context.on("close", lambda _ctx: self._closed())
            self.context = context
        return self.context

    def _closed(self) -> None:
        self.context = None
        self.pages.clear()

    def new_page(self, attempt_id: int, job_id: int) -> Page:
        """Una pestaña para el intento. Cierra las de intentos anteriores de la misma oferta."""
        context = self.ensure_context()
        for other_id, prepared in list(self.pages.items()):
            if prepared.job_id == job_id and other_id != attempt_id:
                self.pages.pop(other_id)
                if not prepared.page.is_closed():
                    prepared.page.close()
        page = context.new_page()  # nunca una pestaña tuya
        self.pages[attempt_id] = PreparedPage(job_id=job_id, page=page)
        return page

    def page_for(self, attempt_id: int) -> Page | None:
        prepared = self.pages.get(attempt_id)
        if prepared is None or prepared.page.is_closed():
            return None
        return prepared.page


_STOP = object()


class BrowserHost:
    """Un hilo con Playwright y una cola de órdenes."""

    def __init__(self, profile_dir: Path, headless: bool, channel: str | None) -> None:
        self.profile_dir = profile_dir
        self.headless = headless
        self.channel = channel
        self._queue: queue.Queue[Any] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def call(self, fn: Callable[[BrowserState], T]) -> T:
        """Ejecuta `fn` en el hilo del navegador y devuelve su resultado (o su excepción)."""
        thread = self._start()
        future: Future[T] = Future()
        self._queue.put((fn, future))
        # Si el hilo muere (Playwright no arranca), nadie resolvería la orden: el worker se
        # quedaría colgado. Se espera a ratos comprobando que siga vivo.
        while True:
            try:
                return future.result(timeout=1)
            except FutureTimeout:
                if not thread.is_alive() and not future.done():
                    raise BrowserUnavailableError(
                        "El navegador de las candidaturas se ha cerrado inesperadamente."
                    ) from None

    def _start(self) -> threading.Thread:
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(
                    target=self._run, name="candidatai-browser", daemon=True
                )
                self._thread.start()
            return self._thread

    def _run(self) -> None:
        try:
            self._serve()
        except BaseException as exc:
            # Playwright no arrancó o el hilo cayó: se resuelven las órdenes pendientes con error.
            error = BrowserUnavailableError(f"No se pudo usar el navegador: {exc}")
            while True:
                try:
                    item = self._queue.get_nowait()
                except queue.Empty:
                    break
                if item is not _STOP:
                    item[1].set_exception(error)

    def _serve(self) -> None:
        timeout_ms = get_policies().applier.step_timeout_seconds * 1000
        with sync_playwright() as pw:
            state = BrowserState(
                playwright=pw,
                profile_dir=self.profile_dir,
                headless=self.headless,
                channel=self.channel,
                step_timeout_ms=timeout_ms,
            )
            while True:
                item = self._queue.get()
                if item is _STOP:
                    break
                fn, future = item
                try:
                    future.set_result(fn(state))
                except BaseException as exc:
                    future.set_exception(exc)
            if state.context is not None:
                with contextlib.suppress(Exception):
                    state.context.close()

    def close(self) -> None:
        with self._lock:
            thread = self._thread
            self._thread = None
        if thread is not None and thread.is_alive():
            self._queue.put(_STOP)
            thread.join(timeout=30)


_host: BrowserHost | None = None
_host_lock = threading.Lock()


def get_host() -> BrowserHost:
    """El navegador de este proceso (el worker). Se crea al primer uso."""
    global _host
    with _host_lock:
        if _host is None:
            settings = get_settings()
            _host = BrowserHost(
                settings.browser_profile_dir, settings.browser_headless, settings.browser_channel
            )
            atexit.register(shutdown_host)
        return _host


def shutdown_host() -> None:
    global _host
    with _host_lock:
        host, _host = _host, None
    if host is not None:
        host.close()
