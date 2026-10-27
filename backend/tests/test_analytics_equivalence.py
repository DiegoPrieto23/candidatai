"""La analítica da los mismos números que antes de optimizar sus consultas.

`tests/fixtures/analytics_synthetic.json` es la salida de las consultas anteriores (una subconsulta
por oferta y paso) sobre la base sintética de `tests/perf/synthetic.py`. Ver
`tests/perf/analytics_snapshot.py` para regenerarlo. Regenerado con el código nuevo, ya solo
vigila que no cambie nada (regresión), no la equivalencia con el de antes.
"""

import json

from app.core import migrations
from app.core.db import session_scope
from tests.perf import analytics_snapshot
from tests.perf.synthetic import populate


def test_analytics_matches_snapshot() -> None:
    migrations.upgrade()
    with session_scope() as session:
        populate(session, jobs=analytics_snapshot.JOBS)
    with session_scope() as session:
        current = analytics_snapshot.outputs(session)
    expected = json.loads(analytics_snapshot.FIXTURE.read_text(encoding="utf-8"))
    for name, value in expected.items():
        assert current[name] == value, name
