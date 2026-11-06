"""Renombrar y eliminar plantillas propias desde la página Plantillas."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.config import get_settings
from app.core.db import session_scope
from app.services import profile
from app.services.documents import default_template, templates, uploads
from app.services.documents.importer import paths as paths_of_upload

UI = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


def own_template(template_id: str = "mi-diseno", source: bytes = b"PK-source") -> Path:
    """Copia de una integrada en `data/templates/`, con su original de Word."""
    builtin = templates.get("ats-simple")
    target = get_settings().user_templates_dir / template_id
    target.mkdir(parents=True)
    for item in builtin.path.iterdir():
        if item.is_file():
            (target / item.name).write_bytes(item.read_bytes())
    meta = (target / templates.META_FILE).read_text(encoding="utf-8")
    meta = meta.replace("id: ats-simple", f"id: {template_id}", 1)
    meta += "\nsource_file: source.docx\n"
    (target / templates.META_FILE).write_text(meta, encoding="utf-8")
    (target / "source.docx").write_bytes(source)
    return target


def test_renaming_changes_the_name_not_the_id(client: TestClient) -> None:
    own_template()
    response = client.patch("/templates/mi-diseno", json={"name": "  Mi  CV bonito "}, headers=UI)
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Mi CV bonito"
    assert response.json()["id"] == "mi-diseno"
    assert templates.get("mi-diseno").meta.name == "Mi CV bonito"


def test_renaming_keeps_the_template_valid_and_the_rest_of_the_file(client: TestClient) -> None:
    folder = own_template()
    client.patch("/templates/mi-diseno", json={"name": "Otro"}, headers=UI)
    assert templates.get("mi-diseno").meta.engine == "docx"
    assert (folder / "source.docx").is_file()


@pytest.mark.parametrize("name", ["", "x" * 81])
def test_a_bad_name_is_rejected(client: TestClient, name: str) -> None:
    own_template()
    response = client.patch("/templates/mi-diseno", json={"name": name}, headers=UI)
    assert response.status_code == 422


def test_blank_name_is_rejected(client: TestClient) -> None:
    own_template()
    response = client.patch("/templates/mi-diseno", json={"name": "   "}, headers=UI)
    assert response.status_code in (400, 422)


def test_builtin_templates_are_not_renamed(client: TestClient) -> None:
    assert client.patch("/templates/ats-simple", json={"name": "x"}, headers=UI).status_code in (
        400,
        422,
    )
    assert templates.get("ats-simple").meta.name != "x"


def listed(client: TestClient) -> set[str]:
    return {t["id"] for t in client.get("/templates").json()["templates"]}


def test_deleting_a_builtin_hides_it_and_it_can_be_restored(client: TestClient) -> None:
    assert "clasica-foto" in listed(client)
    response = client.delete("/templates/clasica-foto", headers=UI)
    assert response.status_code == 200, response.text
    assert response.json()["hidden"] is True and response.json()["default_cleared"] is False
    # Fuera de la lista (y de lo que ve el agente), pero sigue en el programa y se puede restaurar.
    assert "clasica-foto" not in listed(client)
    assert templates.get("clasica-foto").meta.id == "clasica-foto"
    assert [t["id"] for t in client.get("/templates/hidden").json()] == ["clasica-foto"]

    restored = client.post("/templates/clasica-foto/restore", headers=UI)
    assert restored.status_code == 200 and restored.json()["restored"] is True
    assert "clasica-foto" in listed(client)
    assert client.get("/templates/hidden").json() == []
    assert client.post("/templates/clasica-foto/restore", headers=UI).json()["restored"] is False


def test_deleting_a_builtin_default_clears_it_and_a_hidden_one_cannot_be_default(
    client: TestClient,
) -> None:
    with session_scope() as session:
        path = get_settings().data_dir / "profile.yaml"
        path.write_bytes(profile.EXAMPLE_PATH.read_bytes())
        profile.import_profile(session, path)
        default_template.set_default_template(session, "clasica-foto", path)
    response = client.delete("/templates/clasica-foto", headers=UI)
    assert response.json()["default_cleared"] is True and response.json()["hidden"] is True
    assert client.get("/templates/default").json()["template_id"] is None
    refused = client.post("/templates/clasica-foto/default", headers=UI)
    assert refused.status_code in (400, 422) and "restáurala" in refused.text
    client.post("/templates/clasica-foto/restore", headers=UI)
    assert client.post("/templates/clasica-foto/default", headers=UI).status_code == 200


def test_a_hidden_builtin_still_renders_so_old_cvs_and_fallbacks_keep_working(
    client: TestClient,
) -> None:
    client.delete("/templates/ats-simple", headers=UI)
    assert "ats-simple" not in listed(client)
    assert templates.get("ats-simple").meta.engine == "docx"


def test_only_your_templates_are_editable(client: TestClient) -> None:
    own_template()
    found = {t["id"]: t["editable"] for t in client.get("/templates").json()["templates"]}
    assert found["mi-diseno"] is True
    assert found["ats-simple"] is False


def test_deleting_removes_the_folder_and_its_upload(client: TestClient) -> None:
    folder = own_template(source=b"PK-source")
    uploads_dir = paths_of_upload.uploads_dir()
    uploads_dir.mkdir(parents=True, exist_ok=True)
    (uploads_dir / "mi-cv.docx").write_bytes(b"PK-source")
    (uploads_dir / "otro.docx").write_bytes(b"PK-otro")

    response = client.delete("/templates/mi-diseno", headers=UI)
    assert response.status_code == 200, response.text
    assert response.json()["default_cleared"] is False
    assert not folder.exists()
    assert [upload.name for upload in uploads.list_uploads()] == ["otro.docx"]


def test_deleting_the_default_clears_it(client: TestClient) -> None:
    own_template()
    with session_scope() as session:
        path = get_settings().data_dir / "profile.yaml"
        path.write_bytes(profile.EXAMPLE_PATH.read_bytes())
        profile.import_profile(session, path)
        default_template.set_default_template(session, "mi-diseno", path)

    response = client.delete("/templates/mi-diseno", headers=UI)
    assert response.status_code == 200, response.text
    assert response.json()["default_cleared"] is True
    assert client.get("/templates/default").json()["template_id"] is None


@pytest.mark.parametrize("template_id", ["no-existe", "..%2F..%2Fdata"])
def test_unknown_or_outside_templates(client: TestClient, template_id: str) -> None:
    assert client.delete(f"/templates/{template_id}", headers=UI).status_code in (404, 405)
