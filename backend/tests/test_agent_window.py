"""Fase 48.1d: la ventana del agente, siempre a mano. Dónde se abre, si sigue abierta, si el agente
no ha empezado y «Mostrar la ventana». Ningún test abre una ventana ni toca procesos de verdad salvo
el propio (`alive` del proceso de los tests)."""

import base64
import os
import sys
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.config import get_settings
from app.core.db import session_scope
from app.models import AgentRunEvent, AgentTask
from app.models.base import utcnow
from app.services import agent_launch, agent_tasks, console_window, launch_window, terminals
from tests.test_agent_tasks import _run, call, job, seen

UI = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}


def windowed(session: Session, style: launch_window.OpenedStyle = "minimized") -> AgentTask:
    task = agent_tasks.start(
        session,
        "research-company",
        job(session),
        window=agent_tasks.Window(token="abc123", style=style, title="CandidatAI · Investigar"),
    )
    assert task is not None
    return task


def leave_pid(pid: int, token: str = "abc123") -> None:
    path = console_window.pid_file(token)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{pid}\n", encoding="ascii")


# --- Cómo se abre ---------------------------------------------------------------------------------


@pytest.fixture
def windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(launch_window.shutil, "which", lambda name: f"C:/bin/{name}.exe")
    monkeypatch.delenv("CAI_TERMINAL", raising=False)
    get_settings.cache_clear()


def test_minimised_by_default_on_windows(session: Session, windows: None) -> None:
    assert launch_window.style(session) == "minimized"
    assert launch_window.styles() == ["minimized", "behind", "wt"]


def test_cai_terminal_wt_still_means_windows_terminal_until_something_is_chosen(
    session: Session, windows: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CAI_TERMINAL", "wt")
    get_settings.cache_clear()
    assert launch_window.style(session) == "wt"
    launch_window.save(
        session, launch_window.WindowPreference(open_in_window=False, window_style="behind")
    )
    assert launch_window.style(session) == "behind"
    get_settings.cache_clear()


def test_saving_without_a_style_keeps_the_one_chosen(session: Session, windows: None) -> None:
    launch_window.save(
        session, launch_window.WindowPreference(open_in_window=True, window_style="behind")
    )
    saved = launch_window.save(session, launch_window.WindowPreference(open_in_window=False))
    assert (saved.open_in_window, saved.window_style) == (False, "behind")


def test_windows_terminal_chosen_but_gone_falls_back(
    session: Session, windows: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    launch_window.save(
        session, launch_window.WindowPreference(open_in_window=False, window_style="wt")
    )
    monkeypatch.setattr(launch_window.shutil, "which", lambda name: None)
    assert launch_window.style(session) == "minimized"
    assert launch_window.styles() == ["minimized", "behind"]


def test_nothing_to_choose_outside_windows(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert launch_window.style(session) == "terminal"
    assert launch_window.styles() == []
    assert launch_window.get(session).window_style is None


def test_the_window_leaves_its_pid_first() -> None:
    launcher = agent_launch._Launcher("claude", ["claude", "{prompt}"], [])
    path = Path("C:/datos/tmp/windows/abc.pid")
    command = agent_launch.powershell_command(launcher, "hola", pid_file=path)
    assert command.startswith("Set-Content -LiteralPath 'C:")
    assert "-Value $PID" in command
    assert "Set-Content" not in agent_launch.powershell_command(launcher, "hola")

    script = terminals.posix_script(
        ["claude", "hola"],
        unset_env=[],
        env={},
        cwd=Path("/repo"),
        shell_path="/bin/bash",
        pid_file=Path("/datos/tmp/windows/abc.pid"),
    )
    steps = script.split("; ")
    assert steps[1] == "echo $$ > /datos/tmp/windows/abc.pid"  # tras entrar en la carpeta


def test_launching_a_followed_action_records_its_window(
    session: Session, windows: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[tuple[str, str, str]] = []
    monkeypatch.setattr(agent_launch, "_open_terminal", lambda *args: opened.append(args))
    monkeypatch.setattr(agent_launch, "check_target", lambda *a, **k: ("x", None, None))
    launcher = agent_launch._Launcher("claude", ["claude", "{prompt}"], [])
    monkeypatch.setattr(agent_launch, "pick", lambda *a, **k: launcher)
    launch_window.save(
        session, launch_window.WindowPreference(open_in_window=True, window_style="behind")
    )

    agent_launch.launch(session, "process-jobs")
    title, command, style = opened[-1]
    assert (title, style) == ("CandidatAI · Valorar las ofertas nuevas", "behind")
    row = session.query(AgentTask).one()
    assert row.window_style == "behind" and row.window_title == title
    assert row.window_token is not None
    pid_file = console_window.pid_file(row.window_token)
    assert pid_file.parent.is_dir()
    assert str(pid_file) in command

    # Lo que no se sigue (una conversación) no deja PID.
    agent_launch.launch(session, "mock-interview")
    assert "Set-Content" not in opened[-1][1]


def test_followed_windows_are_named_in_the_encoded_command(windows: None) -> None:
    argv, _ = agent_launch.background_console("CandidatAI · Generar CV", "& 'claude'")
    assert argv[0].lower().endswith("conhost.exe")  # la consola clásica, también minimizada
    script = base64.b64decode(argv[-1]).decode("utf-16-le")
    assert script.startswith("$Host.UI.RawUI.WindowTitle = 'CandidatAI · Generar CV'")


# --- Si sigue abierta -----------------------------------------------------------------------------


def test_the_pid_is_picked_up_and_a_live_window_keeps_it_running(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(console_window, "alive", lambda pid: pid == 4242)
    monkeypatch.setattr(console_window, "can_show", lambda: True)
    row = windowed(session)
    view = seen(session)
    assert view.status == "running"
    assert view.window is not None
    assert (view.window.title, view.window.can_show) == ("CandidatAI · Investigar", False)

    leave_pid(4242)
    view = seen(session)
    assert row.window_pid == 4242
    assert view.status == "running" and view.window is not None and view.window.can_show


def test_a_closed_window_says_so_and_keeps_what_was_saved(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(console_window, "alive", lambda pid: False)
    row = windowed(session)
    leave_pid(4242)
    call(session, "get_extraction", job_id=row.job_id)
    view = seen(session)
    assert view.status == "closed" and view.outcome is None
    assert row.window_closed_at is not None
    assert view.last_tool == "get_extraction"
    # Aunque el sistema vuelva a usar ese PID, ya se vio cerrada.
    monkeypatch.setattr(console_window, "alive", lambda pid: True)
    assert seen(session).status == "closed"


def test_closing_the_window_after_finishing_is_not_closed(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(console_window, "alive", lambda pid: False)
    row = windowed(session)
    leave_pid(4242)
    call(session, "save_company_research", job_id=row.job_id)
    assert (seen(session).status, seen(session).outcome) == ("finished", "done")


def test_windows_terminal_cannot_be_brought_back(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(console_window, "alive", lambda pid: True)
    monkeypatch.setattr(console_window, "can_show", lambda: True)
    windowed(session, "wt")
    leave_pid(4242)
    view = seen(session)
    assert view.window is not None and view.window.can_show is False
    task_id = session.query(AgentTask).one().id
    assert agent_tasks.show_window(session, task_id).shown is False


def test_an_unreadable_pid_file_is_ignored(session: Session) -> None:
    windowed(session)
    path = console_window.pid_file("abc123")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("no es un número", encoding="utf-8")
    assert seen(session).status == "running"
    assert console_window.read_pid("abc123") is None
    for bad in (str(2**40), "0", "-3", "9" * 5000):
        path.write_text(bad, encoding="utf-8")
        assert console_window.read_pid("abc123") is None, bad


def test_old_pid_files_are_cleaned() -> None:
    import time

    leave_pid(1, "old")
    leave_pid(2, "new")
    old = console_window.pid_file("old")
    os.utime(old, (time.time() - 8 * 24 * 3600,) * 2)
    console_window.clean_old()
    assert not old.exists()
    assert console_window.pid_file("new").exists()


def test_typographic_quotes_are_doubled_for_powershell() -> None:
    assert agent_launch._quote("O’Brien's") == "'O’’Brien''s'"


# --- Sin señales ----------------------------------------------------------------------------------


def test_no_app_tool_in_three_minutes_is_silent(session: Session) -> None:
    row = windowed(session)
    row.started_at = utcnow() - agent_tasks.SILENT_AFTER - timedelta(seconds=5)
    session.flush()
    assert seen(session).status == "silent"
    call(session, "get_status")
    assert seen(session).status == "running"


def test_silent_gives_way_to_stale(session: Session) -> None:
    row = windowed(session)
    row.started_at = utcnow() - agent_tasks.STALE_AFTER - timedelta(minutes=1)
    session.flush()
    assert seen(session).status == "stale"


def test_a_background_run_without_any_output_is_silent(session: Session) -> None:
    job_id = job(session)
    run = _run(session, job_id)
    run.started_at = utcnow() - agent_tasks.SILENT_AFTER - timedelta(seconds=5)
    session.flush()
    agent_tasks.start(session, "generate-cv", job_id, run_id=run.id)
    assert seen(session).status == "silent"
    session.add(AgentRunEvent(run_id=run.id, seq=1, at=utcnow(), kind="system"))
    session.flush()
    assert seen(session).status == "running"


# --- Mostrar la ventana ---------------------------------------------------------------------------


def test_show_window_brings_back_the_console_of_that_pid(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[int] = []
    monkeypatch.setattr(console_window, "alive", lambda pid: True)

    def show(pid: int) -> console_window.Shown:
        asked.append(pid)
        return console_window.Shown(found=True, foreground=False)

    monkeypatch.setattr(console_window, "show", show)
    task = windowed(session)
    leave_pid(4242)
    result = agent_tasks.show_window(session, task.id)
    assert (result.shown, result.foreground) == (True, False)
    assert asked == [4242]


def test_show_window_of_a_closed_window_does_nothing(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(console_window, "alive", lambda pid: False)
    monkeypatch.setattr(console_window, "show", lambda pid: pytest.fail("no debe buscarla"))
    task = windowed(session)
    leave_pid(4242)
    assert agent_tasks.show_window(session, task.id).shown is False
    with pytest.raises(agent_tasks.AgentTaskNotFoundError):
        agent_tasks.show_window(session, 999)


def test_alive_knows_the_test_process() -> None:
    # En Windows solo cuenta un PowerShell: el proceso de los tests (Python) no lo es.
    expected = sys.platform != "win32"
    assert console_window.alive(os.getpid()) is expected
    assert console_window.alive(2**22 + 7) is False


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


def test_show_window_endpoint_is_only_for_the_ui(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(console_window, "alive", lambda pid: True)
    monkeypatch.setattr(
        console_window, "show", lambda pid: console_window.Shown(found=True, foreground=True)
    )
    with session_scope() as session:
        task_id = windowed(session).id
    leave_pid(4242)
    other = {"Origin": "https://example.com", "Content-Type": "application/json"}
    assert (
        client.post(f"/agent/tasks/{task_id}/show-window", json={}, headers=other).status_code
        == 403
    )
    shown = client.post(f"/agent/tasks/{task_id}/show-window", json={}, headers=UI)
    assert shown.status_code == 200, shown.text
    assert shown.json() == {"shown": True, "foreground": True}
    missing = client.post("/agent/tasks/999/show-window", json={}, headers=UI)
    assert missing.status_code == 404


def test_the_launcher_lists_the_window_styles(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    body = client.get("/agent").json()
    assert body["window_styles"] == [] and body["window_style"] is None
