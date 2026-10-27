"""Salida de la analítica (embudo, calibración e historia) sobre una base sintética fija.

`tests/test_analytics_equivalence.py` la compara con `tests/fixtures/analytics_synthetic.json`,
que se generó con las consultas de antes de optimizarlas: si cambian las consultas, los números
no pueden cambiar. Si cambia el generador (`synthetic.py`) o lo que mide la analítica, regenera el
fichero desde `backend/` y revisa el diff:

    uv run python -m tests.perf.analytics_snapshot
"""

import json
from datetime import date
from pathlib import Path
from types import ModuleType
from typing import Any

from sqlalchemy.orm import Session

FIXTURE = Path(__file__).parents[1] / "fixtures" / "analytics_synthetic.json"
JOBS = 400
SINCE = date(2026, 8, 1)


def outputs(session: Session, analytics: ModuleType | None = None) -> dict[str, Any]:
    """Lo que devuelve cada vista de la analítica, en JSON (con y sin `since`)."""
    if analytics is None:
        from app.services import analytics
    assert analytics is not None
    calls = {
        "funnel": lambda: analytics.get_funnel_stats(session),
        "funnel_since": lambda: analytics.get_funnel_stats(session, SINCE),
        "calibration": lambda: analytics.get_calibration(session),
        "calibration_since": lambda: analytics.get_calibration(session, SINCE, min_cases=5),
        "story": lambda: analytics.get_search_story(session),
    }
    return {name: call().model_dump(mode="json") for name, call in calls.items()}


def main() -> None:
    import os
    import tempfile

    with tempfile.TemporaryDirectory(prefix="cai-snapshot-") as tmp:
        os.environ.update({"CAI_DATA_DIR": tmp, "CAI_EMBEDDINGS": "off"})
        os.environ.pop("CAI_DB_URL", None)
        from app.core import migrations
        from app.core.db import get_engine, session_scope
        from tests.perf.synthetic import populate

        migrations.upgrade()
        with session_scope() as session:
            populate(session, jobs=JOBS)
            data = outputs(session)
        get_engine().dispose()
    text = json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True)
    FIXTURE.write_text(text + "\n", encoding="utf-8")
    print(f"Escrito {FIXTURE}")


if __name__ == "__main__":
    main()
