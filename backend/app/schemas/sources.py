"""Fuentes de ofertas con conector (fase 09): ATS de empresas con portal propio y portales API."""

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
    computed_field,
    field_validator,
    model_validator,
)

ConnectorKind = Literal[
    "greenhouse",
    "lever",
    "ashby",
    "personio",
    "teamtailor",
    "workable",
    "smartrecruiters",
    "recruitee",
    "infojobs",
    "adzuna",
    "manfred",
    "freehire",
]
ATS_KINDS: tuple[ConnectorKind, ...] = (
    "greenhouse",
    "lever",
    "ashby",
    "personio",
    "teamtailor",
    "workable",
    "smartrecruiters",
    "recruitee",
)
PORTAL_KINDS: tuple[ConnectorKind, ...] = ("infojobs", "adzuna", "manfred", "freehire")
KIND_LABELS: dict[str, str] = {
    "greenhouse": "Greenhouse",
    "lever": "Lever",
    "ashby": "Ashby",
    "personio": "Personio",
    "teamtailor": "Teamtailor",
    "workable": "Workable",
    "smartrecruiters": "SmartRecruiters",
    "recruitee": "Recruitee",
    "infojobs": "InfoJobs",
    "adzuna": "Adzuna",
    "manfred": "Manfred",
    "freehire": "freehire",
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


def _website(value: str) -> str:
    """Web de una empresa, reducida a su origen (`https://acme.com`): solo sirve para su logo."""
    value = value.strip()
    if "://" not in value:
        value = f"https://{value}"
    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise ValueError(f"Web no válida: «{value}».") from exc
    host = (parts.hostname or "").lower()
    if parts.scheme not in {"http", "https"} or "." not in host:
        raise ValueError(f"Web no válida: «{value}». Escríbela como `acme.com`.")
    return f"{parts.scheme}://{host}"


Website = Annotated[str, Field(max_length=200), AfterValidator(_website)]


def _careers_url(value: str) -> str:
    """Dirección de la web de empleo de una empresa, tal como la pega la persona."""
    value = value.strip()
    if "://" not in value:
        value = f"https://{value}"
    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise ValueError(f"Dirección no válida: «{value}».") from exc
    if parts.scheme not in {"http", "https"} or "." not in (parts.hostname or ""):
        raise ValueError(f"Dirección no válida: «{value}». Pega la de su web de empleo.")
    if parts.username or parts.password:
        raise ValueError("La dirección no puede llevar usuario ni contraseña.")
    return value


CareersUrl = Annotated[str, Field(min_length=1, max_length=2000), AfterValidator(_careers_url)]
# Lugares a los que se limita una empresa («Solo Madrid»): salen de su dirección o los pone la
# persona. Se aplican a la ubicación de cada oferta, con las mismas reglas que tus zonas.
Places = Annotated[list[Annotated[str, Field(min_length=1, max_length=80)]], Field(max_length=10)]
Language = Annotated[str, Field(pattern=r"^[a-z]{2}$")]


class AtsConfig(_Strict):
    slug: Slug
    region: Literal["global", "eu"] = "global"  # Lever tiene una instancia europea
    # Personio solo da la descripción en el idioma que se le pide (`?language=`). Sin valor, se
    # prueba `es` y, si no trae ninguna, `en`.
    language: Language | None = None
    title_keywords: Keywords = []  # palabras extra que dejan pasar un título en el filtro previo
    website: Website | None = None  # web de la empresa, para su logo en la UI
    careers_url: CareersUrl | None = None  # la dirección con la que se dio de alta
    locations: Places = []  # solo las ofertas de estos lugares (vacío: todas)


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


class ManfredConfig(_Strict):
    query: Text  # la API no busca: se filtra aquí por el título
    lang: Literal["ES", "EN"] = "ES"
    title_keywords: Keywords = []


class FreehireConfig(_Strict):
    query: Text
    country: str = Field(default="es", pattern=r"^[a-z]{2}$")
    remote_only: bool = False
    title_keywords: Keywords = []


SourceConfig = AtsConfig | InfoJobsConfig | AdzunaConfig | ManfredConfig | FreehireConfig


def parse_config(kind: str, config: dict[str, Any]) -> SourceConfig:
    """Valida la configuración guardada de una fuente según su tipo."""
    if kind in ATS_KINDS:
        return AtsConfig.model_validate(config)
    if kind == "infojobs":
        return InfoJobsConfig.model_validate(config)
    if kind == "adzuna":
        return AdzunaConfig.model_validate(config)
    if kind == "manfred":
        return ManfredConfig.model_validate(config)
    if kind == "freehire":
        return FreehireConfig.model_validate(config)
    raise ValueError(f"La fuente de tipo «{kind}» no tiene conector.")


class SourceInput(_Strict):
    """Alta de una fuente. En los ATS, `name` es la empresa tal como quieres verla.

    Una empresa se puede dar de alta solo con `name` y `url` (la dirección de su web de empleo):
    el servicio deduce el ATS, el slug y los lugares. Con `kind` y `slug`, se usan esos."""

    kind: ConnectorKind | None = None
    name: Text
    slug: Slug | None = None
    region: Literal["global", "eu"] = "global"
    query: str | None = Field(default=None, max_length=200)
    where: str | None = Field(default=None, max_length=120)
    province: str | None = Field(default=None, max_length=80)
    country: str = Field(default="es", pattern=r"^[a-z]{2}$")
    language: Language | None = None  # Personio: idioma de la descripción
    lang: Literal["ES", "EN"] = "ES"  # Manfred: idioma de las ofertas
    remote_only: bool = False  # freehire: solo remotas
    title_keywords: Keywords = []
    website: Website | None = None  # ATS: web de la empresa, para su logo
    url: CareersUrl | None = None  # ATS: dirección de su web de empleo
    locations: Places | None = None  # ATS: lugares; sin valor, los de `url`

    @model_validator(mode="after")
    def _fields_for_kind(self) -> Self:
        if self.kind is None:
            if not self.url:
                raise ValueError("Indica la dirección de su web de empleo (`url`) o el tipo.")
            return self
        self.to_config()  # lanza ValueError con el campo que falta o sobra
        return self

    def to_config(self) -> SourceConfig:
        if self.kind is None:
            raise ValueError("Falta el tipo de la fuente: resuelve antes su dirección.")
        keywords = [k.strip() for k in self.title_keywords if k.strip()]
        if self.lang != "ES" and self.kind != "manfred":
            raise ValueError("El idioma de las ofertas (`lang`) solo se usa en Manfred.")
        if self.remote_only and self.kind != "freehire":
            raise ValueError("«Solo remotas» (`remote_only`) solo se usa en freehire.")
        if self.website and self.kind not in ATS_KINDS:
            raise ValueError("La web (`website`) solo se usa en las empresas con portal propio.")
        if (self.url or self.locations) and self.kind not in ATS_KINDS:
            raise ValueError(
                "La dirección y los lugares (`url`, `locations`) solo se usan en las empresas."
            )
        if self.kind in ATS_KINDS:
            if not self.slug:
                raise ValueError(f"Falta el slug del tablero de {KIND_LABELS[self.kind]}.")
            if self.region == "eu" and self.kind != "lever":
                raise ValueError("La región `eu` solo existe en Lever.")
            if self.language and self.kind != "personio":
                raise ValueError("El idioma (`language`) solo se usa en Personio.")
            return AtsConfig(
                slug=self.slug,
                region=self.region,
                language=self.language,
                title_keywords=keywords,
                website=self.website,
                careers_url=self.url,
                locations=[" ".join(p.split()) for p in self.locations or [] if p.strip()],
            )
        if not self.query or not self.query.strip():
            raise ValueError(f"Falta la búsqueda (`query`) para {KIND_LABELS[self.kind]}.")
        if self.kind == "infojobs":
            return InfoJobsConfig(
                query=self.query.strip(), province=self.province, title_keywords=keywords
            )
        if self.kind == "manfred":
            return ManfredConfig(query=self.query.strip(), lang=self.lang, title_keywords=keywords)
        if self.kind == "freehire":
            return FreehireConfig(
                query=self.query.strip(),
                country=self.country,
                remote_only=self.remote_only,
                title_keywords=keywords,
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
    priority: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Puesto en el orden de recorrido, sin empates (1 se recorre primero). Sin valor: al "
            "final si es nueva; si ya existe, conserva el suyo. Un puesto ocupado: una nueva se "
            "inserta ahí y las siguientes bajan uno; una existente se intercambia con la que lo "
            "tenía."
        ),
    )
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
        description=(
            "Ofertas nuevas que abrir en cada recorrido (las que ya están no cuentan); por "
            "defecto, `agent_browse.default_max_offers`."
        ),
    )
    notes: str | None = Field(default=None, max_length=1000)


class Incident(_Strict):
    code: IncidentCode
    message: str = Field(min_length=1, max_length=500)


StopReason = Literal["limit", "watermark", "known_streak", "pages", "incident"]
MAX_WATERMARK_REFS = 20


class SearchWatermark(_Strict):
    """Hasta dónde llegó un recorrido en una búsqueda: lo más reciente que vio, para que el
    siguiente pare al llegar ahí."""

    search_url: SearchUrl = Field(description="La búsqueda (una de `search_urls` o puntual).")
    newest_refs: list[Annotated[str, Field(min_length=1, max_length=2000)]] = Field(
        default=[],
        max_length=MAX_WATERMARK_REFS,
        description=(
            "Referencias (URL o id) de los primeros resultados de la búsqueda, de más reciente a "
            "más antiguo; unas 10."
        ),
    )
    newest_posted_at: AwareDatetime | None = Field(
        default=None, description="Fecha de publicación del resultado más reciente, si se ve."
    )


class SourceRunSummary(_Strict):
    """Lo que hizo el agente en una plataforma: encontradas, nuevas, ya conocidas e incidentes."""

    found: int = Field(ge=0, description="Resultados vistos en las páginas de búsqueda.")
    created: int = Field(ge=0, description="Ofertas dadas de alta como nuevas.")
    existing: int = Field(default=0, ge=0, description="Dadas de alta que ya estaban.")
    skipped_known: int = Field(
        default=0,
        ge=0,
        description="Sin abrir porque ya estaban (`known` o `same_offer` en `check_known`).",
    )
    filtered_out: int = Field(
        default=0, ge=0, description="Vistas en la lista que no pasan tus filtros."
    )
    left_by_limit: int = Field(
        default=0, ge=0, description="Candidatas nuevas que quedaron sin abrir por el límite."
    )
    reopened: int = Field(
        default=0, ge=0, description="De las abiertas, cuántas eran `reopen_candidate`."
    )
    stop_reason: StopReason | None = Field(
        default=None,
        description=(
            "Por qué paró: `limit` (llegó a N nuevas), `watermark` (llegó a lo de la búsqueda "
            "anterior), `known_streak` (varias conocidas seguidas), `pages` (se acabaron las "
            "páginas o el máximo) o `incident`."
        ),
    )
    watermarks: list[SearchWatermark] = Field(
        default=[], max_length=10, description="La marca de agua de cada búsqueda recorrida."
    )
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

    @field_validator("left_by_limit")
    @classmethod
    def _seen_fit_in_found(cls, value: int, info: ValidationInfo) -> int:
        data = info.data
        keys = ("created", "existing", "skipped_known", "filtered_out")
        if data.get("found") is None or any(data.get(k) is None for k in keys):
            return value
        if sum(data[k] for k in keys) + value > data["found"]:
            raise ValueError(
                "`created` + `existing` + `skipped_known` + `filtered_out` + `left_by_limit` "
                "no puede superar `found`."
            )
        return value

    @field_validator("reopened")
    @classmethod
    def _reopened_were_opened(cls, value: int, info: ValidationInfo) -> int:
        created, existing = info.data.get("created"), info.data.get("existing")
        if created is not None and existing is not None and value > created + existing:
            raise ValueError("`reopened` no puede superar `created` + `existing`.")
        return value

    @field_validator("watermarks")
    @classmethod
    def _one_per_search(cls, value: list[SearchWatermark]) -> list[SearchWatermark]:
        urls = [w.search_url for w in value]
        if len(set(urls)) != len(urls):
            raise ValueError("Una sola marca de agua por búsqueda (`search_url` repetida).")
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
    stop_after_known: int


class Issue(BaseModel):
    """Un problema de una ejecución. `item` identifica la oferta si es de una sola."""

    code: str  # http_error, not_found, unexpected_format, invalid_item, store_failed, truncated…
    message: str
    item: str | None = None


def known_count(after_filters: int, created: int, left_by_limit: int) -> int:
    """«Ya las tenías»: de las que pasan tus filtros, las que no son nuevas ni quedaron sin abrir
    por el límite. Es `skipped_known` + `existing` del agente y, en las empresas o en recorridos
    anteriores a esos contadores, lo que pasa los filtros y ya estaba."""
    return max(0, after_filters - created - left_by_limit)


class SourceRunView(BaseModel):
    id: int
    actor: str
    started_at: datetime
    finished_at: datetime | None
    found: int
    after_filters: int
    created: int
    errors: list[Issue]
    # Recorridos del agente (fase 45); en el resto, 0 y sin motivo.
    existing: int = 0
    skipped_known: int = 0
    filtered_out: int = 0
    left_by_limit: int = 0
    reopened: int = 0
    stop_reason: StopReason | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def known(self) -> int:
        """Ya las tenías (ver `known_count`): la misma cifra en la UI, la CLI y el aviso."""
        return known_count(self.after_filters, self.created, self.left_by_limit)


class SeenSearch(BaseModel):
    """La marca de agua vigente de una búsqueda: la del último recorrido que la anotó."""

    search_url: str
    newest_refs: list[str]
    newest_posted_at: datetime | None
    run_id: int
    recorded_at: datetime


class AgentBrowseView(AgentBrowseSource):
    """La plataforma tal como se lista: su configuración y hasta dónde llegó cada búsqueda."""

    last_seen: list[SeenSearch] = []


class SourceView(BaseModel):
    id: int
    kind: str
    kind_label: str
    name: str
    active: bool
    config: dict[str, Any]  # nunca lleva secretos: las claves de los portales van en `.env`
    keys_missing: bool  # portal opcional sin claves en `.env`: se omite al ejecutar
    browse: AgentBrowseView | None = None  # solo en plataformas `agent_browse`
    # Web de la empresa o del portal, para su logo: la que puso el usuario o, si no, la de sus
    # ofertas cuando no están en el dominio del ATS.
    website: str | None = None
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


ResolveMethod = Literal["url", "page", "search", "none"]


class SourceResolution(BaseModel):
    """Lo que la app ha deducido de la dirección de una web de empleo.

    `how`: `url` (es la del ATS), `page` (la web enlaza su ATS), `search` (encontrado por el nombre
    o el dominio) o `none` (no se reconoce: se guarda como plataforma que recorre el agente)."""

    url: str
    how: ResolveMethod
    kind: str | None
    kind_label: str | None
    slug: str | None
    region: Literal["global", "eu"] = "global"
    locations: list[str]  # filtros de lugar que se aplicarán
    website: str | None
    issues: list[str]


class SourceTestResult(BaseModel):
    """Prueba de una fuente sin guardar nada: «12 ofertas encontradas, 3 tras filtros».

    La UI enseña solo las que pasan (`after_filters`); los totales quedan para el diagnóstico."""

    kind: str
    name: str
    found: int
    after_filters: int
    jobs: list[PreviewJob]
    errors: list[Issue]
    filters_applied: bool  # sin perfil importado no se filtra
    message: str
    resolution: SourceResolution | None = None  # en el alta por dirección


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


# --- Búsqueda pública de LinkedIn sin sesión (fase 22) --------------------------------


class LinkedInSearch(BaseModel):
    """Una búsqueda de la plataforma LinkedIn traducida a los parámetros del endpoint público."""

    url: str  # la `search_url` de la que sale
    keywords: str | None
    location: str | None
    params: dict[str, str]  # lo que se enviará (sin `start`)


class LinkedInPublicLimits(BaseModel):
    """Límites de `config/policies.yaml` → `linkedin_public`."""

    max_searches_per_run: int
    max_pages_per_search: int
    delay_seconds: float
    min_hours_between_runs: float
    block_cooldown_days: int
    max_details_per_run: int


class LinkedInPublicView(BaseModel):
    """Estado de la búsqueda pública para la tarjeta de LinkedIn en «Dónde buscar → Portales de
    empleo»."""

    source_id: int | None  # `None` hasta que se activa por primera vez
    enabled: bool
    fetch_detail: bool
    enabled_at: datetime | None
    platform_source_id: int | None  # la plataforma LinkedIn de la que salen las búsquedas
    searches: list[LinkedInSearch]  # las que se lanzarán, en orden
    ignored: list[Issue]  # búsquedas que no se pueden usar (y por qué) o que pasan del límite
    blocked_at: datetime | None  # último bloqueo (429/999, redirección o captcha)
    next_run_at: datetime | None  # a partir de cuándo puede volver a ejecutarse
    last_run: SourceRunView | None
    limits: LinkedInPublicLimits


class LinkedInPublicRunResult(BaseModel):
    source_id: int | None
    run_id: int | None  # `None` si no se ejecutó (`skipped`)
    skipped: str | None
    blocked: bool  # LinkedIn cortó la búsqueda: no se vuelve a intentar en unos días
    requests: int  # peticiones hechas a LinkedIn
    found: int
    after_filters: int
    created: int
    summaries: int  # de las nuevas, cuántas entraron como resumen (`pending_detail`)
    existing: int
    job_ids: list[int]
    errors: list[Issue]
    message: str
