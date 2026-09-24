"""Configuración de la app, leída de variables de entorno y de `.env` en la raíz del repo."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] es la raíz del repo.
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Field(default=REPO_ROOT / "data", validation_alias="JH_DATA_DIR")
    db_url: str | None = Field(default=None, validation_alias="JH_DB_URL")
    soffice_path: Path | None = Field(default=None, validation_alias="SOFFICE_PATH")
    # Qué agente usa la CLI (`claude-code`, `codex`…), para auditar. Por MCP lo dice el cliente.
    client_name: str | None = Field(default=None, validation_alias="JH_CLIENT_NAME")

    @model_validator(mode="after")
    def _resolve_paths(self) -> "Settings":
        # Una ruta relativa (p. ej. JH_DATA_DIR=data-demo) se resuelve desde la raíz del repo,
        # no desde el directorio de trabajo, para que `jh` funcione igual desde cualquier sitio.
        if not self.data_dir.is_absolute():
            self.data_dir = REPO_ROOT / self.data_dir
        self.data_dir = self.data_dir.resolve()
        if self.db_url is None:
            self.db_url = f"sqlite:///{(self.data_dir / 'jobhunter.db').as_posix()}"
        return self

    @property
    def tmp_dir(self) -> Path:
        """Entradas largas de la CLI (`--file`). Se borran tras procesarse bien."""
        return self.data_dir / "tmp"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def cv_template_path(self) -> Path:
        return self.data_dir / "cv_template.docx"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
