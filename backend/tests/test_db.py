"""Engine, sesión y tipos de columna."""

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.core.db import get_engine, session_scope
from app.models import Company, Job, Source


def test_sqlite_pragmas(engine: Engine) -> None:
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert conn.execute(text("PRAGMA synchronous")).scalar() == 1  # NORMAL
        assert conn.execute(text("PRAGMA temp_store")).scalar() == 2  # MEMORY
        assert conn.execute(text("PRAGMA cache_size")).scalar() == -16000
        # Una escritura espera a otra que tarde (un PDF con LibreOffice) en vez de fallar a los 5 s
        # con «database is locked», que tumbaba el worker y con él la app. Más que el tope de la
        # conversión a PDF de la política.
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 90_000


def test_the_busy_timeout_outlasts_the_pdf_conversion() -> None:
    from app.core.db import SQLITE_BUSY_TIMEOUT
    from app.core.policies import get_policies

    assert get_policies().cv.pdf_timeout_seconds < SQLITE_BUSY_TIMEOUT


def test_get_engine_uses_settings(isolated_env: Path) -> None:
    engine = get_engine()
    assert engine.url.database == (isolated_env / "candidatai.db").as_posix()
    assert get_engine() is engine


def test_foreign_keys_enforced(engine: Engine) -> None:
    with pytest.raises(IntegrityError), session_scope(engine) as session:
        session.add(
            Job(
                source_id=99,
                company_id=99,
                url="https://example.com",
                title="x",
                raw_text="x",
                fingerprint="fp",
            )
        )


def test_session_scope_commits_and_rolls_back(engine: Engine) -> None:
    with session_scope(engine) as session:
        session.add(Company(name="Acme", normalized_name="acme"))
    with pytest.raises(RuntimeError), session_scope(engine) as session:
        session.add(Company(name="Globex", normalized_name="globex"))
        session.flush()
        raise RuntimeError("fallo")
    with session_scope(engine) as session:
        names = [c.normalized_name for c in session.query(Company)]
    assert names == ["acme"]


def test_utc_datetime_roundtrip(session: Session) -> None:
    madrid = timezone(timedelta(hours=2))
    run_at = datetime(2026, 9, 1, 11, tzinfo=madrid)
    source = Source(kind="greenhouse", name="GH", last_run_at=run_at)
    session.add(source)
    session.commit()
    session.expire_all()
    assert source.last_run_at == datetime(2026, 9, 1, 9, tzinfo=UTC)
    assert source.last_run_at is not None and source.last_run_at.tzinfo is UTC


def test_utc_datetime_rejects_naive(session: Session) -> None:
    session.add(Source(kind="lever", name="L", last_run_at=datetime(2026, 9, 1)))
    with pytest.raises(StatementError, match="zona horaria"):
        session.flush()


def test_a_savepoint_waits_for_another_writer_instead_of_failing(tmp_path: Path) -> None:
    # Una transacción con SAVEPOINT (descartar una oferta) que lee y después escribe, mientras el
    # worker escribe desde otra conexión: antes fallaba al instante con «database is locked».
    import threading

    from app.core.db import make_engine

    url = f"sqlite:///{tmp_path / 't.db'}"
    api, worker = make_engine(url), make_engine(url)
    with api.begin() as conn:
        conn.execute(text("CREATE TABLE t (x INTEGER)"))
    has_read, worker_done = threading.Event(), threading.Event()

    def worker_writes() -> None:
        has_read.wait(5)
        with worker.begin() as conn:
            conn.execute(text("INSERT INTO t VALUES (1)"))
        worker_done.set()

    thread = threading.Thread(target=worker_writes)
    thread.start()
    with session_scope(api) as session, session.begin_nested():
        session.execute(text("SELECT count(*) FROM t")).all()
        has_read.set()
        worker_done.wait(0.5)  # sin el arreglo, el worker escribe aquí y el INSERT ya no puede
        session.execute(text("INSERT INTO t VALUES (2)"))
    thread.join(10)
    with api.connect() as conn:
        assert sorted(conn.execute(text("SELECT x FROM t")).scalars()) == [1, 2]
