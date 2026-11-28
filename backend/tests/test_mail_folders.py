"""Fase 48.3: de qué buzón y carpeta se leen las respuestas. Carpetas de respuestas aparte de la de
alertas (varias, elegidas en la UI también en la cuenta de `.env`), la lista de carpetas del buzón
(`LIST`, solo nombres) y la lectura de todas, sin descargar dos veces el mismo correo."""

import imaplib
from collections.abc import Callable, Iterator
from datetime import datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.config import get_settings
from app.core.db import session_scope
from app.models import Job
from app.schemas.mail_sources import MailSourceInput, MailSourcePatch
from app.services import mail_sources, replies
from app.services.ingestion.email.mailboxes import decode_imap_utf7, imap_utf7
from tests.imap_support import FOLDER, PASSWORD, USER, fake_imap
from tests.replies_support import APPLIED, DEMO, DEMO_COMPANIES, NOW, add_applied_job

JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


def _plain(host: str, port: int, timeout: float) -> imaplib.IMAP4:
    return imaplib.IMAP4(host, port, timeout=timeout)


def _imap(port: int, **extra: Any) -> MailSourceInput:
    data = {
        "label": "Trabajo",
        "host": "127.0.0.1",
        "port": port,
        "user": USER,
        "password": PASSWORD,
        "folder": FOLDER,
        "allow_private": True,
    }
    return MailSourceInput.model_validate(data | extra)


def _configure_env(monkeypatch: pytest.MonkeyPatch, port: int, **extra: str) -> None:
    env = {
        "CAI_IMAP_HOST": "127.0.0.1",
        "CAI_IMAP_PORT": str(port),
        "CAI_IMAP_USER": USER,
        "CAI_IMAP_PASSWORD": PASSWORD,
        "CAI_IMAP_FOLDER": FOLDER,
    } | extra
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


@pytest.fixture
def applied_job(session: Session) -> Callable[..., Job]:
    def _make(company: str, url: str = "", applied_at: datetime = APPLIED) -> Job:
        return add_applied_job(session, company, url, applied_at)

    return _make


# --- Nombres de carpeta -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name", ["INBOX", "Entrevistas técnicas", "Ñandú & Co", "日本語", "[Gmail]/Todos"]
)
def test_utf7_names_round_trip(name: str) -> None:
    assert decode_imap_utf7(imap_utf7(name)[1:-1].replace('\\"', '"')) == name


def test_a_broken_utf7_chunk_is_left_as_it_is() -> None:
    assert decode_imap_utf7("Roto &@@@-") == "Roto &@@@-"


def test_replies_folders_are_deduplicated_and_limited() -> None:
    data = _imap(1, replies_folders=["inbox", "INBOX", "Procesos", "Procesos"])
    assert data.replies_folders == ["INBOX", "Procesos"]
    with pytest.raises(ValidationError):
        _imap(1, replies_folders=[])
    with pytest.raises(ValidationError):
        _imap(1, replies_folders=[f"C{i}" for i in range(11)])
    with pytest.raises(ValidationError):
        _imap(1, replies_folders=["Mala\ncarpeta"])


# --- Lista de carpetas --------------------------------------------------------------------------


def test_folders_of_a_mailbox_only_lists_them(session: Session) -> None:
    with fake_imap({1: b"Subject: x\r\n\r\nhola"}) as server:
        created = mail_sources.create_mail_source(session, _imap(server.port))
        listed = mail_sources.folders_of(session, created.source.id, factory=_plain)
        before = mail_sources.folders_of_new(_imap(server.port), factory=_plain)
    assert listed.ok and listed.folders == [
        "INBOX",
        "Alertas empleo",
        "Entrevistas técnicas",
        "Procesos",
    ]  # sin «[Gmail]», que no se puede abrir
    assert before.folders == listed.folders
    assert server.violations == []
    assert "EXAMINE" not in server.commands and "UID FETCH" not in server.commands


def test_hostile_folder_names_are_left_out() -> None:
    from app.services.ingestion.email.mailboxes import _parse_list

    data: list[object] = [
        b'(\\HasNoChildren) "/" "INBOX"',
        b'(\\HasNoChildren) "/" "Con\r\nsalto"',
        b'(\\HasNoChildren) "/" "' + b"x" * 300 + b'"',
        (b'(\\HasNoChildren) "/" {9}', b"Barra\\ok"),
        b'(\\HasNoChildren) "/" "Suelto &"',
    ]
    assert _parse_list(data) == ["INBOX", "Barra\\ok", "Suelto &"]


def test_folders_with_a_wrong_password_say_why(session: Session) -> None:
    with fake_imap({}) as server:
        result = mail_sources.folders_of_new(_imap(server.port, password="mal"), factory=_plain)
    assert (result.ok, result.code) == (False, "imap_auth")
    assert "mal" not in result.message


def test_a_folder_mailbox_has_no_folders_to_list(session: Session) -> None:
    created = mail_sources.create_mail_source(
        session, MailSourceInput.model_validate({"label": "Local", "kind": "folder", "folder": "x"})
    )
    assert mail_sources.folders_of(session, created.source.id).code == "not_imap"


# --- La cuenta de `.env` ------------------------------------------------------------------------


def test_env_account_replies_folders_are_chosen_in_the_ui(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_env(monkeypatch, 993, CAI_IMAP_REPLIES_FOLDER="Antigua")
    (principal,) = mail_sources.list_mail_sources(session).sources
    assert principal.replies_folders == ["Antigua"]  # hasta elegirlas, las de `.env`

    patch = MailSourcePatch.model_validate(
        {"read_replies": True, "replies_folders": ["INBOX", "Procesos"]}
    )
    # Cambiar solo el nombre (o mandar las mismas carpetas) no las fija.
    same = MailSourcePatch.model_validate({"label": "Gmail", "replies_folders": ["Antigua"]})
    mail_sources.update_mail_source(session, principal.id, same)
    row = session.get(mail_sources.MailSource, principal.id)
    assert row is not None and row.replies_folders_set is False
    saved = mail_sources.update_mail_source(session, principal.id, patch)
    assert saved.source.replies_folders == ["INBOX", "Procesos"]
    assert saved.source.read_replies is True
    monkeypatch.setenv("CAI_IMAP_REPLIES_FOLDER", "Otra")
    get_settings.cache_clear()
    assert mail_sources.get_mail_source(session, principal.id).replies_folders == [
        "INBOX",
        "Procesos",
    ]
    # La de alertas sigue en `.env`.
    with pytest.raises(mail_sources.MailSourceNotAllowedError, match="carpeta de alertas"):
        mail_sources.update_mail_source(
            session, principal.id, MailSourcePatch.model_validate({"folder": "Otra"})
        )


# --- Probar ------------------------------------------------------------------------------------


def test_probe_replies_opens_each_folder(session: Session) -> None:
    with fake_imap({}) as server:
        box = mail_sources.create_mail_source(
            session, _imap(server.port, replies_folders=["INBOX", "Entrevistas técnicas"])
        ).source
        alerts = mail_sources.probe_mail_source(session, box.id, factory=_plain)
        both = mail_sources.probe_mail_source(session, box.id, factory=_plain, purpose="replies")
        mail_sources.update_mail_source(
            session, box.id, MailSourcePatch.model_validate({"replies_folders": ["INBOX", "No"]})
        )
        missing = mail_sources.probe_mail_source(session, box.id, factory=_plain, purpose="replies")
    assert alerts.ok and "Alertas empleo" in alerts.message
    assert both.ok and "«INBOX», «Entrevistas técnicas»" in both.message
    assert (missing.ok, missing.code) == (False, "imap_folder")
    assert missing.message.startswith("«No»:")
    assert server.violations == []


# --- Lectura de respuestas ----------------------------------------------------------------------


def test_poll_reads_every_replies_folder_and_downloads_each_mail_once(
    session: Session, applied_job: Callable[..., Job], monkeypatch: pytest.MonkeyPatch
) -> None:
    for company, url in DEMO_COMPANIES.items():
        applied_job(company, url)
    # El servidor falso enseña los mismos correos en todas sus carpetas: como una etiqueta de
    # Gmail puesta a un correo que también está en la bandeja de entrada.
    messages = {
        1: (DEMO / "01-entrevista.eml").read_bytes(),
        2: (DEMO / "04-oferta.eml").read_bytes(),
    }
    with fake_imap(messages) as server:
        _configure_env(monkeypatch, server.port)
        row = mail_sources.sync_env_source(session)
        assert row is not None
        mail_sources.update_mail_source(
            session,
            row.id,
            MailSourcePatch.model_validate(
                {"read_replies": True, "replies_folders": ["INBOX", "Procesos"]}
            ),
        )
        result = replies.poll_replies(session, imap_factory=_plain, now=NOW)
    assert result.read == ["Principal · INBOX", "Principal · Procesos"]
    assert result.created == 2
    assert sorted(server.bodies_sent) == [1, 2]  # cada cuerpo una sola vez
    assert server.commands.count("EXAMINE") == 2
    assert server.violations == []


def test_a_broken_folder_does_not_stop_the_others(
    session: Session, applied_job: Callable[..., Job], monkeypatch: pytest.MonkeyPatch
) -> None:
    for company, url in DEMO_COMPANIES.items():
        applied_job(company, url)
    with fake_imap({1: (DEMO / "01-entrevista.eml").read_bytes()}) as server:
        _configure_env(monkeypatch, server.port)
        row = mail_sources.sync_env_source(session)
        assert row is not None
        row.read_replies = True
        row.replies_folders = ["No existe", "INBOX"]
        row.replies_folders_set = True
        session.flush()
        result = replies.poll_replies(session, imap_factory=_plain, now=NOW)
    assert result.created == 1
    assert [(e.code, e.message.split(":")[0]) for e in result.errors] == [
        ("imap_folder", "Principal · No existe")
    ]
    assert result.read == ["Principal · INBOX"]  # solo lo que se ha leído bien


def test_doctor_checks_the_folders_chosen_in_the_ui(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services import doctor

    migrations.upgrade()
    with fake_imap({}) as server:
        _configure_env(monkeypatch, server.port, CAI_IMAP_REPLIES_FOLDER="No existe")
        with session_scope() as session:
            row = mail_sources.sync_env_source(session)
            assert row is not None
            row.replies_folders = ["INBOX", "Procesos"]
            row.replies_folders_set = True
        check = doctor.check_email_replies(get_settings(), imap_factory=_plain)
    assert check.status == doctor.CheckStatus.OK, check.detail
    assert "«INBOX», «Procesos»" in check.detail


def test_without_processes_nothing_is_read(session: Session) -> None:
    assert replies.poll_replies(session, now=NOW).read == []


# --- API ----------------------------------------------------------------------------------------


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app(), base_url="http://127.0.0.1:8000") as client:
        yield client


def test_api_folders_and_replies_probe(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def folders_of(session: Session, source_id: int) -> Any:
        calls.append("saved")
        return mail_sources.MailFolderList(ok=True, folders=["INBOX", "Procesos"])

    def folders_of_new(data: MailSourceInput) -> Any:
        calls.append("new")
        return mail_sources.MailFolderList(ok=True, folders=["INBOX"])

    monkeypatch.setattr(mail_sources, "folders_of", folders_of)
    monkeypatch.setattr(mail_sources, "folders_of_new", folders_of_new)
    body = {"label": "Trabajo", "host": "imap.example.com", "user": "ana@example.com"}
    created = client.post(
        "/mail-sources", json=body | {"replies_folders": ["INBOX", "Procesos"]}, headers=JSON
    )
    assert created.status_code == 201, created.text
    source = created.json()["source"]
    assert source["replies_folders"] == ["INBOX", "Procesos"]

    listed = client.post(f"/mail-sources/{source['id']}/folders", json={}, headers=JSON)
    assert listed.json()["folders"] == ["INBOX", "Procesos"]
    new = client.post("/mail-sources/folders", json=body | {"password": "x"}, headers=JSON)
    assert new.json()["folders"] == ["INBOX"]
    assert calls == ["saved", "new"]

    other = {"Origin": "https://example.com", "Content-Type": "application/json"}
    assert (
        client.post(f"/mail-sources/{source['id']}/folders", json={}, headers=other).status_code
        == 403
    )

    probe = client.post(f"/mail-sources/{source['id']}/test?purpose=replies", json={}, headers=JSON)
    assert probe.status_code == 200 and probe.json()["ok"] is False  # sin contraseña


def test_api_folders_of_a_missing_mailbox(client: TestClient) -> None:
    assert client.post("/mail-sources/99/folders", json={}, headers=JSON).status_code == 404
