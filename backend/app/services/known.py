"""¿Ya tengo estas ofertas? Comprobación de solo lectura antes de abrirlas (`check_known`).

El agente que recorre un portal lee los resultados de una página y, antes de abrir ninguna oferta,
pregunta por el lote. Cada elemento se resuelve en este orden, el mismo que sigue `store_job` al
dar de alta:

1. **Id de plataforma** (el dado o el que se deduce de la URL): `known`.
2. **URL**, comparada como publicación (`reposts.ref_of`: sin esquema, fragmento ni parámetros de
   seguimiento) o, si no, tal cual: `known`.
3. **Huella** (empresa + título + ubicación): `reopen_candidate` si la cerró la empresa o caducó
   hace más de `dedup.reopen_after_days` (`store_job` la dará de alta como reapertura); si no
   (viva, cerrada hace poco o cerrada por ti), `same_offer`.
4. **Título casi igual** de la misma empresa (`ingest.fuzzy_original`, `matched_by: fuzzy_title`):
   igual que la huella. `store_job` tampoco crea oferta para él.
5. Nada de lo anterior: `new`.

No escribe nada: ni publicaciones, ni eventos, ni ofertas.
"""

from datetime import datetime, timedelta
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.models import Application, Company, Job, JobSighting
from app.models.base import utcnow
from app.services import platforms, reposts
from app.services.ingest import (
    closed_by_company,
    find_by_platform,
    fuzzy_original,
    original_of,
)
from app.services.normalize import fingerprint, normalize_company
from app.services.pipeline import Stage

MAX_ITEMS = 100

KnownStatus = Literal["new", "known", "same_offer", "reopen_candidate"]
MatchedBy = Literal["platform_id", "url", "fingerprint", "fuzzy_title"]


class KnownItem(BaseModel):
    """Un resultado de la lista de un portal, con lo que se ve sin abrir la oferta."""

    url: str = Field(min_length=1, max_length=2000, description="URL de la oferta.")
    title: str | None = Field(default=None, max_length=500)
    company: str | None = Field(default=None, max_length=300)
    location: str | None = Field(default=None, max_length=300)
    platform: str | None = Field(default=None, max_length=100)
    external_id: str | None = Field(default=None, max_length=300)


class KnownResult(BaseModel):
    url: str
    status: KnownStatus
    matched_by: MatchedBy | None = None
    job_id: int | None = None
    stage: str | None = None
    closed_by: str | None = None
    closed_at: datetime | None = None


class KnownCounts(BaseModel):
    new: int = 0
    known: int = 0
    same_offer: int = 0
    reopen_candidate: int = 0


class KnownList(BaseModel):
    items: list[KnownResult]
    counts: KnownCounts


def _identity(item: KnownItem) -> tuple[str | None, str | None]:
    """`platform` y `external_id` del elemento: los dados o los que dice su URL. Con `platform` y
    sin id, el id se saca de la URL si es de esa plataforma (al dar de alta, igual)."""
    platform = item.platform or None
    external_id = item.external_id or None
    pid = platforms.detect(item.url)
    if external_id is None:
        if pid is not None and platform in (None, pid.platform):
            return pid.platform, pid.external_id
        return platform, None
    if platform is None:
        # Como al dar de alta un texto pegado: la de la URL si trae ese id o, si no, la del host.
        if pid is not None and pid.external_id == external_id:
            platform = pid.platform
        else:
            platform = platforms.platform_of_host(urlsplit(item.url).hostname)
    return platform, external_id


def _by_url(
    session: Session, url: str, platform: str | None, external_id: str | None
) -> Job | None:
    channel = reposts.channel_of(url, platform)
    ref = reposts.ref_of(url, platform, external_id)
    if channel and ref:
        job_id = session.scalars(
            select(JobSighting.job_id)
            .where(JobSighting.channel == channel, JobSighting.ref == ref)
            .order_by(JobSighting.job_id.desc())
            .limit(1)
        ).first()
        if job_id is not None:
            return session.get(Job, job_id)
    return session.scalars(
        select(Job).where(Job.url == url.strip()).order_by(Job.id.desc()).limit(1)
    ).first()


def _by_fingerprint(session: Session, item: KnownItem) -> Job | None:
    title = " ".join((item.title or "").split())
    company = " ".join((item.company or "").split())
    if not title or not company or not normalize_company(company):
        return None
    location = " ".join(item.location.split()) if item.location else None
    fp = fingerprint(company, title, location)
    job = session.scalars(
        select(Job).where(Job.fingerprint == fp).order_by(Job.id.desc()).limit(1)
    ).first()
    # Una duplicada de antes lleva a su original, como al dar de alta.
    return original_of(session, job) if job is not None else None


def _by_fuzzy_title(
    session: Session, item: KnownItem, platform: str | None, external_id: str | None, now: datetime
) -> Job | None:
    """La misma vacante con un título casi igual, como la reconoce `store_job` al dar de alta.

    Aquí no se sabe de qué fuente viene el resultado, solo su plataforma: un conector sin
    plataforma reconocible (que `store_job` distingue por su fuente) no pasa por aquí, porque lo
    que se comprueba antes de abrir son los resultados de un portal."""
    title = " ".join((item.title or "").split())
    company = " ".join((item.company or "").split())
    normalized = normalize_company(company) if company else ""
    if not title or not normalized:
        return None
    company_id = session.scalars(
        select(Company.id).where(Company.normalized_name == normalized).limit(1)
    ).first()
    if company_id is None:
        return None
    return fuzzy_original(
        session,
        company_id,
        title,
        now,
        skip_platform=platform if external_id else None,
    )


def _result(
    item: KnownItem,
    status: KnownStatus,
    matched_by: MatchedBy,
    job: Job,
    app: Application | None,
) -> KnownResult:
    closed = app is not None and app.stage == Stage.CLOSED
    return KnownResult(
        url=item.url,
        status=status,
        matched_by=matched_by,
        job_id=job.id,
        stage=app.stage if app else None,
        closed_by=app.closed_by if closed and app else None,
        closed_at=app.closed_at if closed and app else None,
    )


def _check_one(
    session: Session, item: KnownItem, now: datetime, reopen_before: datetime
) -> KnownResult:
    platform, external_id = _identity(item)
    if platform and external_id:
        job = find_by_platform(session, platform, external_id)
        if job is not None:
            return _result(item, "known", "platform_id", job, session.get(Application, job.id))
    job = _by_url(session, item.url, platform, external_id)
    if job is not None:
        return _result(item, "known", "url", job, session.get(Application, job.id))
    matched_by: MatchedBy = "fingerprint"
    job = _by_fingerprint(session, item)
    if job is None:
        job = _by_fuzzy_title(session, item, platform, external_id, now)
        matched_by = "fuzzy_title"
    if job is None:
        return KnownResult(url=item.url, status="new")
    app = session.get(Application, job.id)
    reopen = (
        app is not None
        and app.stage == Stage.CLOSED
        and app.closed_at is not None
        and app.closed_at < reopen_before
        # Solo lo que `store_job` daría de alta como reapertura: la cerró la empresa o caducó.
        and closed_by_company(session, job.id, app.closed_by) is True
    )
    return _result(item, "reopen_candidate" if reopen else "same_offer", matched_by, job, app)


def check_known(session: Session, items: list[KnownItem], now: datetime | None = None) -> KnownList:
    """Estado de cada elemento, en el mismo orden. Solo lee."""
    now = now or utcnow()
    reopen_before = now - timedelta(days=get_policies().dedup.reopen_after_days)
    results = [_check_one(session, item, now, reopen_before) for item in items]
    counts = KnownCounts()
    for result in results:
        setattr(counts, result.status, getattr(counts, result.status) + 1)
    return KnownList(items=results, counts=counts)
