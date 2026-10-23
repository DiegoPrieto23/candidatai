"""Varios buzones de alertas (fase 27.4, ADR-045): contraseñas solo en `.env`, lectura de todos
los buzones activos en solo lectura y la cuenta `CAI_IMAP_*` de siempre como «Principal»."""

import imaplib
import json
import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import env_file, migrations
from app.core.config import get_settings
from app.core.db import session_scope
from app.models import Job, MailSource, MailSourceChange
from app.schemas.mail_sources import MailSourceInput, MailSourcePatch
from app.services import ingest, mail_sources
from app.services.ingestion.email import service as email_service
from tests.imap_support import FOLDER, PASSWORD, USER, fake_imap

FIXTURES = Path(__file__).parent / "fixtures" / "email"
LINKEDIN = (FIXTURES / "linkedin_alert.eml").read_bytes()
OTHER = (FIXTURES / "otro_remitente.eml").read_bytes()
INFOJOBS = (FIXTURES / "infojobs_alert.eml").read_bytes()
JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


def _plain(host: str, port: int, timeout: float) -> imaplib.IMAP4:
    return imaplib.IMAP4(host, port, timeout=timeout)


def _no_fetch(url: str) -> str:
    raise ingest.IngestError(f"sin red: {url}")


def _imap(label: str, port: int, **extra: Any) -> MailSourceInput:
    data = {
        "label": label,
        "host": "127.0.0.1",
        "port": port,
        "user": USER,
        "password": PASSWORD,
        "folder": FOLDER,
        "allow_private": True,  # el servidor falso escucha en 127.0.0.1
    }
    return MailSourceInput.model_validate(data | extra)


def _env_text() -> str:
    path = env_file.env_path()
    return path.read_text(encoding="utf-8") if path.exists() else ""


# --- `.env` -------------------------------------------------------------------------------------


def test_env_file_writes_only_its_line_atomically(isolated_env: Path) -> None:
    path = env_file.env_path()
    assert path.parent == isolated_env.parent  # el `.env` del test, nunca el tuyo
    path.write_bytes("# mío\r\nCAI_DATA_DIR=x\r\nCAI_IMAP_A_PASSWORD=viejo\r\n".encode())
    tricky = "a'b\\c $HOME ${X} #no"
    env_file.write_secret("CAI_IMAP_A_PASSWORD", tricky)
    text = path.read_bytes().decode()
    assert text.startswith("# mío\r\nCAI_DATA_DIR=x\r\n") and "viejo" not in text
    assert env_file.read_secret("CAI_IMAP_A_PASSWORD") == tricky  # sin expandir ni cortar
    assert not list(path.parent.glob(".env.*.tmp"))
    env_file.write_secret("CAI_IMAP_A_PASSWORD", None)
    assert env_file.read_secret("CAI_IMAP_A_PASSWORD") is None
    assert path.read_bytes().decode() == "# mío\r\nCAI_DATA_DIR=x\r\n"
    with pytest.raises(ValueError):
        env_file.write_secret("cai-x", "1")


def test_in_docker_the_password_is_not_stored(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAI_IN_DOCKER", "1")
    get_settings.cache_clear()
    with pytest.raises(env_file.SecretNotWritableError):
        env_file.write_secret("CAI_IMAP_A_PASSWORD", "x")
    result = mail_sources.create_mail_source(session, _imap("Trabajo", 993))
    assert result.env_line == "CAI_IMAP_TRABAJO_PASSWORD=…"
    assert "recrea Docker" in result.message and PASSWORD not in result.message
    assert not result.source.has_password
    assert not mail_sources.list_mail_sources(session).can_store_passwords


# --- Altas, cambios y bajas ---------------------------------------------------------------------


def test_create_stores_the_password_only_in_env(session: Session) -> None:
    result = mail_sources.create_mail_source(session, _imap("Gmail personal", 993))
    view = result.source
    assert view.secret_ref == "CAI_IMAP_GMAIL_PERSONAL_PASSWORD" and view.has_password
    assert f"CAI_IMAP_GMAIL_PERSONAL_PASSWORD='{PASSWORD}'" in _env_text()
    row = session.get(MailSource, view.id)
    assert row is not None and PASSWORD not in json.dumps(
        {c.name: str(getattr(row, c.name)) for c in MailSource.__table__.columns}
    )
    assert PASSWORD not in result.model_dump_json()
    assert PASSWORD not in mail_sources.list_mail_sources(session).model_dump_json()
    change = session.scalars(select(MailSourceChange)).one()
    assert change.action == "created" and "password" in change.fields
    assert PASSWORD not in json.dumps(change.fields)

    # Otro con el mismo alias: otra variable.
    other = mail_sources.create_mail_source(session, _imap("Gmail-personal!", 993)).source
    assert other.secret_ref == "CAI_IMAP_GMAIL_PERSONAL_2_PASSWORD"
    with pytest.raises(mail_sources.MailSourceExistsError):
        mail_sources.create_mail_source(session, _imap("gmail personal", 993))


def test_update_and_delete(session: Session) -> None:
    view = mail_sources.create_mail_source(session, _imap("Trabajo", 993)).source
    patch = MailSourcePatch.model_validate({"enabled": False, "password": "nueva"})
    updated = mail_sources.update_mail_source(session, view.id, patch).source
    assert not updated.enabled
    assert env_file.read_secret("CAI_IMAP_TRABAJO_PASSWORD") == "nueva"
    with pytest.raises(ValidationError):  # se valida el buzón entero, como en el alta
        mail_sources.update_mail_source(
            session, view.id, MailSourcePatch.model_validate({"host": "https://x.com"})
        )
    message = mail_sources.delete_mail_source(session, view.id)
    assert "quitado" in message
    assert "CAI_IMAP_TRABAJO_PASSWORD" not in _env_text()
    assert [c.action for c in session.scalars(select(MailSourceChange))] == [
        "created",
        "updated",
        "deleted",
    ]
    with pytest.raises(mail_sources.MailSourceNotFoundError):
        mail_sources.get_mail_source(session, view.id)


@pytest.mark.parametrize(
    ("changes", "fragment"),
    [
        ({"host": "https://imap.gmail.com"}, "Servidor no válido"),
        ({"host": "imap.gmail.com/x"}, "Servidor no válido"),
        ({"host": None}, "servidor y usuario"),
        ({"kind": "folder", "folder": "../fuera"}, "Carpeta no válida"),
        ({"kind": "folder", "folder": "respuestas"}, "otro uso"),
        ({"password": "con\nsalto"}, "saltos de línea"),
        ({"port": 0}, "greater than or equal"),
    ],
)
def test_invalid_mailboxes(changes: dict[str, Any], fragment: str) -> None:
    with pytest.raises(ValidationError, match=fragment):
        MailSourceInput.model_validate({"label": "X", "host": "imap.x.com", "user": "u"} | changes)


def test_private_hosts_need_explicit_permission(session: Session) -> None:
    for host in ("127.0.0.1", "10.0.0.5", "192.168.1.10", "::1"):
        result = mail_sources.probe_new_mail_source(
            _imap("X", 993, host=host, allow_private=False), _plain
        )
        assert (result.ok, result.code) == (False, "host_not_allowed"), host
        assert "Servidor en mi equipo o mi red" in result.message


# --- La cuenta de `.env` («Principal») ----------------------------------------------------------


def _configure_env(monkeypatch: pytest.MonkeyPatch, port: int, password: str = PASSWORD) -> None:
    for key, value in {
        "CAI_IMAP_HOST": "127.0.0.1",
        "CAI_IMAP_PORT": str(port),
        "CAI_IMAP_USER": USER,
        "CAI_IMAP_PASSWORD": password,
        "CAI_IMAP_FOLDER": FOLDER,
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def test_env_account_appears_as_principal(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert mail_sources.list_mail_sources(session).sources == []  # sin IMAP: lista vacía
    _configure_env(monkeypatch, 993)
    (principal,) = mail_sources.list_mail_sources(session).sources
    assert (principal.label, principal.from_env, principal.read_replies) == (
        "Principal",
        True,
        True,
    )
    assert (principal.host, principal.user, principal.folder) == ("127.0.0.1", USER, FOLDER)
    assert principal.has_password and principal.secret_ref == "CAI_IMAP_PASSWORD"
    # Se cambia en `.env`; aquí solo activarla, el nombre o si lee respuestas.
    with pytest.raises(mail_sources.MailSourceNotAllowedError, match="host"):
        mail_sources.update_mail_source(
            session, principal.id, MailSourcePatch.model_validate({"host": "imap.otro.com"})
        )
    with pytest.raises(mail_sources.MailSourceNotAllowedError, match="borra CAI_IMAP_HOST"):
        mail_sources.delete_mail_source(session, principal.id)
    mail_sources.update_mail_source(
        session, principal.id, MailSourcePatch.model_validate({"enabled": False})
    )
    assert mail_sources.active_sources(session) == []
    # Sin `.env`, desaparece de la lista (y no se lee).
    monkeypatch.setenv("CAI_IMAP_HOST", "")
    get_settings.cache_clear()
    assert mail_sources.list_mail_sources(session).sources == []


# --- Lectura -----------------------------------------------------------------------------------


def test_poll_reads_every_active_mailbox_once(
    session: Session, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """El de `.env`, uno añadido desde la UI con el mismo aviso reenviado (no se duplica), otro
    con la contraseña mal (no frena a los demás) y uno desactivado."""
    caplog.set_level(logging.DEBUG)
    with (
        fake_imap({7: LINKEDIN}) as env_server,
        fake_imap({3: LINKEDIN, 4: INFOJOBS}) as second,
        fake_imap({}) as broken,
        fake_imap({5: OTHER}) as disabled,
    ):
        _configure_env(monkeypatch, env_server.port)
        mail_sources.create_mail_source(session, _imap("Segundo", second.port))
        mail_sources.create_mail_source(session, _imap("Roto", broken.port, password="mala-clave"))
        mail_sources.create_mail_source(session, _imap("Apagado", disabled.port, enabled=False))
        result = email_service.poll_email(session, imap_factory=_plain, fetch=_no_fetch)
    for server in (env_server, second, broken, disabled):
        assert server.violations == []
    assert disabled.commands == []  # ni se conecta
    assert result.messages == 2  # el de LinkedIn una sola vez, aunque llegó a dos buzones
    assert len(session.scalars(select(Job)).all()) == result.created > 0
    assert [(e.code, e.message.split(":")[0]) for e in result.errors] == [("imap_auth", "Roto")]
    rows = {row.label: row for row in session.scalars(select(MailSource))}
    assert rows["Roto"].last_error and rows["Roto"].last_error["code"] == "imap_auth"
    assert rows["Segundo"].last_error is None and rows["Segundo"].last_polled_at is not None
    assert rows["Apagado"].last_polled_at is None
    # Ninguna contraseña en el resultado ni en los logs.
    dumped = result.model_dump_json() + caplog.text
    assert PASSWORD not in dumped and "mala-clave" not in dumped


def test_folder_mailbox_and_time_budget(session: Session, isolated_env: Path) -> None:
    mail_sources.create_mail_source(
        session, MailSourceInput(label="Exportados", kind="folder", folder="outlook")
    )
    folder = isolated_env / "inbox" / "outlook"
    assert folder.is_dir()  # se crea al añadirlo
    (folder / "a.eml").write_bytes(INFOJOBS)
    result = email_service.poll_email(session, fetch=_no_fetch)
    assert result.messages == 1 and not result.errors
    probe = mail_sources.probe_mail_source(session, session.scalars(select(MailSource)).one().id)
    assert probe.ok and "1 ficheros" in probe.message

    # Sin tiempo: se anota y se lee en la siguiente pasada.
    ticks: Iterator[float] = iter([0.0, 10_000.0])
    errors: list[Any] = []
    email_service._read_mail(session, None, errors, clock=lambda: next(ticks))
    assert [e.code for e in errors] == ["time_budget"]


def test_demo_reads_no_imap_mailbox(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    mail_sources.create_mail_source(session, _imap("Trabajo", 993))
    monkeypatch.setattr(type(get_settings()), "demo_mode", property(lambda _self: True))
    assert mail_sources.active_sources(session) == []
    result = mail_sources.probe_new_mail_source(_imap("X", 993), _plain)
    assert (result.ok, result.code) == (False, "demo")


def test_replies_only_from_mailboxes_that_read_them(session: Session) -> None:
    mail_sources.create_mail_source(session, _imap("Alertas", 993))
    mail_sources.create_mail_source(session, _imap("Personal", 994, read_replies=True))
    assert [r.label for r in mail_sources.active_sources(session, "replies")] == ["Personal"]


def test_probe_reports_errors_without_the_password() -> None:
    with fake_imap({}) as server:
        ok = mail_sources.probe_new_mail_source(_imap("X", server.port), _plain)
        bad = mail_sources.probe_new_mail_source(
            _imap("X", server.port, password="otra-clave"), _plain
        )
        missing = mail_sources.probe_new_mail_source(
            _imap("X", server.port, folder="No existe"), _plain
        )
    with fake_imap({}) as server2:
        accented = mail_sources.probe_new_mail_source(
            _imap("X", server2.port, password="clavé-ñ"), _plain
        )
    assert (accented.code, "clavé-ñ" in accented.message) == ("imap_auth", False)
    assert ok.ok and "solo lectura" in ok.message
    assert (bad.ok, bad.code) == (False, "imap_auth") and "otra-clave" not in bad.message
    assert missing.code == "imap_folder"
    assert server.violations == [] and "UID FETCH" not in server.commands


# --- API ----------------------------------------------------------------------------------------


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app(), base_url="http://127.0.0.1:8000") as client:
        yield client


def test_api_crud_never_returns_the_password(client: TestClient) -> None:
    body = {"label": "Trabajo", "host": "imap.example.com", "user": "ana@example.com"}
    created = client.post("/mail-sources", json=body | {"password": "s3creta"}, headers=JSON)
    assert created.status_code == 201
    assert "s3creta" not in created.text and created.json()["source"]["has_password"]
    source_id = created.json()["source"]["id"]

    listed = client.get("/mail-sources", headers={"Origin": UI_ORIGIN})
    assert listed.status_code == 200 and "s3creta" not in listed.text
    assert [s["label"] for s in listed.json()["sources"]] == ["Trabajo"]

    patched = client.patch(f"/mail-sources/{source_id}", json={"enabled": False}, headers=JSON)
    assert patched.status_code == 200 and patched.json()["source"]["enabled"] is False
    again = client.post("/mail-sources", json=body, headers=JSON)
    assert again.status_code == 409

    deleted = client.request("DELETE", f"/mail-sources/{source_id}", json={}, headers=JSON)
    assert deleted.status_code == 200
    assert client.post(f"/mail-sources/{source_id}/test", json={}, headers=JSON).status_code == 404
    assert "s3creta" not in _env_text()


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://evil.example", "Content-Type": "application/json"},
        {"Origin": UI_ORIGIN, "Content-Type": "text/plain"},
    ],
)
def test_api_only_from_the_ui(client: TestClient, headers: dict[str, str]) -> None:
    body = {"label": "X", "host": "imap.example.com", "user": "u", "password": "p"}
    response = client.post("/mail-sources", content=json.dumps(body), headers=headers)
    assert response.status_code == 403
    with session_scope() as session:
        assert session.scalars(select(MailSource)).first() is None
    assert (
        client.get("/mail-sources", headers={"Origin": "https://evil.example"}).status_code == 403
    )


def test_api_test_new_mailbox(client: TestClient) -> None:
    body = {"label": "X", "host": "10.1.2.3", "user": "u", "password": "p"}
    result = client.post("/mail-sources/test", json=body, headers=JSON).json()
    assert result == {
        "ok": False,
        "code": "host_not_allowed",
        "message": result["message"],
    }
    assert "p" not in os.environ.get("CAI_IMAP_X_PASSWORD", "")


# --- Revisión: la contraseña tampoco sale en un error -------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {"label": "X", "password": "s3creta-larga"},  # sin servidor: error del modelo entero
        {"label": "X", "host": "imap.x.com", "user": "u", "password": "s3creta\n-larga"},
        {"label": "X", "host": "imap.x.com", "user": "u", "password": "s3creta-larga" * 30},
    ],
    ids=["model-error", "control-char", "too-long"],
)
def test_validation_errors_never_echo_the_password(
    client: TestClient, body: dict[str, Any]
) -> None:
    for method, url in (("POST", "/mail-sources"), ("POST", "/mail-sources/test")):
        response = client.request(method, url, json=body, headers=JSON)
        assert response.status_code == 422
        assert "s3creta" not in response.text


def test_env_file_keeps_unicode_separators_and_rejects_them_in_passwords(
    isolated_env: Path,
) -> None:
    path = env_file.env_path()
    path.write_bytes("OTRA='a b\x85c'\n".encode())
    env_file.write_secret("CAI_IMAP_A_PASSWORD", "x")
    assert path.read_bytes().decode().startswith("OTRA='a b\x85c'\n")
    for bad in ("a b", "a\x85b"):
        with pytest.raises(ValidationError):
            _imap("X", 993, password=bad)


def test_secret_name_does_not_overwrite_an_existing_variable(session: Session) -> None:
    env_file.env_path().write_text("CAI_IMAP_GMAIL_PASSWORD=mía\n", encoding="utf-8")
    view = mail_sources.create_mail_source(session, _imap("Gmail", 993)).source
    assert view.secret_ref == "CAI_IMAP_GMAIL_2_PASSWORD"
    assert env_file.read_secret("CAI_IMAP_GMAIL_PASSWORD") == "mía"


@pytest.mark.parametrize(
    ("data", "fragment"),
    [
        ({"label": "   "}, "Escribe un nombre"),
        ({"kind": "folder", "folder": "CON"}, "Carpeta no válida"),
        ({"kind": "folder", "folder": "alertas."}, "Carpeta no válida"),
    ],
)
def test_more_invalid_inputs(data: dict[str, Any], fragment: str) -> None:
    with pytest.raises(ValidationError, match=fragment):
        MailSourceInput.model_validate({"label": "X", "host": "imap.x.com", "user": "u"} | data)


def test_one_broken_mailbox_does_not_stop_the_run_being_recorded(session: Session) -> None:
    from app.models import Source

    mail_sources.create_mail_source(
        session, MailSourceInput(label="Exportados", kind="folder", folder="ok")
    )
    mail_sources.create_mail_source(session, _imap("Sin clave", 993, password=None))
    result = email_service.poll_email(session, fetch=_no_fetch)
    assert [e.code for e in result.errors] == ["no_password"]
    assert session.get(Source, result.source_id).last_run_at is not None  # type: ignore[union-attr]
