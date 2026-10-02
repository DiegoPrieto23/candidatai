"""El conector IMAP nunca modifica el buzón: lo comprueba un servidor falso que falla ante
cualquier escritura (`tests/imap_support.py`)."""

import imaplib
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Job
from app.services import ingest
from app.services.ingestion.email.mailboxes import (
    MailboxError,
    connect_imap,
    imap_utf7,
    read_imap,
)
from app.services.ingestion.email.service import poll_email
from tests.imap_support import FOLDER, PASSWORD, USER, FakeImap, fake_imap

FIXTURES = Path(__file__).parent / "fixtures" / "email"


def _plain(host: str, port: int, timeout: float) -> imaplib.IMAP4:
    return imaplib.IMAP4(host, port, timeout=timeout)


def _configure(monkeypatch: pytest.MonkeyPatch, server: FakeImap, **overrides: str) -> None:
    env = {
        "JH_IMAP_HOST": "127.0.0.1",
        "JH_IMAP_PORT": str(server.port),
        "JH_IMAP_USER": USER,
        "JH_IMAP_PASSWORD": PASSWORD,
        "JH_IMAP_FOLDER": FOLDER,
    } | overrides
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def _no_fetch(url: str) -> str:
    raise ingest.IngestError(f"sin red: {url}")


MESSAGES = {
    7: (FIXTURES / "linkedin_alert.eml").read_bytes(),
    9: (FIXTURES / "otro_remitente.eml").read_bytes(),
}


def test_poll_reads_imap_without_modifying_it(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    with fake_imap(dict(MESSAGES)) as server:
        _configure(monkeypatch, server)
        first = poll_email(session, imap_factory=_plain, fetch=_no_fetch)
        second = poll_email(session, imap_factory=_plain, fetch=_no_fetch)
    assert server.violations == []
    assert (first.messages, first.created) == (2, 4)
    assert (second.messages, second.created) == (0, 0)
    assert len(session.scalars(select(Job)).all()) == 4
    # La segunda pasada solo pide cabeceras: no vuelve a descargar los correos conocidos.
    fetches = [c for c in server.commands if c == "UID FETCH"]
    assert len(fetches) == 3
    assert set(server.commands) <= {
        "CAPABILITY",
        "LOGIN",
        "EXAMINE",
        "UID SEARCH",
        "UID FETCH",
        "LOGOUT",
    }


def test_strict_server_catches_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """El servidor falso de verdad detecta lo que modificaría el buzón."""
    with fake_imap(dict(MESSAGES)) as server:
        conn = imaplib.IMAP4("127.0.0.1", server.port)
        conn.login(USER, PASSWORD)
        with pytest.raises(imaplib.IMAP4.error):
            conn.select(imap_utf7(FOLDER))  # SELECT (lectura y escritura)
        conn.select(imap_utf7(FOLDER), readonly=True)
        with pytest.raises(imaplib.IMAP4.error):
            conn.uid("STORE", "7", "+FLAGS", "(\\Seen)")
        with pytest.raises(imaplib.IMAP4.error):
            conn.uid("FETCH", "7", "(BODY[])")  # sin PEEK: lo marcaría como leído
        conn.logout()
    assert len(server.violations) == 3


def test_wrong_password_gives_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    with fake_imap({}) as server:
        _configure(monkeypatch, server, JH_IMAP_PASSWORD="otra")
        with pytest.raises(MailboxError) as exc:
            connect_imap(get_settings(), _plain)
    assert exc.value.code == "imap_auth"
    assert "contraseña de aplicación" in exc.value.message
    assert "otra" not in exc.value.message


def test_missing_folder_gives_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    with fake_imap({}) as server:
        _configure(monkeypatch, server, JH_IMAP_FOLDER="No existe")
        with pytest.raises(MailboxError) as exc:
            list(read_imap(get_settings(), lambda _mid: False, 21, _plain))
    assert exc.value.code == "imap_folder"


def test_imap_failure_is_reported_and_local_inbox_still_read(
    session: Session, monkeypatch: pytest.MonkeyPatch, isolated_env: Path
) -> None:
    inbox = isolated_env / "inbox"
    inbox.mkdir(parents=True)
    (inbox / "a.eml").write_bytes(MESSAGES[9])
    with fake_imap({}) as server:
        _configure(monkeypatch, server, JH_IMAP_PASSWORD="otra")
        result = poll_email(session, imap_factory=_plain, fetch=_no_fetch)
    assert [e.code for e in result.errors] == ["imap_auth"]
    assert result.created == 1


def test_unreachable_server(monkeypatch: pytest.MonkeyPatch) -> None:
    with fake_imap({}) as server:
        port = server.port
    monkeypatch.setenv("JH_IMAP_HOST", "127.0.0.1")
    monkeypatch.setenv("JH_IMAP_PORT", str(port))
    monkeypatch.setenv("JH_IMAP_USER", USER)
    monkeypatch.setenv("JH_IMAP_PASSWORD", PASSWORD)
    get_settings.cache_clear()
    with pytest.raises(MailboxError) as exc:
        connect_imap(get_settings(), _plain)
    assert exc.value.code == "network"


@pytest.mark.parametrize(
    ("folder", "encoded"),
    [
        ("INBOX", '"INBOX"'),
        ("Alertas empleo", '"Alertas empleo"'),
        ("Ofertas & más", '"Ofertas &- m&AOE-s"'),
        ('Raro"\\', '"Raro\\"\\\\"'),
    ],
)
def test_imap_utf7(folder: str, encoded: str) -> None:
    assert imap_utf7(folder) == encoded


def test_doctor_checks_login_and_folder_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.doctor import CheckStatus, check_email_alerts

    with fake_imap(dict(MESSAGES)) as server:
        _configure(monkeypatch, server)
        ok = check_email_alerts(get_settings(), _plain)
        _configure(monkeypatch, server, JH_IMAP_PASSWORD="otra")
        bad = check_email_alerts(get_settings(), _plain)
    assert ok.status == CheckStatus.OK
    assert "solo lectura" in ok.detail and FOLDER in ok.detail
    assert bad.status == CheckStatus.ERROR
    assert server.violations == []
    assert "UID FETCH" not in server.commands and "UID SEARCH" not in server.commands


def test_doctor_without_imap(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.doctor import CheckStatus, check_email_alerts

    assert check_email_alerts(get_settings()).status == CheckStatus.OK
    monkeypatch.setenv("JH_IMAP_USER", USER)
    get_settings.cache_clear()
    assert check_email_alerts(get_settings()).status == CheckStatus.WARN


def test_tls_verifies_certificate_and_hostname() -> None:
    import ssl

    from app.services.ingestion.email.mailboxes import tls_context

    context = tls_context()
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
