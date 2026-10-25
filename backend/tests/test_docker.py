"""Docker opcional (fase 26.3): con `CAI_IN_DOCKER=1`, la app sabe que tu agente está fuera
del contenedor. Ningún test arranca Docker: se prueban la configuración y el comportamiento."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from typer.testing import CliRunner

from app import cli
from app.api.deps import UI_ORIGIN
from app.api.main import create_app
from app.core import migrations
from app.core.config import REPO_ROOT, get_settings
from app.core.db import session_scope
from app.services import agent_launch, agent_runs, container, doctor
from app.services.agent_launch import Headless, LaunchError, _Launcher
from app.services.doctor import CheckStatus
from tests.applier_support import cv_ready_job

JSON = {"Origin": UI_ORIGIN, "Content-Type": "application/json"}
GREENHOUSE = "https://boards.greenhouse.io/acme/jobs/1"


@pytest.fixture
def docker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAI_IN_DOCKER", "1")
    get_settings.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    migrations.upgrade()
    with TestClient(create_app()) as client:
        yield client


@pytest.fixture
def headless_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un agente instalado que sí sabe trabajar en segundo plano (fuera de Docker)."""
    launcher = _Launcher(
        "claude",
        ["claude", "{prompt}"],
        ["ANTHROPIC_API_KEY"],
        ["claude", "--resume", "{session_id}"],
        Headless(
            ["claude", "-p", "{prompt}"],
            ["Agent"],
            "Skill({skill})",
            "claude-stream-json",
            "mcp__candidatai__",
        ),
    )
    monkeypatch.setattr(agent_launch, "_launchers", lambda: [launcher])
    monkeypatch.setattr(agent_launch.shutil, "which", lambda name: f"/usr/bin/{name}")


# --- Dónde escucha la API ----------------------------------------------------------------------


def test_api_listens_on_all_interfaces_only_inside_a_real_container(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    marker = tmp_path / ".dockerenv"
    monkeypatch.setattr(container, "CONTAINER_MARKERS", (marker,))
    assert container.listen_host() == "127.0.0.1"
    marker.touch()
    assert container.listen_host() == "127.0.0.1"  # sin CAI_IN_DOCKER
    monkeypatch.setenv("CAI_IN_DOCKER", "1")
    get_settings.cache_clear()
    assert container.listen_host() == "0.0.0.0"
    marker.unlink()  # la variable sola (p. ej. copiada a tu .env) no abre la API a tu red
    assert container.listen_host() == "127.0.0.1"


def test_serve_uses_the_listen_host(monkeypatch: pytest.MonkeyPatch) -> None:
    import uvicorn

    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(uvicorn, "run", lambda *a, **kw: calls.append(kw))
    monkeypatch.setattr(cli.migrations, "ensure_current", lambda: None)
    monkeypatch.setattr(container, "listen_host", lambda settings=None: "0.0.0.0")
    result = CliRunner().invoke(cli.app, ["serve", "--port", "8123"])
    assert result.exit_code == 0, result.output
    assert calls == [{"host": "0.0.0.0", "port": 8123, "reload": False}]


# --- Botones «en tu agente» y segundo plano ----------------------------------------------------


def test_terminal_buttons_copy_the_command_in_docker(
    docker: None, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[tuple[str, str]] = []
    monkeypatch.setattr(agent_launch.sys, "platform", "win32")  # ni siquiera en Windows
    monkeypatch.setattr(agent_launch.shutil, "which", lambda name: f"C:/bin/{name}.exe")
    monkeypatch.setattr(agent_launch, "_open_terminal", lambda t, c: opened.append((t, c)))
    assert agent_launch.no_terminal() == container.TERMINAL
    assert agent_launch.info().reason == container.TERMINAL
    response = client.post("/agent/launch", json={"action": "process-jobs"}, headers=JSON)
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["type"] == "agent_unavailable" and "Docker" in error["message"]
    assert error["details"][0]["received"].startswith("Usa el skill process-jobs")
    assert opened == []


def test_background_is_offered_disabled_with_the_reason(
    headless_agent: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert agent_launch.background_info().available is True
    monkeypatch.setenv("CAI_IN_DOCKER", "1")
    get_settings.cache_clear()
    info = agent_launch.background_info()
    assert info.available is False and info.reason == container.BACKGROUND
    migrations.upgrade()
    with session_scope() as session, pytest.raises(LaunchError) as exc:
        agent_runs.start(session, "process-jobs")
    assert exc.value.code == "unavailable" and "Docker" in str(exc.value)


def test_background_status_in_the_api(
    docker: None, headless_agent: None, client: TestClient
) -> None:
    body = client.get("/agent").json()
    assert body["background"]["available"] is False
    assert body["background"]["reason"] == container.BACKGROUND
    response = client.post("/agent/runs", json={"action": "process-jobs"}, headers=JSON)
    assert response.status_code == 503


# --- Candidatura asistida ----------------------------------------------------------------------


def _job() -> int:
    with session_scope() as session:
        return cv_ready_job(session, GREENHOUSE)


def test_assisted_application_offers_your_browser_and_finish_yourself(
    docker: None, client: TestClient
) -> None:
    job_id = _job()
    state = client.get(f"/jobs/{job_id}/apply").json()
    assert state["in_docker"] is True and state["can_prepare"] is False
    assert state["reason"] == container.ASSISTED_APPLY
    assert state["url"] == GREENHOUSE  # la UI la abre en tu navegador
    for path in (f"/jobs/{job_id}/apply/prepare", "/browser/open"):
        response = client.post(path, headers=JSON)
        assert response.status_code == 409, path
        assert response.json()["error"]["details"][0]["received"] == "docker"
    # «Marcar como enviada» sí: la enviaste tú, desde tu navegador.
    assert client.post(f"/jobs/{job_id}/apply/manual-done", headers=JSON).status_code == 200


def test_nothing_that_drives_the_browser_works_in_docker(docker: None) -> None:
    from app.services.applier import service

    migrations.upgrade()
    job_id = _job()
    with session_scope() as session:
        calls = [
            lambda: service.prepare(session, job_id),
            lambda: service.rescan(session, 1),
            lambda: service.fill_page(session, 1),
            lambda: service.focus(session, 1),
            lambda: service.open_browser(session),
            lambda: service.confirm_submission(session, 1, "Acme", None),  # type: ignore[arg-type]
        ]
        for call in calls:
            with pytest.raises(service.ApplierError) as exc:
                call()
            assert exc.value.code == "docker"


def test_outside_docker_the_state_is_unchanged(client: TestClient) -> None:
    state = client.get(f"/jobs/{_job()}/apply").json()
    assert state["in_docker"] is False and state["can_prepare"] is True


# --- Diagnóstico -------------------------------------------------------------------------------


def test_doctor_has_no_docker_section_outside_docker() -> None:
    assert doctor.check_docker(get_settings()) == []


def test_doctor_docker_section(
    docker: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = get_settings()
    marker = tmp_path / ".dockerenv"
    marker.touch()
    monkeypatch.setattr(container, "CONTAINER_MARKERS", (marker,))
    monkeypatch.setattr(container, "DATA_MOUNT", settings.data_dir)
    checks = {c.name: c for c in doctor.check_docker(settings, is_mount=lambda _p: True)}
    assert list(checks) == [
        "Docker · API",
        "Docker · datos",
        "Docker · tu agente",
        "Docker · límites",
    ]
    assert checks["Docker · API"].status == CheckStatus.OK
    assert checks["Docker · datos"].status == CheckStatus.OK
    assert container.MCP_COMMAND in checks["Docker · tu agente"].detail
    assert "segundo plano" in checks["Docker · límites"].detail
    assert checks["Docker · límites"].status == CheckStatus.OK  # esperados, no se arreglan dentro
    # Sin volumen, tus datos se irían con el contenedor; sin contenedor, la API sigue local.
    marker.unlink()
    checks = {c.name: c for c in doctor.check_docker(settings, is_mount=lambda _p: False)}
    assert checks["Docker · datos"].status == CheckStatus.WARN
    assert checks["Docker · API"].status == CheckStatus.WARN
    assert not any(c.status == CheckStatus.ERROR for c in checks.values())


# --- Dockerfile y compose ----------------------------------------------------------------------


def _compose() -> dict[str, Any]:
    return yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def test_compose_publishes_only_on_localhost_with_data_in_a_volume() -> None:
    service = _compose()["services"]["candidatai"]
    assert service["ports"] == ["127.0.0.1:8000:8000"]
    assert service["command"] == ["cai", "start", "--no-browser"]
    assert service["container_name"] == "candidatai"  # lo usan MCP_COMMAND y CLI_COMMAND
    assert container.MCP_COMMAND == "docker exec -i candidatai cai-mcp"
    # Van por delante del .env, que puede traer el CAI_DATA_DIR de una instalación nativa.
    assert service["environment"] == {"CAI_IN_DOCKER": "1", "CAI_DATA_DIR": "/data"}
    assert service["env_file"] == [{"path": ".env", "required": False}]
    assert service["volumes"] == ["candidatai-data:/data", "candidatai-demo:/data-demo"]
    # Nombres fijos (sin el prefijo del proyecto): los usa la copia de seguridad de la guía.
    assert _compose()["volumes"] == {
        "candidatai-data": {"name": "candidatai-data"},
        "candidatai-demo": {"name": "candidatai-demo"},
    }
    assert "/status" in " ".join(service["healthcheck"]["test"])


def test_demo_compose_only_switches_the_data_folder() -> None:
    demo = yaml.safe_load((REPO_ROOT / "docker-compose.demo.yml").read_text(encoding="utf-8"))
    assert demo == {"services": {"candidatai": {"environment": {"CAI_DATA_DIR": "/data-demo"}}}}
    assert container.DEMO_MOUNT.as_posix() == "/data-demo"


def test_demo_seed_goes_to_its_volume_in_docker(
    docker: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.services import demo
    from app.services.demo import DemoSummary

    targets: list[Path] = []

    def fake_seed(target: Path, **_: Any) -> DemoSummary:
        targets.append(target)
        return DemoSummary(
            data_dir=str(target),
            jobs=0,
            events=0,
            by_stage={},
            by_source={},
            cvs=0,
            pdf_engine=None,
            warnings=[],
        )

    monkeypatch.setattr(demo, "seed", fake_seed)
    result = CliRunner().invoke(cli.app, ["demo", "seed"])
    assert result.exit_code == 0, result.output
    assert targets == [container.DEMO_MOUNT]
    assert container.DEMO_COMPOSE in result.output and "uv run" not in result.output


def test_dockerfile_runs_unprivileged_without_personal_data() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    lines = [line.strip() for line in dockerfile.splitlines()]
    users = [line for line in lines if line.startswith("USER ")]
    assert users == ["USER cai"]
    assert lines.index("USER cai") > max(i for i, x in enumerate(lines) if x.startswith("RUN "))
    assert "CAI_IN_DOCKER=1" in dockerfile and "CAI_DATA_DIR=/data" in dockerfile
    # Sin LibreOffice: el motor html basta.
    assert not any("libreoffice" in line.lower() for line in lines if line.startswith("RUN "))
    assert "--only-shell chromium" in dockerfile
    assert 'CMD ["cai", "start", "--no-browser"]' in dockerfile
    ignored = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
    for entry in ("data", "data-*", ".env", ".env.*", ".git", "**/node_modules", "**/.venv"):
        assert entry in ignored, entry


def test_doctor_in_docker_skips_what_cannot_be_fixed_inside(
    docker: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sin LibreOffice ni agentes a propósito: nada de avisos que piden instalarlos dentro."""
    ok = doctor.CheckResult(name="Motor html (Chromium)", status=CheckStatus.OK, detail="")
    monkeypatch.setattr(doctor, "check_html_engine", lambda: ok)
    monkeypatch.setattr(doctor, "check_pdf_conversion", lambda: pytest.fail("convierte"))
    monkeypatch.setattr(doctor, "check_agents", lambda _s: pytest.fail("busca agentes"))
    checks = {c.name: c for c in doctor.run_doctor(get_settings()).checks}
    assert checks["LibreOffice"] == doctor.DOCKER_NO_SOFFICE
    assert "Conversión a PDF" not in checks and "Agentes" not in checks
    assert "uv sync" not in checks["Embeddings"].detail
    assert "Docker · límites" in checks


def test_browser_tasks_queued_before_docker_fail_with_the_reason(docker: None) -> None:
    """Una tarea del navegador encolada antes de pasar a Docker no espera a un navegador que no
    hay: falla, y el intento queda fallido con el motivo."""
    from app.models import ApplicationAttempt
    from app.services import tasks, worker

    migrations.upgrade()
    job_id = _job()
    with session_scope() as session:
        attempt = ApplicationAttempt(
            job_id=job_id, platform="greenhouse", mode="fill", url=GREENHOUSE, status="queued"
        )
        session.add(attempt)
        session.flush()
        attempt_id = attempt.id
        tasks.enqueue(session, "apply_fill", {"attempt_id": attempt_id})
        tasks.enqueue(session, "browser_open", {})
    outcomes = [o for o in worker.run_pending().outcomes if o.kind in worker.BROWSER_KINDS]
    assert [(o.kind, o.ok) for o in outcomes] == [("apply_fill", False), ("browser_open", False)]
    assert all("Docker" in (o.error or "") for o in outcomes)
    with session_scope() as session:
        row = session.get(ApplicationAttempt, attempt_id)
        assert row is not None and row.status == "failed"
        assert row.error == container.ASSISTED_APPLY
