"""Historial de «Mi perfil» (fase 44.6): cambios por bloques entre versiones, lista y restaurar."""

import copy
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.config import REPO_ROOT
from app.core.db import session_scope
from app.models import ProfileEdit, ProfileVersion
from app.schemas.profile import CandidateProfile
from app.services import profile as profiles
from app.services import profile_editor as editor
from app.services import profile_history as history

EXAMPLE = REPO_ROOT / "demo" / "profile.example.yaml"
JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}
LOCAL = "http://127.0.0.1:8000"


def _base() -> dict[str, Any]:
    return profiles.load_from_yaml(EXAMPLE).model_dump(mode="json")


def _changes(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    return [c.model_dump(exclude_defaults=True) for c in history.compare(old, new)]


def _other_level(level: str) -> str:
    return "B" if level != "B" else "F"


# --- Comparación -----------------------------------------------------------------------------


def test_same_data_has_no_changes() -> None:
    assert history.compare(_base(), _base()) == []


def test_a_field_change_says_before_and_after_in_its_block() -> None:
    old, new = _base(), _base()
    new["headline"] = "Data Engineer · Python"
    new["summary"]["en"] = "Data engineer."
    new["personal"]["city"] = "Vigo"
    [change] = _changes(old, new)
    assert change["block"] == "personal" and change["kind"] == "changed"
    paths = {tuple(f["path"]): (f.get("before"), f.get("after")) for f in change["fields"]}
    assert paths[("headline",)] == (old["headline"], "Data Engineer · Python")
    assert paths[("summary", "en")] == (old["summary"]["en"], "Data engineer.")
    assert paths[("city",)] == (old["personal"]["city"], "Vigo")


def test_skills_are_matched_by_name_added_removed_and_changed() -> None:
    old, new = _base(), _base()
    first, second = old["skills"][0], old["skills"][1]
    new["skills"] = [s for s in new["skills"] if s["name"] != second["name"]]
    new["skills"][0] = {**first, "level": _other_level(first["level"])}
    new["skills"].append({"name": "Rust", "level": "B", "category": None})
    changes = _changes(old, new)
    by_kind = {(c["kind"], c["label"]): c for c in changes}
    changed = by_kind[("changed", first["name"])]
    assert changed["fields"] == [
        {"path": ["level"], "before": first["level"], "after": _other_level(first["level"])}
    ]
    # Sin «Nombre: Rust»: ya es el nombre del elemento.
    assert by_kind[("added", "Rust")]["fields"] == [{"path": ["level"], "after": "B"}]
    removed = by_kind[("removed", second["name"])]
    assert {"path": ["level"], "before": second["level"]} in removed["fields"]
    assert {c["block"] for c in changes} == {"skills"}


def test_reordering_is_a_move_not_a_remove_and_add() -> None:
    old, new = _base(), _base()
    new["skills"].insert(0, new["skills"].pop(2))  # la tercera, primera
    [change] = _changes(old, new)
    assert change["kind"] == "moved"
    assert change["label"] == old["skills"][2]["name"]
    assert change["position"] == (3, 1)
    assert "fields" not in change


def test_a_moved_and_edited_item_counts_as_changed() -> None:
    old, new = _base(), _base()
    moved = new["skills"].pop(2)
    new["skills"].insert(0, {**moved, "category": "Otra"})
    [change] = _changes(old, new)
    assert change["kind"] == "changed" and change["position"] == (3, 1)


def test_nested_achievements_are_their_own_changes_under_their_experience() -> None:
    old, new = _base(), _base()
    job = new["experience"][1]
    before_text = job["achievements"][0]["text"]
    job["achievements"][0]["text"] = "Texto nuevo."
    job["achievements"].append({"id": "a99", "text": "Logro nuevo.", "skills": ["Python"]})
    del job["achievements"][1]
    changes = _changes(old, new)
    parent = f"{job['role']} · {job['company']}"
    assert all(c["block"] == "experience" for c in changes)
    assert all(c["parent"] == parent and c["within"] == "achievements" for c in changes)
    assert [c["kind"] for c in changes] == ["changed", "added", "removed"]
    assert changes[0]["fields"] == [
        {"path": ["text"], "before": before_text, "after": "Texto nuevo."}
    ]
    # Sin el id a la vista: es interno.
    assert changes[1]["fields"] == [
        {"path": ["text"], "after": "Logro nuevo."},
        {"path": ["skills"], "added": ["Python"]},
    ]


def test_lists_of_words_say_what_came_in_and_what_went_out() -> None:
    old, new = _base(), _base()
    roles = new["preferences"]["roles"]
    gone = roles.pop(0)
    roles.append("Ingeniería de plataformas")
    new["basic_skills"] = [*old["basic_skills"], "Kafka"]
    changes = _changes(old, new)
    search = next(c for c in changes if c["block"] == "search")
    assert search["fields"] == [
        {"path": ["roles"], "added": ["Ingeniería de plataformas"], "removed": [gone]}
    ]
    skills = next(c for c in changes if c["block"] == "skills")
    assert skills["fields"] == [{"path": ["basic_skills"], "added": ["Kafka"]}]


def test_cv_and_letter_preferences_go_to_their_own_blocks() -> None:
    old, new = _base(), _base()
    new["preferences"]["cv"]["max_pages"] = 3
    new["preferences"]["cv"]["photo_policy"]["by_country"]["FR"] = False
    letter_before = old["preferences"].get("cover_letter") or {}
    new["preferences"]["cover_letter"] = {**letter_before, "tone": "seco"}
    changes = _changes(old, new)
    cv = next(c for c in changes if c["block"] == "cv")
    paths = {tuple(f["path"]): f for f in cv["fields"]}
    assert paths[("max_pages",)]["after"] == 3
    assert paths[("photo_policy", "by_country", "FR")] == {
        "path": ["photo_policy", "by_country", "FR"],
        "after": False,
    }
    letter = next(c for c in changes if c["block"] == "letter")
    assert [f["path"] for f in letter["fields"]] == [["tone"]]
    assert letter["fields"][0]["after"] == "seco"


def test_private_only_says_it_changed() -> None:
    old, new = _base(), _base()
    new["private"] = {"salary_floor_eur": 99999}
    [change] = history.compare(old, new)
    assert change.block == "private" and change.hidden and change.fields == []
    assert "99999" not in change.model_dump_json()


def test_blocks_follow_the_editor_order_and_are_counted() -> None:
    old, new = _base(), _base()
    new["preferences"]["cv"]["max_pages"] = 3
    for skill in new["skills"][:2]:
        skill["level"] = _other_level(skill["level"])
    new["headline"] = "Otro"
    changes = history.compare(old, new)
    assert history.blocks_of(changes) == ["personal", "skills", "cv"]
    assert [(c.block, c.changes) for c in history.summarize(changes)] == [
        ("personal", 1),
        ("skills", 2),
        ("cv", 1),
    ]


# --- Versiones, origen y restaurar -----------------------------------------------------------


@pytest.fixture
def path(isolated_env: Path, session: Session) -> Path:
    target = isolated_env / "profile.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(EXAMPLE, target)
    profiles.import_profile(session, target, origin="agent")
    session.commit()
    return target


def _hash(path: Path) -> str:
    return editor.file_hash(path.read_bytes())


def _save_headline(session: Session, path: Path, text: str) -> None:
    editor.save_section(session, "headline", text, _hash(path), path=path)


def test_each_version_keeps_where_it_came_from(session: Session, path: Path) -> None:
    _save_headline(session, path, "Uno")
    editor.undo_last(session, _hash(path), path=path)
    origins = list(session.scalars(select(ProfileVersion.origin).order_by(ProfileVersion.id)))
    assert origins == ["agent", "ui", "undo"]


def test_the_list_goes_newest_first_with_what_changed(session: Session, path: Path) -> None:
    _save_headline(session, path, "Uno")
    _save_headline(session, path, "Dos")
    page = history.list_versions(session)
    assert [v.origin for v in page.versions] == ["ui", "ui", "agent"]
    newest, _, first = page.versions
    assert newest.current and not newest.restorable
    assert [(s.block, s.changes) for s in newest.summary] == [("personal", 1)]
    assert first.first and first.summary == [] and first.restorable
    assert not page.has_more


def test_the_list_comes_in_pages(session: Session, path: Path) -> None:
    for n in range(4):
        _save_headline(session, path, f"Titular {n}")
    page = history.list_versions(session, limit=2)
    assert len(page.versions) == 2 and page.has_more
    assert not page.versions[1].first  # la de antes viene en la consulta: tiene con qué comparar
    rest = history.list_versions(session, offset=4, limit=2)
    assert [v.first for v in rest.versions] == [True] and not rest.has_more


def test_the_detail_has_changes_restore_blocks_and_the_technical_diff(
    session: Session, path: Path
) -> None:
    first_id = history.list_versions(session).versions[0].id
    _save_headline(session, path, "Uno")
    latest = history.list_versions(session).versions[0]
    detail = history.version_changes(session, latest.id)
    assert detail.previous_id == first_id and detail.current
    assert [c.block for c in detail.changes] == ["personal"]
    assert detail.restore_blocks == []
    assert "+headline: Uno" in detail.technical_diff
    old = history.version_changes(session, first_id)
    assert old.changes == [] and old.technical_diff == "" and old.restorable
    assert old.restore_blocks == ["personal"]


def test_restoring_writes_only_what_changed_and_can_be_undone(session: Session, path: Path) -> None:
    original = path.read_text(encoding="utf-8")
    first_id = history.list_versions(session).versions[0].id
    _save_headline(session, path, "Uno")
    skills = copy.deepcopy(yaml.safe_load(path.read_text(encoding="utf-8"))["skills"])
    skills[0]["level"] = _other_level(skills[0]["level"])
    editor.save_section(session, "skills", skills, _hash(path), path=path)

    result = editor.restore_version(session, first_id, _hash(path), path=path)

    assert result.blocks == ["personal", "skills"]
    restored = path.read_text(encoding="utf-8")
    assert yaml.safe_load(restored) == yaml.safe_load(original)
    comments = [line for line in original.splitlines() if line.lstrip().startswith("#")]
    assert comments == [line for line in restored.splitlines() if line.lstrip().startswith("#")]
    assert result.file_hash == _hash(path)
    newest = session.scalars(select(ProfileVersion).order_by(ProfileVersion.id.desc())).first()
    assert newest is not None and newest.id == result.profile_version_id
    assert newest.origin == "restore"
    edit = session.scalars(select(ProfileEdit).order_by(ProfileEdit.id.desc())).first()
    assert edit is not None and edit.action == "restore"

    editor.undo_last(session, _hash(path), path=path)  # deshace la restauración
    assert yaml.safe_load(path.read_text(encoding="utf-8"))["skills"] == skills


def test_restoring_a_default_that_the_file_did_not_have(session: Session, path: Path) -> None:
    """`_merge` no escribe `false` en una clave nueva: la restauración tiene que quedar igual."""
    first_id = history.list_versions(session).versions[0].id
    experience = copy.deepcopy(yaml.safe_load(path.read_text(encoding="utf-8"))["experience"])
    experience[0]["achievements"][0]["nda"] = True
    editor.save_section(session, "experience", experience, _hash(path), path=path)
    editor.restore_version(session, first_id, _hash(path), path=path)
    restored = profiles.load_from_yaml(path).model_dump(mode="json")
    first = session.get(ProfileVersion, first_id)
    assert first is not None
    assert restored == CandidateProfile.model_validate(first.data).model_dump(mode="json")


def test_restoring_needs_the_hash_the_ui_read(session: Session, path: Path) -> None:
    first_id = history.list_versions(session).versions[0].id
    _save_headline(session, path, "Uno")
    with pytest.raises(editor.ProfileConflictError):
        editor.restore_version(session, first_id, "otro", path=path)


def test_an_old_version_that_no_longer_validates_is_not_restorable(
    session: Session, path: Path
) -> None:
    first = session.scalars(select(ProfileVersion)).one()
    first.data = {**first.data, "headline": ""}  # con el esquema de hoy no valida
    session.flush()
    _save_headline(session, path, "Uno")
    assert not history.list_versions(session).versions[1].restorable
    with pytest.raises(profiles.ProfileValidationError):
        editor.restore_version(session, first.id, _hash(path), path=path)


def test_the_api_lists_shows_and_restores(isolated_env: Path) -> None:
    migrations.upgrade()
    target = isolated_env / "profile.yaml"
    shutil.copyfile(EXAMPLE, target)
    with session_scope() as session:
        profiles.import_profile(session, target, origin="agent")
    with TestClient(create_app(), base_url=LOCAL) as client:
        state = client.get("/profile/editable").json()
        body = {"file_hash": state["file_hash"], "content": "Uno"}
        assert client.put("/profile/sections/headline", json=body, headers=JSON).status_code == 200
        page = client.get("/profile/versions").json()
        assert [v["origin"] for v in page["versions"]] == ["ui", "agent"]
        first = page["versions"][1]["id"]
        detail = client.get(f"/profile/versions/{first}/changes").json()
        assert detail["restorable"] and detail["restore_blocks"] == ["personal"]
        file_hash = client.get("/profile/editable").json()["file_hash"]
        restored = client.post(
            f"/profile/versions/{first}/restore", json={"file_hash": file_hash}, headers=JSON
        )
        assert restored.status_code == 200, restored.text
        assert restored.json()["blocks"] == ["personal"]
        assert client.get("/profile/versions").json()["versions"][0]["origin"] == "restore"
        assert client.get("/profile/versions/999/changes").status_code == 404


def test_restoring_one_section_leaves_the_rest_of_the_file_byte_for_byte(
    session: Session, path: Path
) -> None:
    original = path.read_text(encoding="utf-8")
    first_id = history.list_versions(session).versions[0].id
    _save_headline(session, path, "Uno")
    editor.restore_version(session, first_id, _hash(path), path=path)
    assert path.read_text(encoding="utf-8") == original


def test_empty_values_repeated_names_and_a_field_equal_to_the_name() -> None:
    old, new = _base(), _base()
    old["personal"]["github"] = None
    new["personal"].pop("github", None)  # None y ausente: lo mismo
    old["personal"]["mobility"] = ""
    new["personal"]["mobility"] = None
    assert history.compare(old, new) == []

    # Dos con el mismo nombre: se emparejan en orden, sin mezclarse.
    old["skills"] = [{"name": "Go", "level": "B"}, {"name": "Go", "level": "C"}]
    new["skills"] = [{"name": "Go", "level": "B"}, {"name": "Go", "level": "F"}]
    [change] = _changes(old, new)
    assert change["fields"] == [{"path": ["level"], "before": "C", "after": "F"}]

    # Solo se omite el campo que da el nombre; otro con el mismo texto se queda.
    new["skills"].append({"name": "Datos", "level": "B", "category": "Datos"})
    added = next(c for c in _changes(old, new) if c["kind"] == "added")
    assert [f["path"] for f in added["fields"]] == [["level"], ["category"]]
