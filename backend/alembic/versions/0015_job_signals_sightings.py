"""señales de oferta y publicaciones vistas

`jobs.signals` (observaciones que no son riesgo de inyección: posible cierre, republicada…) y la
tabla `job_sightings` (cada publicación vista de una oferta), rellenada con una fila por oferta
existente: su primera publicación, con el canal y la referencia de `services/reposts.py` (copiados
aquí, como eran en esta versión, para que la migración no cambie si el servicio cambia).

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-12 10:00:00

"""

import re
from collections.abc import Sequence
from urllib.parse import parse_qs, parse_qsl, urlencode, urlsplit

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_ID_PARAMS = frozenset({"gh_jid", "jobid", "job_id", "jid", "id", "jk", "vjk", "currentjobid"})
_PLATFORM_ID = {
    "infojobs": re.compile(r"/of-i([0-9a-f]{20,40})(?:/|$)", re.IGNORECASE),
    "tecnoempleo": re.compile(r"/rf-([0-9a-f]{10,40})(?:/|$)", re.IGNORECASE),
    "linkedin": re.compile(r"/jobs/view/(?:[^/]*?-)?(\d{6,20})(?:/|$)"),
}
_INDEED_HOST = re.compile(r"(?:^|\.)indeed\.(?:com|[a-z]{2}|co\.[a-z]{2}|com\.[a-z]{2})$")


def _host(url: str | None) -> str:
    try:
        host = urlsplit((url or "").strip()).hostname or ""
    except ValueError:
        return ""
    return host.lower().rstrip(".").removeprefix("www.")


def _platform_of_host(host: str) -> str | None:
    for platform, domain in (
        ("linkedin", "linkedin.com"),
        ("linkedin", "lnkd.in"),
        ("infojobs", "infojobs.net"),
        ("tecnoempleo", "tecnoempleo.com"),
    ):
        if host == domain or host.endswith("." + domain):
            return platform
    return "indeed" if _INDEED_HOST.search(host) else None


def _platform_id(url: str | None) -> str | None:
    host = _host(url)
    platform = _platform_of_host(host)
    if platform is None or not url:
        return None
    parts = urlsplit(url.strip())
    query = parse_qs(parts.query)
    if platform == "indeed":
        for key in ("jk", "vjk"):
            value = query.get(key, [""])[0]
            if re.fullmatch(r"[0-9a-fA-F]{16}", value):
                return value.lower()
        return None
    match = _PLATFORM_ID[platform].search(parts.path)
    if match:
        return match.group(1).lower()
    current = query.get("currentJobId", [""])[0] if platform == "linkedin" else ""
    return current if re.fullmatch(r"\d{6,20}", current) else None


def channel_of(url: str | None, platform: str | None) -> str | None:
    if platform:
        return platform
    host = _host(url)
    return _platform_of_host(host) or host or None


def ref_of(url: str | None, platform: str | None, external_id: str | None) -> str | None:
    if (pid := _platform_id(url)) is not None:
        return pid
    if external_id:
        return external_id[:2000]
    host = _host(url)
    if host and url:
        parts = urlsplit(url.strip())
        ids = [(k, v) for k, v in parse_qsl(parts.query) if k.lower() in _ID_PARAMS]
        query = f"?{urlencode(sorted(ids))}" if ids else ""
        return f"{host}{parts.path.rstrip('/')}{query}"[:2000]
    return None


def upgrade() -> None:
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("signals", sa.JSON(), server_default=sa.text("'{}'"), nullable=False)
        )
    sightings = op.create_table(
        "job_sightings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(length=200), nullable=False),
        sa.Column("ref", sa.String(length=2000), nullable=False),
        sa.Column("seen_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], name=op.f("fk_job_sightings_job_id_jobs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_sightings")),
        sa.UniqueConstraint("job_id", "channel", "ref", name=op.f("uq_job_sightings_job_id")),
    )
    with op.batch_alter_table("job_sightings", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_job_sightings_job_id"), ["job_id"], unique=False)

    # Con tipos (no `sa.text`): así `first_seen_at` llega como `datetime`, no como texto.
    jobs_table = sa.table(
        "jobs",
        sa.column("id", sa.Integer()),
        sa.column("url", sa.String()),
        sa.column("platform", sa.String()),
        sa.column("external_id", sa.String()),
        sa.column("first_seen_at", sa.DateTime()),
    )
    jobs = op.get_bind().execute(sa.select(jobs_table))
    rows = []
    for job_id, url, platform, external_id, first_seen_at in jobs:
        channel = channel_of(url, platform)
        ref = ref_of(url, platform, external_id)
        if channel and ref:
            rows.append(
                {"job_id": job_id, "channel": channel, "ref": ref, "seen_at": first_seen_at}
            )
    if rows:
        op.bulk_insert(sightings, rows)


def downgrade() -> None:
    with op.batch_alter_table("job_sightings", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_job_sightings_job_id"))
    op.drop_table("job_sightings")
    with op.batch_alter_table("jobs", schema=None) as batch_op:
        batch_op.drop_column("signals")
