"""Servicio de perfil: versionado por hash, vista pública, diff, init y resolución de evidencias."""

import copy
import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import ProfileVersion
from app.services import profile
from app.services.profile import EXAMPLE_PATH

EXAMPLE: dict[str, Any] = yaml.safe_load(EXAMPLE_PATH.read_text(encoding="utf-8"))
SECRETS = {
    "email": "lucia.varela@example.com",
    "phone": "+34 600 000 000",
    "salary_floor_eur": 31415,
    "private_note": "Nota privada: no la ve ningún agente",
}


def _write(path: Path, data: dict[str, Any]) -> Path:
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def _with_secrets() -> dict[str, Any]:
    data = copy.deepcopy(EXAMPLE)
    data["private"] = {
        "salary_floor_eur": SECRETS["salary_floor_eur"],
        "notes": SECRETS["private_note"],
        "nested": {"deep": [SECRETS["private_note"]]},
    }
    return data


def _count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(ProfileVersion)) or 0


# --- import_profile / current -------------------------------------------------------------------


def test_import_same_file_twice_creates_one_version(session: Session) -> None:
    first = profile.import_profile(session, EXAMPLE_PATH)
    second = profile.import_profile(session, EXAMPLE_PATH)
    assert first.created is True
    assert second.created is False
    assert second.profile_version_id == first.profile_version_id
    assert second.content_hash == first.content_hash
    assert _count(session) == 1


def test_comments_and_formatting_do_not_create_a_version(session: Session, tmp_path: Path) -> None:
    profile.import_profile(session, EXAMPLE_PATH)
    reformatted = _write(tmp_path / "p.yaml", EXAMPLE)  # sin comentarios, otro formato
    assert profile.import_profile(session, reformatted).created is False


def test_changed_content_creates_new_current_version(session: Session, tmp_path: Path) -> None:
    v1 = profile.import_profile(session, EXAMPLE_PATH)
    data = copy.deepcopy(EXAMPLE)
    data["headline"] = "Data Engineer · Python · SQL"
    v2 = profile.import_profile(session, _write(tmp_path / "p.yaml", data))
    assert v2.created and v2.profile_version_id > v1.profile_version_id
    stored = profile.current(session)
    assert stored.profile_version_id == v2.profile_version_id
    assert stored.profile.headline == "Data Engineer · Python · SQL"


def test_going_back_to_previous_content_creates_a_version(session: Session, tmp_path: Path) -> None:
    v1 = profile.import_profile(session, EXAMPLE_PATH)
    data = copy.deepcopy(EXAMPLE)
    data["headline"] = "Otra cosa"
    profile.import_profile(session, _write(tmp_path / "p.yaml", data))
    v3 = profile.import_profile(session, EXAMPLE_PATH)
    assert v3.created and v3.content_hash == v1.content_hash
    assert profile.current(session).profile.headline == EXAMPLE["headline"]
    assert _count(session) == 3


def test_invalid_file_is_not_imported(session: Session, tmp_path: Path) -> None:
    data = copy.deepcopy(EXAMPLE)
    data["skills"][0]["level"] = "Z"
    with pytest.raises(profile.ProfileValidationError):
        profile.import_profile(session, _write(tmp_path / "p.yaml", data))
    assert _count(session) == 0


def test_current_without_profile(session: Session) -> None:
    with pytest.raises(profile.ProfileNotFoundError, match="jh profile import"):
        profile.current(session)


def test_get_version(session: Session) -> None:
    result = profile.import_profile(session, EXAMPLE_PATH)
    assert profile.get_version(session, result.profile_version_id).profile.headline
    with pytest.raises(profile.ProfileNotFoundError):
        profile.get_version(session, 99)


# --- public_view --------------------------------------------------------------------------------


def _assert_no_secrets(view: dict[str, Any]) -> None:
    text = json.dumps(view, ensure_ascii=False)
    for secret in SECRETS.values():
        assert str(secret) not in text
    assert "private" not in view
    assert "salary" not in text
    for key in ("email", "phone"):
        assert key not in view.get("personal", {})


def test_public_view_never_contains_contact_or_private_data() -> None:
    candidate = profile.CandidateProfile.model_validate(_with_secrets())
    view = profile.public_view(candidate)
    _assert_no_secrets(view)
    assert view["personal"]["name"] == "Lucía Varela Otero"
    assert view["personal"]["city"] == "Santiago de Compostela"
    # Lo que el agente sí necesita: niveles privados de skill, NDA, historias.
    assert view["skills"][0] == {"name": "Python", "level": "F", "category": "Lenguajes"}
    assert view["experience"][0]["achievements"][2]["nda"] is True
    assert len(view["stories"]) == 2
    # Las preferencias de CV también: el agente elige plantilla y orienta la redacción con ellas.
    cv = view["preferences"]["cv"]
    assert cv["default_template"] == "clasica-foto"
    assert cv["instructions"] and cv["avoid"]
    assert cv["template_rules"][0] == {
        "when": {
            "ats": ["workday", "taleo", "successfactors", "icims"],
            "country": [],
            "domain": [],
            "language": [],
        },
        "use": "ats-simple",
    }


@pytest.mark.parametrize(
    "sections",
    [None, ["personal"], ["personal", "preferences"], ["skills"], list(profile.PUBLIC_SECTIONS)],
)
def test_public_view_by_sections_never_leaks(sections: list[Any] | None) -> None:
    candidate = profile.CandidateProfile.model_validate(_with_secrets())
    view = profile.public_view(candidate, sections)
    _assert_no_secrets(view)
    expected = set(sections or profile.PUBLIC_SECTIONS) | {"schema_version"}
    assert set(view) == expected


def test_public_view_is_an_allow_list() -> None:
    # Todo campo de `personal` que no esté en la lista blanca se queda fuera, también los futuros.
    fields = set(profile.CandidateProfile.model_fields["personal"].annotation.model_fields)  # type: ignore[union-attr]
    assert fields - set(profile.PUBLIC_PERSONAL_FIELDS) == {"email", "phone"}
    sections = set(profile.CandidateProfile.model_fields) - set(profile.PUBLIC_SECTIONS)
    assert sections == {"schema_version", "private"}


def test_get_public_profile(session: Session, tmp_path: Path) -> None:
    profile.import_profile(session, _write(tmp_path / "p.yaml", _with_secrets()))
    result = profile.get_public_profile(session, ["personal", "summary"])
    assert result.profile_version_id == 1
    assert set(result.profile) == {"schema_version", "personal", "summary"}
    _assert_no_secrets(result.model_dump(mode="json")["profile"])


# --- diff ---------------------------------------------------------------------------------------


def test_diff_without_versions(session: Session) -> None:
    with pytest.raises(profile.ProfileNotFoundError):
        profile.diff_last_two(session)


def test_diff_with_one_version(session: Session) -> None:
    profile.import_profile(session, EXAMPLE_PATH)
    assert profile.diff_last_two(session) == profile.ProfileDiff(
        from_version=None, to_version=1, diff=""
    )


def test_diff_between_last_two_versions(session: Session, tmp_path: Path) -> None:
    profile.import_profile(session, EXAMPLE_PATH)
    data = copy.deepcopy(EXAMPLE)
    data["headline"] = "Data Engineer · Python"
    profile.import_profile(session, _write(tmp_path / "a.yaml", data))
    data["skills"].append({"name": "Kafka", "level": "B", "category": "Datos"})
    profile.import_profile(session, _write(tmp_path / "b.yaml", data))

    result = profile.diff_last_two(session)
    assert (result.from_version, result.to_version) == (2, 3)
    assert "+- name: Kafka" in result.diff
    assert "headline" not in result.diff  # cambió entre la 1 y la 2, no entre la 2 y la 3
    assert result.diff.startswith("--- versión 2\n+++ versión 3\n")


def test_diff_hides_private_values(session: Session, tmp_path: Path) -> None:
    profile.import_profile(session, EXAMPLE_PATH)
    profile.import_profile(session, _write(tmp_path / "p.yaml", _with_secrets()))
    result = profile.diff_last_two(session)
    assert str(SECRETS["salary_floor_eur"]) not in result.diff
    assert SECRETS["private_note"] not in result.diff
    assert "# private: ha cambiado" in result.diff


# --- init ---------------------------------------------------------------------------------------


def test_init_copies_example_once(isolated_env: Path) -> None:
    dest = profile.init_profile()
    assert dest == isolated_env / "profile.yaml"
    assert dest.read_text(encoding="utf-8") == EXAMPLE_PATH.read_text(encoding="utf-8")
    dest.write_text("mío", encoding="utf-8")
    with pytest.raises(FileExistsError):
        profile.init_profile()
    assert dest.read_text(encoding="utf-8") == "mío"


# --- resolve_evidence ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ref", "expected"),
    [
        ("exp-norteconsulting/a1",
         "Migré 40 procesos ETL de SSIS a pipelines en Python sobre Snowflake. "
         "(métrica: -35 % en tiempo de carga nocturna)"),
        ("exp-norteconsulting/a2",
         "Diseñé el modelo dimensional de ventas y stock usado por 3 equipos de negocio."),
        ("exp-norteconsulting/a3",
         "Construí un asistente interno con LangChain para consultar documentación técnica de "
         "proyectos. [NDA]"),
        ("exp-datagal", "Junior Data Engineer en DataGal (ficticia) (2023-01 – 2024-02)"),
        ("prj-tfg", "Detección de anomalías en consumo eléctrico (TFG): Modelo de detección de "
                    "anomalías sobre series temporales de consumo de 500 hogares."),
        ("edu-grado", "Grado en Ciencia e Ingeniería de Datos, Universidad ficticia de Galicia"),
        ("cert-aws-ccp", "AWS Certified Cloud Practitioner (Amazon Web Services, 2024-05)"),
    ],
)  # fmt: skip
def test_resolve_evidence(ref: str, expected: str) -> None:
    candidate = profile.load_from_yaml(EXAMPLE_PATH)
    assert profile.resolve_evidence(candidate, ref) == expected


@pytest.mark.parametrize("ref", ["exp-acme/a2", "exp-datagal/a9", "st-migracion", "", "a1"])
def test_resolve_unknown_evidence(ref: str) -> None:
    candidate = profile.load_from_yaml(EXAMPLE_PATH)
    with pytest.raises(profile.EvidenceNotFoundError, match="no existe"):
        profile.resolve_evidence(candidate, ref)
