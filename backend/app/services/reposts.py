"""Ofertas republicadas (fase 16): la misma oferta publicada varias veces en el mismo canal.

Cada publicación vista queda en `job_sightings`: la primera al dar de alta la oferta y las
siguientes cuando reaparece con otro id o URL (la huella la reconoce como la misma, o es una
oferta nueva con la misma empresa y título). Una oferta está **republicada** cuando, en los
últimos `reposts.window_days` días, el mismo canal ha mostrado publicaciones distintas de la
misma empresa con el mismo título normalizado (también traducido con `config/title_aliases.yaml`)
y la misma ubicación en al menos `reposts.min_count` días distintos. Se recalcula al ver una
publicación nueva: una señal antigua no caduca sola cuando sus fechas salen de la ventana.

- Varias publicaciones el mismo día: suelen ser varias ubicaciones, no cuenta.
- La misma oferta en varios portales (InfoJobs e Indeed): no es republicar, no cuenta.

Es una observación, no un veredicto: la UI enseña «Republicada ×N» con las fechas.

`stale_repost` (fase 25.3, oferta dudosa) mira el mismo grupo con **todo** el historial, sin
ventana, en el canal con más días: al menos `doubtful.stale_repost_min_count` días con publicación
nueva, o al menos `doubtful.stale_repost_min_span_days` días entre la primera y la última de ese
canal. Una vacante nueva con la misma empresa, título y ciudad un año después también cuenta: el
código no las distingue.
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.models import Job, JobSighting
from app.models.base import utcnow
from app.services import platforms
from app.services.normalize import normalize_location, normalize_title, translate_title
from app.services.signals import RepostSignal, StaleRepostSignal, set_signal

MAX_REF = 2000
# Parámetros de URL que identifican una oferta (no de seguimiento).
ID_PARAMS = frozenset({"gh_jid", "jobid", "job_id", "jid", "id", "jk", "vjk", "currentjobid"})


def _host(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlsplit(url.strip()).hostname
    except ValueError:
        return None
    host = (host or "").lower().rstrip(".")
    return host.removeprefix("www.") or None


def channel_of(url: str | None, platform: str | None) -> str | None:
    """Dónde se publicó: la plataforma (`infojobs`…) o, si no se reconoce, el dominio."""
    if platform:
        return platform
    host = _host(url)
    return platforms.platform_of_host(host) or host


def ref_of(url: str | None, platform: str | None, external_id: str | None) -> str | None:
    """Qué publicación concreta: el id de la plataforma si la URL lo trae, el id que da la fuente
    (los conectores: el `absolute_url` de Greenhouse suele ser `…/careers?gh_jid=77`) o, si no, la
    URL sin esquema ni fragmento, y de los parámetros solo los que identifican la oferta (el resto
    suele ser de seguimiento)."""
    pid = platforms.detect(url)
    if pid is not None:
        return pid.external_id
    if external_id:
        return external_id[:MAX_REF]
    host = _host(url)
    if host and url:
        parts = urlsplit(url.strip())
        ids = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() in ID_PARAMS]
        query = f"?{urlencode(sorted(ids))}" if ids else ""
        return f"{host}{parts.path.rstrip('/')}{query}"[:MAX_REF]
    return None


def title_key(title: str) -> str:
    """Título comparable: normalizado y con los puestos en inglés («ingeniero de datos» ->
    «data engineer»)."""
    return " ".join(translate_title(normalize_title(title)).split())


def note_sighting(
    session: Session,
    job: Job,
    *,
    url: str | None,
    platform: str | None,
    external_id: str | None,
    seen_at: datetime | None = None,
) -> bool:
    """Anota una publicación de `job`. Si es nueva (otro canal o ref), recalcula `reposted` en
    las ofertas de su grupo. Devuelve si era nueva."""
    channel = channel_of(url, platform)
    ref = ref_of(url, platform, external_id)
    if not channel or not ref:
        return False
    exists = session.scalars(
        select(JobSighting.id)
        .where(JobSighting.job_id == job.id, JobSighting.channel == channel, JobSighting.ref == ref)
        .limit(1)
    ).first()
    if exists is not None:
        return False
    session.add(JobSighting(job_id=job.id, channel=channel, ref=ref, seen_at=seen_at or utcnow()))
    session.flush()
    refresh(session, job)
    return True


def _local_date(moment: datetime, zone: ZoneInfo) -> date:
    return moment.astimezone(zone).date()


def compute(
    session: Session, job: Job, now: datetime | None = None, group: list[Job] | None = None
) -> RepostSignal | None:
    """`reposted` del grupo de `job` (misma empresa y `title_key`), o `None` si no lo está."""
    policy = get_policies().reposts
    zone = ZoneInfo(get_policies().calendar.timezone)
    since = (now or utcnow()) - timedelta(days=policy.window_days)
    group = group if group is not None else _group(session, job)
    rows = session.execute(
        select(JobSighting.channel, JobSighting.ref, JobSighting.seen_at).where(
            JobSighting.job_id.in_([j.id for j in group]), JobSighting.seen_at >= since
        )
    ).all()
    # Por canal: la primera vez que se vio cada publicación, y los días distintos de esas fechas.
    first_seen: dict[str, dict[str, datetime]] = defaultdict(dict)
    for channel, ref, seen_at in rows:
        known = first_seen[channel].get(ref)
        if known is None or seen_at < known:
            first_seen[channel][ref] = seen_at
    best: tuple[int, date, str, list[date]] | None = None
    for channel, refs in first_seen.items():
        days = sorted({_local_date(moment, zone) for moment in refs.values()})
        candidate = (len(days), days[-1], channel, days)
        if best is None or candidate[:2] > best[:2]:
            best = candidate
    if best is None or best[0] < policy.min_count:
        return None
    count, _last, channel, days = best
    return RepostSignal(count=count, dates=days, channel=channel, window_days=policy.window_days)


def compute_stale(
    session: Session, job: Job, group: list[Job] | None = None
) -> StaleRepostSignal | None:
    """`stale_repost` del grupo de `job`, con todo su historial de publicaciones."""
    policy = get_policies().doubtful
    zone = ZoneInfo(get_policies().calendar.timezone)
    group = group if group is not None else _group(session, job)
    rows = session.execute(
        select(JobSighting.channel, JobSighting.ref, JobSighting.seen_at).where(
            JobSighting.job_id.in_([j.id for j in group])
        )
    ).all()
    if not rows:
        return None
    first_seen: dict[str, dict[str, datetime]] = defaultdict(dict)
    for channel, ref, seen_at in rows:
        known = first_seen[channel].get(ref)
        if known is None or seen_at < known:
            first_seen[channel][ref] = seen_at
    count, channel = max(
        (len({_local_date(m, zone) for m in refs.values()}), channel)
        for channel, refs in first_seen.items()
    )
    # El intervalo, solo en ese canal: la misma oferta en otro portal semanas después no es
    # republicarla (como en `reposted`). Con una sola publicación en él no hay intervalo.
    moments = list(first_seen[channel].values())
    first, last = _local_date(min(moments), zone), _local_date(max(moments), zone)
    span = (last - first).days
    if count < policy.stale_repost_min_count and span < policy.stale_repost_min_span_days:
        return None
    return StaleRepostSignal(
        count=count, channel=channel, first_seen=first, last_seen=last, span_days=span
    )


def _group(session: Session, job: Job) -> list[Job]:
    """Misma empresa, mismo título comparable y misma ubicación (como la huella): la misma oferta
    en dos ciudades, publicada en días distintos, no es una republicación."""
    key = (title_key(job.title), normalize_location(job.location_raw))
    same_company = session.scalars(select(Job).where(Job.company_id == job.company_id))
    return [
        j
        for j in same_company
        if j.id == job.id or (title_key(j.title), normalize_location(j.location_raw)) == key
    ]


def refresh(session: Session, job: Job, now: datetime | None = None) -> RepostSignal | None:
    """Recalcula `reposted` y `stale_repost` y los escribe en todas las ofertas del grupo."""
    group = _group(session, job)
    signal = compute(session, job, now, group)
    stale = compute_stale(session, job, group)
    for member in group:
        set_signal(member, "reposted", signal)
        set_signal(member, "stale_repost", stale)
    session.flush()
    return signal
