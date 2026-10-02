"""Fuentes con conector (fase 09): alta, prueba sin guardar y ejecución.

Ejecutar una fuente descarga sus ofertas, aplica el filtro previo y guarda las nuevas con el mismo
servicio que el alta manual (`ingest.store_job`): huella, duplicados difusos, detección de riesgo y
evento `found`, que las deja en `pending_extraction`. Es idempotente: una oferta ya vista (por su
id en la fuente, su URL o su huella) no se vuelve a crear ni genera eventos.

Cada ejecución queda en `source_runs`, también si la fuente falla: así el error se ve en la UI.
"""

import logging

import httpx
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.policies import get_policies
from app.models import Company, Job, Source, SourceRun
from app.models.base import utcnow
from app.schemas.profile import Preferences
from app.schemas.sources import (
    ATS_KINDS,
    KIND_LABELS,
    Issue,
    PreviewJob,
    SourceConfig,
    SourceInput,
    SourceList,
    SourceRunResult,
    SourceRunView,
    SourceTestResult,
    SourceView,
    parse_config,
)
from app.services import ingest
from app.services import profile as profile_service
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
from app.services.ingestion.greenhouse import GreenhouseConnector
from app.services.ingestion.infojobs import InfoJobsConnector
from app.services.ingestion.lever import LeverConnector
from app.services.ingestion.prefilter import Prefilter
from app.services.normalize import fingerprint, normalize_company

logger = logging.getLogger(__name__)

CONNECTORS: dict[str, Connector] = {
    c.kind: c
    for c in (
        GreenhouseConnector(),
        LeverConnector(),
        AshbyConnector(),
        InfoJobsConnector(),
        AdzunaConnector(),
    )
}
# Fallos de la fuente que merece la pena reintentar (el worker reintenta con espera creciente).
RETRYABLE_CODES = frozenset({"timeout", "network", "http_error", "rate_limited", "internal_error"})
# Si el detalle de una oferta falla así, no se pide el de las demás en esta ejecución.
_STOP_DETAIL_CODES = frozenset({"unauthorized", "rate_limited"})
MANUAL_LABELS = {**ingest.SOURCE_NAMES, "email_alerts": "Alertas por correo"}


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
        return not (settings.infojobs_client_id and settings.infojobs_client_secret)
    if kind == "adzuna":
        return not (settings.adzuna_app_id and settings.adzuna_app_key)
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
    )


def _last_run(session: Session, source_id: int) -> SourceRun | None:
    return session.scalars(
        select(SourceRun)
        .where(SourceRun.source_id == source_id)
        .order_by(SourceRun.started_at.desc(), SourceRun.id.desc())
        .limit(1)
    ).first()


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
    return SourceList(sources=[_view(session, s) for s in session.scalars(query)])


def connector_sources(session: Session, active_only: bool = True) -> list[Source]:
    query = select(Source).where(Source.kind.in_(CONNECTORS)).order_by(Source.id)
    if active_only:
        query = query.where(Source.active.is_(True))
    return list(session.scalars(query))


# --- Alta y cambios --------------------------------------------------------------------------


def _same_target(kind: str, a: SourceConfig, b: dict[str, object]) -> bool:
    keys = ("slug", "region") if kind in ATS_KINDS else ("query", "where", "province", "country")
    dumped = a.model_dump()
    return all(str(dumped.get(k) or "").lower() == str(b.get(k) or "").lower() for k in keys)


def add_source(session: Session, data: SourceInput) -> SourceView:
    """Da de alta una fuente activa. En un ATS, además marca la empresa como objetivo."""
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
    source = Source(kind=data.kind, name=name, config=config.model_dump(), active=True)
    session.add(source)
    if data.kind in ATS_KINDS:
        company = ingest.get_or_create_company(session, name)
        company.watchlist = True
        if not company.ats_kind:  # no pisa el ATS de otra fuente de la misma empresa
            company.ats_kind = data.kind
            company.ats_slug = config.slug  # type: ignore[union-attr]
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


def preview_source(session: Session, data: SourceInput | int) -> SourceTestResult:
    """Descarga y filtra una fuente (guardada o no) sin guardar nada."""
    if isinstance(data, int):
        source = _source(session, data)
        if source.kind not in CONNECTORS:
            raise NotAConnectorError("Esa fuente no tiene conector que probar.")
        kind, name, config = source.kind, source.name, parse_config(source.kind, source.config)
    else:
        kind, name, config = data.kind, " ".join(data.name.split()), data.to_config()
    prefilter = Prefilter(_preferences(session), config.title_keywords)
    try:
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
    )


# --- Ejecución -------------------------------------------------------------------------------


def _already_stored(session: Session, source: Source, raw: RawJob) -> Job | None:
    """Oferta ya vista: por id en la fuente, por URL o por huella (sin descargar el detalle)."""
    by_id = session.scalars(
        select(Job).where(Job.source_id == source.id, Job.external_id == raw.external_id).limit(1)
    ).first()
    if by_id is not None:
        return by_id
    if raw.url:
        by_url = session.scalars(select(Job).where(Job.url == raw.url).limit(1)).first()
        if by_url is not None:
            return by_url
    fp = fingerprint(raw.company, raw.title, raw.location)
    return session.scalars(select(Job).where(Job.fingerprint == fp).limit(1)).first()


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
) -> list[RawJob]:
    """Toda la parte de red, sin escribir en la BD (SQLite no queda bloqueado mientras se
    descarga): descarga, filtro previo, descarte de lo ya visto y detalle de lo nuevo."""
    connector = CONNECTORS[source.kind]
    fetched = _fetch(source.kind, source.name, config, client)
    prefilter = Prefilter(_preferences(session), config.title_keywords)
    result.found = len(fetched.jobs)
    result.errors.extend(fetched.issues)
    pending: list[RawJob] = []
    details_blocked: ConnectorError | None = None
    skipped_details = 0
    for raw in fetched.jobs:
        if not prefilter.check(raw.title, raw.location, raw.remote).passed:
            continue
        result.after_filters += 1
        if _already_stored(session, source, raw) is not None:
            result.existing += 1
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
    return pending


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
    if stored.duplicate_of is not None:
        result.duplicates += 1


def run_source(session: Session, source_id: int, actor: str = "user") -> SourceRunResult:
    """Ejecuta una fuente y guarda lo nuevo. Un fallo de la fuente no lanza: queda en `errors`
    (y en `source_runs`); `retryable_error` dice al worker si conviene reintentar."""
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
        duplicates=0,
        job_ids=[],
        errors=[],
        message="",
    )
    run = SourceRun(source_id=source.id, actor=actor, started_at=utcnow(), errors=[])
    try:
        config = parse_config(source.kind, source.config)
        with _client() as client:
            pending = _collect(session, source, config, client, result)
        with session.begin_nested():  # si algo inesperado falla, no queda nada a medias
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
    if result.duplicates:
        result.message += f" ({result.duplicates} cerradas como duplicadas)"
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
