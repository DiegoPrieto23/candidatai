"""Contraseñas en el llavero del sistema (fase 41.5), con uno falso en memoria: nunca el real.

Guardar y leer de él, la vuelta a `.env` donde no lo hay, Docker (variables y secretos montados), el
paso de `.env` al llavero con confirmación, `cai doctor` y que ningún valor sale por la API ni por
los logs.
"""

import logging
from collections.abc import Iterator
from pathlib import Path

import keyring
import pytest
from fastapi.testclient import TestClient
from keyring.backends import fail
from sqlalchemy.orm import Session

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import env_file, migrations, secrets
from app.core.config import get_settings
from app.schemas.mail_sources import MailSourceInput, MailSourcePatch
from app.services import doctor, mail_sources, secret_storage
from app.services.ingestion import adzuna
from tests.fake_keyring import MemoryKeyring

JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}
PASSWORD = "abcd efgh ijkl mnop"
SERVICE = secrets.SERVICE


def _imap(label: str = "Gmail", **extra: object) -> MailSourceInput:
    data = {"label": label, "host": "imap.gmail.com", "user": "ana@example.com"}
    return MailSourceInput.model_validate(data | {"password": PASSWORD} | extra)


def _env_text() -> str:
    path = env_file.env_path()
    return path.read_text(encoding="utf-8") if path.exists() else ""


# --- Dónde se guarda -----------------------------------------------------------------------------


def test_with_a_keyring_the_password_never_touches_the_file(
    session: Session, keyring_store: MemoryKeyring
) -> None:
    result = mail_sources.create_mail_source(session, _imap())
    ref = result.source.secret_ref
    assert ref == "CAI_IMAP_GMAIL_PASSWORD"
    assert keyring_store.values == {(SERVICE, ref): PASSWORD}
    assert PASSWORD not in _env_text() and ref not in _env_text()
    assert result.source.password_storage == "keyring" and result.source.has_password
    assert mail_sources.list_mail_sources(session).keyring is True

    row = mail_sources._get(session, result.source.id)
    assert mail_sources.account_of(row).password == PASSWORD

    mail_sources.update_mail_source(
        session, row.id, MailSourcePatch.model_validate({"password": "nueva"})
    )
    assert keyring_store.values[(SERVICE, ref)] == "nueva"

    mail_sources.delete_mail_source(session, row.id)
    assert keyring_store.values == {}


def test_without_a_keyring_it_goes_to_the_file_and_says_so(session: Session) -> None:
    # Los tests van con `CAI_SECRET_STORE=file`: como un Linux sin sesión gráfica.
    assert not secrets.keyring_available()
    result = mail_sources.create_mail_source(session, _imap())
    assert result.source.password_storage == "file"
    assert "CAI_IMAP_GMAIL_PASSWORD=" in _env_text()
    assert mail_sources.list_mail_sources(session).keyring is False


@pytest.mark.parametrize("broken", ["fail_backend", "probe_raises"])
def test_a_missing_or_broken_keyring_counts_as_none(
    broken: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Locked(MemoryKeyring):
        def get_password(self, service: str, username: str) -> str | None:
            raise RuntimeError("org.freedesktop.DBus.Error.ServiceUnknown")

    keyring.set_keyring(fail.Keyring() if broken == "fail_backend" else Locked())
    monkeypatch.setenv("CAI_SECRET_STORE", "auto")
    secrets.reset()
    assert not secrets.keyring_available()
    assert secrets.store("CAI_IMAP_X_PASSWORD", "x") == "file"


def test_the_environment_wins_and_docker_reads_mounted_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, keyring_store: MemoryKeyring
) -> None:
    keyring_store.set_password(SERVICE, "CAI_IMAP_A_PASSWORD", "del-llavero")
    assert secrets.location("CAI_IMAP_A_PASSWORD") == "keyring"
    monkeypatch.setenv("CAI_IMAP_A_PASSWORD", "del-entorno")
    assert secrets.get("CAI_IMAP_A_PASSWORD") == "del-entorno"
    assert secrets.location("CAI_IMAP_A_PASSWORD") == "environment"

    folder = tmp_path / "run-secrets"
    folder.mkdir()
    (folder / "CAI_ADZUNA_APP_KEY").write_text("clave-montada\n", encoding="utf-8")
    monkeypatch.setenv("CAI_SECRETS_DIR", str(folder))
    assert secrets.get(secrets.ADZUNA_APP_KEY) == "clave-montada"
    assert secrets.location(secrets.ADZUNA_APP_KEY) == "environment"


def test_in_docker_nothing_is_stored_and_the_ui_gets_what_to_add(
    session: Session, monkeypatch: pytest.MonkeyPatch, keyring_store: MemoryKeyring
) -> None:
    monkeypatch.setenv("CAI_IN_DOCKER", "1")
    get_settings.cache_clear()
    secrets.reset()
    assert not secrets.keyring_available()  # aunque lo haya: el contenedor no tiene sesión
    result = mail_sources.create_mail_source(session, _imap())
    assert result.env_line == "CAI_IMAP_GMAIL_PASSWORD=…"
    assert result.source.has_password is False and keyring_store.values == {}
    assert "CAI_" not in result.message and ".env" not in result.message
    report = doctor.check_secrets(get_settings())
    assert report.status == doctor.CheckStatus.OK and "contenedor" in report.detail


def test_a_failing_keyring_falls_back_to_the_file_without_old_values(
    monkeypatch: pytest.MonkeyPatch, keyring_store: MemoryKeyring
) -> None:
    keyring_store.set_password(SERVICE, "CAI_IMAP_A_PASSWORD", "vieja")

    def broken(service: str, username: str, password: str) -> None:
        raise OSError("llavero bloqueado")  # no es un `KeyringError`: también se recoge

    monkeypatch.setattr(keyring_store, "set_password", broken)
    assert secrets.store("CAI_IMAP_A_PASSWORD", "nueva") == "file"
    assert secrets.get("CAI_IMAP_A_PASSWORD") == "nueva"  # la vieja no la tapa
    assert secrets.location("CAI_IMAP_A_PASSWORD") == "file"


def test_storing_clears_process_variables_and_their_old_alias(
    monkeypatch: pytest.MonkeyPatch, keyring_store: MemoryKeyring
) -> None:
    monkeypatch.setenv("JH_IMAP_PASSWORD", "antigua")
    assert secrets.get(secrets.IMAP_PASSWORD) == "antigua"
    assert secrets.store(secrets.IMAP_PASSWORD, "nueva") == "keyring"
    assert secrets.get(secrets.IMAP_PASSWORD) == "nueva"


def test_moving_keeps_the_value_already_in_the_keyring(keyring_store: MemoryKeyring) -> None:
    keyring_store.set_password(SERVICE, "CAI_IMAP_A_PASSWORD", "en-uso")
    env_file.write_secret("CAI_IMAP_A_PASSWORD", "del-fichero")
    assert secrets.move_to_keyring("CAI_IMAP_A_PASSWORD")
    assert keyring_store.values[(SERVICE, "CAI_IMAP_A_PASSWORD")] == "en-uso"
    assert "CAI_IMAP_A_PASSWORD" not in _env_text()


# --- De `.env` al llavero ------------------------------------------------------------------------


def test_moving_plaintext_secrets_keeps_the_rest_of_the_file(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    gmail = mail_sources.create_mail_source(session, _imap()).source  # en `.env`: sin llavero
    path = env_file.env_path()
    path.write_text(
        _env_text() + "# mío\nCAI_ADZUNA_APP_ID=id\nJH_ADZUNA_APP_KEY=clave-antigua\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CAI_ADZUNA_APP_ID", "id")
    get_settings.cache_clear()

    plain = secret_storage.list_plaintext(session)
    assert plain.keyring is False
    assert {(s.name, s.kind, s.label) for s in plain.secrets} == {
        ("CAI_IMAP_GMAIL_PASSWORD", "mailbox", "Gmail"),
        ("CAI_ADZUNA_APP_KEY", "adzuna", None),
    }
    refused = secret_storage.move_to_keyring(session, ["CAI_IMAP_GMAIL_PASSWORD"])
    assert refused.moved == []
    assert "CAI_IMAP_GMAIL_PASSWORD" in _env_text()  # sin llavero, se queda como estaba

    store = MemoryKeyring()
    keyring.set_keyring(store)
    monkeypatch.setenv("CAI_SECRET_STORE", "auto")
    secrets.reset()
    result = secret_storage.move_to_keyring(
        session, ["CAI_IMAP_GMAIL_PASSWORD", "CAI_ADZUNA_APP_KEY", "PATH", "CAI_DATA_DIR"]
    )
    assert result.moved == ["CAI_IMAP_GMAIL_PASSWORD", "CAI_ADZUNA_APP_KEY"]
    assert result.failed == []  # lo que no es un secreto de la app ni se intenta
    assert store.values == {
        (SERVICE, "CAI_IMAP_GMAIL_PASSWORD"): PASSWORD,
        (SERVICE, "CAI_ADZUNA_APP_KEY"): "clave-antigua",
    }
    assert _env_text() == "# mío\nCAI_ADZUNA_APP_ID=id\n"
    assert secret_storage.list_plaintext(session).secrets == []
    assert mail_sources.get_mail_source(session, gmail.id).password_storage == "keyring"
    assert adzuna._keys() == {"app_id": "id", "app_key": "clave-antigua"}


def test_doctor_warns_about_plaintext_secrets(
    session: Session, monkeypatch: pytest.MonkeyPatch, keyring_store: MemoryKeyring
) -> None:
    migrations.upgrade()
    assert doctor.check_secrets(get_settings()).status == doctor.CheckStatus.OK
    env_file.write_secret("CAI_INFOJOBS_CLIENT_SECRET", "s3creto")
    report = doctor.check_secrets(get_settings())
    assert report.status == doctor.CheckStatus.WARN
    assert "CAI_INFOJOBS_CLIENT_SECRET" in report.detail and "s3creto" not in report.detail
    assert "llavero" in report.detail


# --- Nada en claro hacia fuera -------------------------------------------------------------------


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app(), base_url="http://127.0.0.1:8000") as client:
        yield client


def test_api_and_logs_never_carry_a_secret(
    client: TestClient,
    keyring_store: MemoryKeyring,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    env_file.write_secret("CAI_ADZUNA_APP_KEY", "clave-en-claro")
    body = {"label": "Trabajo", "host": "imap.example.com", "user": "ana@example.com"}
    texts = [client.post("/mail-sources", json=body | {"password": PASSWORD}, headers=JSON).text]
    texts.append(client.get("/mail-sources", headers={"Origin": UI_ORIGIN}).text)

    plain = client.get("/secrets/plaintext", headers={"Origin": UI_ORIGIN})
    assert plain.status_code == 200
    assert [s["name"] for s in plain.json()["secrets"]] == ["CAI_ADZUNA_APP_KEY"]
    texts.append(plain.text)
    # Mover es una acción de la UI: una web de fuera no puede pedirlo.
    evil = {"Origin": "https://example.com", "Content-Type": "application/json"}
    assert (
        client.post("/secrets/move-to-keyring", json={"names": ["x"]}, headers=evil).status_code
        == 403
    )
    moved = client.post(
        "/secrets/move-to-keyring", json={"names": ["CAI_ADZUNA_APP_KEY"]}, headers=JSON
    )
    assert moved.json()["moved"] == ["CAI_ADZUNA_APP_KEY"]
    texts.append(moved.text)
    texts.append(client.get("/mail-sources", headers={"Origin": UI_ORIGIN}).text)

    logs = "\n".join(record.getMessage() for record in caplog.records)
    for text in [*texts, logs]:
        assert PASSWORD not in text and "clave-en-claro" not in text
    assert "clave-en-claro" not in _env_text()
