"""Base sintética grande para medir el backend y vigilar el número de consultas.

Llena una base vacía y ya migrada con ofertas inventadas, repartidas por etapas y fuentes, con sus
eventos, extracciones, matches, CVs, procesos con hitos, respuestas y alertas (ofertas resumen en
`pending_detail`). Nada de datos personales: empresas, puestos y textos salen de listas genéricas
y el perfil es el de la demo.

Escribe en bloque (miles de filas por sentencia): con los servicios, una a una, 5000 ofertas
tardarían minutos. La etapa de cada oferta sale igualmente de sus eventos: se proyecta con
`pipeline.project`, la misma función que usa `record()`, y un evento fuera de lugar falla igual.
"""

import random
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

from app.models import (
    Application,
    Company,
    Contact,
    Document,
    DocumentRender,
    Event,
    Job,
    JobExtraction,
    Match,
    MessageDraft,
    Milestone,
    NetworkContact,
    Reply,
    Source,
    Task,
)
from app.services import demo, profile
from app.services.matching.service import scoring_key
from app.services.normalize import normalize_company
from app.services.pipeline import EventType, project

NOW = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
SEED = 29

# Qué le pasa a cada oferta, con su peso: con 5000, unas 2000 alertas (ofertas resumen en
# `pending_detail`) y 300 procesos abiertos. Las primeras ofertas recorren todos los casos en este
# orden, así que una base pequeña también tiene de todo.
FATES: dict[str, float] = {
    "in_process": 0.06,
    "alert": 0.40,
    "pending_triage": 0.07,
    "applied": 0.05,
    "rejected_after_apply": 0.07,
    "filtered": 0.08,
    "discarded": 0.15,
    "approved": 0.03,
    "cv_ready": 0.015,
    "pending_extraction": 0.02,
    "expired": 0.02,
    # Los casos que el embudo trata aparte: duplicadas y reabiertas tras un cierre.
    "duplicate": 0.01,
    "filtered_reopened": 0.01,
    "discarded_reopened": 0.01,
}

SOURCES: tuple[tuple[str, str], ...] = (
    ("manual_url", "Alta manual por URL"),
    ("manual_text", "Alta manual por texto"),
    ("email_alerts", "Alertas por correo"),
    ("browser_capture", "Captura del navegador"),
    ("agent_browse", "Búsqueda con navegador"),
    ("greenhouse", "Greenhouse"),
    ("lever", "Lever"),
)
PLATFORMS = ("linkedin", "infojobs", "indeed", "tecnoempleo", "glassdoor")
ROLES = (
    "Data Engineer",
    "Analytics Engineer",
    "Data Analyst",
    "BI Developer",
    "Machine Learning Engineer",
    "Data Scientist",
    "Backend Engineer",
    "Data Platform Engineer",
    "ETL Developer",
    "Cloud Data Architect",
)
LEVELS = ("Junior", "", "Senior", "Lead", "Principal")
CITIES = ("Madrid", "Barcelona", "Valencia", "Bilbao", "Sevilla", "A Coruña", "Remoto", "Málaga")
PREFIXES = ("Nova", "Atlas", "Delta", "Orbe", "Lumen", "Vértice", "Cobalto", "Prisma", "Faro")
SUFFIXES = ("Analytics", "Data", "Labs", "Systems", "Retail", "Energía", "Logística", "Salud")
SKILLS = (
    "Python",
    "SQL",
    "dbt",
    "Snowflake",
    "Apache Airflow",
    "Spark",
    "Power BI",
    "Docker",
    "Kubernetes",
    "AWS",
    "Azure",
    "Kafka",
    "Tableau",
    "Terraform",
    "PostgreSQL",
)
DISCARD_REASONS = ("skills", "salary", "company", "location", "other")
CHANNELS = ("email", "portal", "linkedin", "referral")
PARAGRAPH = (
    "Buscamos una persona para diseñar y mantener pipelines de datos, modelar tablas analíticas y "
    "colaborar con negocio en la definición de métricas. Trabajarás con un equipo pequeño, con "
    "revisiones de código, despliegues frecuentes y guardias rotativas. Ofrecemos horario "
    "flexible, formación anual y un plan de carrera claro. "
)


@dataclass
class SyntheticSummary:
    jobs: int
    alerts: int
    processes: int
    events: int
    by_stage: dict[str, int] = field(default_factory=dict)


@dataclass
class _Event:
    """Lo mínimo para `pipeline.project` y para la fila de `events`."""

    type: str
    occurred_at: datetime
    payload: dict[str, Any] = field(default_factory=dict)
    actor: str = "system"


class _Ids:
    """Ids explícitos: la base está vacía y así un evento puede apuntar a su hito y viceversa."""

    def __init__(self) -> None:
        self._next: dict[str, int] = {}

    def __call__(self, table: str) -> int:
        self._next[table] = self._next.get(table, 0) + 1
        return self._next[table]


def _extraction(rng: random.Random, title: str, city: str) -> dict[str, Any]:
    skills = rng.sample(SKILLS, 7)
    low = rng.randrange(28, 70) * 1000
    salary: dict[str, Any] = {"min": None, "max": None, "currency": None, "period": None}
    if rng.random() < 0.6:
        period = rng.choices(("year", "month", "hour"), (0.85, 0.1, 0.05))[0]
        factor = {"year": 1, "month": 1 / 14, "hour": 1 / 1760}[period]
        salary = {
            "min": round(low * factor),
            "max": round((low + rng.randrange(4, 16) * 1000) * factor),
            "currency": "EUR",
            "period": period,
        }
    return {
        "title_normalized": title,
        "seniority": rng.choice(("junior", "mid", "senior", "lead")),
        "years_experience_min": rng.randrange(0, 8),
        "employment_type": "full_time",
        "remote_mode": rng.choice(("onsite", "hybrid", "remote", "unknown")),
        "locations": [city],
        "languages_required": [{"language": "Inglés", "level": rng.choice(("B1", "B2", "C1"))}],
        "salary": salary,
        "must_have_skills": skills[:4],
        "nice_to_have_skills": skills[4:],
        "responsibilities": ["Construir y mantener pipelines de datos", "Modelar datos de negocio"],
        "domain": rng.choice((None, "retail", "banca", "energía", "salud")),
        "posting_language": "es",
        "application_deadline": None,
        "red_flags": [],
        "injection_suspected": False,
        "injection_excerpt": None,
    }


def _failure(rng: random.Random) -> dict[str, str]:
    name = rng.choice(("location", "salary", "language", "seniority"))
    return {"filter": name, "reason": f"No cumple el filtro «{name}»."}


def _breakdown(score: int) -> dict[str, Any]:
    """Un desglose con la forma de `ScoreBreakdown` (sin embeddings, como en los tests)."""
    ratio = round(score / 100, 2)

    def component(name: str, value: float | None, weight: float, effective: float) -> dict:
        points = round((value or 0) * effective * 100, 2)
        return {
            "name": name,
            "value": value,
            "weight": weight,
            "effective_weight": effective,
            "points": points,
        }

    return {
        "components": [
            component("must_have_coverage", ratio, 0.45, 0.6429),
            component("semantic_similarity", None, 0.3, 0.0),
            component("preferences_fit", 0.8, 0.15, 0.2143),
            component("nice_to_have_coverage", 0.5, 0.1, 0.1429),
        ],
        "must_have": {"ratio": ratio, "covered": [], "missing": []},
        "nice_to_have": {"ratio": 0.5, "covered": [], "missing": []},
        "semantic": None,
        "preferences": {
            "value": 0.8,
            "role": 1.0,
            "role_match": "Data Engineer",
            "remote_mode": 0.7,
            "location": 0.7,
        },
        "notes": [],
    }


def _match_row(
    rng: random.Random, job_id: int, extraction_id: int, passed: bool, when: datetime, key: str
) -> dict[str, Any]:
    score = rng.randrange(20, 96) if passed else rng.randrange(0, 40)
    failures = [] if passed else [_failure(rng)]
    assessment = None
    if rng.random() < 0.3:
        assessment = {
            "verdict": rng.choice(("strong", "possible", "weak")),
            "rationale": "Cubre las obligatorias principales con experiencia demostrada.",
            "risks": [],
            "questions_for_user": [],
        }
    return {
        "job_id": job_id,
        "profile_version_id": 1,
        "extraction_id": extraction_id,
        # Con la huella de ahora: el match está al día y no se recalcula al pedirlo.
        "scoring_key": key,
        "hard_filters": {"passed": passed, "failures": failures},
        "score": score,
        "breakdown": _breakdown(score),
        "assessment": assessment,
        "created_at": when,
    }


def populate(
    session: Session,
    jobs: int = 5000,
    events_per_job: int = 15,
    now: datetime = NOW,
    seed: int = SEED,
) -> SyntheticSummary:
    """Llena la base (vacía y migrada) con `jobs` ofertas repartidas según `FATES`.

    Cada oferta sale de su propio generador aleatorio (semilla y número de oferta): la oferta 7 es
    igual con 10 que con 100 ofertas, y la base pequeña es el principio de la grande. Así los tests
    comparan el número de consultas con datos de la misma forma.
    """
    if session.scalar(select(func.count()).select_from(Job)):
        raise ValueError("La base sintética se crea sobre una base sin ofertas.")
    rng = random.Random(seed)
    ids = _Ids()

    profile.import_profile(session, demo.demo_dir("es") / "profile.example.yaml")
    session.execute(Task.__table__.update().values(status="done"))
    session.flush()

    sources = []
    for kind, name in SOURCES:
        sid = ids("sources")
        sources.append((sid, kind))
        session.execute(insert(Source), [{"id": sid, "kind": kind, "name": name, "config": {}}])
    company_names = sorted(
        {f"{rng.choice(PREFIXES)} {rng.choice(SUFFIXES)} {n}" for n in range(max(10, jobs // 6))}
    )
    companies = []
    for name in company_names:
        companies.append({"id": ids("companies"), "name": name, "normalized_name": name.lower()})
    session.execute(insert(Company), companies)
    network = [
        {
            "id": ids("network"),
            "first_name": f"Persona{i}",
            "last_name": "Ficticia",
            "linkedin_url": f"https://www.linkedin.com/in/persona-ficticia-{i}",
            "company": company["name"],
            "company_key": normalize_company(company["name"]),
            "position": "Data Engineer",
            "connected_on": None,
            "imported_at": now,
        }
        for i, company in enumerate(rng.sample(companies, min(len(companies), 150)))
    ]
    session.execute(insert(NetworkContact), network)

    names, weights = zip(*FATES.items(), strict=True)
    # Eventos de relleno (notas) para llegar a `events_per_job` de media: las alertas llevan pocos.
    alerts = FATES["alert"]
    filler = max(0.0, (events_per_job - 2 * alerts) / (1 - alerts) - 6)

    rows: dict[str, list[dict[str, Any]]] = {t: [] for t in _TABLES}
    total_events = 0
    key = scoring_key()
    fates = []
    for n in range(1, jobs + 1):
        job_rng = random.Random(f"{seed}-{n}")
        fate = names[n - 1] if n <= len(names) else job_rng.choices(names, weights)[0]
        fates.append(fate)
        total_events += _job(rows, job_rng, ids, n, fate, sources, companies, now, filler, key)

    for table, model in _TABLES.items():
        for chunk in _chunks(rows[table], 2000):
            session.execute(insert(model), chunk)
    session.flush()
    by_stage = dict(
        session.execute(select(Application.stage, func.count()).group_by(Application.stage)).all()
    )
    return SyntheticSummary(
        jobs=jobs,
        alerts=fates.count("alert"),
        processes=fates.count("in_process"),
        events=total_events,
        by_stage=by_stage,
    )


# Orden de inserción: cada tabla después de las que referencia.
_TABLES: dict[str, Any] = {
    "jobs": Job,
    "extractions": JobExtraction,
    "matches": Match,
    "documents": Document,
    "renders": DocumentRender,
    "events": Event,
    "applications": Application,
    "milestones": Milestone,
    "contacts": Contact,
    "replies": Reply,
    "drafts": MessageDraft,
}


def _chunks(items: list[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def _job(
    rows: dict[str, list[dict[str, Any]]],
    rng: random.Random,
    ids: _Ids,
    n: int,
    fate: str,
    sources: list[tuple[int, str]],
    companies: list[dict[str, Any]],
    now: datetime,
    filler: float,
    key: str,
) -> int:
    """Una oferta con todo lo suyo. Devuelve cuántos eventos lleva."""
    job_id = ids("jobs")
    company = rng.choice(companies)
    role = rng.choice(ROLES)
    title = f"{rng.choice(LEVELS)} {role}".strip()
    city = rng.choice(CITIES)
    summary = fate == "alert"
    source_id, kind = (
        next(s for s in sources if s[1] == "email_alerts") if summary else rng.choice(sources)
    )
    platform = rng.choice(PLATFORMS) if summary or kind == "agent_browse" else None
    # Las más antiguas, hasta ~6 meses; las alertas, de las últimas semanas (caducan).
    age = rng.uniform(0, 25 if summary else 180)
    t = now - timedelta(days=age)
    text = f"{title} en {company['name']} ({city}). " + PARAGRAPH * (1 if summary else 8)
    rows["jobs"].append(
        {
            "id": job_id,
            "source_id": source_id,
            "company_id": company["id"],
            "external_id": f"syn-{n}" if platform else None,
            "platform": platform,
            "detail_level": "summary" if summary else "full",
            "url": f"https://empleo.example/{job_id}",
            "title": title,
            "location_raw": city,
            "raw_text": text,
            "risk_flags": ["instruction_like"] if rng.random() < 0.01 else [],
            "fingerprint": sha256(f"synthetic-{n}".encode()).hexdigest(),
            "duplicate_of": None,
            "posted_at": None,
            "first_seen_at": t,
            "signals": _signals(rng),
        }
    )

    events: list[_Event] = []

    def add(type_: EventType, actor: str = "system", **payload: Any) -> datetime:
        nonlocal t
        t += timedelta(hours=rng.uniform(0.5, 30))
        events.append(_Event(type_.value, t, payload, actor))
        return t

    found = {"source": kind} | ({"detail_level": "summary"} if summary else {})
    events.append(_Event(EventType.FOUND.value, t, found))
    if summary:
        for _ in range(rng.randrange(0, 3)):
            add(EventType.NOTE, "user", note="Pendiente de mirar.")
        return _close_job(rows, ids, job_id, events)

    if fate == "duplicate":
        add(EventType.DUPLICATE_DETECTED, duplicate_of=max(1, job_id - 1))
        return _close_job(rows, ids, job_id, events)
    if fate != "pending_extraction":
        extraction_id = ids("extractions")
        when = add(EventType.EXTRACTED, "agent", extraction_id=extraction_id)
        rows["extractions"].append(
            {
                "id": extraction_id,
                "job_id": job_id,
                "schema_version": 1,
                "data": _extraction(rng, role, city),
                "created_at": when,
            }
        )
        passed = fate not in ("filtered", "filtered_reopened")
        for _ in range(1 if rng.random() < 0.8 else 2):  # a veces se vuelve a puntuar
            match_id = ids("matches")
            when = add(EventType.SCORED, match_id=match_id, passed=passed)
            row = _match_row(rng, job_id, extraction_id, passed, when, key)
            rows["matches"].append({"id": match_id, **row})
            events[-1].payload["score"] = row["score"]
            if row["assessment"] and passed:
                verdict = row["assessment"]["verdict"]
                add(EventType.FIT_ASSESSED, "agent", match_id=match_id, verdict=verdict)
    for _ in range(round(rng.uniform(0, 2 * filler))):
        add(EventType.NOTE, "user", note="Revisar con calma.")

    if fate == "filtered":
        add(EventType.HARD_FILTER_FAILED, failures=[_failure(rng)])
    elif fate == "filtered_reopened":  # el usuario no está de acuerdo con el filtro
        add(EventType.HARD_FILTER_FAILED, failures=[_failure(rng)])
        add(EventType.REOPENED, "user")
        if rng.random() < 0.5:
            add(EventType.APPROVED, "user")
    elif fate == "discarded_reopened":  # se reabre y se vuelve a descartar
        add(EventType.DISCARDED, "user", reason=rng.choice(DISCARD_REASONS))
        add(EventType.REOPENED, "user")
        add(EventType.DISCARDED, "user", reason=rng.choice(DISCARD_REASONS))
    elif fate == "discarded":
        add(EventType.DISCARDED, "user", reason=rng.choice(DISCARD_REASONS))
    elif fate == "expired":
        add(EventType.EXPIRED)
    elif fate in ("approved", "cv_ready", "applied", "rejected_after_apply", "in_process"):
        add(EventType.APPROVED, "user")
        render_id = None
        if fate != "approved" and rng.random() < 0.7 or fate == "cv_ready":
            render_id = _cv(rows, rng, ids, job_id, add)
        if fate in ("applied", "rejected_after_apply", "in_process"):
            if rng.random() < 0.2:
                _document(rows, job_id, ids("documents"), "cover_letter", t)
            if rng.random() < 0.15:
                _contact(rows, ids, job_id, rng.choice(("given", "requested")), now)
            channel = rng.choice(CHANNELS)
            if render_id is not None:
                add(EventType.APPLIED, "user", channel=channel, render_id=render_id)
            else:
                add(EventType.APPLIED_MANUALLY, "user", channel=channel)
            if rng.random() < 0.3:
                _document(rows, job_id, ids("documents"), "answers", t)
            if fate == "rejected_after_apply":
                if rng.random() < 0.5:
                    add(EventType.FOLLOWUP_SENT, "user")
                when = add(EventType.REJECTED, "user", note="Respuesta genérica.")
                _reply(rows, rng, ids, job_id, company["name"], when, "accepted")
            elif fate == "in_process":
                _process(rows, rng, ids, job_id, company["name"], add, now)
    return _close_job(rows, ids, job_id, events)


def _cv(rows: dict[str, list[dict[str, Any]]], rng: random.Random, ids: _Ids, job_id: int, add):
    document_id = ids("documents")
    render_id = ids("renders")
    template = rng.choice(("ats-simple", "clasica", "moderna"))
    when = add(EventType.CV_GENERATED, "agent", document_id=document_id)
    _document(rows, job_id, document_id, "cv", when)
    add(EventType.CV_RENDERED, document_id=document_id, render_id=render_id, too_long=False)
    add(EventType.CV_VERIFIED, "agent", document_id=document_id, passed=True)
    rows["renders"].append(
        {
            "id": render_id,
            "document_id": document_id,
            "template_id": template,
            "template_hash": "0" * 64,
            "options": {"template_id": template, "max_pages": 1},
            "docx_path": f"cvs/{job_id}/{document_id}/{render_id}/CV.docx",
            "pdf_path": f"cvs/{job_id}/{document_id}/{render_id}/CV.pdf",
            "pages": 1,
            "keyword_coverage": {"present": rng.sample(SKILLS, 4), "missing": []},
            "warnings": [],
            "selected": True,
            "created_at": when,
        }
    )
    return render_id


def _document(
    rows: dict[str, list[dict[str, Any]]],
    job_id: int,
    document_id: int,
    kind: str,
    when: datetime,
) -> None:
    rows["documents"].append(
        {
            "id": document_id,
            "job_id": job_id,
            "profile_version_id": 1,
            "kind": kind,
            "language": "es",
            "content": {"language": "es", "summary": "Contenido de prueba."},
            "verification": {"passed": True, "issues": []},
            "edited_by_user": False,
            "created_at": when,
        }
    )


def _reply(
    rows: dict[str, list[dict[str, Any]]],
    rng: random.Random,
    ids: _Ids,
    job_id: int,
    company: str,
    when: datetime,
    status: str,
) -> None:
    reply_id = ids("replies")
    rows["replies"].append(
        {
            "id": reply_id,
            "message_id": f"<synthetic-{reply_id}@empresa.example>",
            "origin": "local",
            "sender": f"seleccion{reply_id}@empresa.example",
            "sender_name": f"Selección {company}",
            "subject": "Tu candidatura",
            "received_at": when,
            "body_text": "Gracias por tu candidatura. " * rng.randrange(3, 12),
            "risk_flags": [],
            "candidates": [{"job_id": job_id, "reason": "company_name"}],
            "status": status,
            "job_id": job_id,
            "created_at": when,
        }
    )


def _process(
    rows: dict[str, list[dict[str, Any]]],
    rng: random.Random,
    ids: _Ids,
    job_id: int,
    company: str,
    add,
    now: datetime,
) -> None:
    """Un proceso abierto: respuesta, una a tres entrevistas o pruebas (con su hito) y contactos."""
    when = add(EventType.REPLY_RECEIVED, "user")
    _reply(rows, rng, ids, job_id, company, when, rng.choice(("new", "proposed", "accepted")))
    rounds = rng.randrange(1, 4)
    for round_ in range(rounds):
        milestone_id = ids("milestones")
        kind = "test" if rng.random() < 0.25 else "interview"
        type_ = EventType.TEST_ASSIGNED if kind == "test" else EventType.INTERVIEW_SCHEDULED
        when = add(type_, "user", milestone_id=milestone_id)
        # La última ronda, por venir (de mañana a 30 días); las anteriores, cuando se citaron.
        starts = now + timedelta(days=rng.uniform(1, 30)) if round_ == rounds - 1 else when
        rows["milestones"].append(
            {
                "id": milestone_id,
                "job_id": job_id,
                "kind": kind,
                "title": f"Ronda {round_ + 1}",
                "starts_at": starts,
                "ends_at": starts + timedelta(hours=1),
                "all_day": False,
                "location": "Videollamada",
                "status": "scheduled" if starts > now else "done",
                "event_id": None,  # se rellena abajo: el id del evento aún no existe
                "sequence": 0,
                "created_at": when,
                "updated_at": when,
                "interview_type": rng.choice(("hr", "technical", "final")),
            }
        )
        if starts < now and kind == "interview" and rng.random() < 0.6:
            add(EventType.INTERVIEW_DONE, "user", milestone_id=milestone_id)
    if rng.random() < 0.1:
        add(EventType.OFFER_RECEIVED, "user")
        if rng.random() < 0.5:
            add(EventType.ACCEPTED, "user")
    if rng.random() < 0.3:
        _contact(rows, ids, job_id, None, now)
    if rng.random() < 0.3:
        rows["drafts"].append(
            {
                "id": ids("drafts"),
                "job_id": job_id,
                "kind": "followup",
                "body": "Hola, quería saber cómo va el proceso.",
                "status": "draft",
            }
        )


def _contact(
    rows: dict[str, list[dict[str, Any]]],
    ids: _Ids,
    job_id: int,
    referral: str | None,
    now: datetime,
) -> None:
    rows["contacts"].append(
        {
            "id": ids("contacts"),
            "job_id": job_id,
            "name": f"Contacto {job_id}",
            "role": "Talent Acquisition",
            "relation": "referral" if referral else "recruiter",
            "referral": referral,
            "referral_at": now if referral else None,
            "created_at": now,
        }
    )


def _signals(rng: random.Random) -> dict[str, Any]:
    """Alguna señal de oferta dudosa, como las que guarda `services/doubtful.py`."""
    signals: dict[str, Any] = {}
    if rng.random() < 0.08:
        signals["fixed_term"] = {"origin": "extraction"}
    if rng.random() < 0.05:
        signals["ai_screening"] = {"origin": "text", "matched": "ai screening"}
    return signals


def _close_job(
    rows: dict[str, list[dict[str, Any]]], ids: _Ids, job_id: int, events: list[_Event]
) -> int:
    """Escribe los eventos de la oferta y su proyección (la etapa sale de los eventos)."""
    by_milestone: dict[int, int] = {}
    for event in events:
        event_id = ids("events")
        rows["events"].append(
            {
                "id": event_id,
                "job_id": job_id,
                "type": event.type,
                "actor": event.actor,
                "agent_name": "synthetic" if event.actor == "agent" else None,
                "payload": event.payload,
                "occurred_at": event.occurred_at,
                "recorded_at": event.occurred_at,
            }
        )
        if event.type in (EventType.INTERVIEW_SCHEDULED, EventType.TEST_ASSIGNED):
            by_milestone[event.payload["milestone_id"]] = event_id
    for milestone in reversed(rows["milestones"]):
        if milestone["job_id"] != job_id:
            break
        milestone["event_id"] = by_milestone[milestone["id"]]
    state = project(events)
    rows["applications"].append(
        {
            "job_id": job_id,
            "stage": state.stage.value,
            "channel": state.channel,
            "render_id": state.render_id,
            "applied_at": state.applied_at,
            "last_event_at": state.last_event_at,
            "closed_at": state.closed_at,
            "closed_by": state.closed_by.value if state.closed_by else None,
        }
    )
    return len(events)
