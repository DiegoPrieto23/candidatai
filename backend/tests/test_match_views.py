"""`match_views` (la lista de «Por revisar») da lo mismo que `get_match` oferta a oferta."""

from sqlalchemy import func, select, update

from app.core import migrations
from app.core.db import session_scope
from app.models import Application, Match
from app.services.matching import service as matching
from tests.perf.synthetic import populate


def test_match_views_equal_get_match_one_by_one() -> None:
    migrations.upgrade()
    with session_scope() as session:
        populate(session, jobs=60)
        job_ids = list(
            session.scalars(select(Application.job_id).where(Application.stage == "pending_triage"))
        )
        assert len(job_ids) >= 3
        # Uno desfasado (otra huella de puntuación): la lista lo recalcula, como `get_match`.
        stale = session.scalar(select(func.max(Match.id)).where(Match.job_id == job_ids[0]))
        session.execute(update(Match).where(Match.id == stale).values(scoring_key="antigua"))
    with session_scope() as session:
        batch = matching.match_views(session, [*job_ids, 999999])
    assert list(batch) == job_ids
    assert batch[job_ids[0]].match_id > stale
    with session_scope() as session:
        for job_id in job_ids:
            assert batch[job_id] == matching.get_match(session, job_id)
