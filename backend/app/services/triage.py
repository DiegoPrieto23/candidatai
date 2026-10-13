"""Cola de triaje para la UI: ofertas en `pending_triage` con su match, ordenadas por score.

Los matches que falten o estén desfasados se calculan al pedir la cola (el worker los adelanta):
así el triaje funciona aunque `cai worker` no esté en marcha.
"""

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.schemas.llm_io import JobExtraction
from app.services import extractions, jobs
from app.services import profile as profiles
from app.services.matching import service as matching
from app.services.pipeline import Stage

MAX_QUEUE = jobs.MAX_LIMIT


class TriageItem(BaseModel):
    job: jobs.JobRow
    extraction: JobExtraction | None
    match: matching.MatchView | None  # None si aún no hay perfil importado


class TriageQueue(BaseModel):
    items: list[TriageItem]
    total: int  # ofertas en `pending_triage` (puede haber más que `items`)
    triage_threshold: int
    profile_missing: bool  # sin perfil no hay score: la UI lo avisa


def triage_queue(session: Session, limit: int = MAX_QUEUE) -> TriageQueue:
    page = jobs.search_jobs(session, stage=Stage.PENDING_TRIAGE.value, limit=limit)
    ids = [row.id for row in page.items]
    views = matching.match_views(session, ids)
    latest = extractions.latest_rows(session, ids)
    items = []
    for row in page.items:
        view = views.get(row.id)
        ext_row = latest.get(row.id)
        if view is not None:
            row = row.model_copy(update={"score": view.score})
        items.append(
            TriageItem(
                job=row,
                extraction=JobExtraction.model_validate(ext_row.data) if ext_row else None,
                match=view,
            )
        )
    # Mayor score primero; sin score al final. `sorted` es estable: a igual score, las más
    # recientes primero (el orden de `search_jobs`).
    items.sort(key=lambda item: -item.match.score if item.match else 1)
    try:
        profiles.current(session)
        profile_missing = False
    except profiles.ProfileNotFoundError:
        profile_missing = True
    return TriageQueue(
        items=items,
        total=page.total,
        triage_threshold=get_policies().scoring.triage_threshold,
        profile_missing=profile_missing,
    )
