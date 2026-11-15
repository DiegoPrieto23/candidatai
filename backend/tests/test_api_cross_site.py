"""Ninguna web abierta en el navegador puede pedir un cambio a la API (CSRF): `CrossSiteGuard`."""

import re
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core import migrations
from app.core.config import get_settings

EVIL = "https://evil.example"
UNSAFE = ("post", "put", "patch", "delete")


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


def _unsafe_routes() -> list[tuple[str, str]]:
    paths = create_app().openapi()["paths"]
    return [
        (method, re.sub(r"\{[^}]+\}", "1", path))
        for path, ops in paths.items()
        for method in UNSAFE
        if method in ops
    ]


# Lo que un formulario de otra web puede mandar sin comprobación previa CORS.
SIMPLE_BODIES: dict[str, dict[str, Any]] = {
    "form": {"data": {"a": "b"}},
    "text": {"content": b"{}", "headers": {"Content-Type": "text/plain"}},
    "multipart": {"files": {"file": ("cv.pdf", b"%PDF-1.4", "application/pdf")}},
}


def test_other_sites_cannot_change_anything(client: TestClient) -> None:
    # Todas las rutas en un solo test: migrar la BD para cada una tardaría medio minuto.
    routes = _unsafe_routes()
    assert len(routes) > 50
    passed = []
    for method, path in routes:
        for kind, body in SIMPLE_BODIES.items():
            headers = {"Origin": EVIL, **body.get("headers", {})}
            kwargs = {k: v for k, v in body.items() if k != "headers"}
            response = client.request(method.upper(), path, headers=headers, **kwargs)
            if response.status_code != 403 or response.json()["error"]["type"] != "forbidden":
                passed.append(f"{method.upper()} {path} ({kind}): {response.status_code}")
    assert passed == []


@pytest.mark.parametrize("origin", ["null", "http://localhost:3000", "http://127.0.0.1:9999"])
def test_other_local_pages_are_other_sites(client: TestClient, origin: str) -> None:
    response = client.post("/alerts/poll", headers={"Origin": origin})
    assert response.status_code == 403


def test_cross_site_fetch_metadata_without_origin_is_rejected(client: TestClient) -> None:
    response = client.post("/alerts/poll", headers={"Sec-Fetch-Site": "cross-site"})
    assert response.status_code == 403


@pytest.mark.parametrize("origin", ["http://127.0.0.1:5173", "http://127.0.0.1:8000", None])
def test_ui_and_local_clients_still_work(client: TestClient, origin: str | None) -> None:
    # La UI de desarrollo, la compilada (mismo origen que la API) y la CLI o un script.
    headers = {"Origin": origin} if origin else {}
    response = client.post("http://127.0.0.1:8000/alerts/poll", headers=headers)
    assert response.status_code == 200, response.text


def test_extension_reaches_only_capture(client: TestClient) -> None:
    origin = get_settings().capture_origin
    # `/capture` decide con su token, no el middleware: sin él, 401.
    capture = client.post("/capture", headers={"Origin": origin}, json={})
    assert capture.status_code == 401
    assert client.post("/alerts/poll", headers={"Origin": origin}).status_code == 403
    assert client.post("/capture/pair", headers={"Origin": origin}, json={}).status_code == 403
