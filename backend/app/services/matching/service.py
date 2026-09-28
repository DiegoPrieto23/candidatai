"""Matches en la BD: calcular, consultar, valorar y recalcular.

Un match se calcula con la extracción vigente de la oferta, la versión vigente del perfil y la
configuración de puntuación vigente (`scoring_key`); si cualquiera cambia, queda desfasado y se
recalcula al pedirlo (`get_match`), en el worker o con `jh match rescore`.
Los filtros duros cierran la oferta (`hard_filter_failed`) al guardar una extracción y al recalcular
tras importar un perfil nuevo, nunca al consultar. Si el usuario reabrió la oferta después de un
`hard_filter_failed`, los filtros ya no la vuelven a cerrar: decidió él.
"""

import hashlib
import json
from collections.abc import Sequence
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.policies import get_policies, get_skill_aliases
from app.models import Application, Job, Match
from app.models import JobExtraction as JobExtractionRow
from app.schemas.llm_io import FitAssessment, JobExtraction
from app.services import events, extractions, tasks
from app.services import profile as profiles
from app.services.events import JobNotFoundError
from app.services.extractions import ExtractionNotFoundError
from app.services.matching import embeddings, hard_filters, scorer
from app.services.matching.hard_filters import HardFilterResult
from app.services.matching.scorer import ScoreBreakdown
from app.services.pipeline import OPEN_STAGES, Actor, EventType, Stage, job_events


class MatchView(BaseModel):
    job_id: int
    match_id: int
    profile_version_id: int
    extraction_id: int | None
    score: int
    triage_threshold: int
    below_threshold: bool  # la UI la muestra atenuada
    hard_filters: HardFilterResult
    breakdown: ScoreBreakdown
    assessment: FitAssessment | None  # la última valoración del agente, aunque sea de otro cálculo
    assessment_stale: bool  # la valoración es de un match anterior (perfil, oferta o puntuación)
    created_at: datetime


class SaveAssessmentResult(BaseModel):
    ok: bool
    job_id: int
    match_id: int


class RescoreResult(BaseModel):
    scored: int
    closed: list[int]  # ofertas cerradas por no pasar los filtros con el perfil nuevo


def _job(session: Session, job_id: int) -> Job:
    job = session.get(Job, job_id)
    if job is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    return job


def _latest_extraction(session: Session, job_id: int) -> JobExtractionRow:
    row = extractions.latest_rows(session, [job_id]).get(job_id)
    if row is None:
        raise ExtractionNotFoundError(f"La oferta {job_id} aún no tiene extracción.")
    return row


def _stage(session: Session, job_id: int) -> Stage | None:
    app = session.get(Application, job_id)
    return Stage(app.stage) if app else None


def user_overrode_filters(session: Session, job_id: int) -> bool:
    """¿Reabrió el usuario la oferta después de su último `hard_filter_failed`?"""
    seen_failure = False
    overrode = False
    for event in job_events(session, job_id):
        if event.type == EventType.HARD_FILTER_FAILED:
            seen_failure, overrode = True, False
        elif event.type == EventType.REOPENED and seen_failure:
            overrode = True
    return overrode


def _close_if_filtered(
    session: Session, job_id: int, result: HardFilterResult, agent_name: str | None = None
) -> bool:
    if result.passed or _stage(session, job_id) != Stage.PENDING_TRIAGE:
        return False
    if user_overrode_filters(session, job_id):
        return False
    events.record(
        session,
        job_id,
        EventType.HARD_FILTER_FAILED,
        Actor.SYSTEM,
        payload={"failures": [f.model_dump() for f in result.failures]},
        agent_name=agent_name,
    )
    return True


def evaluate_filters(session: Session, job_id: int) -> HardFilterResult:
    job = _job(session, job_id)
    ext = JobExtraction.model_validate(_latest_extraction(session, job_id).data)
    profile = profiles.current(session).profile
    return hard_filters.evaluate(job.title, ext, profile, get_policies().hard_filters)


def after_extraction(session: Session, job_id: int) -> HardFilterResult | None:
    """Tras guardar una extracción: filtros duros (pueden cerrar la oferta) y score en el worker.

    Sin perfil importado no hay con qué comparar: no se filtra ni se puntúa (devuelve `None`).
    """
    try:
        result = evaluate_filters(session, job_id)
    except profiles.ProfileNotFoundError:
        return None
    _close_if_filtered(session, job_id, result)
    tasks.enqueue(session, "score_job", {"job_id": job_id})
    return result


def scoring_key() -> str:
    """Huella de la configuración con que se puntúa: versión del scorer, políticas de puntuación y
    filtros (salvo el umbral de triaje, que no cambia el score), alias de skills y modelo de
    embeddings (o ninguno). Instalar el extra `matching` o editar `policies.yaml` la cambia."""
    policies = get_policies()
    embedder = embeddings.get_embedder()
    config = {
        "scorer": scorer.SCORER_VERSION,
        "scoring": policies.scoring.model_dump(mode="json", exclude={"triage_threshold"}),
        "hard_filters": policies.hard_filters.model_dump(mode="json"),
        "aliases": {k: sorted(v) for k, v in get_skill_aliases().items()},
        "embeddings": embedder.model_name if embedder else None,
    }
    raw = json.dumps(config, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def compute_match(session: Session, job_id: int) -> Match:
    """Calcula y guarda un match nuevo con la extracción y el perfil vigentes (evento `scored`)."""
    job = _job(session, job_id)
    ext_row = _latest_extraction(session, job_id)
    stored = profiles.current(session)
    ext = JobExtraction.model_validate(ext_row.data)
    policies = get_policies()
    filters = hard_filters.evaluate(job.title, ext, stored.profile, policies.hard_filters)
    result = scorer.score(
        job.title, ext, stored.profile, policies.scoring, embeddings.get_embedder()
    )
    match = Match(
        job_id=job_id,
        profile_version_id=stored.profile_version_id,
        extraction_id=ext_row.id,
        scoring_key=scoring_key(),
        hard_filters=filters.model_dump(mode="json"),
        score=result.score,
        breakdown=result.breakdown.model_dump(mode="json"),
        assessment=None,
    )
    session.add(match)
    session.flush()
    if _stage(session, job_id) in OPEN_STAGES:
        events.record(
            session,
            job_id,
            EventType.SCORED,
            Actor.SYSTEM,
            payload={"match_id": match.id, "score": match.score, "passed": filters.passed},
        )
    return match


def _matches(session: Session, job_id: int) -> list[Match]:
    stmt = select(Match).where(Match.job_id == job_id).order_by(Match.id.desc())
    return list(session.scalars(stmt))


def _is_fresh(match: Match, extraction_id: int, profile_version_id: int, key: str) -> bool:
    return (
        match.extraction_id == extraction_id
        and match.profile_version_id == profile_version_id
        and match.scoring_key == key
    )


def current_match(session: Session, job_id: int) -> Match:
    """El match vigente de la oferta; lo calcula si no hay o si está desfasado."""
    _job(session, job_id)
    ext_row = _latest_extraction(session, job_id)
    profile_version_id = profiles.current(session).profile_version_id
    history = _matches(session, job_id)
    if history and _is_fresh(history[0], ext_row.id, profile_version_id, scoring_key()):
        return history[0]
    return compute_match(session, job_id)


def _view(match: Match, history: Sequence[Match]) -> MatchView:
    threshold = get_policies().scoring.triage_threshold
    assessed = next((m for m in history if m.assessment is not None), None)
    return MatchView(
        job_id=match.job_id,
        match_id=match.id,
        profile_version_id=match.profile_version_id,
        extraction_id=match.extraction_id,
        score=match.score,
        triage_threshold=threshold,
        below_threshold=match.score < threshold,
        hard_filters=HardFilterResult.model_validate(match.hard_filters),
        breakdown=ScoreBreakdown.model_validate(match.breakdown),
        assessment=FitAssessment.model_validate(assessed.assessment) if assessed else None,
        assessment_stale=assessed is not None and assessed.id != match.id,
        created_at=match.created_at,
    )


def get_match(session: Session, job_id: int) -> MatchView:
    """Filtros duros, score y desglose vigentes (se recalculan si estaban desfasados)."""
    match = current_match(session, job_id)
    return _view(match, _matches(session, job_id))


def save_fit_assessment(
    session: Session, job_id: int, assessment: FitAssessment, agent_name: str | None = None
) -> SaveAssessmentResult:
    """Guarda la valoración del agente en el match vigente y registra `fit_assessed`."""
    match = current_match(session, job_id)
    events.record(
        session,
        job_id,
        EventType.FIT_ASSESSED,
        Actor.AGENT,
        payload={"match_id": match.id, "verdict": assessment.verdict},
        agent_name=agent_name,
    )
    match.assessment = assessment.model_dump(mode="json")
    session.flush()
    return SaveAssessmentResult(ok=True, job_id=job_id, match_id=match.id)


def match_views(session: Session, job_ids: Sequence[int]) -> dict[int, MatchView]:
    """El match vigente de varias ofertas (calcula los que falten). Omite las que no tienen
    extracción; sin perfil importado devuelve `{}`."""
    try:
        profiles.current(session)
    except profiles.ProfileNotFoundError:
        return {}
    views: dict[int, MatchView] = {}
    for job_id in job_ids:
        try:
            views[job_id] = get_match(session, job_id)
        except ExtractionNotFoundError:
            continue
    return views


def latest_scores(session: Session, job_ids: Sequence[int]) -> dict[int, int]:
    """Score del último match de cada oferta (aunque esté desfasado), para listar y ordenar."""
    if not job_ids:
        return {}
    last = (
        select(func.max(Match.id))
        .where(Match.job_id.in_(job_ids))
        .group_by(Match.job_id)
        .scalar_subquery()
    )
    rows = session.execute(select(Match.job_id, Match.score).where(Match.id.in_(last)))
    return {job_id: score for job_id, score in rows}


def rescore_open_jobs(session: Session) -> RescoreResult:
    """Recalcula las ofertas abiertas con extracción cuyo match esté desfasado (perfil nuevo,
    puntuación cambiada…) y cierra las de `pending_triage` que no pasan los filtros.

    Sin perfil importado lanza `ProfileNotFoundError`: no hay con qué puntuar."""
    profiles.current(session)
    job_ids = session.scalars(
        select(Application.job_id)
        .where(Application.stage.in_([s.value for s in OPEN_STAGES]))
        .order_by(Application.job_id)
    ).all()
    latest = extractions.latest_rows(session, list(job_ids))
    scored, closed = 0, []
    for job_id in job_ids:
        if job_id not in latest:
            continue
        match = current_match(session, job_id)
        scored += 1
        result = HardFilterResult.model_validate(match.hard_filters)
        if _close_if_filtered(session, job_id, result):
            closed.append(job_id)
    return RescoreResult(scored=scored, closed=closed)
