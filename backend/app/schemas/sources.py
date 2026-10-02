"""Fuentes de ofertas con conector (fase 09): ATS de empresas objetivo y portales con API."""

import re
from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

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
    last_run_at: datetime | None
    last_run: SourceRunView | None


class SourceList(BaseModel):
    sources: list[SourceView]


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
