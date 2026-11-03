"""El aviso «Buscando…»: la app sigue una búsqueda abierta en la terminal por lo que anota."""

from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import Source
from app.models.base import utcnow
from app.schemas.sources import Incident, SourceRunSummary
from app.services import agent_launch, search_runs
from app.services.ingestion import browse

UI = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


def portal(session: Session, name: str, **config: object) -> int:
    source = Source(
        kind=browse.KIND,
        name=name,
        active=True,
        config={"allow_agent_browsing": True, "access": "free", "search_urls": [], **config},
    )
    session.add(source)
    session.flush()
    return source.id


def walk(session: Session, source_id: int, *incidents: tuple[str, str]) -> None:
    summary = SourceRunSummary(
        found=10,
        created=0,
        existing=0,
        incidents=[Incident(code=code, message=message) for code, message in incidents],  # type: ignore[arg-type]
    )
    browse.record_run(session, source_id, summary)


def seen(session: Session) -> search_runs.SearchRunView:
    view = search_runs.current(session).run
    assert view is not None
    return view


def test_it_tracks_only_the_boards_the_agent_can_walk(session: Session) -> None:
    one = portal(session, "Uno")
    portal(session, "Bloqueado", access="blocked")
    portal(session, "Sin permiso", allow_agent_browsing=False)
    run = search_runs.start(session, [])
    assert run is not None
    assert run.source_ids == [one]


def test_nothing_to_track_without_boards(session: Session) -> None:
    assert search_runs.start(session, []) is None
    assert search_runs.current(session).run is None


def test_it_stays_running_until_every_board_is_recorded(session: Session) -> None:
    one, two = portal(session, "Uno"), portal(session, "Dos")
    search_runs.start(session, [])
    view = seen(session)
    assert (view.status, view.portals_done, view.portals_total) == ("running", 0, 2)

    walk(session, one)
    view = seen(session)
    assert (view.status, view.portals_done) == ("running", 1)

    walk(session, two)
    view = seen(session)
    assert (view.status, view.outcome, view.found) == ("finished", "done", 20)
    assert view.finished_at is not None


def test_a_walk_from_before_the_search_does_not_count(session: Session) -> None:
    one = portal(session, "Uno")
    walk(session, one)
    search_runs.start(session, [])
    view = seen(session)
    assert (view.status, view.portals_done, view.found) == ("running", 0, 0)


def test_only_real_problems_count_not_the_agents_notes(session: Session) -> None:
    one = portal(session, "Uno")
    search_runs.start(session, [])
    walk(session, one, ("captcha", "Pidió un captcha."), ("other", "Leídas 3 de 6 búsquedas."))
    assert seen(session).problems == 1


def test_the_agent_can_say_it_could_not_search(session: Session) -> None:
    portal(session, "Uno")
    search_runs.start(session, [])
    assert search_runs.finish(session, "no_browser").closed
    view = seen(session)
    assert (view.status, view.outcome) == ("finished", "no_browser")


def test_finish_without_an_open_search_is_not_an_error(session: Session) -> None:
    assert not search_runs.finish(session, "done").closed


def test_without_news_it_never_stays_searching_forever(session: Session) -> None:
    portal(session, "Uno")
    run = search_runs.start(session, [])
    assert run is not None
    run.started_at = utcnow() - search_runs.STALE_AFTER - timedelta(minutes=1)
    session.flush()
    assert seen(session).status == "stale"


def test_a_new_search_replaces_the_previous_notice(session: Session) -> None:
    portal(session, "Uno")
    first = search_runs.start(session, [])
    second = search_runs.start(session, [])
    assert first is not None and second is not None
    assert first.dismissed_at is not None
    assert seen(session).id == second.id


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Windows con `claude` instalado y sin abrir ninguna terminal de verdad."""
    monkeypatch.setattr(agent_launch.sys, "platform", "win32")
    monkeypatch.setattr(agent_launch.shutil, "which", lambda name: f"C:/bin/{name}.exe")
    monkeypatch.setattr(agent_launch, "_open_terminal", lambda *_: None)
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


def test_the_button_starts_tracking_and_the_ui_closes_the_notice(client: TestClient) -> None:
    with session_scope() as session:
        chosen = portal(session, "Uno")
        portal(session, "Dos")
    response = client.post(
        "/agent/launch",
        json={"action": "search-jobs", "search": {"platform_ids": [chosen]}},
        headers=UI,
    )
    assert response.status_code == 202
    run = client.get("/agent/search-run").json()["run"]
    assert (run["status"], run["portals_total"]) == ("running", 1)

    closed = client.post(f"/agent/search-run/{run['id']}/dismiss", json={}, headers=UI)
    assert closed.status_code == 200
    assert client.get("/agent/search-run").json()["run"] is None
    missing = client.post("/agent/search-run/999/dismiss", json={}, headers=UI)
    assert missing.status_code == 404


def test_if_the_window_does_not_open_nothing_is_tracked(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(*_: object) -> None:
        raise OSError("sin terminal")

    monkeypatch.setattr(agent_launch, "_open_terminal", fail)
    with session_scope() as session:
        portal(session, "Uno")
    response = client.post("/agent/launch", json={"action": "search-jobs"}, headers=UI)
    assert response.status_code >= 400
    assert client.get("/agent/search-run").json()["run"] is None


def test_other_agent_actions_do_not_touch_the_notice(client: TestClient) -> None:
    with session_scope() as session:
        portal(session, "Uno")
    client.post("/agent/launch", json={"action": "configure-platforms"}, headers=UI)
    assert client.get("/agent/search-run").json()["run"] is None
