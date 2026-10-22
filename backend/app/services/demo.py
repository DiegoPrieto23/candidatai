"""Modo demo (fase 12.1): `cai demo seed` crea una carpeta de datos con una búsqueda ficticia.

Todo pasa por los servicios de siempre (alta, extracción, filtros, score, eventos de usuario, hitos
y CVs), así que la demo cumple las mismas reglas que los datos reales. Lo único propio de la demo
es el reloj: los servicios fechan «ahora» lo automático (alta, extracción, score), y después se
reparte en las 8 semanas anteriores y se recalcula la proyección.

Determinista: el catálogo (`demo/seed/`) y una semilla fija deciden ofertas, fuentes y destinos.
Solo cambian las fechas, que son relativas al día en que se ejecuta.

Dos idiomas (fase 23.5b): `es`, la candidata de Galicia (`demo/`), y `en`, una candidata de
Dublín (`demo/en/`, misma estructura). Lo que escribe la demo (ofertas, notas, hitos, nombres de
las fuentes) sale del catálogo de su idioma; los mensajes del servidor siguen en español.
"""

import contextlib
import os
import random
import re
import shutil
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from rapidfuzz import fuzz
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import migrations
from app.core.config import DEMO_MARKER, REPO_ROOT, get_settings
from app.core.db import get_engine, session_scope
from app.core.policies import get_policies
from app.models import Event, Job, Match, Source, Task
from app.models import JobExtraction as JobExtractionRow
from app.schemas.cv import CvContent, CvRenderOptions, CvVerification
from app.schemas.llm_io import JobExtraction
from app.schemas.sources import AgentBrowseSource, SourceInput
from app.services import capture as capture_service
from app.services import (
    container,
    demo_extras,
    events,
    extractions,
    ingest,
    network,
    pipeline,
    process,
    profile,
    tasks,
)
from app.services.demo_text import posting_text
from app.services.documents import pdf
from app.services.documents import service as cv_service
from app.services.evals import cv as cv_eval
from app.services.ingestion import browse
from app.services.ingestion import service as sources_service
from app.services.ingestion.email import service as email_service
from app.services.matching import service as matching
from app.services.normalize import fold, normalize_title

DEMO_DIR = REPO_ROOT / "demo"
LANGUAGES = ("es", "en")
SEED = 12
WEEKS = 8
AGENT_NAME = "demo-seed"  # extracciones y CVs: en la auditoría no parecen de un agente real

# Destino de cada oferta y cuántas hay de cada uno (60 en total).
FATES: tuple[tuple[str, int], ...] = (
    ("pending_extraction", 3),
    ("filtered", 8),
    ("pending_triage", 8),
    ("discarded", 14),
    ("approved", 3),
    ("expired", 1),
    ("applied", 7),
    ("rejected_after_apply", 6),
    ("replied", 2),
    ("interview_scheduled", 3),
    ("interview_rejected", 2),
    ("offer", 1),
)
# Las ofertas de `cvs.yaml` (CV verificado) y la de la instrucción oculta (`demo/jobs/02`).
FEATURED = 3


class DemoSeedError(ValueError):
    """La carpeta destino no se puede usar; el mensaje dice por qué."""


class DemoSummary(BaseModel):
    data_dir: str
    jobs: int
    events: int
    by_stage: dict[str, int]
    by_source: dict[str, int]
    cvs: int
    pdf_engine: str | None
    warnings: list[str]


# --- Carpeta destino ------------------------------------------------------------------------


def is_demo_dir(path: Path) -> bool:
    return (path / DEMO_MARKER).is_file()


def prepare_dir(target: Path, force: bool) -> None:
    """Deja `target` vacía con la marca de demo. Nunca toca una carpeta sin la marca."""
    target = target.resolve()
    data = (REPO_ROOT / "data").resolve()
    if target.is_relative_to(data) or data.is_relative_to(target):
        raise DemoSeedError(
            "La demo nunca se crea en `data/`, dentro de ella ni en una carpeta que la contenga: "
            "ahí van tus datos reales."
        )
    if target.exists():
        if not target.is_dir():
            raise DemoSeedError(f"«{target}» existe y no es una carpeta.")
        if any(target.iterdir()):
            if not is_demo_dir(target):
                raise DemoSeedError(
                    f"«{target}» ya existe y no es una demo (no tiene `{DEMO_MARKER}`): no se "
                    "toca. Elige otra carpeta con `--dir`."
                )
            if not force:
                raise DemoSeedError(
                    f"«{target}» ya tiene una demo. Usa `--force` para recrearla desde cero."
                )
            shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    (target / DEMO_MARKER).write_text(
        "Carpeta creada por `cai demo seed`: datos ficticios. Se puede borrar.\n", encoding="utf-8"
    )


@contextlib.contextmanager
def use_data_dir(target: Path, embeddings: bool = True) -> Iterator[None]:
    """Apunta la configuración (y la BD) a `target` mientras dura el bloque.

    Cambia `os.environ`: es para la CLI y los tests, no para usar entre hilos. Sin `embeddings`,
    el score no usa la similitud semántica (el seed no descarga modelos y es reproducible).
    """
    keys = ("CAI_DATA_DIR", "CAI_DB_URL", "CAI_EMBEDDINGS")
    saved = {key: os.environ.get(key) for key in keys}
    os.environ["CAI_DATA_DIR"] = str(target)
    os.environ["CAI_DB_URL"] = f"sqlite:///{(target / 'candidatai.db').as_posix()}"
    if not embeddings:
        os.environ["CAI_EMBEDDINGS"] = "off"
    get_settings.cache_clear()
    get_engine.cache_clear()
    try:
        yield
    finally:
        try:
            get_engine().dispose()
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            get_settings.cache_clear()
            get_engine.cache_clear()


# --- Catálogo ------------------------------------------------------------------------------


def demo_dir(lang: str = "es") -> Path:
    """Los datos de la demo en un idioma: `demo/` (español) o `demo/<idioma>/`."""
    if lang not in LANGUAGES:
        options = ", ".join(LANGUAGES)
        raise DemoSeedError(f"Idioma de la demo no válido: «{lang}». Usa uno de {options}.")
    return DEMO_DIR if lang == "es" else DEMO_DIR / lang


def load_catalog(lang: str = "es") -> dict[str, Any]:
    return yaml.safe_load((demo_dir(lang) / "seed" / "catalog.yaml").read_text(encoding="utf-8"))


def load_cv_jobs(lang: str = "es") -> list[dict[str, Any]]:
    return yaml.safe_load((demo_dir(lang) / "seed" / "cvs.yaml").read_text(encoding="utf-8"))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", fold(text)).strip("-")


@dataclass
class JobPlan:
    fate: str
    title: str
    company: str
    location: str
    text: str
    extraction: JobExtraction
    source_key: str
    offsets: dict[str, float] = field(default_factory=dict)  # días desde el alta
    found_at: datetime | None = None
    cv: dict[str, Any] | None = None
    reason: str | None = None
    note: str | None = None
    channel: str = "portal_manual"
    starts_in: float | None = None  # entrevista o prueba futura: días desde hoy
    hour: int = 10  # hora de Madrid de la entrevista
    job_id: int | None = None  # al escribirla


class _Planner:
    def __init__(self, catalog: dict[str, Any], rng: random.Random) -> None:
        self.catalog = catalog
        self.rng = rng
        self.used: dict[str, list[str]] = {}  # títulos normalizados ya usados por empresa
        self.roles = {
            fit: [r for r in catalog["roles"] if r["fit"] == fit]
            for fit in ("good", "weak", "filtered")
        }

    def _company(self, title: str) -> dict[str, Any]:
        """Una empresa sin otra oferta de título parecido: si no, la alta la daría por duplicada."""
        threshold = get_policies().dedup.fuzzy_title_threshold
        target = normalize_title(title)
        companies = list(self.catalog["companies"])
        self.rng.shuffle(companies)
        for company in companies:
            taken = self.used.setdefault(company["name"], [])
            if all(fuzz.token_set_ratio(target, other) < threshold for other in taken):
                taken.append(target)
                return company
        raise DemoSeedError(f"El catálogo no tiene empresas suficientes para «{title}».")

    def plan(self, fate: str, fit: str, filtered_location: bool = False) -> JobPlan:
        rng = self.rng
        role = rng.choice(self.roles[fit])
        title = rng.choice(role["variants"])
        company = self._company(title)
        place = rng.choice(self.catalog["locations"]["filtered" if filtered_location else "fits"])
        mode = rng.choice(place["modes"])
        must = rng.sample(role["must"], k=min(len(role["must"]), rng.choice((3, 4))))
        nice = rng.sample(role["nice"], k=min(len(role["nice"]), rng.choice((1, 2))))
        languages = role.get("languages") or (
            [self.catalog["second_language"]] if rng.random() < 0.4 else []
        )
        salary = None
        if rng.random() < 0.6:
            low = rng.choice((28, 30, 32, 34, 36, 38, 40)) * 1000
            salary = {"min": low, "max": low + 6000, "currency": "EUR", "period": "year"}
        extraction = JobExtraction(
            title_normalized=role["title"],
            seniority=rng.choice(role["seniority"]),
            years_experience_min=rng.choice(role["years"]),
            employment_type="full_time",
            remote_mode=mode,
            locations=[place["city"]],
            languages_required=languages,
            salary=salary,
            must_have_skills=must,
            nice_to_have_skills=[s for s in nice if s not in must],
            responsibilities=list(role["responsibilities"]),
            domain=company["sector"],
            posting_language=self.catalog["posting_language"],
            application_deadline=None,
            red_flags=[],
            injection_suspected=False,
        )
        text = posting_text(title, company["name"], company["sector"], place["city"], extraction)
        return JobPlan(
            fate=fate,
            title=title,
            company=company["name"],
            location=place["city"],
            text=text,
            extraction=extraction,
            source_key=self._source_for(company["name"]),
        )

    def _source_for(self, company: str) -> str:
        sources = self.catalog["sources"]
        for s in sources:
            if s.get("name") == company and self.rng.random() < 0.8:
                return s["kind"]
        plain = [s for s in sources if "name" not in s]
        return self.rng.choices([s["kind"] for s in plain], [s["weight"] for s in plain])[0]


def _featured(catalog: dict[str, Any], lang: str) -> list[JobPlan]:
    """Las ofertas fijas: dos con CV (`cvs.yaml`) y la de la instrucción oculta (`jobs/02`)."""
    plans = []
    for item in load_cv_jobs(lang):
        job = item["job"]
        text = (
            (REPO_ROOT / job["text_file"]).read_text(encoding="utf-8")
            if "text_file" in job
            else job["text"]
        )
        raw = (
            yaml.safe_load((REPO_ROOT / job["extraction_file"]).read_text(encoding="utf-8"))
            if "extraction_file" in job
            else job["extraction"]
        )
        plans.append(
            JobPlan(
                fate="cv_ready",
                title=job["title"],
                company=job["company"],
                location=job["location"],
                text=text,
                extraction=JobExtraction.model_validate(raw),
                source_key="manual_url",
                cv=item["content"],
            )
        )
    risky = catalog["risky_job"]
    plans.append(
        JobPlan(
            fate="pending_triage",
            title=risky["title"],
            company=risky["company"],
            location=risky["location"],
            text=(REPO_ROOT / risky["text_file"]).read_text(encoding="utf-8"),
            extraction=JobExtraction.model_validate_json(
                (REPO_ROOT / risky["extraction_file"]).read_text(encoding="utf-8")
            ),
            source_key="manual_text",
        )
    )
    return plans


def _u(rng: random.Random, low: float, high: float) -> float:
    return rng.uniform(low, high)


def _timeline(plan: JobPlan, rng: random.Random) -> None:
    """Días desde el alta de cada paso, y cuánto antes de hoy pudo darse de alta."""
    o: dict[str, float] = {}
    fate = plan.fate
    newest, oldest = 0.2, WEEKS * 7 - 0.5  # días antes de hoy
    if fate == "pending_extraction":
        oldest = 3
    elif fate == "pending_triage":
        oldest = 12
    elif fate in ("approved", "cv_ready"):
        o["triage"] = _u(rng, 0.2, 1.5)
        oldest = 10
    elif fate in ("filtered",):
        pass
    elif fate == "discarded":
        o["triage"] = _u(rng, 0.2, 3)
    elif fate == "expired":
        o["triage"] = _u(rng, 0.3, 2)
        o["end"] = o["triage"] + _u(rng, 18, 25)
    else:  # enviadas
        o["triage"] = _u(rng, 0.2, 2)
        o["applied"] = o["triage"] + _u(rng, 0.5, 3)
        plan.channel = rng.choice(("portal_manual", "ats_form", "email", "linkedin_manual"))
        if fate == "applied":
            oldest = 45
            if rng.random() < 0.35:
                o["followup"] = o["applied"] + _u(rng, 7, 10)
        elif fate == "rejected_after_apply":
            o["end"] = o["applied"] + _u(rng, 5, 20)
        else:
            o["reply"] = o["applied"] + _u(rng, 3, 10)
            if fate == "replied":
                plan.starts_in = _u(rng, 2, 9)  # prueba técnica con plazo
                o["milestone"] = o["reply"] + _u(rng, 0.1, 1)
            elif fate == "interview_scheduled":
                plan.starts_in = _u(rng, 1, 10)
                o["milestone"] = o["reply"] + _u(rng, 0.1, 1)
            else:
                o["milestone"] = o["reply"] + _u(rng, 0.1, 1)
                o["interview"] = o["milestone"] + _u(rng, 3, 7)
                o["end"] = o["interview"] + _u(rng, 2, 6)
    plan.hour = rng.choice((9, 10, 11, 12, 16, 17))
    span = max(o.values(), default=0.0)
    oldest = max(oldest, span + newest + 0.5)
    plan.offsets = o
    plan.found_at = None  # lo fija `build_plans` con `now`
    plan.offsets["age"] = _u(rng, span + newest, min(oldest, WEEKS * 7 - 0.5))


def build_plans(rng: random.Random, lang: str = "es") -> list[JobPlan]:
    catalog = load_catalog(lang)
    planner = _Planner(catalog, rng)
    plans = _featured(catalog, lang)
    for job in plans:
        planner.used.setdefault(job.company, []).append(normalize_title(job.title))
    remaining = dict(FATES)
    remaining["pending_triage"] -= 1  # la oferta con la instrucción oculta
    for fate, count in remaining.items():
        for i in range(count):
            if fate == "filtered":
                plan = (
                    planner.plan(fate, "filtered")
                    if i % 2 == 0
                    else planner.plan(fate, "good", filtered_location=True)
                )
            elif fate == "discarded":
                fit = "weak" if i % 2 == 0 else "good"
                plan = planner.plan(fate, fit)
                if fit == "weak":
                    plan.reason = "skills"
                else:
                    plan.reason = rng.choice(("salary", "company", "location", "other"))
                    if plan.reason == "other":
                        plan.note = rng.choice(catalog["discard_notes"])
            elif fate == "pending_triage":
                plan = planner.plan(fate, "weak" if i % 3 == 0 else "good")
            elif fate == "pending_extraction":
                plan = planner.plan(fate, rng.choice(("good", "weak")))
            else:
                plan = planner.plan(fate, "good")
            plans.append(plan)
    for plan in plans:
        _timeline(plan, rng)
    return plans


# --- Escritura -----------------------------------------------------------------------------


def _sources(session: Session, catalog: dict[str, Any]) -> dict[str, Source]:
    """Las fuentes de la demo, con el nombre del catálogo si lo da (`source_names`)."""
    found: dict[str, Source] = {}
    for spec in catalog["sources"]:
        kind = spec["kind"]
        if kind in ingest.SOURCE_NAMES:
            source = ingest._get_or_create_source(session, kind)  # noqa: SLF001
        elif kind == email_service.SOURCE_KIND:
            source = email_service.email_source(session)
        elif kind == capture_service.SOURCE_KIND:
            source = capture_service._source(session)  # noqa: SLF001
        else:
            view = sources_service.add_source(
                session, SourceInput(kind=kind, name=spec["name"], slug=spec["slug"])
            )
            # En pausa: el worker no intenta descargar un tablero que no existe.
            sources_service.set_active(session, view.id, False)
            source = session.get(Source, view.id)
            assert source is not None
        if kind in catalog.get("source_names", {}):
            source.name = catalog["source_names"][kind]
        found[kind] = source
    for spec in catalog.get("platforms", []):
        browse.add_platform(session, AgentBrowseSource.model_validate(spec))
    return found


def _retime(session: Session, job_id: int, found_at: datetime) -> None:
    """Lleva lo automático (alta, extracción, filtros, score) al día del alta."""
    rows = session.scalars(select(Event).where(Event.job_id == job_id).order_by(Event.id)).all()
    for i, event in enumerate(rows):
        when = found_at + timedelta(minutes=5 * i)
        event.occurred_at = when
        event.recorded_at = when
    created = found_at + timedelta(minutes=5)
    job = session.get(Job, job_id)
    assert job is not None
    job.first_seen_at = found_at
    job.posted_at = found_at - timedelta(days=2)
    for model in (JobExtractionRow, Match):
        session.execute(update(model).where(model.job_id == job_id).values(created_at=created))
    session.flush()
    pipeline.rebuild_projection(session, job_id)


def _user(session: Session, job_id: int, type_: str, when: datetime, **kwargs: Any) -> None:
    events.add_user_event(session, job_id, type_, occurred_at=when, **kwargs)


def _story(
    session: Session,
    plan: JobPlan,
    job_id: int,
    now: datetime,
    contact: dict[str, Any],
    texts: dict[str, str],
) -> None:
    """Los pasos del usuario (triaje, envío, respuestas, hitos), con su fecha. Las notas y los
    títulos salen del catálogo (`texts`), en el idioma de la demo."""
    o, found_at = plan.offsets, plan.found_at
    assert found_at is not None

    def at(key: str) -> datetime:
        return found_at + timedelta(days=o[key])

    fate = plan.fate
    if fate in ("pending_extraction", "pending_triage", "filtered"):
        return
    if fate == "discarded":
        _user(session, job_id, "discarded", at("triage"), reason=plan.reason, note=plan.note)
        return
    _user(session, job_id, "approved", at("triage"))
    if fate in ("approved", "cv_ready"):
        return
    if fate == "expired":
        _user(session, job_id, "expired", at("end"), note=texts["expired"])
        return
    _user(session, job_id, "applied_manually", at("applied"), channel=plan.channel)
    if "followup" in o:
        _user(session, job_id, "followup_sent", at("followup"), note=texts["followup"])
    if fate == "applied":
        return
    if fate == "rejected_after_apply":
        _user(session, job_id, "rejected", at("end"), note=texts["rejected"])
        return
    _user(session, job_id, "reply_received", at("reply"), note=texts["reply"])
    process.add_contact(
        session,
        job_id,
        process.ContactFields(
            name=contact["name"],
            role=contact["role"],
            email=f"{_slug(contact['name']).split('-')[0]}@{_slug(plan.company)}.example.com",
        ),
    )
    if fate == "replied":
        assert plan.starts_in is not None
        process.create_milestone(
            session,
            job_id,
            process.MilestoneCreate(
                kind="test",
                title=texts["test"],
                starts_at=now + timedelta(days=plan.starts_in),
                all_day=True,
                occurred_at=at("milestone"),
            ),
        )
        return
    if fate == "interview_scheduled":
        assert plan.starts_in is not None
        day = now + timedelta(days=plan.starts_in)
    else:
        day = at("interview")
    local = day.astimezone(process.local_zone())
    # Entre semana: las futuras se retrasan al lunes; las pasadas se adelantan al viernes (siguen
    # después de la respuesta, que va al menos 3 días antes).
    step = timedelta(days=1 if fate == "interview_scheduled" else -1)
    while local.weekday() >= 5:
        local += step
    starts = local.replace(hour=plan.hour, minute=0, second=0, microsecond=0).astimezone(UTC)
    milestone = process.create_milestone(
        session,
        job_id,
        process.MilestoneCreate(
            kind="interview",
            title=texts["interview"].format(name=contact["name"]),
            starts_at=starts,
            ends_at=starts + timedelta(hours=1),
            location=texts["interview_location"],
            occurred_at=at("milestone"),
        ),
    )
    if fate == "interview_scheduled":
        return
    process.set_milestone_status(
        session,
        milestone.id,
        process.MilestoneStatusChange(status="done", occurred_at=starts + timedelta(hours=1)),
    )
    if fate == "offer":
        _user(session, job_id, "offer_received", at("end"), note=texts["offer"])
    else:
        _user(session, job_id, "rejected", at("end"), note=texts["rejected_after_interview"])


def _pdf_engine() -> tuple[str | None, str | None]:
    """Con qué plantilla salen los PDF: docx con LibreOffice o Word; si no, html con Chromium."""
    if pdf.converter_name() is not None:
        return "ats-simple", pdf.converter_name()
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            if Path(pw.chromium.executable_path).is_file():
                return "moderna-2col", "Chromium (Playwright)"
            # La imagen de Docker (fase 26.3) solo trae el Chromium sin ventana, que no está en
            # `executable_path`: basta con que arranque.
            if container.in_docker():
                pw.chromium.launch().close()
                return "moderna-2col", "Chromium (Playwright)"
    except Exception:  # noqa: BLE001 - sin Playwright o sin navegador: sin PDF
        pass
    return None, None


def _write_cv(session: Session, job_id: int, content: dict[str, Any], template: str) -> None:
    saved = cv_service.save_content(
        session,
        job_id,
        CvContent.model_validate(content),
        CvRenderOptions(template_id=template),
        agent_name=AGENT_NAME,
    )
    cv_service.save_verification(
        session, saved.document_id, CvVerification(passed=True), agent_name=AGENT_NAME
    )


def _populate(
    session: Session, plans: list[JobPlan], now: datetime, catalog: dict[str, Any], lang: str
) -> list[str]:
    sources = _sources(session, catalog)
    template, _engine = _pdf_engine()
    warnings: list[str] = []
    contacts = list(catalog["contacts"])
    for n, plan in enumerate(plans, start=1):
        plan.found_at = now - timedelta(days=plan.offsets["age"])
        source = sources[plan.source_key]
        result = ingest.store_job(
            session,
            source=source,
            title=plan.title,
            company=plan.company,
            text=plan.text,
            url=catalog["job_url"].format(company=_slug(plan.company), n=n),
            location=plan.location,
            posted_at=None,
            html=None,
        )
        if not result.created or result.duplicate_of is not None:
            raise DemoSeedError(f"Oferta repetida en el catálogo: {plan.title} · {plan.company}.")
        job_id = plan.job_id = result.job_id
        if plan.fate != "pending_extraction":
            saved = extractions.save_extraction(
                session, job_id, plan.extraction, agent_name=AGENT_NAME
            )
            filtered = saved.hard_filters is not None and not saved.hard_filters.passed
            if filtered != (plan.fate == "filtered"):
                raise DemoSeedError(
                    f"«{plan.title}» ({plan.company}) debería {'no ' if filtered else ''}pasar "
                    f"los filtros duros: {saved.hard_filters}."
                )
            matching.compute_match(session, job_id)
        _retime(session, job_id, plan.found_at)
        _story(session, plan, job_id, now, contacts[n % len(contacts)], catalog["texts"])
        if plan.cv is not None:
            if template is None:
                warnings.append(
                    f"Sin CV para «{plan.title}»: no hay con qué generar el PDF. Instala "
                    "LibreOffice o `uv run playwright install chromium` y repite con `--force`."
                )
            else:
                _write_cv(session, job_id, plan.cv, template)
    # El score ya está calculado: la cola de `score_job` no tiene nada que hacer.
    for task in session.scalars(select(Task).where(Task.status == "queued")).all():
        tasks.mark_done(session, task.id)
    seeded = [
        demo_extras.SeededJob(p.fate, p.job_id, p.title, p.company)
        for p in plans
        if p.job_id is not None
    ]
    demo_extras.populate(
        session,
        seeded,
        now,
        demo_dir(lang),
        with_letter=template is not None,
        agent_name=AGENT_NAME,
    )
    return warnings


def seed(
    target: Path,
    force: bool = False,
    now: datetime | None = None,
    eval_cv: bool = False,
    compat: bool = False,
    lang: str = "es",
    compat_cases: int | None = None,
) -> DemoSummary:
    """Crea la demo en `target` (por defecto `data-demo/`) en el idioma `lang` (`es` o `en`).
    Ver la cabecera del módulo.

    Con `eval_cv`, añade además los casos del eval de CV (`evals/cv/`) como ofertas aprobadas y
    sin CV. Con `compat`, las 5 ofertas de la matriz de compatibilidad (`evals/compat/jobs.txt`)
    solo con su texto (`compat_cases`: solo las N primeras). Si la demo ya existe, solo añade los
    casos que falten (sin `--force`).
    """
    target = (target if target.is_absolute() else REPO_ROOT / target).resolve()
    extra = eval_cv or compat
    if extra and not force and is_demo_dir(target) and (target / "candidatai.db").is_file():
        return add_eval_cases(target, eval_cv=eval_cv, compat=compat, compat_cases=compat_cases)
    source = demo_dir(lang)
    catalog = load_catalog(lang)
    prepare_dir(target, force)
    shutil.copyfile(source / "profile.example.yaml", target / "profile.yaml")
    shutil.copyfile(DEMO_DIR / "photo.png", target / "photo.png")
    # Red de LinkedIn ficticia (fase 18), donde la buscaría `cai contacts import-linkedin`.
    linkedin = target / "documentos" / "linkedin"
    linkedin.mkdir(parents=True)
    shutil.copyfile(source / "linkedin" / "Connections.csv", linkedin / "Connections.csv")
    (target / "tmp").mkdir()  # entradas `--file` de los agentes sin MCP
    now = now or datetime.now(UTC)
    rng = random.Random(SEED)
    plans = build_plans(rng, lang)
    with use_data_dir(target, embeddings=False):
        migrations.upgrade()
        with session_scope() as session:
            profile.import_profile(session, target / "profile.yaml")
            warnings = _populate(session, plans, now, catalog, lang)
            network.import_connections(session, linkedin / "Connections.csv")
            _add_cases(session, eval_cv, compat, compat_cases)
        with session_scope() as session:
            return _summary(session, target, warnings)


def _add_cases(
    session: Session, eval_cv: bool, compat: bool, compat_cases: int | None = None
) -> None:
    # Primero los de la matriz (solo texto): si van los dos, esos 5 se quedan por extraer.
    if compat:
        cases = cv_eval.load_compat_cases()[:compat_cases]
        cv_eval.add_cases(session, cases, extract=False)
    if eval_cv:
        cv_eval.add_cases(session)


def add_eval_cases(
    target: Path, eval_cv: bool, compat: bool, compat_cases: int | None = None
) -> DemoSummary:
    """Añade a una demo existente los casos de los evals que falten."""
    with use_data_dir(target, embeddings=False):
        migrations.upgrade()
        with session_scope() as session:
            _add_cases(session, eval_cv, compat, compat_cases)
        with session_scope() as session:
            return _summary(session, target, [])


def _summary(session: Session, target: Path, warnings: list[str]) -> DemoSummary:
    jobs = session.scalars(select(Job)).all()
    stages = Counter(str(events.current_stage(session, job.id)) for job in jobs)
    by_source: Counter[str] = Counter()
    for job in jobs:
        source = session.get(Source, job.source_id)
        by_source[source.kind if source else "?"] += 1
    template, engine = _pdf_engine()
    cvs = sum(1 for job in jobs if cv_service.latest_document(session, job.id) is not None)
    return DemoSummary(
        data_dir=str(target),
        jobs=len(jobs),
        events=len(session.scalars(select(Event.id)).all()),
        by_stage=dict(sorted(stages.items())),
        by_source=dict(sorted(by_source.items())),
        cvs=cvs,
        pdf_engine=engine if template else None,
        warnings=warnings,
    )
