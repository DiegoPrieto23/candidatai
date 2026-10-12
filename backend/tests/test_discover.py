"""`jh sources discover` (`ingestion/discover.py`): las tres APIs de ATS simuladas con respx."""

import json
from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from app import cli
from app.core import migrations
from app.models import Company, Source
from app.schemas.sources import SourceInput
from app.services.ingestion import discover
from app.services.ingestion import service as sources

GH = "https://boards-api.greenhouse.io/v1/boards"
LEVER = "https://api.lever.co/v0/postings"
LEVER_EU = "https://api.eu.lever.co/v0/postings"
ASHBY = "https://api.ashbyhq.com/posting-api/job-board"


def _not_found_by_default() -> None:
    """Lo no simulado responde 404, como las tres APIs ante un tablero que no existe."""
    respx.route().mock(return_value=httpx.Response(404, json={"error": "not found"}))


def _greenhouse(slug: str, name: str, titles: list[str]) -> None:
    respx.get(f"{GH}/{slug}").mock(return_value=httpx.Response(200, json={"name": name}))
    jobs = [{"id": i, "title": t} for i, t in enumerate(titles, 1)]
    respx.get(f"{GH}/{slug}/jobs").mock(return_value=httpx.Response(200, json={"jobs": jobs}))


def _run(session: Session, text: str, add: bool = False) -> discover.DiscoverResult:
    return discover.discover(session, discover.parse_companies(text), add=add, sleep=lambda _: None)


def test_parse_companies_and_candidate_slugs() -> None:
    text = (
        "# mis empresas\nAcme Datos, S.L.\n\n"
        "Brétema Analytics | bretema, bretema-io\nacme datos\nX\n"
    )
    assert discover.parse_companies(text) == [
        ("Acme Datos, S.L.", []),
        ("Brétema Analytics", ["bretema", "bretema-io"]),
        ("X", []),
    ]
    assert discover.candidate_slugs("Acme Datos S.L.") == [
        ("acmedatos", True),
        ("acme-datos", True),
        ("acme", False),
    ]
    assert discover.candidate_slugs("Brétema") == [("bretema", True)]
    assert discover.candidate_slugs("Big Co Labs") == [("bigcolabs", True), ("big-co-labs", True)]


@respx.mock
def test_greenhouse_confirmed_by_board_name(session: Session) -> None:
    _greenhouse("acmedatos", "Acme Datos", ["Data Engineer", "BI Analyst", "SRE", "QA"])
    _not_found_by_default()
    [item] = _run(session, "Acme Datos").companies
    [hit] = item.hits
    assert (hit.kind, hit.slug, hit.confidence) == ("greenhouse", "acmedatos", "confirmed")
    assert hit.board_name == "Acme Datos" and hit.jobs_count == 4
    assert hit.sample_titles == ["Data Engineer", "BI Analyst", "SRE"]
    assert (
        hit.add_command == 'jh sources add --kind greenhouse --name "Acme Datos" --slug acmedatos'
    )
    assert item.tried == ["acmedatos", "acme-datos", "acme"]


@respx.mock
def test_greenhouse_with_another_name_is_doubtful(session: Session) -> None:
    _greenhouse("acme", "Acme Rockets Inc.", ["Rocket Engineer"])
    _not_found_by_default()
    [item] = _run(session, "Acme Datos").companies
    [hit] = item.hits
    assert (hit.slug, hit.confidence) == ("acme", "doubtful")


@respx.mock
def test_lever_eu_and_ashby(session: Session) -> None:
    respx.get(f"{LEVER_EU}/bretema").mock(
        return_value=httpx.Response(200, json=[{"id": "1", "text": "Data Engineer"}])
    )
    respx.get(f"{ASHBY}/bretema").mock(
        return_value=httpx.Response(
            200,
            json={"jobs": [{"title": "ML Engineer"}, {"title": "Oculta", "isListed": False}]},
        )
    )
    _not_found_by_default()
    [item] = _run(session, "Brétema").companies
    hits = {h.kind: h for h in item.hits}
    assert hits["lever"].region == "eu" and hits["lever"].confidence == "probable"
    assert hits["lever"].add_command.endswith("--slug bretema --region eu")
    assert hits["ashby"].jobs_count == 1 and hits["ashby"].sample_titles == ["ML Engineer"]
    assert "greenhouse" not in hits


@respx.mock
def test_first_word_slug_is_doubtful_and_nothing_found(session: Session) -> None:
    respx.get(f"{LEVER}/acme").mock(return_value=httpx.Response(200, json=[]))
    _not_found_by_default()
    first, nothing = _run(session, "Acme Datos\nNadie Aquí").companies
    [hit] = first.hits
    assert (hit.kind, hit.confidence, hit.jobs_count) == ("lever", "doubtful", 0)
    assert nothing.hits == [] and nothing.errors == []


@respx.mock
def test_api_errors_are_reported_and_the_rest_continues(session: Session) -> None:
    respx.get(f"{GH}/acmedatos").mock(return_value=httpx.Response(500))
    respx.get(f"{LEVER}/acmedatos").mock(side_effect=httpx.ConnectError("sin red"))
    respx.get(f"{ASHBY}/acmedatos").mock(
        return_value=httpx.Response(200, json={"jobs": [{"title": "Data Engineer"}]})
    )
    _not_found_by_default()
    [item] = _run(session, "Acme Datos").companies
    assert [h.kind for h in item.hits] == ["ashby"]
    assert any("Greenhouse · acmedatos: HTTP 500" in e for e in item.errors)
    assert any("Lever · acmedatos: ConnectError" in e for e in item.errors)


@respx.mock
def test_add_only_reliable_boards_and_marks_existing(session: Session) -> None:
    existing = sources.add_source(
        session, SourceInput(kind="ashby", name="Brétema", slug="bretema")
    )
    _greenhouse("acmedatos", "Acme Datos", ["Data Engineer"])
    respx.get(f"{ASHBY}/bretema").mock(
        return_value=httpx.Response(200, json={"jobs": [{"title": "ML Engineer"}]})
    )
    respx.get(f"{LEVER}/dudosa").mock(return_value=httpx.Response(200, json=[]))
    _not_found_by_default()

    result = _run(session, "Acme Datos\nBrétema\nDudosa Labs", add=True)
    acme, bretema, dudosa = result.companies
    assert acme.added_source_ids and acme.hits[0].existing_source_id == acme.added_source_ids[0]
    assert bretema.hits[0].existing_source_id == existing.id and bretema.added_source_ids == []
    assert dudosa.hits[0].confidence == "doubtful" and dudosa.added_source_ids == []
    assert result.added == 1 and result.found == 3
    added = session.scalars(select(Source).where(Source.kind == "greenhouse")).one()
    assert (added.name, added.config["slug"]) == ("Acme Datos", "acmedatos")
    company = session.scalars(select(Company).where(Company.normalized_name == "acme datos")).one()
    assert company.watchlist is True


@respx.mock
def test_without_add_nothing_is_saved(session: Session) -> None:
    _greenhouse("acmedatos", "Acme Datos", ["Data Engineer"])
    _not_found_by_default()
    result = _run(session, "Acme Datos")
    assert result.added == 0 and result.found == 1
    assert session.scalars(select(Source)).all() == []


def test_read_companies_errors(tmp_path: Path) -> None:
    empty = tmp_path / "vacio.txt"
    empty.write_text("# nada\n\n", encoding="utf-8")
    with pytest.raises(discover.DiscoverError, match="ninguna empresa"):
        discover.read_companies(empty)
    with pytest.raises(discover.DiscoverError, match="No se pudo leer"):
        discover.read_companies(tmp_path / "no-existe.txt")


@respx.mock
def test_cli_discover_json_and_text(
    isolated_env: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    migrations.upgrade()
    monkeypatch.setattr(discover, "DELAY_SECONDS", 0)
    _greenhouse("acmedatos", "Acme Datos", ["Data Engineer"])
    _not_found_by_default()
    companies = tmp_path / "empresas.txt"
    companies.write_text("﻿Acme Datos\nNadie\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli.app, ["sources", "discover", "--file", str(companies), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["found"] == 1 and data["added"] == 0
    assert data["companies"][0]["hits"][0]["slug"] == "acmedatos"

    text = runner.invoke(cli.app, ["sources", "discover", "--file", str(companies), "--add"])
    assert text.exit_code == 0, text.output
    assert "Greenhouse `acmedatos` «Acme Datos», 1 ofertas, confirmada" in text.stdout
    assert "añadida fuente" in text.stdout
    assert "- Nadie: sin tablero" in text.stdout

    missing = runner.invoke(cli.app, ["sources", "discover", "--file", str(tmp_path / "x.txt")])
    assert missing.exit_code == 1


@respx.mock
@pytest.mark.parametrize(
    ("company", "slug", "board"),
    [
        ("Acme Datos", "acme", "Acme"),  # el nombre del tablero es solo una parte
        ("Capital Energy", "capital", "Capital"),  # slug de la primera palabra
    ],
)
def test_partial_name_is_never_confirmed(
    session: Session, company: str, slug: str, board: str
) -> None:
    _greenhouse(slug, board, ["Data Engineer"])
    _not_found_by_default()
    result = _run(session, company, add=True)
    [hit] = result.companies[0].hits
    assert hit.confidence == "doubtful"
    assert result.added == 0


@respx.mock
def test_remote_text_is_cleaned(session: Session) -> None:
    _greenhouse("acmedatos", "Acme \x1b[31mDatos\x1b[0m", ["Data\x1b]0;x\x07 Engineer" + "x" * 300])
    _not_found_by_default()
    [hit] = _run(session, "Acme Datos").companies[0].hits
    assert "\x1b" not in (hit.board_name or "") and "\x1b" not in hit.sample_titles[0]
    assert len(hit.sample_titles[0]) <= discover.MAX_TEXT


def test_slugs_and_command_are_safe() -> None:
    assert discover.parse_companies("Acme | ., -x, ok-1") == [("Acme", ["ok-1"])]
    command = discover._command('Acme `rm` $HOME "x"', "greenhouse", "acme", "global")
    assert "`" not in command and "$" not in command
