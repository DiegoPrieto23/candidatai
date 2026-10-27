"""Señales de oferta dudosa (fase 25.3): observaciones deterministas, no veredictos.

Viven en `jobs.signals` junto a las de la fase 16 y **no cambian el score ni los filtros duros**;
solo filtran si el usuario lo pide en `preferences.exclude_signals` (`employer_hidden`,
`fixed_term`). El agente las lee en `get_match` y las cita en los riesgos de `assess-fit`.

- `salary_range_wide`: el máximo supera al mínimo en más de `doubtful.salary_range_max_pct` %.
- `employer_hidden`: la publica una agencia (`is_agency` de la extracción o un nombre de
  `agencies`) o el nombre de la empresa no dice quién es (`hidden_employer`).
- `fixed_term`: la extracción dice contrato temporal, por obra o de sustitución.
- `ai_screening`: la extracción dice que criba una IA o un test automático, o el texto trae una
  frase de `ai_screening`.
- `stale_repost`: en `services/reposts.py`, porque depende de las publicaciones vistas.

Se calculan al guardar una extracción (`refresh`) y se pueden recalcular todas con
`cai jobs signals --recompute` (tras editar `config/doubtful_patterns.yaml` o `policies.yaml`).
Los patrones vienen de `config/doubtful_patterns.yaml`.
"""

import logging

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.policies import DoubtfulPatterns, get_doubtful_patterns, get_policies
from app.models import Company, Job
from app.schemas.llm_io import JobExtraction
from app.services import reposts
from app.services.normalize import fold
from app.services.signals import (
    DOUBTFUL_CODES,
    AiScreeningSignal,
    DoubtfulCode,
    EmployerHiddenSignal,
    FixedTermSignal,
    JobSignals,
    SalaryRangeSignal,
    set_signal,
)
from app.services.signals import read as read_signals

logger = logging.getLogger(__name__)

# Las que salen de la extracción y del texto; `stale_repost` la calcula `reposts.refresh`.
EXTRACTION_CODES: tuple[DoubtfulCode, ...] = (
    "salary_range_wide",
    "employer_hidden",
    "fixed_term",
    "ai_screening",
)
# Las que el usuario puede convertir en filtro duro (`preferences.exclude_signals`).
FILTERABLE: tuple[DoubtfulCode, ...] = ("employer_hidden", "fixed_term")


class SignalNote(BaseModel):
    """Una señal activa, en texto para el agente y la CLI (la UI lo traduce por `code`)."""

    code: DoubtfulCode
    text: str


def _words_match(name: str, patterns: list[str]) -> str | None:
    folded = f" {fold(name)} "
    return next((p for p in patterns if fold(p) and f" {fold(p)} " in folded), None)


def _text_match(text: str, patterns: list[str]) -> str | None:
    # Como palabras completas: «ai screening» no casa con «Thai screening». Las negaciones («no
    # usamos AI screening») sí casan: es una observación, y el texto lo explica.
    return _words_match(text, patterns)


def salary_range_wide(ext: JobExtraction) -> SalaryRangeSignal | None:
    salary = ext.salary
    if salary is None or not salary.min or salary.max is None:
        return None
    pct = (salary.max - salary.min) / salary.min * 100
    threshold = get_policies().doubtful.salary_range_max_pct
    if pct <= threshold:
        return None
    return SalaryRangeSignal(
        min=salary.min,
        max=salary.max,
        currency=salary.currency,
        pct=round(pct),
        threshold_pct=threshold,
    )


def employer_hidden(
    ext: JobExtraction | None, company: str | None, patterns: DoubtfulPatterns | None = None
) -> EmployerHiddenSignal | None:
    patterns = patterns or get_doubtful_patterns()
    client = ((ext.hiring_entity or "").strip() or None) if ext is not None else None
    if company and (matched := _words_match(company, patterns.hidden_employer)):
        return EmployerHiddenSignal(
            reason="unnamed", origin="company", client=client, matched=matched
        )
    agency_name = _words_match(company, patterns.agencies) if company else None
    if (ext is not None and ext.is_agency) or agency_name:
        # La agencia que dice para quién es también avisa, con otro texto: no es la empresa que
        # contrata.
        if client and company and fold(client) == fold(company):
            client = None
        return EmployerHiddenSignal(
            reason="agency_for_client" if client else "agency",
            origin="company" if agency_name else "extraction",
            client=client,
            matched=agency_name,
        )
    return None


def fixed_term(ext: JobExtraction | None) -> FixedTermSignal | None:
    return FixedTermSignal() if ext is not None and ext.contract_type == "fixed_term" else None


def ai_screening(
    ext: JobExtraction | None, text: str, patterns: DoubtfulPatterns | None = None
) -> AiScreeningSignal | None:
    if ext is not None and ext.mentions_ai_screening:
        return AiScreeningSignal(origin="extraction")
    patterns = patterns or get_doubtful_patterns()
    if matched := _text_match(text, patterns.ai_screening):
        return AiScreeningSignal(origin="text", matched=matched)
    return None


def _company_name(session: Session, job: Job) -> str | None:
    company = session.get(Company, job.company_id)
    return company.name if company else None


def _parse(data: dict[str, object] | None, job_id: int) -> JobExtraction | None:
    if data is None:
        return None
    try:
        return JobExtraction.model_validate(data)
    except ValidationError:  # una fila antigua o editada a mano no para el recálculo
        logger.warning("Extracción no válida en la oferta %s: señales sin ella", job_id)
        return None


def _latest_extractions(session: Session, job_ids: list[int]) -> dict[int, JobExtraction | None]:
    from app.services import extractions  # evita la importación circular

    rows = extractions.latest_rows(session, job_ids)
    return {jid: _parse(rows[jid].data if jid in rows else None, jid) for jid in job_ids}


_UNSET = object()


def refresh(
    session: Session,
    job: Job,
    ext: JobExtraction | None | object = _UNSET,
    company: str | None | object = _UNSET,
    patterns: DoubtfulPatterns | None = None,
) -> JobSignals:
    """Recalcula las señales de oferta dudosa de `job`. Sin `ext` ni `company`, los consulta (la
    extracción vigente y el nombre de la empresa)."""
    if ext is _UNSET:
        ext = _latest_extractions(session, [job.id])[job.id]
    if company is _UNSET:
        company = _company_name(session, job)
    assert ext is None or isinstance(ext, JobExtraction)
    assert company is None or isinstance(company, str)
    patterns = patterns or get_doubtful_patterns()
    set_signal(job, "salary_range_wide", salary_range_wide(ext) if ext else None)
    set_signal(job, "employer_hidden", employer_hidden(ext, company, patterns))
    set_signal(job, "fixed_term", fixed_term(ext))
    set_signal(job, "ai_screening", ai_screening(ext, job.raw_text or "", patterns))
    session.flush()
    return read_signals(job)


class RecomputeResult(BaseModel):
    jobs: int
    with_signals: int
    counts: dict[str, int]


def recompute_all(session: Session) -> RecomputeResult:
    """Recalcula las señales de oferta dudosa de todas las ofertas (no las de la fase 16)."""
    jobs = list(session.scalars(select(Job).order_by(Job.id)))
    # De una vez: la extracción vigente y el nombre de la empresa de todas (no una consulta por
    # oferta). `stale_repost` sí va por grupo.
    exts = _latest_extractions(session, [job.id for job in jobs])
    names = dict(session.execute(select(Company.id, Company.name)).all())
    patterns = get_doubtful_patterns()
    counts = dict.fromkeys(DOUBTFUL_CODES, 0)
    flagged = 0
    for job in jobs:
        refresh(session, job, exts[job.id], names.get(job.company_id), patterns)
        set_signal(job, "stale_repost", reposts.compute_stale(session, job))
        active = active_codes(read_signals(job))
        flagged += bool(active)
        for code in active:
            counts[code] += 1
    session.flush()
    return RecomputeResult(jobs=len(jobs), with_signals=flagged, counts=counts)


def active_codes(signals: JobSignals) -> list[DoubtfulCode]:
    return [code for code in DOUBTFUL_CODES if getattr(signals, code) is not None]


def _money(value: int, currency: str | None) -> str:
    return f"{value:,}".replace(",", ".") + (f" {currency}" if currency else "")


def notes(signals: JobSignals) -> list[SignalNote]:
    """Las señales activas en texto (en español, como los demás mensajes del servidor)."""
    out: list[SignalNote] = []
    if s := signals.salary_range_wide:
        out.append(
            SignalNote(
                code="salary_range_wide",
                text=f"Rango salarial muy amplio: {_money(s.min, s.currency)} – "
                f"{_money(s.max, s.currency)} (el máximo supera al mínimo en un {s.pct} %).",
            )
        )
    if s := signals.employer_hidden:
        text = {
            "agency": "La publica una agencia o consultora de selección y no dice para quién es.",
            "agency_for_client": f"La publica una agencia o consultora de selección para "
            f"{s.client}.",
            "unnamed": "El nombre de la empresa no dice quién contrata.",
        }[s.reason]
        out.append(SignalNote(code="employer_hidden", text=text))
    if signals.fixed_term:
        out.append(
            SignalNote(
                code="fixed_term", text="Contrato temporal (por obra, sustitución o duración fija)."
            )
        )
    if s := signals.stale_repost:
        out.append(
            SignalNote(
                code="stale_repost",
                text=f"Lleva tiempo publicada: vista por primera vez el {s.first_seen:%d/%m/%Y} y "
                f"por última el {s.last_seen:%d/%m/%Y} ({s.span_days} días), con {s.count} "
                f"publicaciones en días distintos en {s.channel}.",
            )
        )
    if s := signals.ai_screening:
        text = "Dice que la cribará una IA o un test automático antes de hablar con nadie"
        out.append(
            SignalNote(
                code="ai_screening",
                text=text + (f" («{s.matched}»)." if s.matched else "."),
            )
        )
    return out
