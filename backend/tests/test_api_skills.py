"""API de la página «Skills» (fase 14): huecos, «es lo mismo que…» con recálculo y marcas."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.services import worker
from app.services.matching import service as matching
from tests.skills_support import add_job, import_demo_profile, use_aliases_copy

JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


@pytest.fixture(autouse=True)
def aliases_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return use_aliases_copy(tmp_path, monkeypatch)


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


def test_gaps_without_profile_is_not_found(client: TestClient) -> None:
    response = client.get("/skills/gaps")
    assert response.status_code == 404
    assert response.json()["error"]["type"] == "not_found"


def test_gaps_lists_missing_skills_and_profile_skills(client: TestClient) -> None:
    import_demo_profile()
    job_id = add_job(["Python", "Kafka"], ["Terraform"])
    body = client.get("/skills/gaps", params={"days": 30}).json()
    assert body["days"] == 30 and body["jobs_considered"] == 1
    assert [g["key"] for g in body["gaps"]] == ["kafka", "terraform"]
    assert body["gaps"][0]["examples"][0]["job_id"] == job_id
    names = {s["name"]: s["level"] for s in body["profile_skills"]}
    assert names["Python"] == "F" and names["dbt"] == "basic"


def test_alias_from_the_ui_rescores_and_changes_the_score(
    client: TestClient, aliases_file: Path
) -> None:
    """Criterio de aceptación: añadir un alias desde la UI recalcula y cambia el score."""
    import_demo_profile()
    job_id = add_job(["Python", "SQL", "Data Warehousing"])
    worker.run_pending()
    with session_scope() as session:
        before = matching.latest_scores(session, [job_id])[job_id]

    response = client.post(
        "/skills/aliases",
        json={"skill": "Data Warehousing", "profile_skill": "Snowflake"},
        headers=JSON,
    )
    assert response.status_code == 200, response.text
    assert response.json()["canonical"] == "Snowflake"
    assert response.json()["rescore_queued"] is True
    assert "Data Warehousing" in aliases_file.read_text(encoding="utf-8")
    assert client.get("/skills/gaps").json()["gaps"] == []

    worker.run_pending()
    with session_scope() as session:
        after = matching.latest_scores(session, [job_id])[job_id]
    assert after > before


def test_alias_conflict_is_rejected(client: TestClient) -> None:
    import_demo_profile()
    response = client.post(
        "/skills/aliases", json={"skill": "Spark", "profile_skill": "Python"}, headers=JSON
    )
    assert response.status_code == 422
    assert "Apache Spark" in response.json()["error"]["message"]


def test_only_the_ui_can_write(client: TestClient, aliases_file: Path) -> None:
    import_demo_profile()
    before = aliases_file.read_bytes()
    other = {"Origin": "https://evil.example", "Content-Type": "application/json"}
    for url, body in [
        ("/skills/aliases", {"skill": "Data Warehousing", "profile_skill": "Snowflake"}),
        ("/skills/marks", {"skill": "Kafka", "status": "gap"}),
    ]:
        assert client.post(url, json=body, headers=other).status_code == 403
        plain = {"Content-Type": "text/plain"}
        assert client.post(url, content='{"skill": "x"}', headers=plain).status_code == 403
    assert aliases_file.read_bytes() == before


def test_marks(client: TestClient) -> None:
    import_demo_profile()
    add_job(["Kafka", "Rust"])
    response = client.post("/skills/marks", json={"skill": "Kafka", "status": "gap"}, headers=JSON)
    assert response.json() == {"ok": True, "key": "kafka", "skill": "Kafka", "mark": "gap"}
    client.post("/skills/marks", json={"skill": "rust", "status": "have"}, headers=JSON)
    marks = {g["key"]: g["mark"] for g in client.get("/skills/gaps").json()["gaps"]}
    assert marks == {"kafka": "gap", "rust": "have"}

    client.post("/skills/marks", json={"skill": "Kafka", "status": None}, headers=JSON)
    marks = {g["key"]: g["mark"] for g in client.get("/skills/gaps").json()["gaps"]}
    assert marks == {"kafka": None, "rust": "have"}
    bad = client.post("/skills/marks", json={"skill": "Kafka", "status": "maybe"}, headers=JSON)
    assert bad.status_code == 422
