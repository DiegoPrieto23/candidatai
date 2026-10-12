"""Plataformas para la búsqueda con el navegador del agente (fase 09b, ADR-016).

Una plataforma es una fuente `agent_browse`: búsquedas ya filtradas que el agente recorre con el
navegador del usuario (skill `search-jobs`). La app no navega: guarda la configuración, recibe
las ofertas por `add_job_from_text` y anota cada recorrido en `source_runs`.

LinkedIn es especial: el agente nunca puede activar su navegación. Solo el usuario, desde la UI y
confirmando el riesgo para su cuenta. Estas reglas viven aquí y no en el skill (ADR-012).
"""

from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.models import Source, SourceRun
from app.models.base import utcnow
from app.schemas.sources import (
    AgentBrowseSource,
    BrowseAccess,
    Issue,
    SourceRunSummary,
    SourceView,
)
from app.services import platforms
from app.services.ingestion.service import SourceNotFoundError, get_source

KIND = "agent_browse"
LINKEDIN = "linkedin"
# Margen para relojes algo desincronizados al anotar un recorrido.
_FUTURE_TOLERANCE_SECONDS = 300


class BrowsingNotAllowedError(ValueError):
    """La plataforma no tiene activada la búsqueda con navegador (o es LinkedIn y la pide el
    agente)."""


class SaveSourceResult(BaseModel):
    source_id: int
    created: bool
    allow_agent_browsing: bool  # el valor que ha quedado guardado
    message: str


class RecordRunResult(BaseModel):
    ok: bool
    run_id: int


def is_linkedin(data: AgentBrowseSource | dict[str, Any]) -> bool:
    """LinkedIn por su id o por cualquiera de sus búsquedas: no vale `platform: "otra"` con URLs
    de linkedin.com."""
    if isinstance(data, AgentBrowseSource):
        platform, urls = data.platform, data.search_urls
    else:
        platform, urls = str(data.get("platform") or ""), list(data.get("search_urls") or [])
    if platform == LINKEDIN:
        return True
    return any(platforms.platform_of_host(_host(url)) == LINKEDIN for url in urls)


def _host(url: str) -> str | None:
    try:
        return urlsplit(url).hostname
    except ValueError:
        return None


def _normalized(name: str) -> str:
    return " ".join(name.split()).casefold()


def _find_by_name(session: Session, name: str) -> Source | None:
    target = _normalized(name)
    for source in session.scalars(select(Source).where(Source.kind == KIND)):
        if _normalized(source.name) == target:
            return source
    return None


def browse_source(session: Session, source_id: int) -> Source:
    """Fuente `agent_browse` con ese id, o error `not_found` / `invalid_request`."""
    source = session.get(Source, source_id)
    if source is None:
        raise SourceNotFoundError(f"No existe la fuente {source_id}.")
    if source.kind != KIND:
        raise ValueError(
            f"La fuente {source_id} no es una plataforma de búsqueda con navegador "
            f'(es de tipo `{source.kind}`). Usa una de `list_sources(kind="agent_browse")`.'
        )
    return source


def require_browsing(source: Source) -> None:
    """Rechaza lo que llega de un recorrido por una plataforma que no lo tiene activado."""
    if not (source.config or {}).get("allow_agent_browsing"):
        where = "LinkedIn" if is_linkedin(source.config or {}) else f"«{source.name}»"
        raise BrowsingNotAllowedError(
            f"La búsqueda con navegador no está activada en {where}. Solo el usuario puede "
            "activarla, en la pantalla Plataformas."
        )


def source_for_job(
    session: Session, source_id: int, url: str | None, platform: str | None = None
) -> Source:
    """La plataforma por la que entra una oferta encontrada navegando. Tiene que tener la
    navegación activada, y una oferta de LinkedIn (por su URL, también `lnkd.in`, o por
    `platform`) solo entra por la plataforma LinkedIn."""
    source = browse_source(session, source_id)
    require_browsing(source)
    linkedin_job = platform == LINKEDIN or (
        bool(url) and platforms.platform_of_host(_host((url or "").strip())) == LINKEDIN
    )
    if linkedin_job and not is_linkedin(source.config or {}):
        raise BrowsingNotAllowedError(
            f"Esa oferta es de LinkedIn y la plataforma «{source.name}» no lo es. Las ofertas de "
            "LinkedIn solo entran por la plataforma LinkedIn, si el usuario la ha activado."
        )
    return source


def _bare_host(url: str) -> str:
    host = (_host(url) or "").lower().rstrip(".")
    return host.removeprefix("www.")


def _check_domains(data: AgentBrowseSource) -> None:
    """Las búsquedas son de la plataforma: de su dominio si la app la conoce y, si no, todas del
    mismo sitio. Así una URL sugerida por el contenido de una página no se cuela como búsqueda."""
    known = data.platform in platforms.PLATFORM_LABELS
    for url in data.search_urls:
        of_url = platforms.platform_of_host(_host(url))
        if known and of_url != data.platform:
            label = platforms.PLATFORM_LABELS[data.platform]
            raise ValueError(f"La búsqueda «{url}» no es de {label}: guárdala en su plataforma.")
        if not known and of_url is not None:
            raise ValueError(
                f"La búsqueda «{url}» es de {platforms.PLATFORM_LABELS[of_url]}: usa "
                f"`platform: {of_url}`."
            )
    if not known and len({_bare_host(url) for url in data.search_urls}) > 1:
        raise ValueError(
            "Las búsquedas de una plataforma deben ser todas del mismo sitio: guarda cada sitio "
            "como una plataforma distinta."
        )


def add_platform(session: Session, data: AgentBrowseSource) -> SaveSourceResult:
    """Alta desde la UI («Añadir plataforma»). A diferencia de `save_source`, no actualiza una
    existente con el mismo nombre. LinkedIn queda siempre desactivada: se activa después en la
    misma pantalla, aceptando el riesgo para la cuenta (ADR-016)."""
    from app.services.ingestion.service import SourceExistsError

    if (existing := _find_by_name(session, data.name)) is not None:
        raise SourceExistsError(
            f"Ya hay una plataforma «{existing.name}»: cambia el nombre o edita la existente."
        )
    if is_linkedin(data):
        data = data.model_copy(update={"allow_agent_browsing": False})
    return save_source(session, data)


def save_source(session: Session, data: AgentBrowseSource) -> SaveSourceResult:
    """Crea o actualiza (por `name`) una plataforma. Nunca activa la navegación en LinkedIn; si el
    usuario ya la activó, se conserva."""
    linkedin = is_linkedin(data)
    if linkedin and data.allow_agent_browsing:
        raise BrowsingNotAllowedError(
            "El agente no puede activar la búsqueda con navegador en LinkedIn: guárdala con "
            "`allow_agent_browsing: false`. Solo el usuario puede activarla, en la pantalla "
            "Plataformas, asumiendo el riesgo para su cuenta."
        )
    if linkedin and data.platform != LINKEDIN:
        data = data.model_copy(update={"platform": LINKEDIN})
    _check_domains(data)

    existing = _find_by_name(session, data.name)
    if existing is not None and is_linkedin(existing.config or {}) and not linkedin:
        raise ValueError(
            f"«{existing.name}» es la plataforma LinkedIn y no puede pasar a ser otra: guarda la "
            "nueva con otro nombre."
        )
    allow = not linkedin if data.allow_agent_browsing is None else data.allow_agent_browsing
    kept = False
    if existing is not None and linkedin and (existing.config or {}).get("allow_agent_browsing"):
        allow, kept = True, True  # lo activó el usuario: el agente no lo desactiva

    config = data.model_dump(exclude={"name"})
    config["allow_agent_browsing"] = allow
    if config["max_offers"] is None:
        config["max_offers"] = get_policies().agent_browse.default_max_offers
    name = " ".join(data.name.split())

    if existing is None:
        source = Source(kind=KIND, name=name, config=config, active=True)
        session.add(source)
        session.flush()
        message = f"Plataforma «{name}» guardada (id {source.id})."
    else:
        source = existing
        source.name = name
        source.config = config
        session.flush()
        message = f"Plataforma «{name}» actualizada (id {source.id})."
    if kept:
        message += " La búsqueda con navegador sigue activada: la activó el usuario."
    elif linkedin:
        message += (
            " La búsqueda con navegador queda desactivada: solo el usuario puede activarla en "
            "la pantalla Plataformas."
        )
    return SaveSourceResult(
        source_id=source.id, created=existing is None, allow_agent_browsing=allow, message=message
    )


def record_run(session: Session, source_id: int, summary: SourceRunSummary) -> RecordRunResult:
    """Anota un recorrido del agente (actor `agent`) y avanza `last_run_at`."""
    source = browse_source(session, source_id)
    require_browsing(source)
    now = utcnow()
    finished = summary.finished_at or now
    started = summary.started_at or finished
    for value in (started, finished):
        if (value - now).total_seconds() > _FUTURE_TOLERANCE_SECONDS:
            raise ValueError("Las fechas del recorrido no pueden estar en el futuro.")
    run = SourceRun(
        source_id=source.id,
        actor="agent",
        started_at=started,
        finished_at=finished,
        found=summary.found,
        after_filters=summary.created + summary.existing,
        created=summary.created,
        errors=[
            Issue(code=i.code, message=i.message).model_dump(exclude_none=True)
            for i in summary.incidents
        ],
    )
    session.add(run)
    if source.last_run_at is None or source.last_run_at < finished:
        source.last_run_at = finished
    session.flush()
    return RecordRunResult(ok=True, run_id=run.id)


def update_settings(
    session: Session,
    source_id: int,
    *,
    allow_agent_browsing: bool | None = None,
    priority: int | None = None,
    access: BrowseAccess | None = None,
    confirm_risk: bool = False,
) -> SourceView:
    """Cambios del usuario desde la UI. Activar LinkedIn exige `confirm_risk`."""
    source = browse_source(session, source_id)
    config = dict(source.config or {})
    enabling = allow_agent_browsing and not config.get("allow_agent_browsing")
    if enabling and is_linkedin(config) and not confirm_risk:
        raise BrowsingNotAllowedError(
            "Activar la búsqueda con navegador en LinkedIn requiere confirmar el riesgo "
            "para tu cuenta (`confirm_risk: true`)."
        )
    if allow_agent_browsing is not None:
        config["allow_agent_browsing"] = allow_agent_browsing
    if priority is not None:
        config["priority"] = priority
    if access is not None:
        config["access"] = access
    # Valida el resultado con el mismo esquema que `save_source`.
    AgentBrowseSource.model_validate({"name": source.name, **config})
    source.config = config
    session.flush()
    return get_source(session, source.id)
