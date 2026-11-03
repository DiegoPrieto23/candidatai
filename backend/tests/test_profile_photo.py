"""Subir la foto del CV desde «Mi perfil»: solo la UI, solo imágenes de verdad y opcional."""

import base64
from collections.abc import Iterator
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.config import get_settings
from app.services.documents import photo

JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


def image(fmt: str) -> bytes:
    out = BytesIO()
    Image.new("RGB", (20, 20), "red").save(out, format=fmt)
    return out.getvalue()


def body(content: bytes) -> dict[str, str]:
    return {"content_base64": base64.b64encode(content).decode()}


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app(), base_url="http://127.0.0.1:8000") as client:
        yield client


def test_without_photo_nothing_is_required(client: TestClient) -> None:
    assert client.get("/profile/photo").json()["exists"] is False
    assert client.get("/profile/photo/file").status_code == 404


def test_upload_replaces_the_previous_one_and_can_be_removed(client: TestClient) -> None:
    data_dir = get_settings().data_dir
    first = client.put("/profile/photo", json=body(image("JPEG")), headers=JSON)
    assert first.status_code == 200
    assert first.json()["filename"] == "photo.jpg"

    second = client.put("/profile/photo", json=body(image("PNG")), headers=JSON).json()
    assert second["filename"] == "photo.png"
    assert not (data_dir / "photo.jpg").exists()
    assert client.get("/profile/photo").json()["filename"] == "photo.png"
    served = client.get("/profile/photo/file")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"

    (data_dir / "cache" / "photo").mkdir(parents=True)
    (data_dir / "cache" / "photo" / "x.png").write_bytes(b"x")
    assert (
        client.request("DELETE", "/profile/photo", json={}, headers=JSON).json()["exists"] is False
    )
    assert not (data_dir / "photo.png").exists()
    assert not (data_dir / "cache" / "photo" / "x.png").exists()


@pytest.mark.parametrize(
    "content",
    [
        b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
        b"no soy una imagen",
        image("GIF"),
    ],
    ids=["svg", "text", "gif"],
)
def test_only_real_images_are_accepted(client: TestClient, content: bytes) -> None:
    response = client.put("/profile/photo", json=body(content), headers=JSON)
    assert response.status_code == 422
    assert client.get("/profile/photo").json()["exists"] is False
    assert not list(get_settings().data_dir.glob("photo.*"))


def test_too_large(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    monkeypatch.setattr(photo, "MAX_PHOTO_BYTES", 10)
    response = client.put("/profile/photo", json=body(image("PNG")), headers=JSON)
    assert response.status_code == 422
    assert "10 MB" in response.json()["error"]["message"]


def test_only_the_ui_can_change_it(client: TestClient) -> None:
    content = body(image("PNG"))
    # Un formulario de otra web no puede mandar JSON sin la comprobación previa que no se concede.
    assert (
        client.put(
            "/profile/photo",
            content=content["content_base64"],
            headers={"Content-Type": "text/plain"},
        ).status_code
        == 403
    )
    assert (
        client.put(
            "/profile/photo",
            json=content,
            headers={"Origin": "https://evil.example", "Content-Type": "application/json"},
        ).status_code
        == 403
    )
    assert (
        client.request(
            "DELETE", "/profile/photo", json={}, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.get("/profile/photo", headers={"Origin": "https://evil.example"}).status_code == 403
    )
