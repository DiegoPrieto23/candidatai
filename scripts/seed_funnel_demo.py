"""Genera ofertas FICTICIAS con su histórico de eventos para probar el dashboard del embudo.

Uso (desde la raíz del repo):
    uv run --directory backend python ../scripts/seed_funnel_demo.py [--jobs 1000] [--data-dir DIR]

Escribe en una BD aparte: por defecto `data/funnel-demo/` (nunca en tu `data/jobhunter.db`). Para
ver el dashboard con esos datos, arranca la API con `JH_DATA_DIR` apuntando a ese directorio
(relativo a la raíz del repo, como `--data-dir`):
    $env:JH_DATA_DIR = "data/funnel-demo"; uv run --directory backend jh serve      (PowerShell)

Se niega a sembrar una BD que ya tiene ofertas. Empresas y puestos inventados; ningún dato real.
Los eventos se registran con `events.record()`, como en la app: el histórico es siempre válido.
"""

import argparse
import os
import random
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import migrations
from app.core.config import REPO_ROOT, get_settings
from app.core.db import get_engine, session_scope
from app.models import Company, Job, JobExtraction, Source
from app.services import events

DEFAULT_DIR = REPO_ROOT / "data" / "funnel-demo"
WEEKS = 26
SOURCES = (
    ("greenhouse", "Greenhouse · Arnela Analytics"),
    ("lever", "Lever · Faro Logística"),
    ("email_alerts", "Alertas por correo"),
    ("browser_capture", "Botón «Enviar a Job Hunter»"),
    ("agent_browse", "Portal de empleo de prueba"),
)
TITLES = (
    "data engineer", "data analyst", "analytics engineer", "bi developer", "ml engineer",
    "data scientist", "backend developer", "python developer", "etl developer",
    "data architect", "product analyst", "mlops engineer",
)  # fmt: skip
DISCARD_REASONS = ("skills", "seniority", "location", "salary", "company", "other")
FILTERS = ("seniority", "years", "remote_mode", "location", "language", "title_keyword")


class _Path:
    """Registra los eventos de una oferta en orden, sin pasar de `now`."""

    def __init__(self, session: Session, job_id: int, start: datetime, now: datetime) -> None:
        self.session, self.job_id, self.at, self.now = session, job_id, start, now

    def step(self, kind: str, hours: float, payload: dict[str, object] | None = None) -> bool:
        when = self.at + timedelta(hours=hours)
        if when >= self.now:
            return False
        actor = "system" if kind in ("hard_filter_failed", "duplicate_detected") else "user"
        events.record(self.session, self.job_id, kind, actor, payload=payload, occurred_at=when)
        self.at = when
        return True


def _history(path: _Path, rng: random.Random) -> None:  # noqa: PLR0911 - un camino por rama
    r = rng.random
    if r() < 0.05:
        path.step("duplicate_detected", 1)
        return
    if r() < 0.1 or not path.step("extracted", rng.uniform(1, 24)):
        return  # se queda sin extraer
    if r() < 0.2:
        failures = [{"filter": f, "reason": "-"} for f in rng.sample(FILTERS, rng.randint(1, 2))]
        path.step("hard_filter_failed", 0.1, {"failures": failures})
        if r() > 0.1 or not path.step("reopened", rng.uniform(2, 72)):
            return
    if r() < 0.3:
        return  # pendiente de triaje
    if r() < 0.55:
        path.step("discarded", rng.uniform(1, 72), {"reason": rng.choice(DISCARD_REASONS)})
        return
    if not path.step("approved", rng.uniform(1, 72)) or r() < 0.2:
        return
    if not path.step("applied_manually", rng.uniform(4, 96)):
        return
    if r() < 0.45:
        if r() < 0.3:
            path.step(rng.choice(("withdrawn", "expired")), rng.uniform(240, 720))
        return  # sin respuesta
    wait = rng.uniform(12, 24 * 21)
    if r() < 0.5:
        path.step("rejected", wait)
        return
    if not path.step("reply_received", wait) or r() < 0.4:
        return
    if not path.step("interview_scheduled", rng.uniform(24, 168)) or r() < 0.6:
        if r() < 0.5:
            path.step("rejected", rng.uniform(72, 240))
        return
    if path.step("offer_received", rng.uniform(72, 336)):
        path.step("accepted" if r() < 0.5 else "withdrawn", rng.uniform(24, 120))


def seed(session: Session, jobs: int, now: datetime, rng_seed: int = 7) -> int:
    """Crea `jobs` ofertas ficticias vistas en las últimas `WEEKS` semanas con su histórico."""
    rng = random.Random(rng_seed)
    sources = [Source(kind=kind, name=name) for kind, name in SOURCES]
    session.add_all(sources)
    session.flush()
    for n in range(1, jobs + 1):
        company = Company(name=f"Empresa ficticia {n}", normalized_name=f"empresa ficticia {n}")
        session.add(company)
        session.flush()
        seen = now - timedelta(hours=rng.uniform(1, WEEKS * 7 * 24))
        title = rng.choice(TITLES)
        job = Job(
            source_id=rng.choice(sources).id,
            company_id=company.id,
            url=f"https://example.com/ficticia/{n}",
            title=title.title(),
            raw_text="Oferta ficticia para la demo del embudo.",
            fingerprint=f"funnel-demo-{n}",
            first_seen_at=seen,
        )
        session.add(job)
        session.flush()
        session.add(
            JobExtraction(job_id=job.id, schema_version=1, data={"title_normalized": title})
        )
        events.record(session, job.id, "found", "system", occurred_at=seen)
        _history(_Path(session, job.id, seen, now), rng)
    return jobs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jobs", type=int, default=1000)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args(argv)

    # Como `JH_DATA_DIR`: una ruta relativa es relativa a la raíz del repo.
    data_dir = args.data_dir if args.data_dir.is_absolute() else REPO_ROOT / args.data_dir
    os.environ["JH_DATA_DIR"] = str(data_dir.resolve())
    get_settings.cache_clear()
    get_engine.cache_clear()
    migrations.upgrade()
    with session_scope() as session:
        if session.scalar(select(func.count()).select_from(Job)):
            print(f"{data_dir} ya tiene ofertas: usa otro --data-dir o bórralo.")
            return 1
        created = seed(session, args.jobs, datetime.now(UTC))
    print(f"{created} ofertas ficticias creadas en {data_dir}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
