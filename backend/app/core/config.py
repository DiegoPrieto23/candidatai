"""Configuración de la app, leída de variables de entorno y de `.env` en la raíz del repo."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] es la raíz del repo.
REPO_ROOT = Path(__file__).resolve().parents[3]


# Id de la extensión de `extension/`: lo fija la clave pública (`key`) de su manifiesto.
DEFAULT_EXTENSION_ID = "hnaofhehllbkghfehnehamjbkcmdjmle"


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
    # `off` desactiva la similitud semántica aunque esté instalado el extra `matching` (tests, CI).
    embeddings: Literal["auto", "off"] = Field(default="auto", validation_alias="JH_EMBEDDINGS")
    # Conectores opcionales de portales (fase 09). Sin claves, esas fuentes se omiten con un aviso.
    infojobs_client_id: str | None = Field(default=None, validation_alias="JH_INFOJOBS_CLIENT_ID")
    infojobs_client_secret: str | None = Field(
        default=None, validation_alias="JH_INFOJOBS_CLIENT_SECRET"
    )
    adzuna_app_id: str | None = Field(default=None, validation_alias="JH_ADZUNA_APP_ID")
    adzuna_app_key: str | None = Field(default=None, validation_alias="JH_ADZUNA_APP_KEY")
    # Alertas por correo (fase 09b): IMAP en solo lectura sobre una carpeta. Sin host, solo se
    # lee la carpeta local `data/inbox/`.
    imap_host: str | None = Field(default=None, validation_alias="JH_IMAP_HOST")
    imap_port: int = Field(default=993, validation_alias="JH_IMAP_PORT")
    imap_user: str | None = Field(default=None, validation_alias="JH_IMAP_USER")
    imap_password: SecretStr | None = Field(default=None, validation_alias="JH_IMAP_PASSWORD")
    imap_folder: str = Field(default="INBOX", validation_alias="JH_IMAP_FOLDER")
    # Botón «Enviar a Job Hunter» (fase 09b): id de la extensión cuyo origen acepta `POST /capture`.
    # Por defecto, el que fija la clave pública de `extension/manifest.json`.
    capture_extension_id: str = Field(
        default=DEFAULT_EXTENSION_ID,
        pattern=r"^[a-p]{32}$",
        validation_alias="JH_CAPTURE_EXTENSION_ID",
    )

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
    def models_dir(self) -> Path:
        """Caché de los modelos de embeddings (se descargan la primera vez)."""
        return self.data_dir / "models"

    @property
    def evals_dir(self) -> Path:
        """Casos de evaluación propios (`*.jsonl`) e informes (`reports/`)."""
        return self.data_dir / "evals"

    @property
    def imap_configured(self) -> bool:
        password = self.imap_password.get_secret_value() if self.imap_password else ""
        return bool(self.imap_host and self.imap_user and password)

    @property
    def capture_token_path(self) -> Path:
        """Hash del token de la extensión de captura (`jh capture token`)."""
        return self.data_dir / "capture_token"

    @property
    def capture_origin(self) -> str:
        return f"chrome-extension://{self.capture_extension_id}"

    @property
    def inbox_dir(self) -> Path:
        """Correos exportados (`.eml`, `.mbox`) para las alertas sin IMAP. `samples/` no se lee."""
        return self.data_dir / "inbox"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def user_templates_dir(self) -> Path:
        """Plantillas de CV del usuario (`data/templates/<id>/`, ver docs/CV_TEMPLATES.md)."""
        return self.data_dir / "templates"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
