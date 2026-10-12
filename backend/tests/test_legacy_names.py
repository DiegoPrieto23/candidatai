"""Compatibilidades del nombre anterior (Job Hunter → CandidatAI, fase 23.1, ADR-034): las
variables `JH_*` se siguen leyendo, la BD `jobhunter.db` se sigue usando y `cai doctor` lo avisa."""

from pathlib import Path

import pytest

from app.core.config import Settings, get_settings
from app.services import doctor


def _settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


def test_legacy_env_vars_still_work(
    isolated_env: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_dir = tmp_path / "datos-de-antes"
    monkeypatch.delenv("CAI_DATA_DIR")
    monkeypatch.delenv("CAI_EMBEDDINGS")
    monkeypatch.setenv("JH_DATA_DIR", str(old_dir))
    monkeypatch.setenv("JH_EMBEDDINGS", "off")
    settings = _settings()
    assert settings.data_dir == old_dir.resolve()
    assert settings.embeddings == "off"


def test_new_env_vars_win_over_legacy(isolated_env: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JH_DATA_DIR", str(isolated_env.parent / "otra"))
    assert _settings().data_dir == isolated_env.resolve()


def test_new_db_by_default(isolated_env: Path) -> None:
    settings = _settings()
    assert settings.db_url is not None and settings.db_url.endswith("/candidatai.db")
    assert settings.uses_legacy_db is False


def test_legacy_db_is_used_if_it_is_the_only_one(isolated_env: Path) -> None:
    isolated_env.mkdir(parents=True, exist_ok=True)
    (isolated_env / "jobhunter.db").write_bytes(b"")
    settings = _settings()
    assert settings.db_url is not None and settings.db_url.endswith("/jobhunter.db")
    assert settings.uses_legacy_db is True
    # Con las dos, manda la nueva.
    (isolated_env / "candidatai.db").write_bytes(b"")
    assert _settings().db_url.endswith("/candidatai.db")  # type: ignore[union-attr]


def test_doctor_warns_about_legacy_names(
    isolated_env: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("JH_IMAP_HOST=imap.example.com\nCAI_AGENT=claude-code\n", encoding="utf-8")
    clean = doctor.check_legacy_names(_settings(), tmp_path / "no-existe.env")
    assert clean.status == doctor.CheckStatus.OK

    monkeypatch.setenv("JH_AGENT", "codex")
    isolated_env.mkdir(parents=True, exist_ok=True)
    (isolated_env / "jobhunter.db").write_bytes(b"")
    check = doctor.check_legacy_names(_settings(), env_file)
    assert check.status == doctor.CheckStatus.WARN
    assert "JH_AGENT → CAI_AGENT" in check.detail
    assert "JH_IMAP_HOST → CAI_IMAP_HOST" in check.detail
    assert "jobhunter.db" in check.detail
    # Solo nombres: nunca el valor de una variable.
    assert "imap.example.com" not in check.detail and "codex" not in check.detail
