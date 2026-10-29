"""Fixtures de las E2E: la app arrancada sobre una carpeta temporal (con la demo o vacía) y un
Chromium sin ventana con un contexto por test, que falla ante errores que no se ven en pantalla.

La demo se siembra una vez por sesión y cada módulo arranca su app sobre una copia: un módulo que
cambia datos no ensucia a los demás. Si un test necesita datos solo suyos, que use `fresh_demo_app`.
"""

import os
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import pytest
from playwright.sync_api import Browser, ConsoleMessage, Page, Playwright, Response, sync_playwright

from tests.e2e import harness

VIEWPORT = {"width": 1440, "height": 900}
LOCALES = {"es": "es-ES", "en": "en-GB"}

# Nada sale a internet: el navegador pasa por un proxy muerto y cada contexto corta lo que no vaya
# a 127.0.0.1 o localhost.
LOCAL_ONLY = re.compile(r"^(?!https?://(127\.0\.0\.1|localhost)[:/])")
# Lo esperado, que no cuenta como error. Cada entrada, con su porqué.
EXTERNAL_LOAD_FAILED = re.compile(r"^Failed to load resource: net::ERR_")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # Todo lo de esta carpeta es E2E, aunque un módulo olvide el marcador. Salvo el instalador
    # (`e2e_install`), que tarda minutos: solo con `-m e2e_install`.
    for item in items:
        in_folder = Path(str(item.fspath)).is_relative_to(Path(__file__).parent)
        if in_folder and item.get_closest_marker("e2e_install") is None:
            item.add_marker(pytest.mark.e2e)


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[None]) -> Iterator[None]:
    report = yield
    # Para que la fixture del navegador sepa, al cerrar, si el test falló.
    setattr(item, f"report_{report.when}", report)
    return report


@pytest.fixture(scope="session", autouse=True)
def _ui_built() -> None:
    if not harness.ui_built():
        if os.environ.get("CI"):  # en la CI, saltarlas dejaría el job en verde sin probar nada
            pytest.fail("Falta frontend/dist/index.html: el job tiene que ejecutar `pnpm build`")
        pytest.skip(
            "Falta la UI compilada (frontend/dist/index.html): ejecuta `pnpm build` en frontend/"
        )


@pytest.fixture(scope="session")
def demo_seed(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """La demo sembrada una vez con `cai demo seed`; nadie arranca la app sobre ella."""
    root = tmp_path_factory.mktemp("e2e-seed")
    data_dir = root / "data"
    harness.seed_demo(data_dir)
    yield data_dir
    harness.remove_dir(root)


class AppFactory(Protocol):
    def __call__(self, seed: Path | None, **kwargs: Any) -> harness.AppServer: ...


@pytest.fixture(scope="session")
def _start_app(tmp_path_factory: pytest.TempPathFactory) -> Iterator[AppFactory]:
    """Arranca una app en una carpeta temporal nueva, vacía o copia de `seed`, y la para y la
    borra al cerrar el ámbito que la pidió (ver `_scoped_app`)."""
    started: list[tuple[harness.AppServer, Path]] = []

    def start(seed: Path | None, **kwargs: Any) -> harness.AppServer:
        root = tmp_path_factory.mktemp("e2e-app")
        data_dir = root / "data"
        try:
            if seed is not None:
                harness.copy_data(seed, data_dir)
            server = harness.start_app(data_dir, **kwargs)
        except BaseException:
            harness.remove_dir(root)
            raise
        started.append((server, root))
        return server

    yield start
    for server, root in started:  # por si algo quedó vivo
        harness.stop_app(server)
        harness.remove_dir(root)


def _scoped_app(start: AppFactory, seed: Path | None, **kwargs: Any) -> Iterator[harness.AppServer]:
    server = start(seed, **kwargs)
    try:
        yield server
    finally:
        harness.stop_app(server)
        harness.remove_dir(server.data_dir.parent)


@pytest.fixture(scope="module")
def app_extra_env() -> dict[str, str]:
    """Variables de más para las apps de un módulo: el módulo la redefine si las necesita (un
    servidor local de la fixture, p. ej.)."""
    return {}


@pytest.fixture(scope="module")
def demo_app(
    _start_app: AppFactory, demo_seed: Path, app_extra_env: dict[str, str]
) -> Iterator[harness.AppServer]:
    """La app con la demo, compartida por los tests de un módulo."""
    yield from _scoped_app(_start_app, demo_seed, extra_env=app_extra_env)


@pytest.fixture
def fresh_demo_app(
    _start_app: AppFactory, demo_seed: Path, app_extra_env: dict[str, str]
) -> Iterator[harness.AppServer]:
    """La app con la demo, solo para este test (para los que cambian datos)."""
    yield from _scoped_app(_start_app, demo_seed, extra_env=app_extra_env)


@pytest.fixture
def empty_app(_start_app: AppFactory, app_extra_env: dict[str, str]) -> Iterator[harness.AppServer]:
    """La app en una carpeta vacía: el primer arranque, sin perfil ni ofertas."""
    yield from _scoped_app(_start_app, None, extra_env=app_extra_env)


@pytest.fixture(scope="module")
def empty_shared_app(
    _start_app: AppFactory, app_extra_env: dict[str, str]
) -> Iterator[harness.AppServer]:
    """La app vacía compartida por los tests de un módulo que solo miran (estados vacíos)."""
    yield from _scoped_app(_start_app, None, extra_env=app_extra_env)


# --- Navegador ----------------------------------------------------------------------------------


@pytest.fixture(scope="session")
def playwright() -> Iterator[Playwright]:
    with sync_playwright() as pw:
        yield pw


@pytest.fixture(scope="session")
def browser(playwright: Playwright) -> Iterator[Browser]:
    browser = playwright.chromium.launch(
        headless=True, proxy={"server": harness.DEAD_PROXY, "bypass": "127.0.0.1,localhost"}
    )
    yield browser
    browser.close()


@pytest.fixture
def lang(request: pytest.FixtureRequest) -> str:
    """Idioma de la UI: español salvo `@pytest.mark.parametrize("lang", ["en"], indirect=True)`."""
    return str(getattr(request, "param", "es"))


@dataclass
class PageErrors:
    """Lo que falla sin verse: errores de consola, excepciones y respuestas 5xx de la API."""

    base_url: str
    console: list[str] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    responses: list[str] = field(default_factory=list)
    log: list[str] = field(default_factory=list)

    def on_console(self, message: ConsoleMessage) -> None:
        self.log.append(f"[{message.type}] {message.text}")
        if message.type == "error" and not self._expected(message):
            self.console.append(message.text)

    def _expected(self, message: ConsoleMessage) -> bool:
        # Un recurso de internet (un logo, una fuente) que se ha cortado: no es un fallo de la app.
        # Uno de la propia app que no carga, sí.
        url = str(message.location.get("url", ""))
        return bool(EXTERNAL_LOAD_FAILED.search(message.text)) and not url.startswith(self.base_url)

    def on_exception(self, error: Exception) -> None:
        self.exceptions.append(str(error))
        self.log.append(f"[pageerror] {error}")

    def on_response(self, response: Response) -> None:
        if response.status >= 500 and response.url.startswith(self.base_url):
            self.responses.append(f"{response.status} {response.request.method} {response.url}")

    def problems(self) -> list[str]:
        return (
            [f"console.error: {m}" for m in self.console]
            + [f"excepción sin capturar: {m}" for m in self.exceptions]
            + [f"respuesta {m}" for m in self.responses]
        )


def _artifact_dir(item: pytest.Item) -> Path:
    name = re.sub(r"[^\w.-]+", "_", item.nodeid.split("::", 1)[-1])[:120]
    path = harness.ARTIFACTS / name
    harness.remove_dir(path)
    path.mkdir(parents=True)
    return path


@pytest.fixture
def page_errors() -> PageErrors:
    return PageErrors("")


@pytest.fixture
def page(
    request: pytest.FixtureRequest, browser: Browser, lang: str, page_errors: PageErrors
) -> Iterator[Page]:
    """Una pestaña en un contexto nuevo, sin ventana, en escritorio y en `lang`. Para la app del
    test (`demo_app`, `fresh_demo_app`, `empty_app` o `empty_shared_app`), `base_url` apunta a
    ella: `page.goto("/")`.

    Al cerrar, falla si hubo errores invisibles; si el test falló, deja en `.e2e-artifacts/` la
    captura, el HTML, la consola y la traza de Playwright (`playwright show-trace traza.zip`)."""
    server = next(
        (
            request.getfixturevalue(name)
            for name in ("fresh_demo_app", "empty_app", "empty_shared_app", "demo_app")
            if name in request.fixturenames
        ),
        None,
    )
    base_url = server.url if server is not None else None
    page_errors.base_url = base_url or ""
    context = browser.new_context(
        base_url=base_url, locale=LOCALES[lang], viewport=VIEWPORT, timezone_id="Europe/Madrid"
    )
    context.set_default_timeout(15_000)
    context.route(LOCAL_ONLY, lambda route: route.abort())
    context.tracing.start(screenshots=True, snapshots=True, sources=False)
    tab = context.new_page()
    tab.on("console", page_errors.on_console)
    tab.on("pageerror", page_errors.on_exception)
    tab.on("response", page_errors.on_response)
    try:
        yield tab
    finally:
        problems = page_errors.problems()
        report = getattr(request.node, "report_call", None)
        # Un `xfail` que falla como se esperaba también deja sus pruebas, y no se cuenta dos veces.
        failed = report is not None and (report.failed or hasattr(report, "wasxfail"))
        if problems or failed:
            folder = _artifact_dir(request.node)
            try:
                tab.screenshot(path=folder / "captura.png", full_page=True)
                (folder / "pagina.html").write_text(tab.content(), encoding="utf-8")
            except Exception as exc:  # noqa: BLE001 - el diagnóstico no tapa el fallo
                (folder / "captura-error.txt").write_text(str(exc), encoding="utf-8")
            lines = page_errors.log + [f"[problema] {p}" for p in problems]
            (folder / "consola.txt").write_text("\n".join(lines), encoding="utf-8")
            if server is not None:
                (folder / "app.log").write_text(server.logs(), encoding="utf-8")
            context.tracing.stop(path=folder / "traza.zip")
        else:
            context.tracing.stop()
        context.close()
    # Si el test ya falló, sus problemas van en `consola.txt`.
    if problems and not failed:
        pytest.fail("Errores que no se ven en la página:\n" + "\n".join(problems), pytrace=False)
