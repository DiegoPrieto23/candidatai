"""Umbral antes de gastar (fase 25.4): «Evaluar encaje» en segundo plano solo valora las ofertas con
score suficiente. Las demás se quedan sin valorar, con el motivo en la UI. El skill en una terminal
sigue valorando lo que le pidas.

El umbral sale, por este orden, de la página «Agente» (`agent_preferences`, `scope="setting"`, el
número en `model`), de `background_runs.assess_min_score` de `config/policies.yaml` o, si no, del
de triaje menos `DEFAULT_GAP`.
"""

from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.models import AgentPreference
from app.services import jobs
from app.services.matching import service as matching
from app.services.pipeline import Stage

SCOPE, KEY = "setting", "assess_min_score"
DEFAULT_GAP = 10
MAX_JOBS = 30  # ofertas por ejecución: más alargaría la orden y la ejecución

Source = Literal["ui", "policies", "default"]


class AssessThreshold(BaseModel):
    value: int  # el que se aplica
    source: Source
    triage_threshold: int
    default: int  # el de `policies.yaml` o, si no hay, el de triaje menos 10


class AssessThresholdInput(BaseModel):
    value: int | None = Field(ge=0, le=100)  # `None`: vuelve al de `policies.yaml`


class AssessPlan(BaseModel):
    """Las pendientes de triaje sin valoración vigente, partidas por el umbral."""

    threshold: int
    eligible: list[int]  # las que valora la ejecución (como mucho `MAX_JOBS`)
    skipped: dict[int, int]  # oferta → su score, por debajo del umbral


def prompt(assess: AssessPlan) -> str:
    """La orden de la ejecución: solo con los ids de las que pasan (números, ningún texto)."""
    ids = ", ".join(str(job_id) for job_id in assess.eligible)
    return (
        f"Usa el skill assess-fit de CandidatAI con las ofertas {ids}. Solo esas: las demás "
        f"pendientes tienen un score por debajo de {assess.threshold} y no se valoran en segundo "
        "plano."
    )


def _stored(session: Session) -> AgentPreference | None:
    return session.scalars(
        select(AgentPreference).where(AgentPreference.scope == SCOPE, AgentPreference.key == KEY)
    ).first()


def get_threshold(session: Session) -> AssessThreshold:
    policies = get_policies()
    triage = policies.scoring.triage_threshold
    configured = policies.background_runs.assess_min_score
    default = configured if configured is not None else max(0, triage - DEFAULT_GAP)
    row = _stored(session)
    if row is not None and row.model is not None and row.model.isdigit():
        return AssessThreshold(
            value=int(row.model), source="ui", triage_threshold=triage, default=default
        )
    source: Source = "policies" if configured is not None else "default"
    return AssessThreshold(value=default, source=source, triage_threshold=triage, default=default)


def set_threshold(session: Session, data: AssessThresholdInput) -> AssessThreshold:
    session.execute(
        delete(AgentPreference).where(AgentPreference.scope == SCOPE, AgentPreference.key == KEY)
    )
    if data.value is not None:
        session.add(AgentPreference(scope=SCOPE, key=KEY, model=str(data.value)))
    session.flush()
    return get_threshold(session)


def plan(session: Session, threshold: int | None = None) -> AssessPlan:
    """`threshold`: otro umbral solo para esta vez (la matriz de `cai eval compat` usa 0)."""
    threshold = get_threshold(session).value if threshold is None else threshold
    page = jobs.search_jobs(session, stage=Stage.PENDING_TRIAGE.value, limit=jobs.MAX_LIMIT)
    views = matching.match_views(session, [row.id for row in page.items])
    eligible: list[tuple[int, int]] = []
    skipped: dict[int, int] = {}
    for job_id, view in views.items():
        if view.assessment is not None and not view.assessment_stale:
            continue  # ya valorada con este cálculo
        if view.score >= threshold:
            eligible.append((view.score, job_id))
        else:
            skipped[job_id] = view.score
    eligible.sort(reverse=True)  # las de más score primero
    return AssessPlan(
        threshold=threshold,
        eligible=[job_id for _, job_id in eligible[:MAX_JOBS]],
        skipped=dict(sorted(skipped.items())),
    )
