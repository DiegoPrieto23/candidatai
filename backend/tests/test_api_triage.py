"""API del triaje: cola ordenada por score, match de una oferta y aprobar/descartar/reabrir."""

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.schemas.llm_io import JobExtraction
from app.services import extractions, ingest, profile
from tests.matching_support import demo_extraction_data


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


def import_profile() -> None:
    with session_scope() as session:
        profile.import_profile(session, profile.EXAMPLE_PATH)


def add_extracted(title: str, company: str, **changes: Any) -> int:
    with session_scope() as session:
        job_id = ingest.add_from_text(session, title, company, "Oferta de ejemplo. " * 20).job_id
        data = {**demo_extraction_data("01-data-engineer"), **changes}
        extractions.save_extraction(session, job_id, JobExtraction.model_validate(data))
        return job_id


def test_triage_queue_sorted_by_score(client: TestClient) -> None:
    import_profile()
    weak = add_extracted("Data Engineer", "Uno", must_have_skills=["Kafka", "Scala"])
    strong = add_extracted("Data Engineer", "Dos")
    filtered = add_extracted("Data Engineer", "Tres", seniority="lead")  # cerrada por filtros
    body = client.get("/triage").json()
    assert [item["job"]["id"] for item in body["items"]] == [strong, weak]
    assert filtered not in [item["job"]["id"] for item in body["items"]]
    assert body["total"] == 2 and body["triage_threshold"] == 55
    assert body["profile_missing"] is False
    first = body["items"][0]
    assert first["job"]["score"] == first["match"]["score"]
    assert first["extraction"]["title_normalized"] == "Data Engineer"
    assert first["match"]["hard_filters"] == {"passed": True, "failures": []}
    assert {c["skill"] for c in first["match"]["breakdown"]["must_have"]["covered"]} == {
        "Python",
        "SQL",
        "Snowflake",
        "dbt",
    }
    assert body["items"][1]["match"]["below_threshold"] is True


def test_triage_without_profile(client: TestClient) -> None:
    job_id = add_extracted("Data Engineer", "Uno")
    body = client.get("/triage").json()
    assert body["profile_missing"] is True
    assert [(i["job"]["id"], i["match"]) for i in body["items"]] == [(job_id, None)]


def test_job_match_endpoint(client: TestClient) -> None:
    import_profile()
    job_id = add_extracted("Data Engineer", "Uno")
    response = client.get(f"/jobs/{job_id}/match")
    assert response.status_code == 200
    assert response.json()["job_id"] == job_id
    assert client.get("/jobs/99/match").status_code == 404


def test_job_match_without_extraction_is_404(client: TestClient) -> None:
    import_profile()
    with session_scope() as session:
        job_id = ingest.add_from_text(session, "T", "C", "Oferta de ejemplo. " * 20).job_id
    response = client.get(f"/jobs/{job_id}/match")
    assert response.status_code == 404
    assert response.json()["error"]["message"] == f"La oferta {job_id} aún no tiene extracción."


def test_approve_and_discard_with_reason(client: TestClient) -> None:
    import_profile()
    a, b = add_extracted("Data Engineer", "Uno"), add_extracted("Data Engineer", "Dos")
    assert client.post(f"/jobs/{a}/events", json={"type": "approved"}).json()["stage"] == "approved"
    response = client.post(
        f"/jobs/{b}/events", json={"type": "discarded", "reason": "salary", "note": "Muy bajo"}
    )
    assert response.status_code == 201 and response.json()["stage"] == "closed"
    event = client.get(f"/jobs/{b}").json()["events"][-1]
    assert (event["type"], event["actor"]) == ("discarded", "user")
    assert event["payload"] == {"reason": "salary", "note": "Muy bajo"}
    assert client.get("/triage").json()["items"] == []


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"type": "discarded"}, "Descartar necesita un motivo"),
        ({"type": "discarded", "reason": "other"}, "explica el motivo en la nota"),
        ({"type": "discarded", "reason": "other", "note": "   "}, "explica el motivo en la nota"),
        ({"type": "approved", "reason": "salary"}, "`reason` solo se usa al descartar"),
    ],
)
def test_discard_needs_reason(client: TestClient, body: dict[str, Any], message: str) -> None:
    import_profile()
    job_id = add_extracted("Data Engineer", "Uno")
    response = client.post(f"/jobs/{job_id}/events", json=body)
    assert response.status_code == 422
    assert message in response.json()["error"]["message"]


def test_unknown_discard_reason_is_validation_error(client: TestClient) -> None:
    import_profile()
    job_id = add_extracted("Data Engineer", "Uno")
    response = client.post(f"/jobs/{job_id}/events", json={"type": "discarded", "reason": "x"})
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "reason"


def test_reopen_hard_filtered_job_returns_to_triage(client: TestClient) -> None:
    import_profile()
    job_id = add_extracted("Data Engineer", "Uno", seniority="lead")
    assert client.get(f"/jobs/{job_id}").json()["stage"] == "closed"
    reopened = client.post(f"/jobs/{job_id}/events", json={"type": "reopened"})
    assert reopened.json()["stage"] == "pending_triage"
    item = client.get("/triage").json()["items"][0]
    assert item["job"]["id"] == job_id
    assert item["match"]["hard_filters"]["passed"] is False
