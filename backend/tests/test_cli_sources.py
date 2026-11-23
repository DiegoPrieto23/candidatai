"""CLI `cai sources add | list | test | run | enable | disable`."""

import json
from pathlib import Path

import httpx
import pytest
import respx
from typer.testing import CliRunner

from app import cli
from app.core import migrations
from app.core.db import session_scope
from app.services import profile
from tests.sources_support import GREENHOUSE_URL, mock_greenhouse

runner = CliRunner()
ADD = ["sources", "add", "--kind", "greenhouse", "--name", "Acme Datos", "--slug", "acmedatos"]


@pytest.fixture
def db(isolated_env: Path) -> None:
    migrations.upgrade()
    with session_scope() as session:
        profile.import_profile(session, profile.EXAMPLE_PATH)


def _json(args: list[str]) -> dict:
    result = runner.invoke(cli.app, [*args, "--json"])
    return json.loads(result.stdout)


def test_add_and_list(db: None) -> None:
    result = runner.invoke(cli.app, ADD)
    assert result.exit_code == 0, result.output
    assert "Fuente añadida. Pruébala con `cai sources test 1`." in result.stdout
    assert "Greenhouse      Acme Datos [acmedatos] (activa)" in result.stdout

    listed = _json(["sources", "list"])
    assert [(s["id"], s["kind"], s["config"]["slug"]) for s in listed["sources"]] == [
        (1, "greenhouse", "acmedatos")
    ]
    assert _json(["sources", "list", "--kind", "lever"])["sources"] == []


def test_add_errors_use_the_common_format(db: None) -> None:
    runner.invoke(cli.app, ADD)
    again = runner.invoke(cli.app, [*ADD, "--json"])
    assert again.exit_code == 1
    assert json.loads(again.stdout)["error"]["type"] == "exists"

    bad = runner.invoke(
        cli.app, ["sources", "add", "--kind", "greenhouse", "--name", "X", "--json"]
    )
    error = json.loads(bad.stdout)["error"]
    assert error["type"] == "validation_error"
    assert "slug" in json.dumps(error, ensure_ascii=False)

    text = runner.invoke(cli.app, ["sources", "add", "--kind", "workday", "--name", "X"])
    assert text.exit_code == 1 and "Error:" in text.stderr


@respx.mock
def test_test_without_saving_and_by_id(db: None) -> None:
    mock_greenhouse()
    result = runner.invoke(
        cli.app,
        ["sources", "test", "--kind", "greenhouse", "--name", "Acme", "--slug", "acmedatos"],
    )
    assert result.exit_code == 0, result.output
    assert "Acme: 5 ofertas encontradas, 3 tras filtros." in result.stdout
    assert "  + Data Engineer · Vigo, Spain" in result.stdout
    assert "  - Account Executive · Madrid  (El título no encaja" in result.stdout

    runner.invoke(cli.app, ADD)
    by_id = _json(["sources", "test", "1"])
    assert (by_id["found"], by_id["after_filters"]) == (5, 3)
    assert _json(["sources", "list"])["sources"][0]["last_run"] is None  # probar no ejecuta


def test_test_needs_a_target(db: None) -> None:
    result = runner.invoke(cli.app, ["sources", "test", "--json"])
    assert result.exit_code == 1
    assert "--name y --url" in json.loads(result.stdout)["error"]["message"]


@respx.mock
def test_test_of_a_failing_source_exits_1(db: None) -> None:
    respx.get(GREENHOUSE_URL).mock(return_value=httpx.Response(404))
    runner.invoke(cli.app, ADD)
    result = runner.invoke(cli.app, ["sources", "test", "1"])
    assert result.exit_code == 1
    assert "Conviene revisar el slug" in result.stdout


@respx.mock
def test_run_twice(db: None) -> None:
    mock_greenhouse()
    runner.invoke(cli.app, ADD)

    first = runner.invoke(cli.app, ["sources", "run"])
    assert first.exit_code == 0, first.output
    assert (
        "Greenhouse · Acme Datos: 5 ofertas encontradas, 3 tras filtros, 3 nuevas" in first.stdout
    )
    assert "Nuevas en pending_extraction: 1, 2, 3." in first.stdout

    second = _json(["sources", "run", "1"])
    assert [(r["created"], r["existing"]) for r in second["runs"]] == [(0, 3)]
    listed = runner.invoke(cli.app, ["sources", "list"])
    assert "5 vistas, 3 pasan tus filtros, 3 ya las tenías, 0 nuevas" in listed.stdout


def test_run_without_sources(db: None) -> None:
    result = runner.invoke(cli.app, ["sources", "run"])
    assert result.exit_code == 0
    assert "No hay fuentes activas" in result.stdout


def test_enable_disable(db: None) -> None:
    runner.invoke(cli.app, ADD)
    assert _json(["sources", "disable", "1"])["active"] is False
    assert "(pausada)" in runner.invoke(cli.app, ["sources", "list"]).stdout
    assert _json(["sources", "enable", "1"])["active"] is True
    missing = runner.invoke(cli.app, ["sources", "disable", "9", "--json"])
    assert json.loads(missing.stdout)["error"]["type"] == "not_found"


def test_needs_migrated_db(isolated_env: Path) -> None:
    result = runner.invoke(cli.app, ["sources", "list", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["type"] == "database_not_ready"


def test_add_new_kinds_with_their_options(db: None) -> None:
    personio = _json(
        ["sources", "add", "--kind", "personio", "--name", "Acme Datos", "--slug", "acmedatos",
         "--language", "en"]
    )  # fmt: skip
    assert personio["config"]["language"] == "en" and personio["kind_label"] == "Personio"
    manfred = _json(
        ["sources", "add", "--kind", "manfred", "--name", "Manfred", "--query", "data",
         "--lang", "EN"]
    )  # fmt: skip
    assert manfred["config"] == {"query": "data", "lang": "EN", "title_keywords": []}
    freehire = _json(
        ["sources", "add", "--kind", "freehire", "--name", "freehire", "--query", "python",
         "--country", "pt", "--remote-only"]
    )  # fmt: skip
    assert freehire["config"] == {
        "query": "python", "country": "pt", "remote_only": True, "title_keywords": []
    }  # fmt: skip
    listed = runner.invoke(cli.app, ["sources", "list"])
    assert "Personio        Acme Datos [acmedatos] (activa)" in listed.stdout


def test_list_explains_an_agent_run_with_the_same_numbers_as_the_ui(db: None) -> None:
    from app.schemas.sources import AgentBrowseSource, SourceRunSummary
    from app.services.ingestion import browse

    with session_scope() as session:
        saved = browse.save_source(
            session,
            AgentBrowseSource(
                name="Tecnoempleo",
                platform="tecnoempleo",
                search_urls=["https://www.tecnoempleo.com/ofertas-trabajo/?te=data"],
            ),
        )
        summary = SourceRunSummary(
            found=30,
            created=6,
            existing=1,
            skipped_known=9,
            filtered_out=10,
            left_by_limit=4,
            reopened=2,
            stop_reason="limit",
        )
        browse.record_run(session, saved.source_id, summary)

    listed = runner.invoke(cli.app, ["sources", "list"])
    assert listed.exit_code == 0, listed.output
    assert (
        "30 vistas, 20 pasan tus filtros, 10 ya las tenías, 6 nuevas (de ellas, 2 reabiertas). "
        "Alcanzó el límite: quedan 4 sin abrir"
    ) in listed.stdout
    run = _json(["sources", "list"])["sources"][0]["last_run"]
    assert (run["known"], run["left_by_limit"], run["stop_reason"]) == (10, 4, "limit")


def test_already_had_never_goes_below_zero() -> None:
    from app.schemas.sources import known_count

    assert known_count(after_filters=3, created=2, left_by_limit=0) == 1
    # Datos incoherentes (un recorrido antiguo o de otra vía): nunca una cifra negativa.
    assert known_count(after_filters=2, created=3, left_by_limit=1) == 0


def test_the_limit_reason_in_singular_and_without_a_number() -> None:
    from app.cli_commands import _stop_reason_text

    assert _stop_reason_text("limit", 1) == "Alcanzó el límite: queda 1 sin abrir"
    assert _stop_reason_text("limit", 0) == "Alcanzó el límite"
