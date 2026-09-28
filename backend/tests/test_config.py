from pathlib import Path

import pytest

from app.core.config import REPO_ROOT, Settings, get_settings


def test_repo_root_is_detected() -> None:
    assert (REPO_ROOT / "AGENTS.md").is_file()
    assert (REPO_ROOT / "backend" / "pyproject.toml").is_file()


def test_default_data_dir_is_repo_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JH_DATA_DIR")
    settings = Settings(_env_file=None)
    assert settings.data_dir == (REPO_ROOT / "data").resolve()


def test_relative_data_dir_resolves_from_repo_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("JH_DATA_DIR", "data-demo")
    settings = Settings(_env_file=None)
    assert settings.data_dir == (REPO_ROOT / "data-demo").resolve()


def test_db_url_is_derived_from_data_dir(isolated_env: Path) -> None:
    settings = Settings(_env_file=None)
    assert settings.db_url == f"sqlite:///{(isolated_env / 'jobhunter.db').resolve().as_posix()}"


def test_explicit_db_url_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JH_DB_URL", "sqlite:///:memory:")
    assert Settings(_env_file=None).db_url == "sqlite:///:memory:"


def test_soffice_path_is_optional(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert Settings(_env_file=None).soffice_path is None
    monkeypatch.setenv("SOFFICE_PATH", str(tmp_path / "soffice.exe"))
    assert Settings(_env_file=None).soffice_path == tmp_path / "soffice.exe"


def test_get_settings_creates_data_dir(isolated_env: Path) -> None:
    assert not isolated_env.exists()
    settings = get_settings()
    assert settings.data_dir.is_dir()
    assert settings.user_templates_dir == settings.data_dir / "templates"
