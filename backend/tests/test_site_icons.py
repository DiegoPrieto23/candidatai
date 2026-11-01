"""Iconos de «Dónde buscar» servidos por la app: se descargan una vez y se sirven de disco."""

import os
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core import migrations
from app.core.config import get_settings
from app.core.db import session_scope
from app.schemas.sources import AgentBrowseSource
from app.services import liveness, site_icons
from app.services.ingestion import browse

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
ICO = b"\x00\x00\x01\x00" + b"\x00" * 40
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 20
DAY = 24 * 3600.0


@pytest.fixture(autouse=True)
def _no_download_left_behind() -> Iterator[None]:
    yield
    site_icons.wait_downloads()


def test_image_type_accepts_only_known_images() -> None:
    assert site_icons.image_type(PNG) == "png"
    assert site_icons.image_type(ICO) == "ico"
    assert site_icons.image_type(WEBP) == "webp"
    assert site_icons.image_type(b"GIF89a...") == "gif"
    assert site_icons.image_type(b"\xff\xd8\xff\xe0") == "jpg"
    assert site_icons.image_type(b"<svg onload=alert(1)>") is None  # SVG puede ejecutar código
    assert site_icons.image_type(b"<!doctype html>") is None


def test_candidates_try_the_known_one_then_the_site_and_its_parent_domain() -> None:
    assert site_icons.candidates("https://www.tecnoempleo.com")[0] == (
        "https://www.tecnoempleo.com/graficos/logo_te_192.png"
    )
    assert site_icons.candidates("https://careers.acme.com") == [
        "https://careers.acme.com/favicon.ico",
        "https://careers.acme.com/apple-touch-icon.png",
        "https://acme.com/favicon.ico",
        "https://acme.com/apple-touch-icon.png",
    ]
    # En `acme.co.uk`, el dominio padre (`co.uk`) no es la empresa: no se le pregunta.
    assert site_icons.candidates("https://acme.co.uk") == [
        "https://acme.co.uk/favicon.ico",
        "https://acme.co.uk/apple-touch-icon.png",
    ]
    assert all("//com.es/" not in url for url in site_icons.candidates("https://jobs.acme.com.es"))
    assert site_icons.site_key("https://www.InfoJobs.net") == "infojobs.net"
    assert site_icons.site_key("file:///c:/x") is None


@respx.mock
def test_downloads_once_then_serves_from_disk() -> None:
    first = respx.get("https://acme.com/favicon.ico").mock(return_value=httpx.Response(404))
    second = respx.get("https://acme.com/apple-touch-icon.png").mock(
        return_value=httpx.Response(200, content=PNG)
    )
    icon = site_icons.get_icon("https://acme.com")
    assert icon == site_icons.Icon(PNG, "image/png")
    assert (get_settings().icons_dir / "acme.com.png").read_bytes() == PNG
    assert site_icons.get_icon("https://acme.com") == icon
    assert first.call_count == 1 and second.call_count == 1  # la segunda vez, de disco


@respx.mock
def test_rejects_what_is_not_a_small_image() -> None:
    respx.get("https://acme.com/favicon.ico").mock(
        return_value=httpx.Response(200, content=b"<html>no es un icono</html>")
    )
    respx.get("https://acme.com/apple-touch-icon.png").mock(
        return_value=httpx.Response(200, content=PNG + b"\x00" * site_icons.MAX_ICON_BYTES)
    )
    assert site_icons.get_icon("https://acme.com") is None
    assert not list(get_settings().icons_dir.glob("acme.com.*[!s]"))  # solo el `.miss`


def test_a_site_without_icon_is_not_asked_again_for_a_day() -> None:
    asked: list[str] = []

    def nothing(url: str) -> bytes | None:
        asked.append(url)
        return None

    assert site_icons.get_icon("https://acme.com", fetch=nothing, now=1000.0) is None
    assert len(asked) == 2  # `/favicon.ico` y `/apple-touch-icon.png`
    marker = get_settings().icons_dir / "acme.com.miss"
    os.utime(marker, (1000.0, 1000.0))
    assert site_icons.get_icon("https://acme.com", fetch=nothing, now=1000.0 + DAY / 2) is None
    assert len(asked) == 2
    site_icons.get_icon("https://acme.com", fetch=nothing, now=1000.0 + 2 * DAY)
    assert len(asked) == 4


def test_without_network_nothing_is_written_and_it_retries_next_time() -> None:
    def offline(url: str) -> bytes | None:
        raise site_icons.Unreachable("sin red")

    assert site_icons.get_icon("https://acme.com", fetch=offline) is None
    assert not get_settings().icons_dir.exists() or not any(get_settings().icons_dir.iterdir())
    assert site_icons.get_icon("https://acme.com", fetch=lambda _url: ICO) == site_icons.Icon(
        ICO, "image/x-icon"
    )


def test_an_expired_icon_is_refreshed_or_kept_if_the_site_fails() -> None:
    site_icons.get_icon("https://acme.com", fetch=lambda _url: PNG)
    path = get_settings().icons_dir / "acme.com.png"
    old = path.stat().st_mtime - site_icons.ICON_TTL - 10
    os.utime(path, (old, old))

    def offline(url: str) -> bytes | None:
        raise site_icons.Unreachable("sin red")

    assert site_icons.get_icon("https://acme.com", fetch=offline) == site_icons.Icon(
        PNG, "image/png"
    )
    # Ya no reintenta en cada visita: hasta dentro de `MISS_TTL`.
    assert site_icons.get_icon("https://acme.com", fetch=lambda _url: ICO).content == PNG
    os.utime(path, (old, old))
    assert site_icons.get_icon("https://acme.com", fetch=lambda _url: ICO).content == ICO
    assert not path.exists() and (path.with_suffix(".ico")).exists()


@respx.mock
def test_never_goes_to_the_local_network_or_linkedin(monkeypatch: pytest.MonkeyPatch) -> None:
    route = respx.route().mock(return_value=httpx.Response(200, content=PNG))
    assert site_icons.download("https://www.linkedin.com/favicon.ico") is None
    assert site_icons.download("http://127.0.0.1/favicon.ico") is None
    monkeypatch.setattr(liveness, "_resolve", lambda _host: ["192.168.1.10"])
    assert site_icons.download("https://intranet.acme.com/favicon.ico") is None
    assert route.call_count == 0


def test_concurrent_requests_for_the_same_site_do_not_clash() -> None:
    """La API atiende cada icono en un hilo: varias fuentes del mismo dominio, a la vez."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=8) as pool:
        icons = list(
            pool.map(
                lambda _i: site_icons.get_icon("https://acme.com", fetch=lambda _u: PNG), range(16)
            )
        )
    assert all(icon == site_icons.Icon(PNG, "image/png") for icon in icons)
    assert sorted(p.name for p in get_settings().icons_dir.iterdir()) == ["acme.com.png"]


def test_an_icon_that_cannot_be_read_is_downloaded_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """En Windows, leerlo mientras otro hilo lo renombra da «acceso denegado»: no es un 500."""
    site_icons.get_icon("https://acme.com", fetch=lambda _u: PNG)

    def locked(self: Path) -> bytes:
        raise PermissionError(13, "Permission denied", str(self))

    monkeypatch.setattr(Path, "read_bytes", locked)
    asked: list[str] = []

    def fetch(url: str) -> bytes:
        asked.append(url)
        return PNG

    assert site_icons.get_icon("https://acme.com", fetch=fetch) == site_icons.Icon(PNG, "image/png")
    assert asked


def test_without_network_it_gives_up_at_the_first_failure() -> None:
    asked: list[str] = []

    def offline(url: str) -> bytes | None:
        asked.append(url)
        raise site_icons.Unreachable("sin red")

    assert site_icons.get_icon("https://careers.acme.com", fetch=offline) is None
    assert len(asked) == 1  # no espera a que fallen las otras tres


def test_icon_now_does_not_wait_and_asks_each_site_once() -> None:
    """Sin icono en disco, `None` enseguida; la descarga va aparte y una sola vez por web."""
    release = threading.Event()
    calls: list[str] = []

    def slow(url: str) -> bytes:
        calls.append(url)
        release.wait(5)
        return PNG

    started = time.monotonic()
    assert [site_icons.icon_now("https://acme.com", fetch=slow) for _ in range(5)] == [None] * 5
    assert time.monotonic() - started < 1
    release.set()
    site_icons.wait_downloads()
    assert calls == ["https://acme.com/favicon.ico"]
    assert site_icons.icon_now("https://acme.com", fetch=slow) == site_icons.Icon(PNG, "image/png")
    assert len(calls) == 1


def test_many_sites_do_not_start_many_threads() -> None:
    release = threading.Event()

    def slow(_url: str) -> bytes:
        release.wait(5)
        return PNG

    for n in range(12):
        assert site_icons.icon_now(f"https://empresa{n}.example", fetch=slow) is None
    icon_threads = [t for t in threading.enumerate() if t.name == "cai-icons"]
    assert 0 < len(icon_threads) <= site_icons.MAX_DOWNLOADS
    release.set()
    site_icons.wait_downloads()
    assert len(list(get_settings().icons_dir.glob("*.png"))) == 12


def test_icon_now_serves_the_expired_one_while_it_refreshes() -> None:
    site_icons.get_icon("https://acme.com", fetch=lambda _url: PNG)
    later = time.time() + 31 * DAY
    assert site_icons.icon_now("https://acme.com", fetch=lambda _url: ICO, now=later).content == PNG
    site_icons.wait_downloads()
    assert site_icons.icon_now("https://acme.com", fetch=lambda _url: PNG).content == ICO


def test_icon_now_does_not_ask_again_a_site_without_icon() -> None:
    site_icons.get_icon("https://acme.com", fetch=lambda _url: None)
    calls: list[str] = []
    assert site_icons.icon_now("https://acme.com", fetch=lambda url: calls.append(url)) is None
    site_icons.wait_downloads()
    assert calls == []


def test_a_failed_background_download_can_be_retried() -> None:
    def broken(_url: str) -> bytes:
        raise RuntimeError("fallo inesperado")

    assert site_icons.icon_now("https://acme.com", fetch=broken) is None
    site_icons.wait_downloads()
    site_icons.icon_now("https://acme.com", fetch=lambda _url: PNG)
    site_icons.wait_downloads()
    assert site_icons.icon_now("https://acme.com") == site_icons.Icon(PNG, "image/png")


# --- API ---------------------------------------------------------------------------------------


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


@respx.mock
def test_the_api_serves_the_icon_of_each_source(client: TestClient) -> None:
    respx.get("https://acmedatos.example/favicon.ico").mock(
        return_value=httpx.Response(200, content=ICO)
    )
    respx.get("https://www.infojobs.net/favicon.ico").mock(
        return_value=httpx.Response(200, content=PNG)
    )
    body = {"kind": "greenhouse", "name": "Acme Datos", "slug": "acmedatos"}
    company = client.post("/sources", json=body).json()["id"]
    # Sin web todavía: nada que descargar.
    assert client.get(f"/sources/{company}/icon").status_code == 204
    client.post(f"/sources/{company}/website", json={"website": "acmedatos.example"})
    # La primera vez no espera a la descarga: 204 sin caché, y la UI lo vuelve a pedir.
    pending = client.get(f"/sources/{company}/icon", params={"v": "acmedatos.example"})
    assert pending.status_code == 204 and pending.headers["cache-control"] == "no-store"
    site_icons.wait_downloads()
    icon = client.get(f"/sources/{company}/icon", params={"v": "acmedatos.example"})
    assert icon.status_code == 200 and icon.content == ICO
    assert icon.headers["content-type"] == "image/x-icon"
    assert icon.headers["x-content-type-options"] == "nosniff"
    with session_scope() as session:
        platform = AgentBrowseSource.model_validate(
            {
                "name": "InfoJobs",
                "platform": "infojobs",
                "search_urls": ["https://www.infojobs.net/ofertas-trabajo?q=data"],
            }
        )
        platform_id = browse.save_source(session, platform).source_id
    client.get(f"/sources/{platform_id}/icon")
    site_icons.wait_downloads()
    assert client.get(f"/sources/{platform_id}/icon").content == PNG
    assert client.get("/sources/9999/icon").status_code == 404


@respx.mock
def test_the_linkedin_platform_never_asks_linkedin(client: TestClient) -> None:
    """La app no consulta LinkedIn por su cuenta: su plataforma se queda con la inicial."""
    route = respx.route().mock(return_value=httpx.Response(200, content=PNG))
    with session_scope() as session:
        linkedin = AgentBrowseSource.model_validate(
            {
                "name": "LinkedIn",
                "platform": "linkedin",
                "search_urls": ["https://www.linkedin.com/jobs/search/?keywords=data"],
                "allow_agent_browsing": False,
            }
        )
        source_id = browse.save_source(session, linkedin).source_id
    assert client.get(f"/sources/{source_id}/icon").status_code == 204
    site_icons.wait_downloads()
    assert route.call_count == 0


@respx.mock
def test_a_slow_site_does_not_hold_the_request(client: TestClient) -> None:
    """Una web que tarda no retiene la petición, y cinco peticiones la piden una sola vez."""
    release = threading.Event()

    def slow(_request: httpx.Request) -> httpx.Response:
        release.wait(5)
        return httpx.Response(200, content=PNG)

    route = respx.get("https://lenta.example/favicon.ico").mock(side_effect=slow)
    body = {"kind": "greenhouse", "name": "Lenta", "slug": "lenta"}
    company = client.post("/sources", json=body).json()["id"]
    client.post(f"/sources/{company}/website", json={"website": "lenta.example"})
    started = time.monotonic()
    statuses = [client.get(f"/sources/{company}/icon").status_code for _ in range(5)]
    assert statuses == [204] * 5
    assert time.monotonic() - started < 2
    release.set()
    site_icons.wait_downloads()
    assert route.call_count == 1
    assert client.get(f"/sources/{company}/icon").content == PNG
