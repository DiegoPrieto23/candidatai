"""Fuentes con conector (fase 09): alta, prueba sin guardar y ejecución.

Ejecutar una fuente descarga sus ofertas, aplica el filtro previo y guarda las nuevas con el mismo
servicio que el alta manual (`ingest.store_job`): huella, duplicados difusos, detección de riesgo y
evento `found`, que las deja en `pending_extraction`. Es idempotente: una oferta ya vista (por su
id en la fuente, su URL o su huella) no se vuelve a crear ni genera eventos.

Cada ejecución queda en `source_runs`, también si la fuente falla: así el error se ve en la UI.
"""

import logging
from datetime import datetime
from typing import Any, cast
from urllib.parse import urlsplit

import httpx
from pydantic import TypeAdapter
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core import secrets
from app.core.config import get_settings
from app.core.policies import get_policies
from app.models import Company, Job, Source, SourceRun
from app.models.base import utcnow
from app.schemas.profile import Preferences
from app.schemas.sources import (
    ATS_KINDS,
    KIND_LABELS,
    AgentBrowseLimits,
    AgentBrowseSource,
    AgentBrowseView,
    Issue,
    PreviewJob,
    SeenSearch,
    SourceConfig,
    SourceInput,
    SourceList,
    SourceResolution,
    SourceRunResult,
    SourceRunView,
    SourceTestResult,
    SourceView,
    StopReason,
    Website,
    parse_config,
)
from app.services import ingest, platforms
from app.services import profile as profile_service
from app.services.ingestion import resolve
from app.services.ingestion.adzuna import AdzunaConnector
from app.services.ingestion.ashby import AshbyConnector
from app.services.ingestion.base import (
    Connector,
    ConnectorError,
    FetchResult,
    MissingKeysError,
    RawJob,
    make_client,
)
from app.services.ingestion.freehire import FreehireConnector
from app.services.ingestion.greenhouse import GreenhouseConnector
from app.services.ingestion.infojobs import InfoJobsConnector
from app.services.ingestion.lever import LeverConnector
from app.services.ingestion.manfred import ManfredConnector
from app.services.ingestion.max_offers import default_max_offers
from app.services.ingestion.personio import PersonioConnector
from app.services.ingestion.prefilter import Prefilter
from app.services.ingestion.recruitee import RecruiteeConnector
from app.services.ingestion.smartrecruiters import SmartRecruitersConnector
from app.services.ingestion.teamtailor import TeamtailorConnector
from app.services.ingestion.workable import WorkableConnector
from app.services.matching.hard_filters import location_matches
from app.services.normalize import fingerprint, fold, normalize_company

logger = logging.getLogger(__name__)

CONNECTORS: dict[str, Connector] = {
    c.kind: c
    for c in (
        GreenhouseConnector(),
        LeverConnector(),
        AshbyConnector(),
        PersonioConnector(),
        TeamtailorConnector(),
        WorkableConnector(),
        SmartRecruitersConnector(),
        RecruiteeConnector(),
        InfoJobsConnector(),
        AdzunaConnector(),
        ManfredConnector(),
        FreehireConnector(),
    )
}
# Fallos de la fuente que merece la pena reintentar (el worker reintenta con espera creciente).
RETRYABLE_CODES = frozenset({"timeout", "network", "http_error", "rate_limited", "internal_error"})
# Si el detalle de una oferta falla así, no se pide el de las demás en esta ejecución.
_STOP_DETAIL_CODES = frozenset({"unauthorized", "rate_limited"})
MANUAL_LABELS = {
    **ingest.SOURCE_NAMES,
    "email_alerts": "Alertas por correo",
    "browser_capture": "Botón «Enviar a CandidatAI»",
    "agent_browse": "Búsqueda con navegador",
    "linkedin_public": "LinkedIn · búsqueda pública",
}


# Dominios de los propios ATS: una oferta publicada en ellos no dice cuál es la web de la empresa.
_ATS_DOMAINS = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "personio.de",
    "personio.com",
    "teamtailor.com",
    "workable.com",
    "smartrecruiters.com",
    "recruitee.com",
)
# Web de cada portal con API, para su logo.
_PORTAL_SITES = {
    "infojobs": "https://www.infojobs.net",
    "adzuna": "https://www.adzuna.es",
    "manfred": "https://www.getmanfred.com",
    "freehire": "https://freehire.me",
}
_WEBSITE: TypeAdapter[str | None] = TypeAdapter(Website | None)


class SourceNotFoundError(LookupError):
    pass


class SourceExistsError(ValueError):
    pass


class NotAConnectorError(ValueError):
    pass


# --- Consultas -------------------------------------------------------------------------------


def keys_missing(kind: str) -> bool:
    settings = get_settings()
    if kind == "infojobs":
        return not (settings.infojobs_client_id and secrets.get(secrets.INFOJOBS_CLIENT_SECRET))
    if kind == "adzuna":
        return not (settings.adzuna_app_id and secrets.get(secrets.ADZUNA_APP_KEY))
    return False


def _run_view(run: SourceRun) -> SourceRunView:
    return SourceRunView(
        id=run.id,
        actor=run.actor,
        started_at=run.started_at,
        finished_at=run.finished_at,
        found=run.found,
        after_filters=run.after_filters,
        created=run.created,
        errors=[Issue.model_validate(e) for e in run.errors],
        existing=run.existing,
        skipped_known=run.skipped_known,
        filtered_out=run.filtered_out,
        left_by_limit=run.left_by_limit,
        reopened=run.reopened,
        stop_reason=cast(StopReason | None, run.stop_reason),
    )


def _last_run(session: Session, source_id: int) -> SourceRun | None:
    return session.scalars(
        select(SourceRun)
        .where(SourceRun.source_id == source_id)
        .order_by(SourceRun.started_at.desc(), SourceRun.id.desc())
        .limit(1)
    ).first()


# Recorridos que se miran para la marca de agua de cada búsqueda.
LAST_SEEN_RUNS = 50


def _seen_search(run: SourceRun, mark: Any) -> SeenSearch | None:
    """Una marca guardada, o `None` si no sirve para parar (vacía) o está mal (editada a mano)."""
    if not isinstance(mark, dict) or not isinstance(mark.get("search_url"), str):
        return None
    if not mark.get("newest_refs") and not mark.get("newest_posted_at"):
        return None
    try:
        posted = mark.get("newest_posted_at")
        return SeenSearch(
            search_url=mark["search_url"],
            newest_refs=[str(r) for r in mark.get("newest_refs") or []],
            newest_posted_at=datetime.fromisoformat(posted) if posted else None,
            run_id=run.id,
            recorded_at=run.finished_at or run.started_at,
        )
    except (TypeError, ValueError):
        logger.warning("Marca de agua no válida en el recorrido %s", run.id)
        return None


def _last_seen(session: Session, source_id: int) -> list[SeenSearch]:
    """La marca de agua vigente de cada búsqueda: la del último recorrido anotado que dejó una
    útil (las de antes siguen en su recorrido, como historial). Se ordena por orden de anotación,
    no por las fechas que da el agente."""
    runs = session.scalars(
        select(SourceRun)
        .where(SourceRun.source_id == source_id, SourceRun.watermarks.is_not(None))
        .order_by(SourceRun.id.desc())
        .limit(LAST_SEEN_RUNS)
    )
    seen: dict[str, SeenSearch] = {}
    for run in runs:
        for mark in run.watermarks or []:
            view = _seen_search(run, mark)
            if view is not None and view.search_url not in seen:
                seen[view.search_url] = view
    return list(seen.values())


def _browse(session: Session, source: Source) -> AgentBrowseView | None:
    if source.kind != "agent_browse":
        return None
    try:
        config = AgentBrowseSource.model_validate({"name": source.name, **(source.config or {})})
    except ValueError:  # config editada a mano: se lista igual, sin el bloque tipado
        logger.warning("Configuración no válida en la plataforma %s", source.id)
        return None
    return AgentBrowseView(**config.model_dump(), last_seen=_last_seen(session, source.id))


def _website(session: Session, source: Source) -> str | None:
    """Web para el logo: la del portal, la que puso el usuario o la de sus ofertas más recientes
    si no están en el dominio del ATS (Teamtailor, p. ej., las publica en `careers.acme.com`)."""
    if source.kind in _PORTAL_SITES:
        return _PORTAL_SITES[source.kind]
    if source.kind not in ATS_KINDS:
        return None
    if website := (source.config or {}).get("website"):
        return str(website)
    urls = session.scalars(
        select(Job.url).where(Job.source_id == source.id).order_by(Job.id.desc()).limit(10)
    )
    for url in urls:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if parts.scheme not in {"http", "https"} or "." not in host:
            continue
        if not any(host == d or host.endswith(f".{d}") for d in _ATS_DOMAINS):
            return f"{parts.scheme}://{host}"
    return None


def icon_home(session: Session, source_id: int) -> str | None:
    """Web de la que sale el icono de una fuente en «Dónde buscar»: en una plataforma, la de su
    primera búsqueda; si no, la de `_website`."""
    source = _source(session, source_id)
    if source.kind != "agent_browse":
        return _website(session, source)
    for url in (source.config or {}).get("search_urls") or []:
        parts = urlsplit(str(url))
        if parts.scheme in {"http", "https"} and parts.hostname:
            return f"{parts.scheme}://{parts.hostname.lower()}"
    return None


def _view(session: Session, source: Source) -> SourceView:
    last = _last_run(session, source.id)
    return SourceView(
        id=source.id,
        kind=source.kind,
        kind_label=KIND_LABELS.get(source.kind) or MANUAL_LABELS.get(source.kind, source.kind),
        name=source.name,
        active=source.active,
        config=dict(source.config or {}),
        keys_missing=keys_missing(source.kind),
        browse=_browse(session, source),
        website=_website(session, source),
        last_run_at=source.last_run_at,
        last_run=_run_view(last) if last else None,
    )


def _source(session: Session, source_id: int) -> Source:
    source = session.get(Source, source_id)
    if source is None:
        raise SourceNotFoundError(f"No existe la fuente {source_id}.")
    return source


def get_source(session: Session, source_id: int) -> SourceView:
    return _view(session, _source(session, source_id))


def list_sources(session: Session, kind: str | None = None) -> SourceList:
    query = select(Source).order_by(Source.name, Source.id)
    if kind:
        query = query.where(Source.kind == kind)
    limits = get_policies().agent_browse.model_dump()
    # El de las plataformas nuevas: el último que elegiste para todas o, si no, el de las políticas.
    limits["default_max_offers"] = default_max_offers(session)
    return SourceList(
        sources=[_view(session, s) for s in session.scalars(query)],
        agent_browse=AgentBrowseLimits.model_validate(limits),
    )


def connector_sources(session: Session, active_only: bool = True) -> list[Source]:
    query = select(Source).where(Source.kind.in_(CONNECTORS)).order_by(Source.id)
    if active_only:
        query = query.where(Source.active.is_(True))
    return list(session.scalars(query))


# --- Alta y cambios --------------------------------------------------------------------------


def _same_target(kind: str, a: SourceConfig, b: dict[str, object]) -> bool:
    if kind in ATS_KINDS:
        keys: tuple[str, ...] = ("slug", "region")
    else:
        keys = ("query", "where", "province", "country", "lang", "remote_only")
    dumped = a.model_dump()
    return all(str(dumped.get(k) or "").lower() == str(b.get(k) or "").lower() for k in keys)


def add_source(session: Session, data: SourceInput) -> SourceView:
    """Da de alta una fuente activa. En un ATS, además marca la empresa como objetivo.

    Con solo `name` y `url`, deduce antes el ATS (`resolve.py`). Si no reconoce ninguno, la web se
    guarda como plataforma que el agente recorre con el navegador."""
    if data.kind is None:
        resolved, resolution, _ = _resolve_input(session, data)
        if resolved is None:
            return _add_browse_page(session, data, resolution)
        data = resolved
    elif data.url and data.kind in ATS_KINDS:
        changes: dict[str, object] = {}
        if not data.website:
            changes["website"] = resolve.company_website(data.url)
        if data.locations is None:  # los lugares firmes de la dirección (`office=Madrid`)
            changes["locations"] = resolve.url_filters(data.url)[0]
        data = _validated(data, **changes)
    config = data.to_config()
    for existing in session.scalars(select(Source).where(Source.kind == data.kind)):
        if _same_target(data.kind, config, existing.config or {}):
            raise SourceExistsError(
                f"Ya existe esa fuente de {KIND_LABELS[data.kind]}: «{existing.name}» "
                f"(id {existing.id})."
            )
    name = " ".join(data.name.split())
    if data.kind in ATS_KINDS and not normalize_company(name):
        raise ValueError(f"Nombre de empresa no válido: «{name}».")
    stored = config.model_dump()
    for optional in ("language", "website", "careers_url"):  # el idioma solo lo usa Personio
        if optional in stored and stored[optional] is None:
            del stored[optional]
    if stored.get("locations") == []:
        del stored["locations"]
    source = Source(kind=data.kind, name=name, config=stored, active=True)
    session.add(source)
    if data.kind in ATS_KINDS:
        company = ingest.get_or_create_company(session, name)
        company.watchlist = True
        if not company.ats_kind:  # no pisa el ATS de otra fuente de la misma empresa
            company.ats_kind = data.kind
            company.ats_slug = config.slug  # type: ignore[union-attr]
    session.flush()
    return _view(session, source)


def _validated(data: SourceInput, **changes: object) -> SourceInput:
    return SourceInput.model_validate({**data.model_dump(), **changes})


def _profile_places(session: Session) -> list[str]:
    preferences = _preferences(session)
    if preferences is None:
        return []
    return [*preferences.locations.preferred, *preferences.locations.allowed]


def _resolve_input(
    session: Session, data: SourceInput
) -> tuple[SourceInput | None, SourceResolution, FetchResult | None]:
    """Del nombre y la dirección, la fuente completa (o `None` si no hay ATS reconocible), lo
    deducido para enseñarlo y, si hizo falta descargar el tablero, lo descargado.

    Los lugares de la ruta (`/madrid/`) solo cuentan si casan con alguna oferta del tablero o con
    tus lugares: así `/engineering/` no se toma por un sitio."""
    assert data.url is not None
    name = " ".join(data.name.split())
    found = resolve.resolve(name, data.url)
    view = SourceResolution(
        url=found.url,
        how=found.how,
        kind=found.board.kind if found.board else None,
        kind_label=found.kind_label,
        slug=found.board.slug if found.board else None,
        region="eu" if found.board and found.board.region == "eu" else "global",
        locations=list(data.locations) if data.locations is not None else list(found.locations),
        website=data.website or found.website,
        issues=found.issues,
    )
    if found.board is None:
        return None, view, None
    resolved = _validated(
        data,
        kind=found.board.kind,
        slug=found.board.slug,
        region=view.region,
        url=found.url,
        website=view.website,
        locations=view.locations,
    )
    fetched = None
    # Los de la ruta que ya están en los parámetros no hace falta confirmarlos.
    found.place_candidates = [
        c for c in found.place_candidates if not any(fold(c) == fold(p) for p in view.locations)
    ]
    if data.locations is None and found.place_candidates:
        try:
            with _client() as client:
                fetched = _fetch(found.board.kind, name, resolved.to_config(), client)
        except ConnectorError:
            fetched = None  # la prueba o la ejecución darán el error
        places = _profile_places(session)
        jobs = [j.location for j in fetched.jobs if j.location] if fetched else []
        for candidate in found.place_candidates:
            if any(location_matches(loc, [candidate]) for loc in jobs) or any(
                location_matches(place, [candidate]) for place in places
            ):
                label = _place_label(candidate, jobs)
                if not any(fold(label) == fold(p) for p in view.locations):
                    view.locations.append(label)
        resolved = _validated(resolved, locations=view.locations)
    return resolved, view, fetched


def _place_label(candidate: str, locations: list[str]) -> str:
    """«madrid» de la dirección se enseña como lo escribe el tablero: «Madrid»."""
    for location in locations:
        for part in location.replace(";", ",").split(","):
            if location_matches(part, [candidate]) and len(part.split()) == len(candidate.split()):
                return part.strip()
    return candidate.title()


def _add_browse_page(session: Session, data: SourceInput, found: SourceResolution) -> SourceView:
    """Una web de empleo sin ATS reconocible: plataforma que el agente recorre con el navegador
    al buscar, como un portal más. La empresa queda como objetivo."""
    from app.services.ingestion import browse

    name = " ".join(data.name.split())
    host = urlsplit(found.url).hostname
    platform = platforms.platform_of_host(host) or resolve.platform_id(found.url)
    saved = browse.add_platform(
        session, AgentBrowseSource(name=name, platform=platform, search_urls=[found.url])
    )
    if normalize_company(name):
        ingest.get_or_create_company(session, name).watchlist = True
    session.flush()
    return get_source(session, saved.source_id)


def set_locations(session: Session, source_id: int, places: list[str]) -> SourceView:
    """Cambia los lugares a los que se limita una empresa («Solo Madrid»); vacío, todos."""
    source = _source(session, source_id)
    if source.kind not in ATS_KINDS:
        raise NotAConnectorError("Solo las empresas con portal propio (ATS) tienen lugares.")
    config = dict(source.config or {})
    cleaned = list(dict.fromkeys(" ".join(p.split()) for p in places if p.strip()))
    if cleaned:
        config["locations"] = cleaned
    else:
        config.pop("locations", None)
    parse_config(source.kind, config)
    source.config = config
    session.flush()
    return _view(session, source)


def _company_of(session: Session, source: Source) -> Company | None:
    return session.scalars(
        select(Company).where(Company.normalized_name == normalize_company(source.name))
    ).first()


def set_active(session: Session, source_id: int, active: bool) -> SourceView:
    """Activa o pausa una fuente. La empresa deja de ser objetivo solo si no le queda ninguna
    otra fuente de ATS activa."""
    source = _source(session, source_id)
    if source.kind not in CONNECTORS:
        raise NotAConnectorError("Solo se pueden activar o pausar las fuentes con conector.")
    source.active = active
    session.flush()
    if source.kind in ATS_KINDS and (company := _company_of(session, source)) is not None:
        siblings = session.scalars(
            select(Source).where(Source.kind.in_(ATS_KINDS), Source.active.is_(True))
        )
        company.watchlist = any(
            normalize_company(s.name) == company.normalized_name for s in siblings
        )
    session.flush()
    return _view(session, source)


def set_website(session: Session, source_id: int, website: str | None) -> SourceView:
    """Pone o quita la web de una empresa con portal propio, que la UI usa para su logo."""
    source = _source(session, source_id)
    if source.kind not in ATS_KINDS:
        raise NotAConnectorError("Solo las empresas con portal propio (ATS) tienen web.")
    config = dict(source.config or {})
    value = _WEBSITE.validate_python(website.strip() if website and website.strip() else None)
    if value is None:
        config.pop("website", None)
    else:
        config["website"] = value
    parse_config(source.kind, config)
    source.config = config
    session.flush()
    return _view(session, source)


# --- Descarga y filtro -----------------------------------------------------------------------


def _preferences(session: Session) -> Preferences | None:
    try:
        return profile_service.current(session).profile.preferences
    except profile_service.ProfileNotFoundError:
        return None


def _fetch(kind: str, name: str, config: SourceConfig, client: httpx.Client) -> FetchResult:
    result = CONNECTORS[kind].fetch(name, config, client)
    limit = get_policies().connectors.max_jobs_per_source
    if len(result.jobs) > limit:
        result.issues.append(
            Issue(
                code="truncated",
                message=f"La fuente devolvió {len(result.jobs)} ofertas; solo se procesan {limit} "
                "(`connectors.max_jobs_per_source`).",
            )
        )
        result.jobs = result.jobs[:limit]
    return result


def _client() -> httpx.Client:
    return make_client(get_policies().connectors.timeout_seconds)


def _summary(found: int, after: int, created: int | None = None, existing: int = 0) -> str:
    noun = "oferta encontrada" if found == 1 else "ofertas encontradas"
    text = f"{found} {noun}, {after} tras filtros"
    if created is not None:
        text += f", {created} {'nueva' if created == 1 else 'nuevas'}"
        if existing:
            text += f", {existing} ya {'estaba' if existing == 1 else 'estaban'}"
    return text


def _places(config: SourceConfig) -> list[str]:
    return list(getattr(config, "locations", []) or [])


def preview_source(session: Session, data: SourceInput | int) -> SourceTestResult:
    """Descarga y filtra una fuente (guardada o no) sin guardar nada. Con solo nombre y dirección,
    deduce antes el ATS y lo devuelve en `resolution`."""
    resolution: SourceResolution | None = None
    fetched: FetchResult | None = None
    if isinstance(data, int):
        source = _source(session, data)
        if source.kind not in CONNECTORS:
            raise NotAConnectorError("Esa fuente no tiene conector que probar.")
        kind, name, config = source.kind, source.name, parse_config(source.kind, source.config)
    else:
        if data.kind is None:
            resolved, resolution, fetched = _resolve_input(session, data)
            if resolved is None:
                return _unrecognized(session, data, resolution)
            data = resolved
        assert data.kind is not None
        kind, name, config = data.kind, " ".join(data.name.split()), data.to_config()
    prefilter = Prefilter(_preferences(session), config.title_keywords, _places(config))
    try:
        if fetched is None:
            with _client() as client:
                fetched = _fetch(kind, name, config, client)
    except ConnectorError as exc:
        return SourceTestResult(
            kind=kind,
            name=name,
            found=0,
            after_filters=0,
            jobs=[],
            errors=[Issue(code=exc.code, message=exc.message)],
            filters_applied=prefilter.active,
            message=exc.message,
            resolution=resolution,
        )
    previews = []
    for raw in fetched.jobs:
        verdict = prefilter.check(raw.title, raw.location, raw.remote)
        previews.append(
            PreviewJob(
                external_id=raw.external_id,
                title=raw.title,
                company=raw.company,
                location=raw.location,
                url=raw.url,
                passed=verdict.passed,
                reason=verdict.reason,
            )
        )
    after = sum(p.passed for p in previews)
    message = _summary(len(previews), after)
    if not prefilter.active:
        message += " (sin perfil importado no se filtra)"
    return SourceTestResult(
        kind=kind,
        name=name,
        found=len(previews),
        after_filters=after,
        jobs=previews,
        errors=fetched.issues,
        filters_applied=prefilter.active,
        message=message,
        resolution=resolution,
    )


def _unrecognized(
    session: Session, data: SourceInput, resolution: SourceResolution
) -> SourceTestResult:
    """Prueba de una web sin ATS reconocible: no hay nada que descargar sin navegador."""
    return SourceTestResult(
        kind="agent_browse",
        name=" ".join(data.name.split()),
        found=0,
        after_filters=0,
        jobs=[],
        errors=[],
        filters_applied=_preferences(session) is not None,
        message=(
            "No se reconoce ninguna web de empleo conocida en esa dirección: se guardará como "
            "plataforma que tu agente recorre con el navegador al buscar."
        ),
        resolution=resolution,
    )


# --- Ejecución -------------------------------------------------------------------------------


def _already_stored(session: Session, source: Source, raw: RawJob) -> tuple[Job, bool] | None:
    """Oferta ya vista: por id en la fuente, por URL o por huella (sin descargar el detalle). El
    segundo valor dice si es la misma publicación (id o URL) o solo la misma huella."""
    by_id = session.scalars(
        select(Job)
        .where(Job.source_id == source.id, Job.external_id == raw.external_id)
        .order_by(Job.id.desc())
        .limit(1)
    ).first()
    if by_id is not None:
        return by_id, True
    if raw.url:
        by_url = session.scalars(
            select(Job).where(Job.url == raw.url).order_by(Job.id.desc()).limit(1)
        ).first()
        if by_url is not None:
            return by_url, True
    fp = fingerprint(raw.company, raw.title, raw.location)
    by_fp = ingest.latest_by_fingerprint(session, fp)
    return (by_fp, False) if by_fp is not None else None


def _finish(
    session: Session, source: Source, run: SourceRun, result: SourceRunResult, *, ok: bool
) -> SourceRunResult:
    """Registra la ejecución. Si la fuente falló entera, `last_run_at` no avanza: así el worker
    la vuelve a encolar al arrancar aunque se agoten los reintentos."""
    run.finished_at = utcnow()
    run.found, run.after_filters, run.created = result.found, result.after_filters, result.created
    run.errors = [issue.model_dump() for issue in result.errors]
    session.add(run)
    if ok:
        source.last_run_at = run.started_at
    session.flush()
    result.run_id = run.id
    return result


def _collect(
    session: Session,
    source: Source,
    config: SourceConfig,
    client: httpx.Client,
    result: SourceRunResult,
) -> tuple[list[RawJob], list[tuple[int, RawJob, bool]]]:
    """Toda la parte de red, sin escribir en la BD (SQLite no queda bloqueado mientras se
    descarga): descarga, filtro previo, descarte de lo ya visto y detalle de lo nuevo.

    Devuelve lo nuevo y lo ya visto (con su oferta), para anotar luego si es otra publicación."""
    connector = CONNECTORS[source.kind]
    fetched = _fetch(source.kind, source.name, config, client)
    prefilter = Prefilter(_preferences(session), config.title_keywords, _places(config))
    result.found = len(fetched.jobs)
    result.errors.extend(fetched.issues)
    pending: list[RawJob] = []
    seen: list[tuple[int, RawJob, bool]] = []
    details_blocked: ConnectorError | None = None
    skipped_details = 0
    for raw in fetched.jobs:
        if not prefilter.check(raw.title, raw.location, raw.remote).passed:
            continue
        result.after_filters += 1
        stored = _already_stored(session, source, raw)
        # Una vacante que cerró la empresa y vuelve (fase 45) se guarda como oferta nueva.
        if stored is not None and (
            stored[1] or ingest.republication(session, stored[0], same_id=False) != "reopening"
        ):
            result.existing += 1
            seen.append((stored[0].id, raw, stored[1]))
            continue
        if raw.needs_detail:
            if details_blocked is not None:
                skipped_details += 1
                continue
            try:
                raw = connector.complete(raw, client)
            except ConnectorError as exc:
                result.errors.append(
                    Issue(code=exc.code, message=exc.message, item=raw.external_id)
                )
                # Sin permiso o con límite de peticiones, el resto fallaría igual.
                if exc.code in _STOP_DETAIL_CODES:
                    details_blocked = exc
                continue
        pending.append(raw)
    if skipped_details:
        result.errors.append(
            Issue(
                code="details_skipped",
                message=f"No se pidió el detalle de {skipped_details} ofertas más: se intentará "
                "en la próxima ejecución.",
            )
        )
    return pending, seen


def _note_seen(session: Session, seen: list[tuple[int, RawJob, bool]]) -> None:
    """Lo ya visto con otro id o URL es otra publicación de la misma oferta (fase 16); si estaba
    cerrada, puede reabrirse o avisar (fase 45, `ingest.note_known`)."""
    for job_id, raw, same_id in seen:
        job = session.get(Job, job_id)
        if job is not None:
            ingest.note_known(
                session,
                job,
                same_id=same_id,
                url=raw.url,
                platform=None,
                external_id=raw.external_id,
            )


def _store(session: Session, source: Source, raw: RawJob, result: SourceRunResult) -> None:
    try:
        with session.begin_nested():  # una oferta que falla no deshace las demás
            stored = ingest.store_job(
                session,
                source=source,
                title=raw.title,
                company=raw.company,
                text=ingest.clean_text(raw.text),
                url=raw.url,
                location=raw.location,
                posted_at=raw.posted_at,
                html=raw.html,
                external_id=raw.external_id,
            )
    except ingest.IngestError as exc:
        result.errors.append(Issue(code="store_failed", message=str(exc), item=raw.external_id))
        return
    except SQLAlchemyError as exc:
        logger.warning("No se pudo guardar la oferta %s", raw.external_id, exc_info=True)
        result.errors.append(
            Issue(
                code="store_failed",
                message=f"Error de base de datos ({type(exc).__name__}).",
                item=raw.external_id,
            )
        )
        return
    if not stored.created:
        result.existing += 1
        return
    result.created += 1
    result.job_ids.append(stored.job_id)


def run_source(
    session: Session, source_id: int, actor: str = "user", *, search_run_id: int | None = None
) -> SourceRunResult:
    """Ejecuta una fuente y guarda lo nuevo. Un fallo de la fuente no lanza: queda en `errors`
    (y en `source_runs`); `retryable_error` dice al worker si conviene reintentar. Con
    `search_run_id`, el recorrido queda ligado a esa búsqueda de «Buscar ahora»."""
    source = _source(session, source_id)
    if source.kind not in CONNECTORS:
        raise NotAConnectorError(f"La fuente «{source.name}» no tiene conector.")
    label = f"{KIND_LABELS[source.kind]} · {source.name}"
    result = SourceRunResult(
        source_id=source.id,
        name=source.name,
        kind=source.kind,
        run_id=None,
        skipped=None,
        found=0,
        after_filters=0,
        created=0,
        existing=0,
        job_ids=[],
        errors=[],
        message="",
    )
    run = SourceRun(
        source_id=source.id,
        actor=actor,
        started_at=utcnow(),
        errors=[],
        search_run_id=search_run_id,
    )
    try:
        config = parse_config(source.kind, source.config)
        with _client() as client:
            pending, seen = _collect(session, source, config, client, result)
        with session.begin_nested():  # si algo inesperado falla, no queda nada a medias
            _note_seen(session, seen)
            for raw in pending:
                _store(session, source, raw, result)
    except MissingKeysError as exc:
        result.skipped = exc.message
        result.message = f"{label}: omitida. {exc.message}"
        return result
    except ConnectorError as exc:
        result.errors.append(Issue(code=exc.code, message=exc.message))
        result.message = f"{label}: error. {exc.message}"
        return _finish(session, source, run, result, ok=False)
    except Exception as exc:  # un fallo inesperado también queda en `source_runs`
        logger.exception("Fallo inesperado al ejecutar la fuente %s", source_id)
        result.created, result.job_ids = 0, []
        name = type(exc).__name__
        result.errors.append(
            Issue(code="internal_error", message=f"Error interno ({name}); detalles en el log.")
        )
        result.message = f"{label}: error interno ({name})."
        return _finish(session, source, run, result, ok=False)
    result.message = f"{label}: " + _summary(
        result.found, result.after_filters, result.created, result.existing
    )
    if result.errors:
        result.message += f"; {len(result.errors)} avisos"
    return _finish(session, source, run, result, ok=True)


def retryable_error(result: SourceRunResult) -> str | None:
    """El error de toda la fuente si merece reintento (red, 5xx, 429); si no, `None`."""
    if result.found or result.skipped:
        return None
    for issue in result.errors:
        if issue.code in RETRYABLE_CODES and issue.item is None:
            return issue.message
    return None
