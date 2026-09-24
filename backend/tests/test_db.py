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


def test_get_engine_uses_settings(isolated_env: Path) -> None:
    engine = get_engine()
    assert engine.url.database == (isolated_env / "jobhunter.db").as_posix()
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
