"""Configuración de la app, leída de variables de entorno y de `.env` en la raíz del repo."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> parents[3] es la raíz del repo.
REPO_ROOT = Path(__file__).resolve().parents[3]


# Id de la extensión de `extension/`: lo fija la clave pública (`key`) de su manifiesto.
DEFAULT_EXTENSION_ID = "hnaofhehllbkghfehnehamjbkcmdjmle"

# Prefijo de las variables de entorno. Hasta la fase 23 era `JH_` (Job Hunter): se sigue leyendo
# como respaldo, para que un `.env` antiguo funcione sin tocarlo (ADR-034).
ENV_PREFIX = "CAI_"
LEGACY_ENV_PREFIX = "JH_"
DB_FILENAME = "candidatai.db"
LEGACY_DB_FILENAME = "jobhunter.db"


def _env(name: str) -> AliasChoices:
    """`CAI_<name>` y, si no está, `JH_<name>`."""
    return AliasChoices(f"{ENV_PREFIX}{name}", f"{LEGACY_ENV_PREFIX}{name}")


# Fichero marca de una carpeta de datos creada por `cai demo seed` (fase 12.1).
DEMO_MARKER = ".demo"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    data_dir: Path = Field(default=REPO_ROOT / "data", validation_alias=_env("DATA_DIR"))
    db_url: str | None = Field(default=None, validation_alias=_env("DB_URL"))
    soffice_path: Path | None = Field(default=None, validation_alias="SOFFICE_PATH")
    # Qué agente usa la CLI (`claude-code`, `codex`…), para auditar. Por MCP lo dice el cliente.
    client_name: str | None = Field(default=None, validation_alias=_env("CLIENT_NAME"))
    # Qué agente abren los botones de la UI (ADR-024), por su nombre en `.agents/manifest.yaml`.
    # Sin valor, el primero con `launch` que esté instalado.
    agent: str | None = Field(default=None, validation_alias=_env("AGENT"))
    # `off` desactiva la similitud semántica aunque esté instalado el extra `matching` (tests, CI).
    embeddings: Literal["auto", "off"] = Field(default="auto", validation_alias=_env("EMBEDDINGS"))
    # Conectores opcionales de portales (fase 09). Sin claves, esas fuentes se omiten con un aviso.
    infojobs_client_id: str | None = Field(
        default=None, validation_alias=_env("INFOJOBS_CLIENT_ID")
    )
    infojobs_client_secret: str | None = Field(
        default=None, validation_alias=_env("INFOJOBS_CLIENT_SECRET")
    )
    adzuna_app_id: str | None = Field(default=None, validation_alias=_env("ADZUNA_APP_ID"))
    adzuna_app_key: str | None = Field(default=None, validation_alias=_env("ADZUNA_APP_KEY"))
    # Alertas por correo (fase 09b): IMAP en solo lectura sobre una carpeta. Sin host, solo se
    # lee la carpeta local `data/inbox/`.
    imap_host: str | None = Field(default=None, validation_alias=_env("IMAP_HOST"))
    imap_port: int = Field(default=993, validation_alias=_env("IMAP_PORT"))
    imap_user: str | None = Field(default=None, validation_alias=_env("IMAP_USER"))
    imap_password: SecretStr | None = Field(default=None, validation_alias=_env("IMAP_PASSWORD"))
    imap_folder: str = Field(default="INBOX", validation_alias=_env("IMAP_FOLDER"))
    # Respuestas de las empresas (fase 15): misma cuenta, otra carpeta (por defecto, la bandeja de
    # entrada). Solo se descargan los correos que casan con una candidatura enviada.
    imap_replies_folder: str = Field(default="INBOX", validation_alias=_env("IMAP_REPLIES_FOLDER"))
    # Botón «Enviar a CandidatAI» (fase 09b): id de la extensión cuyo origen acepta `POST /capture`.
    # Por defecto, el que fija la clave pública de `extension/manifest.json`.
    capture_extension_id: str = Field(
        default=DEFAULT_EXTENSION_ID,
        pattern=r"^[a-p]{32}$",
        validation_alias=_env("CAPTURE_EXTENSION_ID"),
    )
    # Candidatura asistida (fase 11): navegador visible salvo en tests; `chrome` o `msedge` usan
    # el navegador instalado en vez del Chromium de Playwright.
    browser_headless: bool = Field(default=False, validation_alias=_env("BROWSER_HEADLESS"))
    browser_channel: str | None = Field(default=None, validation_alias=_env("BROWSER_CHANNEL"))
    # Otra carpeta con la UI compilada (por defecto, `frontend/dist`).
    ui_dir_override: Path | None = Field(default=None, validation_alias=_env("UI_DIR"))
    # Solo tests: permite abrir formularios servidos en 127.0.0.1 (nunca la API de la app).
    applier_allow_loopback: bool = Field(
        default=False, validation_alias=_env("APPLIER_ALLOW_LOOPBACK")
    )

    @model_validator(mode="after")
    def _resolve_paths(self) -> "Settings":
        # Una ruta relativa (p. ej. CAI_DATA_DIR=data-demo) se resuelve desde la raíz del repo,
        # no desde el directorio de trabajo, para que `cai` funcione igual desde cualquier sitio.
        if not self.data_dir.is_absolute():
            self.data_dir = REPO_ROOT / self.data_dir
        self.data_dir = self.data_dir.resolve()
        if self.db_url is None:
            self.db_url = f"sqlite:///{self.default_db_path.as_posix()}"
        return self

    @property
    def default_db_path(self) -> Path:
        """`candidatai.db`, salvo que solo exista la de antes de la fase 23 (`jobhunter.db`): esa
        se sigue usando tal cual, sin moverla ni copiarla."""
        current = self.data_dir / DB_FILENAME
        legacy = self.data_dir / LEGACY_DB_FILENAME
        return legacy if not current.exists() and legacy.exists() else current

    @property
    def uses_legacy_db(self) -> bool:
        return self.default_db_path.name == LEGACY_DB_FILENAME

    @property
    def demo_mode(self) -> bool:
        """La carpeta de datos es una demo (`cai demo seed`): la UI muestra un banner."""
        return (self.data_dir / DEMO_MARKER).is_file()

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
        """Hay IMAP en `.env` y se puede usar. Nunca en una demo: su worker leería tu buzón real
        y mezclaría tus alertas y respuestas con los datos inventados (fase 23.5b). En la demo, el
        correo se prueba con `.eml` en su `inbox/`."""
        if self.demo_mode:
            return False
        password = self.imap_password.get_secret_value() if self.imap_password else ""
        return bool(self.imap_host and self.imap_user and password)

    @property
    def capture_token_path(self) -> Path:
        """Hash del token de la extensión de captura (`cai capture token`)."""
        return self.data_dir / "capture_token"

    @property
    def capture_origin(self) -> str:
        return f"chrome-extension://{self.capture_extension_id}"

    @property
    def inbox_dir(self) -> Path:
        """Correos exportados (`.eml`, `.mbox`) para las alertas sin IMAP. `samples/` no se lee."""
        return self.data_dir / "inbox"

    @property
    def replies_inbox_dir(self) -> Path:
        """Respuestas de empresas exportadas (`.eml`, `.mbox`), alternativa sin IMAP (fase 15)."""
        return self.inbox_dir / "respuestas"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def ui_dir(self) -> Path:
        """UI compilada (`pnpm build`, o la que trae la release) que sirve la API (fase 23.4)."""
        return self.ui_dir_override or REPO_ROOT / "frontend" / "dist"

    @property
    def browser_profile_dir(self) -> Path:
        """Perfil persistente del navegador de las candidaturas. Solo lo abre el worker."""
        return self.data_dir / "browser-profile"

    @property
    def applications_dir(self) -> Path:
        """Capturas de las candidaturas asistidas (`<job_id>/<intento>/`)."""
        return self.data_dir / "applications"

    @property
    def user_templates_dir(self) -> Path:
        """Plantillas de CV del usuario (`data/templates/<id>/`, ver docs/CV_TEMPLATES.md)."""
        return self.data_dir / "templates"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    return settings
