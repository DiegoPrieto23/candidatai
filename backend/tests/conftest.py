from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_engine, make_engine
from app.models import Base, Company, Job, Source


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Cada test usa su propio directorio de datos y sin variables heredadas del usuario."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("JH_DATA_DIR", str(data_dir))
    monkeypatch.delenv("JH_DB_URL", raising=False)
    monkeypatch.delenv("SOFFICE_PATH", raising=False)
    monkeypatch.delenv("JH_CLIENT_NAME", raising=False)
    # Sin IMAP aunque el `.env` del usuario lo configure (las variables mandan sobre `.env`).
    for name in ("JH_IMAP_HOST", "JH_IMAP_USER", "JH_IMAP_PASSWORD"):
        monkeypatch.setenv(name, "")
    monkeypatch.setenv("JH_IMAP_FOLDER", "INBOX")
    # Sin modelo de embeddings en los tests: nada de descargas; los que lo necesitan usan uno falso.
    monkeypatch.setenv("JH_EMBEDDINGS", "off")
    get_settings.cache_clear()
    get_engine.cache_clear()
    yield data_dir
    get_engine.cache_clear()
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def no_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin red: «¿sigue abierta?» resuelve los dominios (fase 16); aquí todos son públicos."""
    from app.services import liveness

    monkeypatch.setattr(liveness, "_resolve", lambda _host: ["93.184.215.14"])


@pytest.fixture
def engine(isolated_env: Path) -> Iterator[Engine]:
    """Engine sobre SQLite temporal con el esquema de los modelos."""
    isolated_env.mkdir(parents=True, exist_ok=True)
    engine = make_engine(f"sqlite:///{(isolated_env / 'test.db').as_posix()}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    with Session(engine) as session:
        yield session


@pytest.fixture
def make_job(session: Session) -> Callable[..., Job]:
    """Crea una oferta mínima (con su fuente y empresa) sin eventos."""
    counter = iter(range(1, 10_000))

    def _make(title: str = "Data Engineer") -> Job:
        n = next(counter)
        source = Source(kind="manual_text", name="Manual")
        company = Company(name=f"Acme {n}", normalized_name=f"acme {n}")
        session.add_all([source, company])
        session.flush()
        job = Job(
            source_id=source.id,
            company_id=company.id,
            url=f"https://example.com/jobs/{n}",
            title=title,
            raw_text="Texto de ejemplo.",
            fingerprint=f"fp-{n}",
        )
        session.add(job)
        session.flush()
        return job

    return _make
