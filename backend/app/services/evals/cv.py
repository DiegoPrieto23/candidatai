"""Eval de CV (fase 12.2): mide los CVs que deja el agente con `generar-cv` sobre casos fijos.

Los casos (`evals/cv/cases.jsonl`) son ofertas inventadas contra el perfil de `demo/`.
`cai demo seed --eval-cv` las da de alta en la demo ya aprobadas; el agente genera el CV de cada
una; `cai eval cv` comprueba lo que quedó guardado. No genera nada: un caso sin CV sale como
«pendiente», no como fallo.

Comprobaciones por CV (`CHECKS`): evidencias que existen en el perfil, skills que están en el perfil
y ninguna de las prohibidas del caso, ninguna skill básica que la oferta no pida, una página,
cobertura de las keywords que la candidata puede cubrir, idioma de la oferta y verificación del rol
`verificador` en `passed`.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.core.validation import describe_error
from app.models import Document, DocumentRender, Event, Job
from app.models.base import utcnow
from app.schemas.cv import CvContent
from app.schemas.llm_io import JobExtraction
from app.schemas.profile import CandidateProfile
from app.services import events, extractions, ingest
from app.services import profile as profile_service
from app.services.demo_text import posting_text
from app.services.documents import checks
from app.services.documents.service import CV_KIND
from app.services.matching import service as matching
from app.services.matching.skills import alias_index, canonical
from app.services.pipeline import EventType

CASES_PATH = REPO_ROOT / "evals" / "cv" / "cases.jsonl"
# La matriz de compatibilidad (fase 12.3): ids de `cases.jsonl`, uno por línea.
COMPAT_PATH = REPO_ROOT / "evals" / "compat" / "jobs.txt"
URL_PREFIX = "https://empleo.example.com/eval-cv/"
DEFAULT_MIN_COVERAGE = 0.8
AGENT_NAME = "demo-seed"

CheckName = Literal[
    "evidence", "skills", "basic_skills", "one_page", "coverage", "language", "verified"
]
CHECKS: dict[CheckName, str] = {
    "evidence": "Evidencias que existen en el perfil",
    "skills": "Sin skills inventadas ni prohibidas",
    "basic_skills": "Sin skills básicas que la oferta no pide",
    "one_page": "Una página",
    "coverage": "Cobertura de keywords",
    "language": "Idioma de la oferta",
    "verified": "Verificado por el rol verificador",
}
CaseStatus = Literal["passed", "failed", "pending", "missing"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseJob(_Strict):
    title: str = Field(min_length=1)
    company: str = Field(min_length=1)
    location: str = Field(min_length=1)


class CaseExpect(_Strict):
    keywords: list[str] = []  # deben aparecer en el CV
    forbidden_skills: list[str] = []  # no las tiene la candidata: no deben aparecer


class CvEvalCase(_Strict):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    job: CaseJob
    extraction: JobExtraction
    expect: CaseExpect = CaseExpect()
    note: str | None = None


class CvEvalFileError(ValueError):
    pass


class CvEvalNotDemoError(ValueError):
    """`cai eval cv` mide los casos contra el perfil demo: solo tiene sentido en la demo."""


class CheckResult(BaseModel):
    name: CheckName
    passed: bool | None  # None: no se pudo medir (p. ej. sin PDF)
    detail: str | None = None


class CaseResult(BaseModel):
    id: str
    job_id: int | None
    status: CaseStatus
    agent_name: str | None = None
    document_id: int | None = None
    checks: list[CheckResult] = []


class CvEvalReport(BaseModel):
    created_at: datetime
    agent: str | None  # filtro `--agent`
    min_coverage: float
    cases: list[CaseResult]
    evaluated: int
    passed: int
    pending: int
    checks_passed: dict[CheckName, int]


# --- Casos ---------------------------------------------------------------------------------


def load_cases(path: Path = CASES_PATH) -> list[CvEvalCase]:
    cases: list[CvEvalCase] = []
    seen: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        where = f"{path.name}, línea {number}"
        try:
            case = CvEvalCase.model_validate(json.loads(line))
        except json.JSONDecodeError as exc:
            raise CvEvalFileError(f"{where}: JSON no válido ({exc.msg}).") from exc
        except ValidationError as exc:
            error = exc.errors(include_url=False)[0]
            field = ".".join(str(p) for p in error["loc"]) or "(caso)"
            _, reason = describe_error(error)
            raise CvEvalFileError(f"{where}: {field}: {reason}") from exc
        if case.id in seen:
            raise CvEvalFileError(f"{where}: id repetido «{case.id}».")
        seen.add(case.id)
        cases.append(case)
    return cases


def load_compat_cases(path: Path = COMPAT_PATH) -> list[CvEvalCase]:
    """Los casos de `cases.jsonl` que lista `evals/compat/jobs.txt`, en ese orden."""
    by_id = {c.id: c for c in load_cases()}
    ids = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    unknown = [i for i in ids if i not in by_id]
    if unknown:
        raise CvEvalFileError(f"{path.name}: no están en cases.jsonl: {', '.join(unknown)}.")
    return [by_id[i] for i in ids]


def case_url(case_id: str) -> str:
    """Identificador estable de cada caso en la demo: la URL de su oferta."""
    return URL_PREFIX + case_id


def _case_job(session: Session, case_id: str) -> Job | None:
    return session.scalars(select(Job).where(Job.url == case_url(case_id))).first()


def add_cases(
    session: Session, cases: list[CvEvalCase] | None = None, extract: bool = True
) -> list[int]:
    """Da de alta los casos como ofertas aprobadas y sin CV. Las que ya existen no se tocan.

    Devuelve los `job_id` de todos los casos, en orden. Usa los servicios de siempre (alta,
    extracción, filtros, score y `approved`); un caso que no pase los filtros es un error del
    fichero de casos. Sin `extract`, solo el alta con el texto (quedan en `pending_extraction`):
    así un agente recorre el flujo entero (matriz de compatibilidad, fase 12.3).
    """
    job_ids: list[int] = []
    for case in cases if cases is not None else load_cases():
        existing = _case_job(session, case.id)
        if existing is not None:
            job_ids.append(existing.id)
            continue
        text = posting_text(
            case.job.title,
            case.job.company,
            case.extraction.domain or "tecnología",
            case.job.location,
            case.extraction,
        )
        result = ingest.add_from_text(
            session,
            case.job.title,
            case.job.company,
            text,
            url=case_url(case.id),
            location=case.job.location,
        )
        if not result.created:
            raise CvEvalFileError(
                f"El caso «{case.id}» coincide con la oferta {result.job_id} de la demo (misma "
                "empresa, puesto y ubicación): cambia la empresa del caso."
            )
        if not extract:
            job_ids.append(result.job_id)
            continue
        saved = extractions.save_extraction(
            session, result.job_id, case.extraction, agent_name=AGENT_NAME
        )
        if saved.hard_filters is not None and not saved.hard_filters.passed:
            raise CvEvalFileError(
                f"El caso «{case.id}» no pasa los filtros duros del perfil demo: "
                + "; ".join(f.reason for f in saved.hard_filters.failures)
            )
        matching.compute_match(session, result.job_id)
        events.add_user_event(session, result.job_id, EventType.APPROVED)
        job_ids.append(result.job_id)
    return job_ids


# --- Comprobaciones ------------------------------------------------------------------------


def _content_text(content: CvContent, profile: CandidateProfile) -> str:
    """El texto que sale en el CV: lo redactado más lo que el render toma del perfil (puesto y
    empresa, nombre del proyecto, formación y certificaciones)."""
    experiences = {e.id: e for e in profile.experience}
    projects = {p.id: p for p in profile.projects}
    education = {e.id: e for e in profile.education}
    certifications = {c.id: c for c in profile.certifications}
    parts = [content.subtitle, content.summary]
    for exp in content.experience:
        if exp.experience_id in experiences:
            ref = experiences[exp.experience_id]
            parts.append(f"{ref.role} · {ref.company}")
        parts += [b.text for b in exp.bullets]
    for prj in content.projects:
        if prj.project_id in projects:
            parts.append(projects[prj.project_id].name)
        parts += [b.text for b in prj.bullets]
    parts += [education[i].title for i in content.education_ids if i in education]
    parts += [certifications[i].name for i in content.certification_ids if i in certifications]
    for group in content.skills:
        parts += [group.group, *group.items]
    return "\n".join(parts)


def _skill_keys(profile: CandidateProfile, index: dict[str, str]) -> tuple[set[str], set[str]]:
    """Skills del perfil (con nivel) y básicas, canónicas."""
    levels = {canonical(s.name, index) for s in profile.skills if s.level != "B"}
    basics = {canonical(n, index) for n in profile.basic_skills}
    basics |= {canonical(s.name, index) for s in profile.skills if s.level == "B"}
    return levels, basics - levels


def check_cv(
    case: CvEvalCase,
    content: CvContent,
    profile: CandidateProfile,
    pages: int | None,
    verification: dict[str, object] | None,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
) -> list[CheckResult]:
    """Las comprobaciones de un CV. Funciones puras sobre lo guardado: sin BD."""
    index = alias_index()
    results: list[CheckResult] = []

    refs = profile.evidence_refs()
    bad = [
        ref
        for item in [*content.experience, *content.projects]
        for bullet in item.bullets
        for ref in bullet.evidence
        if ref not in refs
    ]
    results.append(
        CheckResult(
            name="evidence",
            passed=not bad,
            detail=f"No existen en el perfil: {', '.join(bad)}." if bad else None,
        )
    )

    levels, basics = _skill_keys(profile, index)
    listed = [item for group in content.skills for item in group.items]
    unknown = [i for i in listed if checks.skill_key(i, index) not in levels | basics]
    folded = checks.fold_text(_content_text(content, profile))
    forbidden = [
        s for s in case.expect.forbidden_skills if checks.skill_mentioned(folded, s, index)
    ]
    problems = []
    if unknown:
        problems.append(f"no están en el perfil: {', '.join(unknown)}")
    if forbidden:
        problems.append(f"no las tiene y aparecen: {', '.join(forbidden)}")
    results.append(
        CheckResult(
            name="skills",
            passed=not problems,
            detail=("Skills que " + "; ".join(problems) + ".") if problems else None,
        )
    )

    requested = {canonical(s, index) for s in checks.requested_skills(case.extraction)}
    unrequested = [i for i in listed if checks.skill_key(i, index) in basics - requested]
    # También en el titular y el resumen (en los bullets no: pueden citar un logro que la nombra).
    headline = checks.fold_text(f"{content.subtitle}\n{content.summary}")
    names = {canonical(n, index): n for n in profile.basic_skills}
    names |= {canonical(s.name, index): s.name for s in profile.skills if s.level == "B"}
    for key in sorted(basics - requested):
        name = names.get(key)
        if name and name not in unrequested and checks.skill_mentioned(headline, name, index):
            unrequested.append(name)
    results.append(
        CheckResult(
            name="basic_skills",
            passed=not unrequested,
            detail=f"Básicas que la oferta no pide: {', '.join(unrequested)}."
            if unrequested
            else None,
        )
    )

    results.append(
        CheckResult(
            name="one_page",
            passed=None if pages is None else pages == 1,
            detail="Sin PDF: no se ha podido medir." if pages is None else f"{pages} páginas.",
        )
    )

    # Solo cuenta lo que la candidata puede cubrir: lo que la oferta pide y está en su perfil,
    # más las keywords esperadas del caso. Lo que no tiene, no se le puede pedir.
    coverable = [
        s
        for s in checks.requested_skills(case.extraction)
        if canonical(s, index) in levels | basics
    ]
    targets: dict[str, str] = {}  # por skill canónica: «Postgres» y «PostgreSQL» cuentan una vez
    for keyword in [*coverable, *case.expect.keywords]:
        targets.setdefault(canonical(keyword, index), keyword)
    missing = [k for k in targets.values() if not checks.skill_mentioned(folded, k, index)]
    ratio = 1.0 if not targets else (len(targets) - len(missing)) / len(targets)
    results.append(
        CheckResult(
            name="coverage",
            passed=ratio >= min_coverage,
            detail=f"{ratio:.0%} de {len(targets)}"
            + (f"; faltan {', '.join(missing)}." if missing else "."),
        )
    )

    expected_language = "en" if case.extraction.posting_language.startswith("en") else "es"
    results.append(
        CheckResult(
            name="language",
            passed=content.language == expected_language,
            detail=None
            if content.language == expected_language
            else f"CV en «{content.language}» para una oferta en «{expected_language}».",
        )
    )

    verified = bool(verification and verification.get("passed"))
    results.append(
        CheckResult(
            name="verified",
            passed=verified,
            detail=None if verified else "Sin verificación del rol `verificador` en `passed`.",
        )
    )
    return results


# --- Evaluación sobre la BD ----------------------------------------------------------------


def _documents(session: Session, job_id: int) -> list[Document]:
    return list(
        session.scalars(
            select(Document)
            .where(Document.job_id == job_id, Document.kind == CV_KIND)
            .order_by(Document.id.desc())
        )
    )


def _author(session: Session, document: Document) -> str | None:
    """Quién guardó el CV: `agent_name` de su evento `cv_generated`."""
    for event in session.scalars(
        select(Event).where(
            Event.job_id == document.job_id, Event.type == EventType.CV_GENERATED.value
        )
    ):
        if event.payload.get("document_id") == document.id:
            return event.agent_name
    return None


def _pages(session: Session, document_id: int) -> int | None:
    """Páginas del render que se enviaría (el seleccionado) o, si no hay, del último."""
    renders = list(
        session.scalars(
            select(DocumentRender)
            .where(DocumentRender.document_id == document_id)
            .order_by(DocumentRender.selected.desc(), DocumentRender.id.desc())
        )
    )
    return renders[0].pages if renders else None


def evaluate(
    session: Session,
    cases: list[CvEvalCase] | None = None,
    agent: str | None = None,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
) -> CvEvalReport:
    """Mide el último CV de cada caso (o el último de `agent`)."""
    if not get_settings().demo_mode:
        raise CvEvalNotDemoError(
            "El eval de CV usa los casos del perfil demo: ejecútalo con CAI_DATA_DIR apuntando a "
            "la demo (`cai demo seed --eval-cv`)."
        )
    results: list[CaseResult] = []
    for case in cases if cases is not None else load_cases():
        job = _case_job(session, case.id)
        if job is None:
            results.append(CaseResult(id=case.id, job_id=None, status="missing"))
            continue
        document = next(
            (
                d
                for d in _documents(session, job.id)
                if agent is None or _author(session, d) == agent
            ),
            None,
        )
        if document is None:
            results.append(CaseResult(id=case.id, job_id=job.id, status="pending"))
            continue
        profile = profile_service.get_version(session, document.profile_version_id).profile
        found = check_cv(
            case,
            CvContent.model_validate(document.content),
            profile,
            _pages(session, document.id),
            document.verification,
            min_coverage,
        )
        failed = any(c.passed is False for c in found)
        results.append(
            CaseResult(
                id=case.id,
                job_id=job.id,
                status="failed" if failed else "passed",
                agent_name=_author(session, document),
                document_id=document.id,
                checks=found,
            )
        )
    measured = [r for r in results if r.status in ("passed", "failed")]
    return CvEvalReport(
        created_at=utcnow(),
        agent=agent,
        min_coverage=min_coverage,
        cases=results,
        evaluated=len(measured),
        passed=sum(r.status == "passed" for r in measured),
        pending=len(results) - len(measured),
        checks_passed={
            name: sum(1 for r in measured for c in r.checks if c.name == name and c.passed)
            for name in CHECKS
        },
    )


# --- Informe -------------------------------------------------------------------------------

STATUS_LABELS: dict[CaseStatus, str] = {
    "passed": "pasa",
    "failed": "falla",
    "pending": "pendiente",
    "missing": "sin alta",
}
_MARK = {True: "✔", False: "✘", None: "—"}


def to_markdown(report: CvEvalReport) -> str:
    agent = report.agent or "todos"
    lines = [
        "# Evaluación de CVs",
        "",
        f"- Fecha: {report.created_at:%Y-%m-%d %H:%M} UTC",
        f"- Agente: {agent}",
        f"- Cobertura mínima: {report.min_coverage:.0%}",
        f"- Evaluados: {report.evaluated} · pasan: {report.passed} · pendientes: {report.pending}",
        "",
        "| Caso | Estado | Agente | " + " | ".join(CHECKS.values()) + " |",
        "|---|---|---|" + "---|" * len(CHECKS),
    ]
    for case in report.cases:
        marks = {c.name: _MARK[c.passed] for c in case.checks}
        cells = [marks.get(name, "") for name in CHECKS]
        lines.append(
            f"| `{case.id}` | {STATUS_LABELS[case.status]} | {case.agent_name or ''} | "
            + " | ".join(cells)
            + " |"
        )
    details = [
        f"- `{case.id}` · {CHECKS[c.name]}: {c.detail}"
        for case in report.cases
        for c in case.checks
        if c.passed is False and c.detail
    ]
    if details:
        lines += ["", "## Fallos", "", *details]
    if report.pending:
        lines += [
            "",
            "Pendientes: lanza `generar-cv` sobre esos casos (`sin alta`: antes, "
            "`cai demo seed --eval-cv`).",
        ]
    return "\n".join(lines) + "\n"


def save_report(report: CvEvalReport, reports_dir: Path) -> tuple[Path, Path]:
    reports_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"-{report.agent}" if report.agent else ""
    stem = f"cv-{report.created_at:%Y%m%d-%H%M%S}{suffix}"
    json_path, md_path = reports_dir / f"{stem}.json", reports_dir / f"{stem}.md"
    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(to_markdown(report), encoding="utf-8")
    return json_path, md_path
