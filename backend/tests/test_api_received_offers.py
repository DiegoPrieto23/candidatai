"""API de las ofertas recibidas (fase 21): datos en la ficha y comparación para la UI."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import ProfileVersion
from app.services import events, profile
from tests.test_api_process import _event, _job


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


def _floor(value: int) -> None:
    with session_scope() as session:
        data = profile.load_from_yaml(profile.EXAMPLE_PATH).model_dump(mode="json")
        data["private"] = {"salary_floor_eur": value}
        session.add(ProfileVersion(data=data, content_hash="api"))


def test_save_show_compare_and_delete(client: TestClient) -> None:
    job_id = _job(client)
    _event(client, job_id, type="applied_manually", channel="email")
    _floor(40_000)
    assert client.get(f"/jobs/{job_id}/received-offer").json() is None

    body = {"base_salary": 44_000, "variable": 2_000, "work_mode": "hybrid", "respond_by": None}
    saved = client.post(f"/jobs/{job_id}/received-offer", json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["amounts_private"] is True
    assert client.get(f"/jobs/{job_id}/received-offer").json()["base_salary"] == 44_000
    with session_scope() as session:
        assert "offer_received" in [e.type for e in events.get_timeline(session, job_id).events]

    view = client.get("/received-offers").json()
    assert view["floor_eur"] == 40_000
    [offer] = view["offers"]
    assert (offer["floor_diff_base"], offer["floor_diff_total"]) == (4_000, 6_000)

    assert client.post(f"/jobs/{job_id}/received-offer/delete").json() == {"ok": True}
    assert client.get("/received-offers").json()["offers"] == []
    assert client.post(f"/jobs/{job_id}/received-offer/delete").status_code == 404


def test_errors(client: TestClient) -> None:
    job_id = _job(client)  # aprobada, sin enviar: aún no puede haber oferta
    response = client.post(f"/jobs/{job_id}/received-offer", json={"base_salary": 1})
    assert response.status_code == 409
    assert client.get(f"/jobs/{job_id}/received-offer").json() is None
    bad = client.post(f"/jobs/{job_id}/received-offer", json={"currency": "euros", "x": 1})
    assert bad.status_code == 422
    assert client.get("/jobs/999/received-offer").status_code == 404
