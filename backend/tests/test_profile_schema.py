"""`CandidateProfile` y `load_from_yaml`: perfiles válidos y rotos, con errores claros."""

import copy
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.schemas.profile import CandidateProfile, ProfileConsistencyError
from app.services.profile import (
    EXAMPLE_PATH,
    ProfileIssue,
    ProfileNotFoundError,
    ProfileValidationError,
    field_path,
    load_from_yaml,
)

EXAMPLE: dict[str, Any] = yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))


def _write(tmp_path: Path, data: dict[str, Any] | str) -> Path:
    path = tmp_path / "profile.yaml"
    text = data if isinstance(data, str) else yaml.safe_dump(data, allow_unicode=True)
    path.write_text(text, encoding="utf-8")
    return path


def _issues(tmp_path: Path, change: Callable[[dict[str, Any]], None]) -> dict[str, ProfileIssue]:
    data = copy.deepcopy(EXAMPLE)
    change(data)
    with pytest.raises(ProfileValidationError) as info:
        load_from_yaml(_write(tmp_path, data))
    return {issue.field: issue for issue in info.value.issues}


def test_example_profile_is_valid() -> None:
    profile = load_from_yaml(EXAMPLE_PATH)
    assert profile.personal.name == "Lucía Varela Otero"
    assert [e.id for e in profile.experience] == ["exp-norteconsulting", "exp-datagal"]
    assert profile.experience[0].end == "present"
    assert profile.private == {"salary_floor_eur": None}


def test_yaml_with_bom_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "profile.yaml"
    path.write_text(EXAMPLE_PATH.read_text(encoding="utf-8"), encoding="utf-8-sig")
    assert load_from_yaml(path).headline


@pytest.mark.parametrize(
    ("loc", "expected"),
    [
        (("experience", 1, "achievements", 0, "id"), "experience[1].achievements[0].id"),
        (("headline",), "headline"),
        (("preferences", "cv", "photo_policy", "by_country", "gb"),
         "preferences.cv.photo_policy.by_country.gb"),
        ((), "(perfil)"),
    ],
)  # fmt: skip
def test_field_path(loc: tuple[str | int, ...], expected: str) -> None:
    assert field_path(loc) == expected


def test_field_errors_carry_their_path(tmp_path: Path) -> None:
    def change(d: dict[str, Any]) -> None:
        d["experience"][1]["achievements"][0]["id"] = "A 1"
        d["experience"][0]["start"] = "2024-13"
        d["skills"][0]["level"] = "X"
        d["preferences"]["remote_modes"] = ["anywhere"]
        d["stories"][1]["result"] = ""
        d["unknown"] = 1
        del d["headline"]

    issues = _issues(tmp_path, change)
    assert set(issues) == {
        "experience[1].achievements[0].id",
        "experience[0].start",
        "skills[0].level",
        "preferences.remote_modes[0]",
        "stories[1].result",
        "unknown",
        "headline",
    }
    assert issues["skills[0].level"].reason == "Debe ser uno de: F, C+, C, B."
    assert issues["skills[0].level"].received == "X"
    assert "AAAA-MM" in issues["experience[0].start"].reason
    assert issues["unknown"].reason == "Campo no permitido: no existe en el esquema."
    assert issues["headline"].reason == "Campo obligatorio."
    assert issues["headline"].received is None


@pytest.mark.parametrize("value", ["2024-3", "2024/03", "present", "marzo 2024"])
def test_start_date_format(tmp_path: Path, value: str) -> None:
    issues = _issues(tmp_path, lambda d: d["experience"][0].update(start=value))
    assert "AAAA-MM" in issues["experience[0].start"].reason


def test_full_date_parsed_by_yaml_is_rejected(tmp_path: Path) -> None:
    text = EXAMPLE_PATH.read_text(encoding="utf-8").replace("start: 2024-03", "start: 2024-03-01")
    with pytest.raises(ProfileValidationError) as info:
        load_from_yaml(_write(tmp_path, text))
    [issue] = info.value.issues
    assert issue.field == "experience[0].start"
    assert "AAAA-MM" in issue.reason


def test_end_before_start(tmp_path: Path) -> None:
    issues = _issues(tmp_path, lambda d: d["experience"][1].update(end="2022-12"))
    assert issues["experience[1]"].reason == "`end` no puede ser anterior a `start`."


def test_summary_needs_a_language(tmp_path: Path) -> None:
    issues = _issues(tmp_path, lambda d: d.update(summary={}))
    assert "al menos un idioma" in issues["summary"].reason


def test_story_needs_evidence(tmp_path: Path) -> None:
    issues = _issues(tmp_path, lambda d: d["stories"][0].update(evidence=[]))
    assert "stories[0].evidence" in issues


def test_duplicate_ids(tmp_path: Path) -> None:
    def change(d: dict[str, Any]) -> None:
        d["projects"][0]["id"] = "exp-datagal"
        d["experience"][1]["achievements"][1]["id"] = "a1"
        d["skills"].append({"name": "python", "level": "C"})
        d["basic_skills"].append("SQL")

    issues = _issues(tmp_path, change)
    assert set(issues) == {
        "projects[0].id",
        "experience[1].achievements[1].id",
        "skills[12].name",
        "basic_skills[3]",
    }
    assert issues["projects[0].id"].received == "exp-datagal"
    assert "exp-datagal" in issues["experience[1].achievements[1].id"].reason


def test_same_achievement_id_in_different_experiences_is_fine() -> None:
    profile = load_from_yaml(EXAMPLE_PATH)
    assert profile.experience[0].achievements[0].id == profile.experience[1].achievements[0].id


def test_undeclared_skills(tmp_path: Path) -> None:
    def change(d: dict[str, Any]) -> None:
        d["experience"][0]["achievements"][1]["skills"].append("Rust")
        d["projects"][0]["skills"].append("PyTorch")
        d["experience"][1]["achievements"][1]["skills"].append("docker")  # basic_skills: vale

    issues = _issues(tmp_path, change)
    assert set(issues) == {"experience[0].achievements[1].skills[3]", "projects[0].skills[3]"}
    assert "basic_skills" in issues["projects[0].skills[3]"].reason


@pytest.mark.parametrize("ref", ["exp-nope/a1", "exp-datagal/a9", "st-migracion", "a1"])
def test_broken_evidence(tmp_path: Path, ref: str) -> None:
    issues = _issues(tmp_path, lambda d: d["stories"][1].update(evidence=[ref]))
    assert issues["stories[1].evidence[0]"].received == ref


@pytest.mark.parametrize("ref", ["exp-datagal", "prj-tfg", "edu-grado", "cert-aws-ccp"])
def test_evidence_can_cite_other_sections(tmp_path: Path, ref: str) -> None:
    data = copy.deepcopy(EXAMPLE)
    data["stories"][1]["evidence"] = [ref]
    assert load_from_yaml(_write(tmp_path, data)).stories[1].evidence == [ref]


def test_consistency_error_directly_from_pydantic() -> None:
    data = copy.deepcopy(EXAMPLE)
    data["stories"][0]["evidence"] = ["exp-nope/a1"]
    with pytest.raises(ValueError, match="La evidencia no existe") as info:
        CandidateProfile.model_validate(data)
    assert isinstance(info.value.errors()[0]["ctx"]["error"], ProfileConsistencyError)  # type: ignore[attr-defined]


def test_preferences_validation(tmp_path: Path) -> None:
    def change(d: dict[str, Any]) -> None:
        d["preferences"]["seniority_target"] = ["junior", "guru"]
        d["preferences"]["languages_for_work"] = ["es", "english"]
        d["preferences"]["cv"]["photo_policy"]["by_country"]["gb"] = False
        d["preferences"]["cv"]["max_pages"] = 0

    issues = _issues(tmp_path, change)
    assert set(issues) == {
        "preferences.seniority_target[1]",
        "preferences.languages_for_work[1]",
        "preferences.cv.photo_policy.by_country.gb",
        "preferences.cv.max_pages",
    }


def test_schema_version(tmp_path: Path) -> None:
    issues = _issues(tmp_path, lambda d: d.update(schema_version=2))
    assert issues["schema_version"].reason == "Debe ser uno de: 1."


def test_malformed_yaml_reports_line(tmp_path: Path) -> None:
    with pytest.raises(ProfileValidationError) as info:
        load_from_yaml(_write(tmp_path, "headline: [sin cerrar\nsummary: x\n"))
    [issue] = info.value.issues
    assert issue.field == "(yaml)"
    assert "línea" in issue.reason


@pytest.mark.parametrize("text", ["", "- una lista\n", "solo texto\n"])
def test_yaml_must_be_a_mapping(tmp_path: Path, text: str) -> None:
    with pytest.raises(ProfileValidationError) as info:
        load_from_yaml(_write(tmp_path, text))
    assert info.value.issues[0].reason == "Debe ser un objeto YAML."


def test_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ProfileNotFoundError, match="jh profile init"):
        load_from_yaml(tmp_path / "no.yaml")
