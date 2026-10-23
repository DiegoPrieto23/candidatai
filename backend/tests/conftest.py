import os
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
    # Las `JH_*` de antes de la fase 23 se leen como respaldo: ninguna del usuario en los tests.
    for name in [n for n in os.environ if n.upper().startswith("JH_")]:
        monkeypatch.delenv(name)
    monkeypatch.setenv("CAI_DATA_DIR", str(data_dir))
    monkeypatch.delenv("CAI_DB_URL", raising=False)
    monkeypatch.delenv("SOFFICE_PATH", raising=False)
    monkeypatch.delenv("CAI_CLIENT_NAME", raising=False)
    monkeypatch.setenv("CAI_IN_DOCKER", "false")  # fase 26.3: ni aunque los tests corran en Docker
    # Sin IMAP aunque el `.env` del usuario lo configure (las variables mandan sobre `.env`).
    for name in ("CAI_IMAP_HOST", "CAI_IMAP_USER", "CAI_IMAP_PASSWORD"):
        monkeypatch.setenv(name, "")
    monkeypatch.setenv("CAI_IMAP_FOLDER", "INBOX")
    # Fase 27.4: las contraseñas de los buzones se escriben en un `.env` del test, nunca en el tuyo.
    monkeypatch.setenv("CAI_ENV_FILE", str(tmp_path / ".env"))
    for name in [n for n in os.environ if n.startswith("CAI_IMAP_") and n.endswith("_PASSWORD")]:
        if name != "CAI_IMAP_PASSWORD":
            monkeypatch.delenv(name)
    # Sin modelo de embeddings en los tests: nada de descargas; los que lo necesitan usan uno falso.
    monkeypatch.setenv("CAI_EMBEDDINGS", "off")
    # Sin el Ollama de quien ejecuta los tests (fase 24.6): un puerto donde no escucha nada.
    monkeypatch.setenv("CAI_OLLAMA_URL", "http://127.0.0.1:9")
    monkeypatch.delenv("OLLAMA_CONTEXT_LENGTH", raising=False)
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


@pytest.fixture(autouse=True)
def no_layout(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """La maquetación del PDF (fase 25.5) mira posiciones reales: con el conversor falso (una línea
    por párrafo) daría avisos sin sentido. Los tests que la prueban llevan `@pytest.mark.layout`."""
    from app.services.documents import layout

    if request.node.get_closest_marker("layout") is None:
        monkeypatch.setattr(layout, "ENABLED", False)


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
