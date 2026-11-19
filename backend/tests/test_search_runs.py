"""El aviso «Buscando…»: la app sigue una búsqueda abierta en la terminal por lo que anota."""

from collections.abc import Iterator
from datetime import timedelta

import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select
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


# --- «Buscar ahora» con las empresas (fase 45) -------------------------------------------------


def company(session: Session, name: str, *, ran_hours_ago: float | None = None) -> int:
    source = Source(kind="greenhouse", name=name, active=True, config={"slug": name.lower()})
    if ran_hours_ago is not None:
        source.last_run_at = utcnow() - timedelta(hours=ran_hours_ago)
    session.add(source)
    session.flush()
    return source.id


def _finish_tasks(session: Session, run_id: int, status: str = "done") -> None:
    from app.models import SearchRun, Task

    run = session.get(SearchRun, run_id)
    assert run is not None
    for task in session.scalars(select(Task).where(Task.id.in_(run.task_ids or []))):
        task.status = status
    session.flush()


def test_one_click_queues_the_companies_on_the_same_search(session: Session) -> None:
    from app.models import SearchRun, Task

    board = portal(session, "Uno")
    acme = company(session, "Acme")
    company(session, "Reciente", ran_hours_ago=2)
    old = company(session, "Antigua", ran_hours_ago=30)
    paused = company(session, "Pausada")
    session.get(Source, paused).active = False  # type: ignore[union-attr]

    result = search_runs.start_search(session, [board])

    assert (result.portals, result.companies, result.companies_skipped) == (1, 2, 1)
    run = session.get(SearchRun, result.run_id)
    assert run is not None and run.source_ids == [board] and run.company_ids == [acme, old]
    queued = session.scalars(select(Task).where(Task.id.in_(run.task_ids or []))).all()
    assert sorted(t.payload["source_id"] for t in queued) == [acme, old]
    assert {t.payload["search_run_id"] for t in queued} == {run.id}


def test_the_notice_waits_for_the_agent_and_the_companies(session: Session) -> None:
    board = portal(session, "Uno")
    company(session, "Acme")
    run_id = search_runs.start_search(session, [board]).run_id
    assert run_id is not None
    view = seen(session)
    assert (view.status, view.companies_total, view.companies_done) == ("running", 1, 0)

    # El agente termina, pero las empresas no: sigue «Buscando…».
    walk(session, board)
    search_runs.finish(session, "done")
    assert seen(session).status == "running"

    _finish_tasks(session, run_id)
    view = seen(session)
    assert (view.status, view.outcome, view.companies_done) == ("finished", "done", 1)


def test_the_companies_alone_without_portals(session: Session) -> None:
    portal(session, "Uno")  # activo, pero no elegido
    company(session, "Acme")
    result = search_runs.start_search(session, [])
    assert (result.portals, result.companies) == (0, 1)
    assert result.run_id is not None
    assert seen(session).portals_total == 0
    _finish_tasks(session, result.run_id, "failed")  # una tarea que falla también acaba
    assert seen(session).status == "finished"


def test_nothing_to_do_says_why(session: Session) -> None:
    company(session, "Reciente", ran_hours_ago=1)
    result = search_runs.start_search(session, [])
    assert (result.run_id, result.companies_skipped) == (None, 1)
    assert "hace poco" in result.message
    assert search_runs.current(session).run is None


def test_runs_are_tied_to_the_search(session: Session) -> None:
    from app.models import SourceRun

    board = portal(session, "Uno")
    run_id = search_runs.start_search(session, [board], include_companies=False).run_id
    walk(session, board)
    tied = session.scalars(select(SourceRun).where(SourceRun.source_id == board)).one()
    assert tied.search_run_id == run_id
    # Un recorrido sin búsqueda abierta (pedido en el chat) no queda ligado a nada.
    search_runs.finish(session, "done")
    walk(session, board)
    last = session.scalars(select(SourceRun).order_by(SourceRun.id.desc())).first()
    assert last is not None and last.search_run_id is None


@respx.mock
def test_click_runs_the_companies_and_the_agent_follows_the_same_search(
    client: TestClient,
) -> None:
    from app.services import worker
    from tests.sources_support import mock_greenhouse

    mock_greenhouse()
    with session_scope() as session:
        board = portal(session, "Uno")
        acme = company(session, "Acmedatos")

    started = client.post("/search/run", json={"portal_ids": [board]}, headers=UI)
    assert started.status_code == 200, started.text
    body = started.json()
    assert (body["portals"], body["companies"]) == (1, 1)

    launched = client.post(
        "/agent/launch",
        json={
            "action": "search-jobs",
            "search": {"platform_ids": [board], "search_run_id": body["run_id"]},
        },
        headers=UI,
    )
    assert launched.status_code == 202, launched.text
    run = client.get("/agent/search-run").json()["run"]
    assert (run["id"], run["companies_total"]) == (body["run_id"], 1)

    worker.run_pending()
    with session_scope() as session:
        from app.models import SourceRun

        company_run = session.scalars(select(SourceRun).where(SourceRun.source_id == acme)).one()
        assert company_run.search_run_id == body["run_id"]
    run = client.get("/agent/search-run").json()["run"]
    assert (run["status"], run["companies_done"]) == ("running", 1)  # falta el agente
    assert run["created"] > 0

    missing = client.post(
        "/agent/launch",
        json={"action": "search-jobs", "search": {"search_run_id": 999}},
        headers=UI,
    )
    assert missing.status_code == 404


def test_a_second_click_does_not_queue_the_companies_twice(session: Session) -> None:
    company(session, "Acme")
    first = search_runs.start_search(session, [])
    second = search_runs.start_search(session, [])
    assert (first.companies, second.companies, second.companies_skipped) == (1, 0, 1)
    assert second.run_id is None


def test_only_usable_portals_enter_the_search(session: Session) -> None:
    board = portal(session, "Uno")
    blocked = portal(session, "Bloqueado", access="blocked")
    result = search_runs.start_search(session, [board, blocked, 999], include_companies=False)
    assert result.portals == 1
    assert seen(session).portals_total == 1


def test_retried_or_deleted_tasks(session: Session) -> None:
    from app.models import SearchRun, Task

    company(session, "Acme")
    company(session, "Beta")
    run_id = search_runs.start_search(session, []).run_id
    run = session.get(SearchRun, run_id)
    assert run is not None and run.task_ids is not None
    first, second = (session.get(Task, task_id) for task_id in run.task_ids)
    assert first is not None and second is not None
    # Una falló y espera su reintento: sigue buscando, también pasados 30 minutos.
    first.status, first.attempts = "queued", 1
    run.started_at -= timedelta(hours=1)
    session.delete(second)  # una tarea borrada de la cola cuenta como acabada
    session.flush()
    view = seen(session)
    assert (view.status, view.companies_done, view.portals_finished) == ("running", 1, True)


def test_the_agent_cannot_follow_a_closed_search_and_stop_keeps_the_companies(
    session: Session,
) -> None:
    board = portal(session, "Uno")
    company(session, "Acme")
    run_id = search_runs.start_search(session, [board]).run_id
    assert run_id is not None
    # Tu agente no se pudo abrir: deja de esperarlo, pero no de esperar a las empresas.
    search_runs.stop(session, run_id)
    view = seen(session)
    assert (view.status, view.portals_finished) == ("running", True)
    with pytest.raises(search_runs.SearchRunNotFoundError):
        search_runs.attach(session, run_id)
    _finish_tasks(session, run_id)
    assert (seen(session).status, seen(session).outcome) == ("finished", "stopped")


def test_the_new_routes_are_only_for_the_ui(client: TestClient) -> None:
    other = {"Origin": "https://evil.example", "Content-Type": "application/json"}
    assert client.post("/search/run", json={}, headers=other).status_code == 403
    assert client.post("/search/run/1/stop", json={}, headers=other).status_code == 403
    assert client.post("/search/run/999/stop", json={}, headers=UI).status_code == 404
