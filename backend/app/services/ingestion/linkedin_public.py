"""Búsqueda pública de LinkedIn sin sesión (fase 22, ADR-033). Apagada por defecto.

Consulta los endpoints públicos `jobs-guest` de LinkedIn, los mismos que sirven la búsqueda a quien
no ha iniciado sesión, con las búsquedas de la plataforma LinkedIn de la pantalla Plataformas
(sus `search_urls`). Reglas que viven aquí y no en la UI ni en un skill (ADR-012):

- solo si el usuario la ha activado desde la UI, aceptando el riesgo. El agente no puede: no hay
  herramienta MCP ni comando que la active, y `save_source` no toca esta fuente;
- sin cookies, sin cuenta, sin redirecciones y con un user-agent honesto que dice qué es;
- límites de `config/policies.yaml` → `linkedin_public`: búsquedas por ejecución, páginas por
  búsqueda, pausa entre peticiones (≥ 10 s), una ejecución al día y descripciones por ejecución;
- corte inmediato ante 429, 999, 401/403, cualquier redirección (authwall, checkpoint) o una página
  de captcha o anti-bot: no se hace ninguna petición más, se anota y no se reintenta en
  `block_cooldown_days` días;
- lo que pasa el filtro previo entra como resumen (`pending_detail`), igual que las alertas por
  correo, y se completa con el botón de captura. Solo con `fetch_detail` (otro interruptor, también
  apagado) se pide la descripción de las nuevas por el endpoint público.

El HTML de LinkedIn es contenido no confiable: se lee como datos y pasa por la detección de riesgo
al guardar. Nunca se sigue un enlace que venga en él.
"""

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import lxml.html
from lxml.etree import ParserError
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.policies import LinkedInPublicPolicy, get_policies
from app.models import Source, SourceRun
from app.models.base import utcnow
from app.schemas.profile import Preferences
from app.schemas.sources import (
    Issue,
    LinkedInPublicLimits,
    LinkedInPublicRunResult,
    LinkedInPublicView,
    LinkedInSearch,
    SourceRunView,
)
from app.services import ingest, platforms
from app.services import profile as profile_service
from app.services.ingestion.base import html_fragment_to_text, parse_datetime
from app.services.ingestion.browse import KIND as BROWSE_KIND
from app.services.ingestion.browse import BrowsingNotAllowedError, is_linkedin
from app.services.ingestion.prefilter import Prefilter

logger = logging.getLogger(__name__)

KIND = "linkedin_public"
NAME = "LinkedIn · búsqueda pública"
SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL_URL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}"
# Honesto: dice qué es y para qué. Solo ASCII en cabeceras.
USER_AGENT = "CandidatAI/0.1 (local personal job search app; public job search, no login)"

# Parámetros de una búsqueda de LinkedIn que se pasan tal cual al endpoint público.
_TEXT_PARAMS = ("keywords", "location")
_CODE_PARAMS = ("geoId", "distance", "f_TPR", "f_WT", "f_E", "f_JT")
_CODE = re.compile(r"^[A-Za-z0-9,._-]{1,60}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_JOB_URN = re.compile(r"jobPosting:(\d{6,20})")
_BLOCK_STATUS = frozenset({401, 403, 429, 999})
# Señales de una página de control servida con HTTP 200 (se buscan solo si no hay ofertas).
_BLOCK_MARKERS = (
    "captcha",
    "checkpoint/challenge",
    "authwall",
    "security check",
    "security verification",
    "unusual activity",
    "verificación de seguridad",
    "actividad inusual",
)
_MAX_BYTES = 2_000_000

Sleep = Callable[[float], None]


class LinkedInBlockedError(Exception):
    """LinkedIn ha cortado: no se hace ninguna petición más en esta ejecución."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class _FetchError(Exception):
    """Fallo de una petición que no es un bloqueo (red, 404, 5xx)."""


# --- Fuente y estado -------------------------------------------------------------------------


def _find_source(session: Session) -> Source | None:
    return session.scalars(select(Source).where(Source.kind == KIND).limit(1)).first()


def _get_or_create_source(session: Session) -> Source:
    source = _find_source(session)
    if source is None:
        source = Source(kind=KIND, name=NAME, config={"enabled": False}, active=True)
        session.add(source)
        session.flush()
    return source


def _config(source: Source | None) -> dict[str, Any]:
    return dict(source.config or {}) if source is not None else {}


def is_enabled(source: Source | None) -> bool:
    return bool(_config(source).get("enabled"))


def _parse_dt(value: Any) -> datetime | None:
    return parse_datetime(value) if isinstance(value, str) else None


def _linkedin_platforms(session: Session) -> list[Source]:
    rows = session.scalars(select(Source).where(Source.kind == BROWSE_KIND).order_by(Source.id))
    return [s for s in rows if is_linkedin(s.config or {})]


def _search_from_url(url: str, default_time_posted: str | None) -> LinkedInSearch:
    """Traduce una búsqueda de linkedin.com a parámetros del endpoint público, o `ValueError`."""
    try:
        parts = urlsplit(url.strip())
    except ValueError as exc:
        raise ValueError("no es una URL válida") from exc
    if parts.scheme not in {"http", "https"} or platforms.platform_of_host(parts.hostname) != (
        "linkedin"
    ):
        raise ValueError("no es de linkedin.com")
    if not parts.path.rstrip("/").endswith("/jobs/search"):
        raise ValueError("no es una búsqueda de empleo (linkedin.com/jobs/search?…)")
    query = parse_qs(parts.query)
    params: dict[str, str] = {}
    for key in _TEXT_PARAMS:
        value = " ".join((query.get(key, [""])[0]).split())
        if value and not _CONTROL.search(value):
            params[key] = value[:200]
    if not params.get("keywords") and not (params.get("location") or query.get("geoId")):
        raise ValueError("no dice ni palabras clave ni ubicación")
    for key in _CODE_PARAMS:
        value = query.get(key, [""])[0].strip()
        if value and _CODE.match(value):
            params[key] = value
    if "f_TPR" not in params and default_time_posted:
        params["f_TPR"] = default_time_posted
    return LinkedInSearch(
        url=url,
        keywords=params.get("keywords"),
        location=params.get("location"),
        params=params,
    )


def searches(session: Session) -> tuple[list[LinkedInSearch], list[Issue]]:
    """Las búsquedas que se lanzarán (hasta `max_searches_per_run`) y las que no, con el motivo."""
    policy = get_policies().linkedin_public
    usable: list[LinkedInSearch] = []
    ignored: list[Issue] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for platform in _linkedin_platforms(session):
        for url in (platform.config or {}).get("search_urls") or []:
            try:
                search = _search_from_url(str(url), policy.default_time_posted)
            except ValueError as exc:
                ignored.append(Issue(code="unusable_search", message=f"{exc}.", item=str(url)))
                continue
            key = tuple(sorted(search.params.items()))
            if key in seen:
                continue
            seen.add(key)
            if len(usable) >= policy.max_searches_per_run:
                ignored.append(
                    Issue(
                        code="over_limit",
                        message="Pasa del límite de búsquedas por ejecución "
                        "(`linkedin_public.max_searches_per_run`).",
                        item=str(url),
                    )
                )
                continue
            usable.append(search)
    return usable, ignored


def _last_run(session: Session, source: Source) -> SourceRun | None:
    return session.scalars(
        select(SourceRun)
        .where(SourceRun.source_id == source.id)
        .order_by(SourceRun.started_at.desc(), SourceRun.id.desc())
        .limit(1)
    ).first()


def next_run_at(
    source: Source | None, policy: LinkedInPublicPolicy | None = None
) -> datetime | None:
    """Desde cuándo puede volver a ejecutarse: una vez al día y, tras un bloqueo, unos días más."""
    if source is None:
        return None
    policy = policy or get_policies().linkedin_public
    candidates = []
    if source.last_run_at is not None:
        candidates.append(source.last_run_at + timedelta(hours=policy.min_hours_between_runs))
    if (blocked := _parse_dt(_config(source).get("blocked_at"))) is not None:
        candidates.append(blocked + timedelta(days=policy.block_cooldown_days))
    return max(candidates) if candidates else None


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


def get_view(session: Session) -> LinkedInPublicView:
    policy = get_policies().linkedin_public
    source = _find_source(session)
    config = _config(source)
    usable, ignored = searches(session)
    linkedin = _linkedin_platforms(session)
    last = _last_run(session, source) if source is not None else None
    return LinkedInPublicView(
        source_id=source.id if source is not None else None,
        enabled=bool(config.get("enabled")),
        fetch_detail=bool(config.get("fetch_detail")),
        enabled_at=_parse_dt(config.get("enabled_at")),
        platform_source_id=linkedin[0].id if linkedin else None,
        searches=usable,
        ignored=ignored,
        blocked_at=_parse_dt(config.get("blocked_at")),
        next_run_at=next_run_at(source, policy),
        last_run=_run_view(last) if last is not None else None,
        limits=LinkedInPublicLimits.model_validate(policy.model_dump()),
    )


def update_settings(
    session: Session,
    *,
    enabled: bool | None = None,
    fetch_detail: bool | None = None,
    confirm_risk: bool = False,
) -> LinkedInPublicView:
    """Cambios del usuario desde la UI. Encender cualquiera de los dos interruptores exige
    `confirm_risk`; apagarlos, nunca. No lo usa la interfaz para agentes."""
    source = _find_source(session)
    config = _config(source)
    enabling = bool(enabled) and not config.get("enabled")
    enabling_detail = bool(fetch_detail) and not config.get("fetch_detail")
    turning_on = enabling or enabling_detail
    if turning_on and not confirm_risk:
        raise BrowsingNotAllowedError(
            "Activar la búsqueda pública de LinkedIn requiere confirmar que aceptas el riesgo "
            "(`confirm_risk: true`): va contra sus condiciones de uso y puede bloquear tu IP."
        )
    if enabling_detail and not (config.get("enabled") or enabling):
        raise ValueError(
            "Activa antes la búsqueda pública: la descarga de la descripción va con ella."
        )
    if enabling and not searches(session)[0]:
        raise ValueError(
            "No hay ninguna búsqueda de LinkedIn que usar: añade a la plataforma LinkedIn una URL "
            "de linkedin.com/jobs/search con palabras clave o ubicación."
        )
    if source is None:
        if not turning_on:
            return get_view(session)  # apagar lo que nunca se encendió: nada que guardar
        source = _get_or_create_source(session)
        config = _config(source)
    if enabled is not None:
        if enabled and not config.get("enabled"):
            config["enabled_at"] = utcnow().isoformat()
        config["enabled"] = enabled
    if fetch_detail is not None:
        config["fetch_detail"] = fetch_detail
    source.config = config  # dict nuevo: SQLAlchemy no ve los cambios dentro del JSON
    session.flush()
    return get_view(session)


def due(session: Session, now: datetime | None = None) -> bool:
    """Si el worker debe encolarla: activada, con búsquedas y fuera de los límites de tiempo."""
    source = _find_source(session)
    if not is_enabled(source):
        return False
    when = next_run_at(source)
    if when is not None and (now or utcnow()) < when:
        return False
    return bool(searches(session)[0])


# --- Red ---------------------------------------------------------------------------------------


def make_client(timeout: float, transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """Sin cookies (cada petición sin estado), sin redirecciones y con un user-agent honesto."""
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return httpx.Client(
        timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        },
        follow_redirects=False,
        transport=transport,
    )


def _looks_blocked(body: str) -> bool:
    text = body.lower()
    return any(marker in text for marker in _BLOCK_MARKERS)


class _Gate:
    """Hace las peticiones de una ejecución: pausa entre todas ellas y corte ante un bloqueo."""

    def __init__(self, client: httpx.Client, sleep: Sleep, delay: float) -> None:
        self.client, self.sleep, self.delay = client, sleep, delay
        self.requests = 0

    def get(self, url: str, params: dict[str, str] | None = None) -> str:
        if self.requests:
            self.sleep(self.delay)
        self.requests += 1
        try:
            response = self.client.get(url, params=params)
        except httpx.TimeoutException as exc:
            raise _FetchError("LinkedIn no respondió a tiempo.") from exc
        except httpx.HTTPError as exc:
            raise _FetchError(f"No se pudo conectar con LinkedIn: {type(exc).__name__}.") from exc
        status = response.status_code
        if status in _BLOCK_STATUS:
            raise LinkedInBlockedError(f"LinkedIn respondió HTTP {status}: corta la búsqueda.")
        if response.is_redirect or 300 <= status < 400:
            raise LinkedInBlockedError(
                f"LinkedIn redirigió (HTTP {status}), probablemente a su inicio de sesión o a un "
                "control: no se sigue."
            )
        if status >= 400:
            raise _FetchError(f"LinkedIn respondió con un error HTTP {status}.")
        return response.content[:_MAX_BYTES].decode(response.encoding or "utf-8", "replace")


# --- Lectura del HTML --------------------------------------------------------------------------


@dataclass
class _Card:
    external_id: str
    title: str
    company: str
    location: str | None
    posted_at: datetime | None
    text: str = ""
    html: str | None = None
    full: bool = False


def _cls(name: str) -> str:
    return f"contains(concat(' ', normalize-space(@class), ' '), ' {name} ')"


def _find(node: Any, classes: tuple[str, ...], tags: tuple[str, ...] = ()) -> list[Any]:
    """Descendientes con alguna de esas clases o, si no hay, con alguna de esas etiquetas."""
    found = node.xpath(".//*[" + " or ".join(_cls(c) for c in classes) + "]")
    if not found and tags:
        found = node.xpath(" | ".join(f".//{t}" for t in tags))
    return list(found)


def _text_of(node: Any, classes: tuple[str, ...], tags: tuple[str, ...] = ()) -> str | None:
    found = _find(node, classes, tags)
    if not found:
        return None
    value = " ".join(found[0].text_content().split())
    return value or None


def _card_id(node: Any) -> str | None:
    for attr in ("data-entity-urn", "data-id"):
        if (match := _JOB_URN.search(node.get(attr) or "")) is not None:
            return match.group(1)
    for link in node.iter("a"):
        pid = platforms.detect(link.get("href") or "")
        if pid is not None and pid.platform == "linkedin":
            return pid.external_id
    return None


def parse_results(body: str) -> tuple[list[_Card], list[Issue]]:
    """Tarjetas de una página de resultados. Lo que no trae id, título o empresa se salta."""
    if not body.strip():
        return [], []
    try:
        root = lxml.html.fragment_fromstring(body, create_parent="div")
    except (ParserError, ValueError):
        return [], [Issue(code="unexpected_format", message="LinkedIn devolvió HTML ilegible.")]
    cards: list[_Card] = []
    issues: list[Issue] = []
    nodes = root.xpath(
        ".//*[" + _cls("base-search-card") + " or " + _cls("job-search-card") + "]"
        " | .//*[@data-entity-urn]"
    )
    outer = set(nodes)
    for node in nodes:
        # Una tarjeta puede contener otra que también casa (p. ej. un `data-entity-urn` dentro):
        # se toma la de fuera.
        if any(a in outer for a in node.iterancestors()):
            continue
        external_id = _card_id(node)
        title = _text_of(node, ("base-search-card__title",), ("h3",))
        company = _text_of(node, ("base-search-card__subtitle",), ("h4",))
        if not external_id or not title or not company:
            issues.append(
                Issue(
                    code="invalid_item",
                    message="Tarjeta de LinkedIn sin id, título o empresa: ignorada.",
                    item=external_id,
                )
            )
            continue
        time_node = node.xpath(".//time")
        posted = parse_datetime(time_node[0].get("datetime")) if time_node else None
        cards.append(
            _Card(
                external_id=external_id,
                title=title[:300],
                company=company[:200],
                location=_text_of(node, ("job-search-card__location",)),
                posted_at=posted,
            )
        )
    return cards, issues


def parse_detail(body: str) -> tuple[str, str] | None:
    """Descripción (texto y HTML del bloque) de la página pública de una oferta."""
    try:
        root = lxml.html.fragment_fromstring(body, create_parent="div")
    except (ParserError, ValueError):
        return None
    blocks = _find(root, ("show-more-less-html__markup", "description__text"))
    if not blocks:
        return None
    fragment = lxml.html.tostring(blocks[0], encoding="unicode")
    text = html_fragment_to_text(fragment)[: ingest.MAX_TEXT_CHARS]
    return (text, fragment) if text else None


def _summary_text(card: _Card) -> str:
    lines = [card.title, card.company, card.location or ""]
    note = "(Resumen de la búsqueda pública de LinkedIn: falta la descripción de la oferta.)"
    return "\n".join([*(line for line in lines if line), "", note])


# --- Ejecución ---------------------------------------------------------------------------------


@dataclass
class _Collected:
    pending: list[_Card] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    blocked: str | None = None


def _preferences(session: Session) -> Preferences | None:
    try:
        return profile_service.current(session).profile.preferences
    except profile_service.ProfileNotFoundError:
        return None


def _collect(
    session: Session,
    gate: _Gate,
    run_searches: list[LinkedInSearch],
    fetch_detail: bool,
    policy: LinkedInPublicPolicy,
    result: LinkedInPublicRunResult,
) -> _Collected:
    """Toda la red, sin escribir: resultados, filtro previo, lo ya visto y, si se pidió, el
    detalle de lo nuevo. Un bloqueo para todo en el acto."""
    out = _Collected()
    prefilter = Prefilter(_preferences(session), [])
    seen_ids: set[str] = set()
    fresh: list[_Card] = []
    try:
        for search in run_searches:
            start = 0
            for page in range(policy.max_pages_per_search):
                try:
                    body = gate.get(SEARCH_URL, {**search.params, "start": str(start)})
                except _FetchError as exc:
                    out.issues.append(Issue(code="http_error", message=str(exc), item=search.url))
                    break
                cards, issues = parse_results(body)
                out.issues.extend(issues)
                if not cards:
                    if body.strip() and _looks_blocked(body):
                        raise LinkedInBlockedError(
                            "LinkedIn sirvió una página de control (captcha, inicio de sesión o "
                            "anti-bot) en vez de resultados."
                        )
                    if page == 0 and body.strip():
                        out.issues.append(
                            Issue(
                                code="page_changed",
                                message="La respuesta de LinkedIn no trae ofertas reconocibles: "
                                "puede que haya cambiado su formato.",
                                item=search.url,
                            )
                        )
                    break
                start += len(cards)
                for card in cards:
                    if card.external_id in seen_ids:
                        continue
                    seen_ids.add(card.external_id)
                    result.found += 1
                    if not prefilter.check_summary(card.title, card.location).passed:
                        continue
                    result.after_filters += 1
                    if ingest.find_by_platform(session, "linkedin", card.external_id) is not None:
                        result.existing += 1
                        continue
                    fresh.append(card)
        details = 0
        for card in fresh:
            if fetch_detail and details < policy.max_details_per_run:
                details += 1
                try:
                    body = gate.get(DETAIL_URL.format(id=card.external_id))
                except _FetchError as exc:
                    out.issues.append(
                        Issue(code="detail_failed", message=str(exc), item=card.external_id)
                    )
                else:
                    parsed = parse_detail(body)
                    if parsed is None and _looks_blocked(body):
                        raise LinkedInBlockedError(
                            "LinkedIn sirvió una página de control en vez de la oferta."
                        )
                    if parsed is not None and len(parsed[0]) >= ingest.MIN_TEXT_CHARS:
                        card.text, card.html, card.full = parsed[0], parsed[1], True
            out.pending.append(card)
        if fetch_detail and len(fresh) > details:
            out.issues.append(
                Issue(
                    code="details_skipped",
                    message=f"Sin descripción para {len(fresh) - details} ofertas por el límite "
                    "`linkedin_public.max_details_per_run`: entran como resumen.",
                )
            )
    except LinkedInBlockedError as exc:
        out.blocked = exc.message
        # Lo ya leído se guarda; lo que faltaba por pedir, como resumen.
        kept = {c.external_id for c in out.pending}
        out.pending += [c for c in fresh if c.external_id not in kept]
    return out


def _store(session: Session, source: Source, card: _Card, result: LinkedInPublicRunResult) -> None:
    pid = platforms.PlatformId("linkedin", card.external_id)
    try:
        with session.begin_nested():  # una oferta que falla no deshace las demás
            stored = ingest.store_job(
                session,
                source=source,
                title=card.title,
                company=card.company,
                text=card.text if card.full else _summary_text(card),
                url=platforms.canonical_url(pid) or "",
                location=card.location,
                posted_at=card.posted_at,
                html=card.html,
                external_id=card.external_id,
                platform="linkedin",
                detail_level="full" if card.full else "summary",
            )
    except ingest.IngestError as exc:
        result.errors.append(Issue(code="store_failed", message=str(exc), item=card.external_id))
        return
    except SQLAlchemyError as exc:
        logger.warning("No se pudo guardar la oferta %s", card.external_id, exc_info=True)
        result.errors.append(
            Issue(
                code="store_failed",
                message=f"Error de base de datos ({type(exc).__name__}).",
                item=card.external_id,
            )
        )
        return
    if not stored.created:
        result.existing += 1
        return
    result.created += 1
    result.job_ids.append(stored.job_id)
    if not card.full:
        result.summaries += 1


def _empty_result(source: Source | None, skipped: str | None = None) -> LinkedInPublicRunResult:
    return LinkedInPublicRunResult(
        source_id=source.id if source is not None else None,
        run_id=None,
        skipped=skipped,
        blocked=False,
        requests=0,
        found=0,
        after_filters=0,
        created=0,
        summaries=0,
        existing=0,
        job_ids=[],
        errors=[],
        message=f"{NAME}: {skipped}" if skipped else "",
    )


def _when(value: datetime) -> str:
    from zoneinfo import ZoneInfo

    local = value.astimezone(ZoneInfo(get_policies().connectors.timezone))
    return local.strftime("%d/%m a las %H:%M")


def _claim(session: Session, source: Source, started: datetime) -> bool:
    """Reserva la ejecución del día antes de salir a la red, con un `UPDATE` condicionado al
    `last_run_at` leído y un commit: otra ejecución a la vez (worker, «Buscar ahora», CLI) ve la
    reserva y no lanza una segunda ráfaga. Si el proceso muere a medias, el día ya cuenta."""
    previous = source.last_run_at
    condition = Source.last_run_at.is_(None) if previous is None else Source.last_run_at == previous
    claimed = session.execute(
        update(Source)
        .where(Source.id == source.id, condition)
        .values(last_run_at=started)
        .execution_options(synchronize_session=False)
    ).rowcount
    if not claimed:
        session.rollback()
        return False
    session.commit()  # visible ya para las demás sesiones
    session.refresh(source)
    return True


def run(
    session: Session,
    actor: str = "user",
    *,
    client: httpx.Client | None = None,
    sleep: Sleep = time.sleep,
    now: datetime | None = None,
) -> LinkedInPublicRunResult:
    """Ejecuta la búsqueda pública si está activada y le toca. Si no, no hace ninguna petición y
    devuelve `skipped` con el motivo. Nunca lanza por un fallo de LinkedIn: queda en `errors`."""
    source = _find_source(session)
    if not is_enabled(source):
        raise BrowsingNotAllowedError(
            "La búsqueda pública de LinkedIn está desactivada. Solo el usuario puede activarla, "
            "en la tarjeta de LinkedIn de la pantalla Plataformas."
        )
    assert source is not None
    policy = get_policies().linkedin_public
    now = now or utcnow()
    when = next_run_at(source, policy)
    if when is not None and now < when:
        blocked = _parse_dt(_config(source).get("blocked_at"))
        reason = (
            "LinkedIn la bloqueó hace poco"
            if blocked is not None and blocked + timedelta(days=policy.block_cooldown_days) == when
            else "ya se ejecutó hace menos de un día"
        )
        return _empty_result(source, f"{reason}; la próxima, a partir del {_when(when)}.")
    run_searches, _ignored = searches(session)
    if not run_searches:
        return _empty_result(
            source, "no hay búsquedas de LinkedIn que usar (revisa la plataforma LinkedIn)."
        )

    result = _empty_result(source)
    started = utcnow()
    if not _claim(session, source, started):
        return _empty_result(source, "ya hay otra ejecución en marcha o acaba de terminar.")
    fetch_detail = bool(_config(source).get("fetch_detail"))
    own_client = client is None
    http = client or make_client(policy.timeout_seconds)
    gate = _Gate(http, sleep, policy.delay_seconds)
    try:
        collected = _collect(session, gate, run_searches, fetch_detail, policy, result)
    finally:
        if own_client:
            http.close()
    result.requests = gate.requests
    result.errors.extend(collected.issues)
    if collected.blocked:
        result.blocked = True
        result.errors.append(Issue(code="blocked", message=collected.blocked))

    run_row = SourceRun(source_id=source.id, actor=actor, started_at=started, errors=[])
    with session.begin_nested():
        for card in collected.pending:
            _store(session, source, card, result)
        config = _config(source)
        if collected.blocked:
            config["blocked_at"] = utcnow().isoformat()
        source.config = config
        run_row.finished_at = utcnow()
        run_row.found, run_row.after_filters = result.found, result.after_filters
        run_row.created = result.created
        run_row.errors = [issue.model_dump() for issue in result.errors]
        session.add(run_row)
        session.flush()
    result.run_id = run_row.id
    result.message = _describe(result, policy)
    return result


def _describe(result: LinkedInPublicRunResult, policy: LinkedInPublicPolicy) -> str:
    noun = "oferta encontrada" if result.found == 1 else "ofertas encontradas"
    text = f"{NAME}: {result.found} {noun}, {result.after_filters} tras filtros, "
    text += f"{result.created} {'nueva' if result.created == 1 else 'nuevas'}"
    if result.summaries:
        text += f" ({result.summaries} como resumen)"
    if result.existing:
        text += f", {result.existing} ya {'estaba' if result.existing == 1 else 'estaban'}"
    if result.blocked:
        text += (
            f". LinkedIn cortó la búsqueda: no se vuelve a intentar en "
            f"{policy.block_cooldown_days} días"
        )
    elif result.errors:
        text += f"; {len(result.errors)} avisos"
    return text
