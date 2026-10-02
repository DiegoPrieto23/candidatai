"""Fuentes de ofertas con conector (fase 09): ATS de empresas objetivo y portales con API."""

import re
from datetime import datetime
from typing import Annotated, Any, Literal, Self
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

ConnectorKind = Literal["greenhouse", "lever", "ashby", "infojobs", "adzuna"]
ATS_KINDS: tuple[ConnectorKind, ...] = ("greenhouse", "lever", "ashby")
PORTAL_KINDS: tuple[ConnectorKind, ...] = ("infojobs", "adzuna")
KIND_LABELS: dict[str, str] = {
    "greenhouse": "Greenhouse",
    "lever": "Lever",
    "ashby": "Ashby",
    "infojobs": "InfoJobs",
    "adzuna": "Adzuna",
}
InfoJobsSince = Literal["_24_HOURS", "_7_DAYS", "_15_DAYS", "ANY"]

# El slug va en la ruta de la URL del ATS: nada de `/`, `?`, `#` ni `..`.
_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")


def _slug(value: str) -> str:
    value = value.strip()
    if not _SLUG.match(value) or ".." in value:
        raise ValueError(
            "Slug no válido: letras, dígitos, `.`, `-` o `_`, tal como aparece en la URL del "
            "tablero (p. ej. `acme` en boards.greenhouse.io/acme)."
        )
    return value


Slug = Annotated[str, AfterValidator(_slug)]
Text = Annotated[str, Field(min_length=1, max_length=200)]
Keywords = Annotated[list[Annotated[str, Field(min_length=1, max_length=80)]], Field(max_length=50)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AtsConfig(_Strict):
    slug: Slug
    region: Literal["global", "eu"] = "global"  # Lever tiene una instancia europea
    title_keywords: Keywords = []  # palabras extra que dejan pasar un título en el filtro previo


class InfoJobsConfig(_Strict):
    query: Text
    province: str | None = Field(default=None, max_length=80)
    since: InfoJobsSince = "_7_DAYS"
    title_keywords: Keywords = []


class AdzunaConfig(_Strict):
    query: Text
    where: str | None = Field(default=None, max_length=120)
    country: str = Field(default="es", pattern=r"^[a-z]{2}$")
    max_days_old: int = Field(default=7, ge=1, le=60)
    title_keywords: Keywords = []


SourceConfig = AtsConfig | InfoJobsConfig | AdzunaConfig


def parse_config(kind: str, config: dict[str, Any]) -> SourceConfig:
    """Valida la configuración guardada de una fuente según su tipo."""
    if kind in ATS_KINDS:
        return AtsConfig.model_validate(config)
    if kind == "infojobs":
        return InfoJobsConfig.model_validate(config)
    if kind == "adzuna":
        return AdzunaConfig.model_validate(config)
    raise ValueError(f"La fuente de tipo «{kind}» no tiene conector.")


class SourceInput(_Strict):
    """Alta de una fuente. En los ATS, `name` es la empresa tal como quieres verla."""

    kind: ConnectorKind
    name: Text
    slug: Slug | None = None
    region: Literal["global", "eu"] = "global"
    query: str | None = Field(default=None, max_length=200)
    where: str | None = Field(default=None, max_length=120)
    province: str | None = Field(default=None, max_length=80)
    country: str = Field(default="es", pattern=r"^[a-z]{2}$")
    title_keywords: Keywords = []

    @model_validator(mode="after")
    def _fields_for_kind(self) -> Self:
        self.to_config()  # lanza ValueError con el campo que falta o sobra
        return self

    def to_config(self) -> SourceConfig:
        keywords = [k.strip() for k in self.title_keywords if k.strip()]
        if self.kind in ATS_KINDS:
            if not self.slug:
                raise ValueError(f"Falta el slug del tablero de {KIND_LABELS[self.kind]}.")
            if self.region == "eu" and self.kind != "lever":
                raise ValueError("La región `eu` solo existe en Lever.")
            return AtsConfig(slug=self.slug, region=self.region, title_keywords=keywords)
        if not self.query or not self.query.strip():
            raise ValueError(f"Falta la búsqueda (`query`) para {KIND_LABELS[self.kind]}.")
        if self.kind == "infojobs":
            return InfoJobsConfig(
                query=self.query.strip(), province=self.province, title_keywords=keywords
            )
        return AdzunaConfig(
            query=self.query.strip(),
            where=self.where,
            country=self.country,
            title_keywords=keywords,
        )


# --- Plataformas para la búsqueda con el navegador del agente (fase 09b) ----------------------

BrowseAccess = Literal["free", "login", "blocked"]
IncidentCode = Literal[
    "captcha", "anti_bot", "login_required", "page_changed", "suspicious_content", "error", "other"
]
_PLATFORM = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")


def _platform(value: str) -> str:
    value = value.strip().lower()
    if not _PLATFORM.match(value):
        raise ValueError(
            "Plataforma no válida: minúsculas, dígitos, `-` o `_` (p. ej. `tecnoempleo`)."
        )
    return value


def _search_url(value: str) -> str:
    value = value.strip()
    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise ValueError(f"URL no válida: «{value}».") from exc
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError(f"URL no válida: «{value}». Debe empezar por http:// o https://.")
    return value


Platform = Annotated[str, AfterValidator(_platform)]
SearchUrl = Annotated[str, Field(min_length=1, max_length=2000), AfterValidator(_search_url)]


class AgentBrowseSource(_Strict):
    """Una plataforma donde el agente busca con el navegador del usuario (`agent_browse`).

    Se identifica por `name`: guardar otra con el mismo nombre la actualiza."""

    name: Text = Field(description="Nombre de la plataforma tal como quieres verlo.")
    platform: Platform = Field(description="Id corto: `linkedin`, `infojobs`, `tecnoempleo`…")
    search_urls: list[SearchUrl] = Field(
        min_length=1,
        max_length=10,
        description="Búsquedas ya filtradas por puesto y ubicación (URLs http/https).",
    )
    priority: int = Field(default=5, ge=1, le=10, description="1 se recorre primero.")
    access: BrowseAccess = Field(
        default="free", description="`free`, `login` (inicias sesión tú) o `blocked`."
    )
    allow_agent_browsing: bool | None = Field(
        default=None,
        description=(
            "Si el agente puede recorrerla. Por defecto, sí; en LinkedIn, no (y solo el usuario "
            "puede activarla, en la UI)."
        ),
    )
    max_offers: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Ofertas que abrir; por defecto, `agent_browse.default_max_offers`.",
    )
    notes: str | None = Field(default=None, max_length=1000)


class Incident(_Strict):
    code: IncidentCode
    message: str = Field(min_length=1, max_length=500)


class SourceRunSummary(_Strict):
    """Lo que hizo el agente en una plataforma: encontradas, nuevas, ya conocidas e incidentes."""

    found: int = Field(ge=0, description="Resultados vistos en las páginas de búsqueda.")
    created: int = Field(ge=0, description="Ofertas dadas de alta como nuevas.")
    existing: int = Field(default=0, ge=0, description="Dadas de alta que ya estaban.")
    incidents: list[Incident] = Field(default=[], max_length=50)
    started_at: AwareDatetime | None = None
    finished_at: AwareDatetime | None = None

    # Validadores de campo (no de modelo): así el error señala el campo y no toda la entrada.
    @field_validator("existing")
    @classmethod
    def _not_more_than_found(cls, value: int, info: ValidationInfo) -> int:
        found, created = info.data.get("found"), info.data.get("created")
        if found is not None and created is not None and created + value > found:
            raise ValueError("`created` + `existing` no puede superar `found`.")
        return value

    @field_validator("finished_at")
    @classmethod
    def _after_start(cls, value: datetime | None, info: ValidationInfo) -> datetime | None:
        started = info.data.get("started_at")
        if value is not None and started is not None and value < started:
            raise ValueError("`finished_at` es anterior a `started_at`.")
        return value


class AgentBrowseLimits(BaseModel):
    """Límites de `config/policies.yaml` → `agent_browse`, para el agente que navega."""

    max_result_pages: int
    delay_seconds: float
    default_max_offers: int


class Issue(BaseModel):
    """Un problema de una ejecución. `item` identifica la oferta si es de una sola."""

    code: str  # http_error, not_found, unexpected_format, invalid_item, store_failed, truncated…
    message: str
    item: str | None = None


class SourceRunView(BaseModel):
    id: int
    actor: str
    started_at: datetime
    finished_at: datetime | None
    found: int
    after_filters: int
    created: int
    errors: list[Issue]


class SourceView(BaseModel):
    id: int
    kind: str
    kind_label: str
    name: str
    active: bool
    config: dict[str, Any]  # nunca lleva secretos: las claves de los portales van en `.env`
    keys_missing: bool  # portal opcional sin claves en `.env`: se omite al ejecutar
    browse: AgentBrowseSource | None = None  # solo en plataformas `agent_browse`
    last_run_at: datetime | None
    last_run: SourceRunView | None


class SourceList(BaseModel):
    sources: list[SourceView]
    agent_browse: AgentBrowseLimits  # límites de la búsqueda con navegador


class PreviewJob(BaseModel):
    external_id: str
    title: str
    company: str
    location: str | None
    url: str
    passed: bool
    reason: str | None  # por qué no pasa el filtro previo


class SourceTestResult(BaseModel):
    """Prueba de una fuente sin guardar nada: «12 ofertas encontradas, 3 tras filtros»."""

    kind: str
    name: str
    found: int
    after_filters: int
    jobs: list[PreviewJob]
    errors: list[Issue]
    filters_applied: bool  # sin perfil importado no se filtra
    message: str


class SourceRunResult(BaseModel):
    source_id: int
    name: str
    kind: str
    run_id: int | None  # `None` si se omitió (portal sin claves)
    skipped: str | None
    found: int
    after_filters: int
    created: int
    existing: int  # ya estaban (por id en la fuente o por huella)
    duplicates: int  # nuevas, pero cerradas como duplicado difuso de otra
    job_ids: list[int]  # ofertas creadas, en `pending_extraction`
    errors: list[Issue]
    message: str


class SourceRunBatch(BaseModel):
    runs: list[SourceRunResult]
