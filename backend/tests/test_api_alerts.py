"""API de la bandeja «Alertas» (`/alerts`)."""

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.services import profile

FIXTURES = Path(__file__).parent / "fixtures" / "email"


@pytest.fixture
def client(isolated_env: Path) -> Iterator[TestClient]:
    migrations.upgrade()
    with session_scope() as session:
        profile.import_profile(session, profile.EXAMPLE_PATH)
    (isolated_env / "inbox").mkdir()
    shutil.copy(FIXTURES / "linkedin_alert.eml", isolated_env / "inbox" / "a.eml")
    with TestClient(create_app()) as client:
        yield client


def test_poll_list_and_discard(client: TestClient) -> None:
    assert client.get("/alerts").json()["total"] == 0
    polled = client.post("/alerts/poll").json()
    assert (polled["created"], polled["summaries"]) == (3, 3)

    alerts = client.get("/alerts").json()
    assert (alerts["total"], alerts["passed"]) == (3, 2)
    first = alerts["jobs"][0]
    assert first["prefilter_passed"] and first["platform_label"] == "LinkedIn"
    assert first["url"].startswith("https://www.linkedin.com/jobs/view/")

    job = client.get(f"/jobs/{first['job_id']}").json()
    assert job["stage"] == "pending_detail"

    discarded = client.post(
        f"/jobs/{first['job_id']}/events", json={"type": "discarded", "reason": "location"}
    )
    assert discarded.status_code == 201, discarded.json()
    assert discarded.json()["stage"] == "closed"
    assert client.get("/alerts").json()["total"] == 2


def test_status_counts_pending_detail(client: TestClient) -> None:
    client.post("/alerts/poll")
    assert client.get("/status").json()["by_stage"]["pending_detail"] == 3
