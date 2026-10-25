"""Fase 27.5: preferencias de búsqueda nuevas en el perfil y sus filtros duros.

Años mínimos, sueldo mínimo privado (`private.salary_floor_eur`), palabras que descartan del
perfil, contrato y jornada, tipo de empresa (`employer_kind`) y la equivalencia de
`exclude_signals: [fixed_term]`. La cifra del sueldo no sale nunca hacia el agente.
"""

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.config import REPO_ROOT
from app.core.db import session_scope
from app.core.policies import HardFilterPolicy, get_policies
from app.schemas.profile import CandidateProfile
from app.services import profile, profile_editor
from app.services.ingestion.prefilter import Prefilter
from app.services.matching import service as matching
from app.services.matching.hard_filters import SALARY_REASON, evaluate, salary_gap
from tests.agent_support import mcp_call
from tests.matching_support import _demo_profile_data, demo_extraction, demo_profile
from tests.skills_support import add_job

TITLE = "Data Engineer (m/f/d)"
FLOOR = 61_234  # por encima de los 42 000 de la oferta demo: la descarta

JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}
LOCAL = "http://127.0.0.1:8000"


def policy(**changes: object) -> HardFilterPolicy:
    return get_policies().hard_filters.model_copy(update=changes)


def profile_with(floor: int | None = None, **preferences: Any) -> CandidateProfile:
    data = json.loads(json.dumps(_demo_profile_data()))
    data["preferences"].update(preferences)
    data["private"] = {"salary_floor_eur": floor}
    return CandidateProfile.model_validate(data)


def failures(ext=None, prof=None, pol=None, title: str = TITLE) -> dict[str, str]:
    result = evaluate(title, ext or demo_extraction(), prof or profile_with(), pol or policy())
    return {f.filter: f.reason for f in result.failures}


def bare_profile_data() -> dict[str, Any]:
    """El perfil demo sin nada de la fase 27.5: como lo tenía alguien antes."""
    data = json.loads(json.dumps(_demo_profile_data()))
    for key in (
        "min_years_required",
        "discard_title_keywords",
        "contract_types",
        "employment_types",
        "excluded_employer_kinds",
    ):
        data["preferences"].pop(key, None)
    data["private"] = {"salary_floor_eur": None}
    return data


# --- Esquema ----------------------------------------------------------------------------------


def test_defaults_are_empty_and_not_dumped() -> None:
    prof = CandidateProfile.model_validate(bare_profile_data())
    prefs = prof.preferences
    assert prefs.min_years_required is None
    assert prefs.discard_title_keywords == prefs.contract_types == []
    assert prefs.employment_types == prefs.excluded_employer_kinds == []
    dumped = prof.model_dump(mode="json")
    assert dumped == bare_profile_data()  # mismo volcado que antes de la fase
    assert profile.content_hash(prof) == profile.content_hash(
        CandidateProfile.model_validate(bare_profile_data())
    )
    for key in ("min_years_required", "discard_title_keywords", "contract_types"):
        assert key not in dumped["preferences"]


def test_min_years_cannot_exceed_max() -> None:
    with pytest.raises(ValueError, match="mínimo de años"):
        profile_with(min_years_required=5, max_years_required=3)
    assert profile_with(min_years_required=3, max_years_required=3)


@pytest.mark.parametrize("floor", ["cuarenta mil", True, -5, 0, 35000.5])
def test_invalid_salary_floor_is_rejected_without_echoing_it(floor: object) -> None:
    data = bare_profile_data()
    data["private"] = {"salary_floor_eur": floor}
    with pytest.raises(ValueError, match="sueldo mínimo") as info:
        CandidateProfile.model_validate(data)
    issue = info.value.errors()[0]["ctx"]["error"].issues[0]  # type: ignore[attr-defined]
    assert issue.received is None


def test_unknown_values_are_rejected() -> None:
    with pytest.raises(ValueError):
        profile_with(contract_types=["indefinido"])
    with pytest.raises(ValueError):
        profile_with(excluded_employer_kinds=["direct"])


# --- Filtros duros ----------------------------------------------------------------------------


def test_a_profile_without_new_fields_filters_as_before() -> None:
    bare = CandidateProfile.model_validate(bare_profile_data())
    ext = demo_extraction(
        contract_type="fixed_term", employment_type="part_time", employer_kind="consultancy"
    )
    assert failures(ext, bare) == {}


def test_min_years_with_tolerance() -> None:
    prof = profile_with(min_years_required=4, max_years_required=6)
    assert "years" in failures(demo_extraction(years_experience_min=2), prof)
    assert "mínimo es 4" in failures(demo_extraction(years_experience_min=2), prof)["years"]
    assert failures(demo_extraction(years_experience_min=3), prof) == {}  # 1 de tolerancia
    assert failures(demo_extraction(years_experience_min=None), prof) == {}


@pytest.mark.parametrize(
    ("salary", "discarded"),
    [
        ({"min": 50000, "max": 58000, "currency": "EUR", "period": "year"}, True),
        ({"min": 50000, "max": 62000, "currency": "EUR", "period": "year"}, False),
        ({"min": 4000, "max": 5000, "currency": "EUR", "period": "month"}, True),  # 60 000
        ({"min": 4000, "max": 5200, "currency": "eur", "period": "month"}, False),  # 62 400
        ({"min": 50000, "max": None, "currency": "EUR", "period": "year"}, True),  # solo mínimo
        ({"min": None, "max": 70000, "currency": "EUR", "period": "year"}, False),
        ({"min": 30000, "max": 40000, "currency": "USD", "period": "year"}, False),
        ({"min": 20, "max": 25, "currency": "EUR", "period": "hour"}, False),
        ({"min": 30000, "max": 40000, "currency": None, "period": "year"}, False),
        ({"min": 30000, "max": 40000, "currency": "EUR", "period": None}, False),
        (None, False),
    ],
)
def test_salary_floor(salary: dict[str, Any] | None, discarded: bool) -> None:
    got = failures(demo_extraction(salary=salary), profile_with(FLOOR))
    assert ("salary" in got) == discarded
    if discarded:
        assert got["salary"] == SALARY_REASON
        assert str(FLOOR) not in got["salary"] and "61" not in got["salary"]


def test_salary_gap_is_the_difference_for_the_ui() -> None:
    ext = demo_extraction()  # 36 000 – 42 000 EUR al año
    assert salary_gap(ext, 50_000) == 8_000
    assert salary_gap(ext, 42_000) is None
    assert salary_gap(ext, None) is None


def test_no_floor_never_filters_by_salary() -> None:
    assert "salary" not in failures(
        demo_extraction(salary={"min": 1, "max": 2, "currency": "EUR", "period": "year"})
    )


@pytest.mark.parametrize(
    ("contract", "employment", "filtered"),
    [
        ("permanent", "full_time", False),
        ("fixed_term", "full_time", True),
        ("unknown", "full_time", False),
        (None, "full_time", False),
        ("permanent", "part_time", True),
        ("permanent", "contract", False),  # no dice la jornada
        ("permanent", "unknown", False),
        ("freelance", "internship", True),
    ],
)
def test_contract_and_employment(contract: str | None, employment: str, filtered: bool) -> None:
    prof = profile_with(contract_types=["permanent", "freelance"], employment_types=["full_time"])
    ext = demo_extraction(contract_type=contract, employment_type=employment)
    assert ("contract" in failures(ext, prof)) == filtered


def test_exclude_signals_fixed_term_is_the_same_as_not_accepting_it() -> None:
    ext = demo_extraction(contract_type="fixed_term")
    by_signal = failures(ext, profile_with(exclude_signals=["fixed_term"]))
    by_contract = failures(ext, profile_with(contract_types=["permanent", "freelance"]))
    assert by_signal == by_contract
    assert set(by_signal) == {"contract"}
    # Las dos formas a la vez: manda la más estricta.
    both = profile_with(exclude_signals=["fixed_term"], contract_types=["fixed_term", "permanent"])
    assert "contract" in failures(ext, both)
    assert failures(demo_extraction(contract_type="permanent"), both) == {}


@pytest.mark.parametrize(
    ("changes", "filtered"),
    [
        ({"employer_kind": "consultancy"}, True),
        ({"employer_kind": "agency"}, False),
        ({"employer_kind": "direct"}, False),
        ({"employer_kind": "unknown"}, False),
        ({}, False),
    ],
)
def test_employer_kind(changes: dict[str, Any], filtered: bool) -> None:
    prof = profile_with(excluded_employer_kinds=["consultancy"])
    assert ("employer_kind" in failures(demo_extraction(**changes), prof)) == filtered


def test_is_agency_counts_as_agency() -> None:
    prof = profile_with(excluded_employer_kinds=["agency"])
    assert "employer_kind" in failures(demo_extraction(is_agency=True), prof)
    assert "employer_kind" in failures(
        demo_extraction(is_agency=True, employer_kind="unknown"), prof
    )
    # La extracción dice algo más concreto: manda (también `consultancy` frente a `is_agency`).
    assert failures(demo_extraction(is_agency=True, employer_kind="consultancy"), prof) == {}
    assert failures(demo_extraction(is_agency=True, employer_kind="direct"), prof) == {}


def test_discard_keywords_of_profile_and_policy_add_up() -> None:
    prof = profile_with(discard_title_keywords=["Prácticas"])
    pol = policy(discard_title_keywords=["sales"])
    assert "title_keyword" in failures(prof=prof, pol=pol, title="Data Engineer en prácticas")
    assert "title_keyword" in failures(prof=prof, pol=pol, title="Sales Data Engineer")
    assert failures(prof=prof, pol=pol) == {}


# --- Filtro previo ----------------------------------------------------------------------------


def test_prefilter_uses_the_profile_keywords(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_policies().hard_filters, "discard_title_keywords", ["sales"])
    prefilter = Prefilter(demo_profile(discard_title_keywords=["becario"]).preferences, [])
    for title in ("Data Engineer becario", "Sales Data Engineer"):
        verdict = prefilter.check(title, "Vigo", None)
        assert not verdict.passed and "palabras de descarte" in (verdict.reason or "")
    assert prefilter.check("Data Engineer", "Vigo", None).passed


# --- Servicio, API y privacidad ---------------------------------------------------------------


@pytest.fixture
def client(isolated_env: Path) -> Iterator[TestClient]:
    migrations.upgrade()
    shutil.copyfile(REPO_ROOT / "demo" / "profile.example.yaml", isolated_env / "profile.yaml")
    with session_scope() as session:
        profile.import_profile(session, isolated_env / "profile.yaml")
    with TestClient(create_app(), base_url=LOCAL) as client:
        yield client


def _floor(client: TestClient) -> dict[str, Any]:
    response = client.get("/profile/salary-floor")
    assert response.status_code == 200, response.text
    return response.json()


def test_salary_floor_from_the_ui_filters_without_leaking(
    client: TestClient, isolated_env: Path
) -> None:
    job_id = add_job(["Python", "SQL"])
    state = _floor(client)
    assert state["salary_floor_eur"] == 30000

    body = {"file_hash": state["file_hash"], "salary_floor_eur": FLOOR}
    saved = client.put("/profile/salary-floor", json=body, headers=JSON)
    assert saved.status_code == 200, saved.text
    assert saved.json()["changed"] and saved.json()["rescore_queued"]
    assert "diff" not in saved.json()
    text = (isolated_env / "profile.yaml").read_text(encoding="utf-8")
    assert f"salary_floor_eur: {FLOOR}" in text
    assert "# bruto anual en euros" in text  # conserva el comentario
    assert _floor(client)["salary_floor_eur"] == FLOOR

    # Con el hash de antes: conflicto.
    stale = client.put("/profile/salary-floor", json=body, headers=JSON)
    assert stale.status_code == 409

    # La oferta demo (42 000) queda por debajo: el motivo sin cifras; la diferencia, solo la UI.
    with session_scope() as session:
        view = matching.get_match(session, job_id)
    reasons = {f.filter: f.reason for f in view.hard_filters.failures}
    assert reasons["salary"] == SALARY_REASON
    gap = client.get(f"/jobs/{job_id}/salary-gap")
    assert gap.status_code == 200 and gap.json() == {"gap_eur": FLOOR - 42000}

    # Hacia el agente: ni la cifra ni la diferencia (MCP; la CLI `--json` da lo mismo por la
    # paridad).
    for tool, args in (
        ("get_match", {"job_id": job_id}),
        ("get_profile", {}),
        ("get_timeline", {"job_id": job_id}),
        ("get_status", {}),
    ):
        _error, out = mcp_call(tool, args)
        dumped = json.dumps(out, ensure_ascii=False, default=str)
        assert str(FLOOR) not in dumped and str(FLOOR - 42000) not in dumped, tool
        assert "salary_floor_eur" not in dumped, tool

    # El diff del historial lo oculta.
    with session_scope() as session:
        diff = profile.diff_last_two(session)
    assert str(FLOOR) not in json.dumps(diff.model_dump(mode="json"), ensure_ascii=False)

    # Quitarlo: `null`, y deja de filtrar por sueldo.
    state = _floor(client)
    body = {"file_hash": state["file_hash"], "salary_floor_eur": None}
    assert client.put("/profile/salary-floor", json=body, headers=JSON).status_code == 200
    assert _floor(client)["salary_floor_eur"] is None
    assert client.get(f"/jobs/{job_id}/salary-gap").json() == {"gap_eur": None}


def test_salary_floor_routes_are_ui_only(client: TestClient) -> None:
    body = {"file_hash": _floor(client)["file_hash"], "salary_floor_eur": 40000}
    as_form = client.put("/profile/salary-floor", data={"salary_floor_eur": "1"})
    assert as_form.status_code == 403  # no es JSON: no viene de la UI
    evil = {"Origin": "https://evil.example", "Content-Type": "application/json"}
    assert client.get("/profile/salary-floor", headers=evil).status_code == 403
    assert client.put("/profile/salary-floor", json=body, headers=evil).status_code == 403
    bad = {**body, "salary_floor_eur": 0}
    assert client.put("/profile/salary-floor", json=bad, headers=JSON).status_code == 422


def test_editable_profile_shows_the_policy_keywords(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_policies().hard_filters, "discard_title_keywords", ["sales"])
    state = client.get("/profile/editable").json()
    assert state["policy_discard_title_keywords"] == ["sales"]
    assert state["policy_years_tolerance"] == get_policies().hard_filters.years_tolerance
    assert "private" not in state["profile"]


def test_saving_preferences_rescores_open_jobs(client: TestClient, isolated_env: Path) -> None:
    job_id = add_job(["Python", "SQL"])
    state = client.get("/profile/editable").json()
    prefs = state["profile"]["preferences"]
    prefs["employment_types"] = ["part_time"]
    body = {"file_hash": state["file_hash"], "content": prefs}
    saved = client.put("/profile/sections/preferences", json=body, headers=JSON)
    assert saved.status_code == 200, saved.text
    data = yaml.safe_load((isolated_env / "profile.yaml").read_text(encoding="utf-8"))
    assert data["preferences"]["employment_types"] == ["part_time"]
    with session_scope() as session:
        result = matching.rescore_open_jobs(session)
        view = matching.get_match(session, job_id)
    assert job_id in result.closed
    assert "contract" in {f.filter for f in view.hard_filters.failures}


def test_salary_floor_without_profile_file(isolated_env: Path) -> None:
    assert profile_editor.get_salary_floor(isolated_env / "nada.yaml").salary_floor_eur is None


def test_section_diff_never_shows_the_salary(client: TestClient, isolated_env: Path) -> None:
    # Una clave nueva de `preferences` va al final, justo antes de `private`: el diff la rodea de
    # contexto. Se quita y se vuelve a añadir.
    state = _floor(client)
    body = {"file_hash": state["file_hash"], "salary_floor_eur": FLOOR}
    assert client.put("/profile/salary-floor", json=body, headers=JSON).status_code == 200
    editable = client.get("/profile/editable").json()
    prefs = editable["profile"]["preferences"]
    prefs.pop("excluded_employer_kinds")
    body = {"file_hash": editable["file_hash"], "content": prefs}
    assert client.put("/profile/sections/preferences", json=body, headers=JSON).status_code == 200
    editable = client.get("/profile/editable").json()
    prefs = editable["profile"]["preferences"]
    prefs["excluded_employer_kinds"] = ["agency", "consultancy"]
    body = {"file_hash": editable["file_hash"], "content": prefs, "dry_run": True}
    preview = client.put("/profile/sections/preferences", json=body, headers=JSON)
    assert preview.status_code == 200, preview.text
    diff = preview.json()["diff"]
    assert "consultancy" in diff
    assert str(FLOOR) not in diff
    assert "<oculto>" in diff  # la línea de contexto, con el valor oculto


def test_mask_private_keeps_everything_else() -> None:
    text = (
        "preferences:\n  roles: [Data Engineer]\nprivate:   # nunca sale\n"
        "  salary_floor_eur: 30000   # bruto\n  nota: algo\n  vacio:\nschema_version: 1\n"
    )
    masked = profile_editor._mask_private(text)
    assert "30000" not in masked and "algo" not in masked
    assert "  roles: [Data Engineer]" in masked and "schema_version: 1" in masked
    assert "  vacio:\n" in masked
    inline = profile_editor._mask_private("private: {salary_floor_eur: 30000}\n")
    assert inline == "private: <oculto>\n"
