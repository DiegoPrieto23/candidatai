"""«Mi perfil» editable (fase 25.7): guardar una sección de `data/profile.yaml` desde la UI."""

import copy
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT
from app.models import ProfileEdit, ProfileVersion, Task
from app.services import profile as profiles
from app.services import profile_editor as editor

EXAMPLE = REPO_ROOT / "demo" / "profile.example.yaml"


@pytest.fixture
def path(isolated_env: Path, session: Session) -> Path:
    target = isolated_env / "profile.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(EXAMPLE, target)
    profiles.import_profile(session, target)
    session.commit()
    return target


def _state(session: Session, path: Path) -> editor.EditableProfile:
    return editor.get_editable(session, path)


def _section(session: Session, path: Path, name: str) -> Any:
    profile = _state(session, path).profile
    assert profile is not None
    return copy.deepcopy(profile[name])


def _save(session: Session, path: Path, section: str, value: Any, **kw: Any) -> Any:
    state = _state(session, path)
    return editor.save_section(session, section, value, state.file_hash, path=path, **kw)  # type: ignore[arg-type]


def test_editable_profile_shows_contact_but_not_private(session: Session, path: Path) -> None:
    state = _state(session, path)
    assert state.exists and state.issues == [] and state.undo_available == 0
    assert state.profile is not None
    assert state.profile["personal"]["email"] == "lucia.varela@example.com"
    assert "private" not in state.profile
    assert state.file_hash == editor.file_hash(path.read_bytes())


def test_saving_a_section_keeps_comments_and_format_elsewhere(session: Session, path: Path) -> None:
    before = path.read_text(encoding="utf-8")
    experience = _section(session, path, "experience")
    experience[1]["achievements"][1]["text"] = "Monté pipelines de ingesta de datos de sensores."

    result = _save(session, path, "experience", experience)

    after = path.read_text(encoding="utf-8")
    changed = [
        line
        for line in result.diff.splitlines()
        if line[:1] in "+-" and line[:3] not in ("+++", "---")
    ]
    assert changed == [
        "-        text: Participé en la creación de pipelines de ingesta de datos de sensores.",
        "+        text: Monté pipelines de ingesta de datos de sensores.",
    ]
    # Todo lo demás, byte a byte, comentarios incluidos.
    assert (
        before.replace(
            "Participé en la creación de pipelines de ingesta", "Monté pipelines de ingesta"
        )
        == after
    )
    assert result.version_created and result.rescore_queued
    assert result.file_hash == editor.file_hash(path.read_bytes())


def test_a_change_elsewhere_in_the_section_keeps_its_comments(session: Session, path: Path) -> None:
    preferences = _section(session, path, "preferences")
    preferences["max_years_required"] = 5
    _save(session, path, "preferences", preferences)
    text = path.read_text(encoding="utf-8")
    assert "max_years_required: 5" in text
    assert "seniority_target: [junior, mid]   # todos los niveles que aceptas" in text
    assert "instructions: >-                 # opcional; orienta el énfasis" in text


def test_a_valid_save_creates_a_version_queues_rescore_and_keeps_a_copy(
    session: Session, path: Path
) -> None:
    original = path.read_bytes()
    versions = len(session.scalars(select(ProfileVersion)).all())
    _save(session, path, "headline", "Analytics Engineer · dbt · SQL")
    session.commit()

    assert len(session.scalars(select(ProfileVersion)).all()) == versions + 1
    assert session.scalars(select(Task).where(Task.kind == "rescore_all")).all()
    copies = list(editor.history_dir().glob("*.yaml"))
    assert len(copies) == 1 and copies[0].read_bytes() == original
    assert profiles.current(session).profile.headline == "Analytics Engineer · dbt · SQL"
    edit = session.scalars(select(ProfileEdit)).one()
    assert (edit.target, edit.section, edit.action) == ("profile", "headline", "save")
    assert edit.hash_before == editor.file_hash(original)
    assert edit.hash_after == editor.file_hash(path.read_bytes())

    undone = editor.undo_last(session, editor.file_hash(path.read_bytes()), path=path)
    assert path.read_bytes() == original
    assert undone.undo_available == 0 and undone.version_created
    assert profiles.current(session).profile.headline.startswith("Data Engineer")
    with pytest.raises(editor.NothingToUndoError):
        editor.undo_last(session, editor.file_hash(path.read_bytes()), path=path)


def test_the_same_content_does_not_write_or_create_a_version(session: Session, path: Path) -> None:
    before = path.read_bytes()
    result = _save(session, path, "skills", _section(session, path, "skills"))
    assert not result.changed and result.diff == "" and not result.version_created
    assert path.read_bytes() == before
    assert not list(editor.history_dir().glob("*.yaml"))


def test_a_stale_hash_is_a_conflict_and_does_not_write(session: Session, path: Path) -> None:
    stale = _state(session, path).file_hash
    path.write_text(path.read_text(encoding="utf-8") + "\n# a mano\n", encoding="utf-8")
    before = path.read_bytes()
    with pytest.raises(editor.ProfileConflictError) as exc:
        editor.save_section(session, "headline", "Otro", stale, path=path)
    assert exc.value.current_hash == editor.file_hash(before)
    assert path.read_bytes() == before


def test_an_invalid_change_writes_nothing_and_says_where(session: Session, path: Path) -> None:
    before = path.read_bytes()
    experience = _section(session, path, "experience")
    experience[0]["end"] = "2023-13"
    experience[1]["role"] = ""
    with pytest.raises(profiles.ProfileValidationError) as exc:
        _save(session, path, "experience", experience)
    assert {issue.field for issue in exc.value.issues} == {
        "experience[0].end",
        "experience[1].role",
    }
    assert path.read_bytes() == before

    # Las comprobaciones entre secciones, con el campo exacto: una skill sin declarar.
    experience = _section(session, path, "experience")
    experience[0]["achievements"][0]["skills"].append("Cobol")
    with pytest.raises(profiles.ProfileValidationError) as exc:
        _save(session, path, "experience", experience)
    assert [i.field for i in exc.value.issues] == ["experience[0].achievements[0].skills[4]"]
    assert path.read_bytes() == before
    # Nada a medias: ni copia ni fila de auditoría.
    assert not list(editor.history_dir().glob("*.yaml"))
    assert session.scalars(select(ProfileEdit)).all() == []


def test_dry_run_returns_the_diff_without_writing(session: Session, path: Path) -> None:
    before = path.read_bytes()
    preferences = _section(session, path, "preferences")
    preferences["remote_modes"] = ["remote"]
    result = _save(session, path, "preferences", preferences, dry_run=True)
    assert result.dry_run and result.changed
    assert "-  remote_modes: [remote, hybrid]" in result.diff
    assert "+  remote_modes: [remote]" in result.diff
    assert path.read_bytes() == before and result.profile_version_id is None


def test_new_items_get_stable_ids_from_their_name(session: Session, path: Path) -> None:
    experience = _section(session, path, "experience")
    experience.insert(
        0,
        {
            "company": "Ría Analytics (ficticia)",
            "role": "Analytics Engineer",
            "start": "2026-05",
            "end": "present",
            "achievements": [{"text": "Monté el modelo de dbt."}, {"text": "Bajé el coste."}],
        },
    )
    experience[1]["achievements"].append({"text": "Documenté los pipelines."})
    result = _save(session, path, "experience", experience)
    assert result.generated_ids == [
        "exp-ria-analytics",
        "exp-ria-analytics/a1",
        "exp-ria-analytics/a2",
        "exp-norteconsulting/a4",
    ]
    saved = profiles.load_from_yaml(path)
    assert saved.experience[0].id == "exp-ria-analytics"

    # Renombrar no cambia el id.
    experience = _section(session, path, "experience")
    experience[0]["company"] = "Ría Data"
    _save(session, path, "experience", experience)
    assert profiles.load_from_yaml(path).experience[0].id == "exp-ria-analytics"


def test_a_generated_id_does_not_collide_with_another_section(session: Session, path: Path) -> None:
    projects = _section(session, path, "projects")
    projects.append({"name": "tfg", "text": "Otro proyecto."})
    result = _save(session, path, "projects", projects)
    assert result.generated_ids == ["prj-tfg-2"]


def test_deleting_what_a_story_cites_is_rejected(session: Session, path: Path) -> None:
    before = path.read_bytes()
    experience = _section(session, path, "experience")
    del experience[0]["achievements"][0]  # exp-norteconsulting/a1, en «Migración de SSIS…»
    with pytest.raises(editor.ProfileReferencedError) as exc:
        _save(session, path, "experience", experience)
    assert exc.value.refs == {"exp-norteconsulting/a1": ["Migración de SSIS a Python"]}
    assert path.read_bytes() == before

    experience = _section(session, path, "experience")
    del experience[0]["achievements"][1]  # a2: no la cita ninguna historia
    _save(session, path, "experience", experience)
    ids = [a.id for a in profiles.load_from_yaml(path).experience[0].achievements]
    assert ids == ["a1", "a3"]


def test_contact_fields_are_editable_but_never_public(session: Session, path: Path) -> None:
    personal = _section(session, path, "personal")
    personal["phone"] = "+34600111222"  # sin comillas, YAML lo leería como número
    personal["availability"] = "no"  # y esto, como `false`
    _save(session, path, "personal", personal)
    saved = profiles.load_from_yaml(path)
    assert saved.personal.phone == "+34600111222"
    assert saved.personal.availability == "no"
    public = profiles.get_public_profile(session).profile
    assert "phone" not in public["personal"] and "email" not in public["personal"]


def test_multiline_text_is_kept_readable(session: Session, path: Path) -> None:
    stories = _section(session, path, "stories")
    stories[0]["action"] = "Primero migré un dominio.\nDespués, el resto."
    _save(session, path, "stories", stories)
    assert "action: |-\n" in path.read_text(encoding="utf-8")
    assert profiles.load_from_yaml(path).stories[0].action == (
        "Primero migré un dominio.\nDespués, el resto."
    )


def test_editable_profile_with_an_invalid_file_still_returns_its_data(
    session: Session, path: Path
) -> None:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["headline"] = ""
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    state = _state(session, path)
    assert state.profile is not None and state.profile["headline"] == ""
    assert [i.field for i in state.issues] == ["headline"]


def test_history_keeps_only_the_last_copies(
    session: Session, path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.policies import get_policies

    monkeypatch.setattr(get_policies().profile_editing, "history_keep", 2)
    for n in range(3):
        _save(session, path, "headline", f"Titular {n}")
    assert len(list(editor.history_dir().glob("*.yaml"))) == 2


def test_a_key_the_ui_does_not_send_is_removed(session: Session, path: Path) -> None:
    """`content` es la sección entera: lo que no viene, se borra (la UI reenvía lo que leyó)."""
    experience = _section(session, path, "experience")
    del experience[0]["achievements"][2]["nda"]
    _save(session, path, "experience", experience)
    assert not profiles.load_from_yaml(path).experience[0].achievements[2].nda


def test_a_crlf_file_stays_crlf(session: Session, path: Path) -> None:
    lf = path.read_bytes().replace(b"\r\n", b"\n")
    path.write_bytes(lf.replace(b"\n", b"\r\n"))
    _save(session, path, "headline", "Analytics Engineer")
    raw = path.read_bytes()
    assert b"headline: Analytics Engineer\r\n" in raw
    assert raw.count(b"\n") == raw.count(b"\r\n")


def test_undo_of_a_copy_with_bom_returns_the_right_hash(session: Session, path: Path) -> None:
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())  # guardado con BOM en un editor
    _save(session, path, "headline", "Otro titular")
    undone = editor.undo_last(session, editor.file_hash(path.read_bytes()), path=path)
    assert undone.file_hash == editor.file_hash(path.read_bytes())
    # Y se puede seguir guardando con ese hash, sin un `conflict` falso.
    editor.save_section(session, "headline", "Tercero", undone.file_hash, path=path)
