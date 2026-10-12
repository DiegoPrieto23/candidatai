"""Red de LinkedIn (fase 18): importar `Connections.csv`, cruce por empresa y referencias."""

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import Contact, NetworkContact
from app.services import analytics, events, ingest, jobs, network, process
from tests.agent_support import POSTING_TEXT, cli_call

DEMO_CSV = Path(__file__).resolve().parents[2] / "demo" / "linkedin" / "Connections.csv"
HEADER = "First Name,Last Name,URL,Email Address,Company,Position,Connected On\n"


def _write(tmp_path: Path, rows: list[str], name: str = "Connections.csv") -> Path:
    path = tmp_path / name
    path.write_text(HEADER + "".join(f"{r}\n" for r in rows), encoding="utf-8")
    return path


def _job(session: Session, company: str, title: str = "Data Engineer") -> int:
    return ingest.add_from_text(session, title, company, POSTING_TEXT + company).job_id


# --- Importación ----------------------------------------------------------------------------


def test_parses_the_real_linkedin_export_with_its_notes_preamble() -> None:
    rows, skipped = network.parse_connections(network.read_file(DEMO_CSV))
    assert skipped == 0
    assert len(rows) == 10
    first = rows[0]
    assert (first.first_name, first.last_name) == ("Uxía", "Barreiro Castro")
    assert first.company_key == "bretema analytics"  # sin «S.L.» ni tildes
    assert first.connected_on == date(2024, 3, 14)
    assert first.linkedin_url == "https://www.linkedin.com/in/uxia-barreiro-demo"
    assert "email" not in first.model_dump()  # el email no se guarda aunque venga
    assert rows[6].company_key == "trasno labs"  # «Trasno Labs, S.L.» entre comillas
    assert rows[-1].company is None and rows[-1].company_key is None


def test_spanish_headers_iso_and_spanish_dates_and_bad_urls(tmp_path: Path) -> None:
    path = tmp_path / "c.csv"
    path.write_text(
        "Nombre,Apellidos,URL,Empresa,Cargo,Fecha de conexión\n"
        "Ana,Ríos,javascript:alert(1),Acme,CTO,2024-05-02\n"
        "Luis,,https://es.linkedin.com/in/luis/,Acme,,12 oct. 2023\n"
        ",,,,,\n"
        ",,https://www.linkedin.com/in/nadie,Acme,,\n",
        encoding="utf-8",
    )
    rows, skipped = network.parse_connections(network.read_file(path))
    assert [(r.first_name, r.linkedin_url, r.connected_on) for r in rows] == [
        ("Ana", None, date(2024, 5, 2)),
        ("Luis", "https://es.linkedin.com/in/luis", date(2023, 10, 12)),
    ]
    assert skipped == 1  # sin nombre (la vacía no cuenta)


def test_rejects_a_file_that_is_not_the_export(tmp_path: Path) -> None:
    path = tmp_path / "otro.csv"
    path.write_text("a,b,c\n1,2,3\n", encoding="utf-8")
    with pytest.raises(network.NetworkImportError, match="First Name"):
        network.parse_connections(network.read_file(path))


def test_import_syncs_and_unlinks_removed_people(session: Session, tmp_path: Path) -> None:
    first = network.import_connections(session, DEMO_CSV)
    assert (first.total, first.added, first.updated, first.removed) == (10, 10, 0, 0)
    assert first.without_company == 1
    job_id = _job(session, "Brétema Analytics")
    uxia = session.scalars(select(NetworkContact).where(NetworkContact.first_name == "Uxía")).one()
    contact = network.add_to_process(
        session, job_id, network.AddFromNetwork(network_contact_id=uxia.id, relation="referral")
    )

    # Uxía ya no está, Antón cambia de cargo y entra alguien nuevo.
    path = _write(
        tmp_path,
        [
            "Antón,Lema Vidal,https://www.linkedin.com/in/anton-lema-demo,,Brétema Analytics,"
            "Head of Talent,02 Nov 2023",
            "Rosalía,Nova,https://www.linkedin.com/in/rosalia-nova-demo,,Trasno Labs,CTO,"
            "01 Jan 2026",
            "Rosalía,Nova,https://www.linkedin.com/in/rosalia-nova-demo,,Trasno Labs,CTO,"
            "01 Jan 2026",
        ],
    )
    second = network.import_connections(session, path)
    assert (second.total, second.added, second.updated, second.removed) == (2, 1, 1, 9)
    assert second.skipped == 1  # repetida
    kept = session.get(Contact, contact.id)
    assert kept is not None and kept.network_contact_id is None  # el contacto del proceso sigue
    assert kept.name == "Uxía Barreiro Castro"


def test_an_empty_export_does_not_wipe_the_network(session: Session, tmp_path: Path) -> None:
    network.import_connections(session, DEMO_CSV)
    with pytest.raises(network.NetworkImportError, match="no se borra"):
        network.import_connections(session, _write(tmp_path, []))
    assert session.scalar(select(NetworkContact.id).limit(1)) is not None


def test_missing_file_is_not_found(session: Session, tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        network.import_connections(session, tmp_path / "no.csv")


# --- Cruce por empresa ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("job", "person", "expected"),
    [
        ("bretema analytics", "bretema analytics", "exact"),
        ("acme analytics", "acmeanalytics", "exact"),
        ("bretema analytics", "bretema", "probable"),
        ("lucerna", "lucerna banca privada", "probable"),
        ("amazon web services", "amazon", "probable"),
        ("acme analytics", "acme", None),  # una palabra corta: demasiado ambigua
        ("banco santander", "banco atlantico demo", None),
        ("banco santander", "banco", None),  # genérica
        ("meta", "metaphor", None),
        ("trasno labs", "faro norte analytics", None),
        ("", "acme", None),
    ],
)
def test_match_kind(job: str, person: str, expected: str | None) -> None:
    assert network.match_kind(job, person) == expected


def test_known_counts_and_job_network(session: Session) -> None:
    network.import_connections(session, DEMO_CSV)
    bretema = _job(session, "Brétema Analytics, S.L.")
    lucerna = _job(session, "Lucerna Banca Privada")
    nobody = _job(session, "Banco Santander")
    assert network.known_counts(session, [bretema, lucerna, nobody]) == {bretema: 3, lucerna: 1}

    view = network.job_network(session, bretema)
    assert view.network_size == 10
    assert [(p.name, p.match) for p in view.people] == [
        ("Antón Lema Vidal", "exact"),
        ("Uxía Barreiro Castro", "exact"),
        ("Sabela Outeiro Rial", "probable"),
    ]
    assert all(p.contact_id is None for p in view.people)

    # Las filas de la bandeja y del triaje llevan el recuento.
    page = jobs.search_jobs(session)
    assert {row.id: row.known_contacts for row in page.items} == {
        bretema: 3,
        lucerna: 1,
        nobody: 0,
    }


def test_no_network_means_no_counts(session: Session) -> None:
    job_id = _job(session, "Brétema Analytics")
    assert network.known_counts(session, [job_id]) == {}
    view = network.job_network(session, job_id)
    assert view.network_size == 0 and view.people == [] and view.imported_at is None


def test_add_to_process_copies_name_role_and_url_once(session: Session) -> None:
    network.import_connections(session, DEMO_CSV)
    job_id = _job(session, "Brétema Analytics")
    person = network.job_network(session, job_id).people[0]
    data = network.AddFromNetwork(network_contact_id=person.id, relation="recruiter")
    added = network.add_to_process(session, job_id, data)
    assert (added.name, added.role, added.relation) == (
        "Antón Lema Vidal",
        "Talent Acquisition Partner",
        "recruiter",
    )
    assert added.linkedin == "https://www.linkedin.com/in/anton-lema-demo"
    assert added.email is None  # nunca sale de la red
    again = network.add_to_process(
        session, job_id, network.AddFromNetwork(network_contact_id=person.id, relation="referral")
    )
    assert again.id == added.id and again.relation == "referral"
    assert network.job_network(session, job_id).people[0].contact_id == added.id

    with pytest.raises(network.NetworkContactNotFoundError):
        network.add_to_process(
            session, job_id, network.AddFromNetwork(network_contact_id=999, relation="recruiter")
        )


def test_agent_view_has_no_contact_details(session: Session) -> None:
    network.import_connections(session, DEMO_CSV)
    job_id = _job(session, "Brétema Analytics")
    process.add_contact(
        session,
        job_id,
        process.ContactFields(
            name="Marta Pena",
            role="Recruiter",
            email="marta@example.com",
            phone="600000000",
            linkedin="https://www.linkedin.com/in/marta",
            notes="Me habló de la oferta",
            relation="recruiter",
        ),
    )
    view = network.job_contacts(session, job_id)
    dumped = json.dumps(view.model_dump(mode="json"), ensure_ascii=False)
    for secret in ("example.com", "600000000", "linkedin.com", "Me habló"):
        assert secret not in dumped
    assert view.network_imported
    assert [c.name for c in view.contacts] == ["Marta Pena"]
    assert [p.name for p in view.network] == [
        "Antón Lema Vidal",
        "Uxía Barreiro Castro",
        "Sabela Outeiro Rial",
    ]


# --- Referencias y embudo -------------------------------------------------------------------


def test_referral_mark_sets_and_clears_its_date(session: Session) -> None:
    job_id = _job(session, "Acme")
    contact = process.add_contact(session, job_id, process.ContactFields(name="Ana"))
    asked = process.set_referral(session, contact.id, process.ReferralChange(referral="requested"))
    assert asked.referral == "requested" and asked.referral_at is not None
    given = process.set_referral(session, contact.id, process.ReferralChange(referral="given"))
    assert given.referral == "given" and given.referral_at is not None
    cleared = process.set_referral(session, contact.id, process.ReferralChange(referral=None))
    assert cleared.referral is None and cleared.referral_at is None
    assert events.current_stage(session, job_id) == "pending_extraction"  # sin eventos


def test_funnel_by_referral(session: Session) -> None:
    referred, asked, plain, unsent = (_job(session, name) for name in ("A1", "B2", "C3", "D4"))
    for job_id in (referred, asked, plain):
        events.record(session, job_id, "applied_manually", "user", payload={"channel": "email"})
    events.record(session, referred, "reply_received", "user")
    for job_id, status in ((referred, "given"), (asked, "requested"), (unsent, "requested")):
        contact = process.add_contact(session, job_id, process.ContactFields(name="Ana"))
        process.set_referral(session, contact.id, process.ReferralChange(referral=status))
    # Una referencia pedida y otra dada en la misma oferta: cuenta como dada.
    extra = process.add_contact(session, referred, process.ContactFields(name="Luis"))
    process.set_referral(session, extra.id, process.ReferralChange(referral="requested"))

    groups = {g.group: g for g in analytics.get_funnel_stats(session).by_referral}
    assert list(groups) == ["given", "requested", "none"]
    assert (groups["given"].found, groups["given"].applied, groups["given"].replied) == (1, 1, 1)
    assert groups["given"].reply_rate == 1.0
    assert (groups["requested"].found, groups["requested"].applied) == (2, 1)
    assert groups["requested"].reply_rate == 0.0
    assert (groups["none"].found, groups["none"].applied, groups["none"].reply_rate) == (1, 1, 0.0)


def test_funnel_by_referral_is_empty_but_complete(session: Session) -> None:
    groups = analytics.get_funnel_stats(session).by_referral
    assert [(g.group, g.found, g.reply_rate) for g in groups] == [
        ("given", 0, None),
        ("requested", 0, None),
        ("none", 0, None),
    ]


# --- CLI y API ------------------------------------------------------------------------------


def test_cli_import_linkedin(tmp_path: Path) -> None:
    migrations.upgrade()
    failed, out = cli_call(["contacts", "import-linkedin", str(DEMO_CSV), "--json"])
    assert not failed, out
    assert out["total"] == 10 and out["added"] == 10
    failed, out = cli_call(["contacts", "import-linkedin", str(tmp_path / "no.csv"), "--json"])
    assert failed and out["error"]["type"] == "not_found"


def test_cli_import_uses_the_default_file() -> None:
    migrations.upgrade()
    target = network.default_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(DEMO_CSV.read_bytes())
    failed, out = cli_call(["contacts", "import-linkedin", "--json"])
    assert not failed and out["path"] == "documentos/linkedin/Connections.csv"


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


UI = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


def test_api_network_flow(client: TestClient) -> None:
    status = client.get("/network").json()
    assert status["size"] == 0 and status["default_file_exists"] is False
    assert client.post("/network/import", json={}, headers=UI).status_code == 404

    target = network.default_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(DEMO_CSV.read_bytes())
    other = {"Origin": "https://evil.example", "Content-Type": "application/json"}
    assert client.post("/network/import", json={}, headers=other).status_code == 403
    imported = client.post("/network/import", json={}, headers=UI)
    assert imported.status_code == 200, imported.text
    assert imported.json()["total"] == 10
    assert client.get("/network").json()["size"] == 10

    with session_scope() as session:
        job_id = _job(session, "Meiga Fintech")
    view = client.get(f"/jobs/{job_id}/network").json()
    assert [p["name"] for p in view["people"]] == ["Xoán Castiñeiras Mouriño"]
    person_id = view["people"][0]["id"]

    added = client.post(
        f"/jobs/{job_id}/contacts/from-network",
        json={"network_contact_id": person_id, "relation": "recruiter"},
    )
    assert added.status_code == 201, added.text
    contact = added.json()
    assert contact["relation"] == "recruiter" and contact["network_contact_id"] == person_id

    marked = client.post(f"/contacts/{contact['id']}/referral", json={"referral": "given"})
    assert marked.status_code == 200 and marked.json()["referral"] == "given"
    bad = client.post(f"/contacts/{contact['id']}/referral", json={"referral": "maybe"})
    assert bad.status_code == 422
    assert client.get("/jobs/999/network").status_code == 404

    rows = client.get("/jobs").json()["items"]
    assert [r["known_contacts"] for r in rows if r["id"] == job_id] == [1]
