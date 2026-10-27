"""Ofertas «resumen» en `pending_detail` (fase 09b): la bandeja «Alertas» y su caducidad.

El prefiltro (título, ubicación y seniority del título contra `preferences`) se calcula al
listar, no se guarda: así no se desfasa al cambiar el perfil. No se llama al agente.
"""

from datetime import datetime, timedelta
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.engine import Row
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.models import Application, Company, Job
from app.models.base import utcnow
from app.services import platforms
from app.services import profile as profile_service
from app.services.events import record
from app.services.ingestion.prefilter import Prefilter
from app.services.pipeline import Actor, EventType, Stage


class AlertJob(BaseModel):
    job_id: int
    title: str
    company: str
    location: str | None
    platform: str | None
    platform_label: str | None
    url: str
    first_seen_at: datetime
    expires_at: datetime
    prefilter_passed: bool
    prefilter_reason: str | None
    risk_flags: list[str]


class AlertList(BaseModel):
    jobs: list[AlertJob]
    total: int
    passed: int  # cuántas pasan el prefiltro
    filters_applied: bool  # sin perfil no se filtra


class ExpireResult(BaseModel):
    expired: list[int]
    message: str


def _prefilter(session: Session) -> Prefilter:
    try:
        preferences = profile_service.current(session).profile.preferences
    except profile_service.ProfileNotFoundError:
        preferences = None
    return Prefilter(preferences, [])


def _pending_detail(session: Session) -> list[Row[Any]]:
    """Las ofertas resumen, con lo que enseña la lista (columnas sueltas, sin cargar objetos del
    ORM: puede haber miles)."""
    stmt = (
        select(
            Job.id,
            Job.title,
            Job.location_raw,
            Job.platform,
            Job.url,
            Job.first_seen_at,
            Job.risk_flags,
            Company.name.label("company"),
        )
        .join(Application, Application.job_id == Job.id)
        .join(Company, Company.id == Job.company_id)
        .where(Application.stage == Stage.PENDING_DETAIL.value)
    )
    return list(session.execute(stmt).all())


def list_alerts(session: Session) -> AlertList:
    """Ofertas en `pending_detail`: primero las que pasan el prefiltro y, dentro, las más
    recientes."""
    prefilter = _prefilter(session)
    days = get_policies().email_alerts.summary_expire_days
    jobs = []
    for job in _pending_detail(session):
        verdict = prefilter.check_summary(job.title, job.location_raw)
        jobs.append(
            AlertJob(
                job_id=job.id,
                title=job.title,
                company=job.company,
                location=job.location_raw,
                platform=job.platform,
                platform_label=platforms.PLATFORM_LABELS.get(job.platform or ""),
                url=job.url,
                first_seen_at=job.first_seen_at,
                expires_at=job.first_seen_at + timedelta(days=days),
                prefilter_passed=verdict.passed,
                prefilter_reason=verdict.reason,
                risk_flags=list(job.risk_flags or []),
            )
        )
    jobs.sort(key=lambda j: (not j.prefilter_passed, -j.first_seen_at.timestamp(), -j.job_id))
    return AlertList(
        jobs=jobs,
        total=len(jobs),
        passed=sum(j.prefilter_passed for j in jobs),
        filters_applied=prefilter.active,
    )


def expire_summaries(session: Session, now: datetime | None = None) -> ExpireResult:
    """Cierra con `expired` los resúmenes sin completar más antiguos que `summary_expire_days`."""
    now = now or utcnow()
    days = get_policies().email_alerts.summary_expire_days
    limit = now - timedelta(days=days)
    expired = []
    for job in _pending_detail(session):
        if job.first_seen_at < limit:
            record(
                session,
                job.id,
                EventType.EXPIRED,
                Actor.SYSTEM,
                {"reason": "summary_not_completed", "days": days},
                occurred_at=now,
            )
            expired.append(job.id)
    if expired:
        message = f"Resúmenes caducados (más de {days} días sin completar): {len(expired)}."
    else:
        message = "Ningún resumen caducado."
    return ExpireResult(expired=expired, message=message)
