"""Las tablas temporales de la analítica no se quedan en la conexión, ni con commit ni con
rollback (lo normal en una lectura de la API o del servidor MCP)."""

import pytest
from sqlalchemy import text

from app.core import migrations
from app.core.db import get_engine, get_sessionmaker, session_scope
from app.services import analytics
from tests.perf.synthetic import populate


@pytest.mark.parametrize("end", ["commit", "rollback"])
def test_temp_tables_are_gone_after_the_call(end: str) -> None:
    migrations.upgrade()
    with session_scope() as session:
        populate(session, jobs=30)
    get_engine().dispose()
    session = get_sessionmaker()()
    try:
        analytics.get_funnel_stats(session)
        analytics.get_calibration(session)
        analytics.get_search_story(session)
        getattr(session, end)()
        names = session.execute(text("SELECT name FROM sqlite_temp_master")).scalars().all()
        assert names == []
    finally:
        session.close()
