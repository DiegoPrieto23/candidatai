from collections.abc import Iterator
from pathlib import Path

import pytest

from app.core.config import get_settings


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Cada test usa su propio directorio de datos y sin variables heredadas del usuario."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("JH_DATA_DIR", str(data_dir))
    monkeypatch.delenv("JH_DB_URL", raising=False)
    monkeypatch.delenv("SOFFICE_PATH", raising=False)
    get_settings.cache_clear()
    yield data_dir
    get_settings.cache_clear()
