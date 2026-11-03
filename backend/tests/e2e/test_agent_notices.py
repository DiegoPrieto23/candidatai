"""Avisos de lo que lanzan los botones, preguntas del agente en el portal, un CV que no cabe y
renombrar o eliminar plantillas propias, de punta a punta con la app real."""

import copy
import json
import os
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import Page, expect

from tests.e2e.agent import api, cai, demo_cv_content
from tests.e2e.flows import _db, job_ready_to_apply, projected_stage
from tests.e2e.harness import AppServer, run_cai, t

pytestmark = pytest.mark.e2e

SHOTS = os.environ.get("CAI_E2E_SHOTS")


def shot(page: Page, name: str) -> None:
    if SHOTS:
        page.screenshot(path=str(Path(SHOTS) / f"{name}.png"), full_page=True)


def _start_task(server: AppServer, action: str, total: int = 0, job_id: int | None = None) -> None:
    """Lo que hace el botón al abrir la terminal: aquí no se abre ninguna ventana."""
    with _db(server) as db:
        db.execute(
            "INSERT INTO agent_tasks (action, job_id, total, started_at) VALUES (?, ?, ?, ?)",
            (action, job_id, total, datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")),
        )
        db.commit()


def test_the_notice_follows_what_the_agent_saves(page: Page, fresh_demo_app: AppServer) -> None:
    server = fresh_demo_app
    _start_task(server, "process-jobs", total=3)
    page.goto(f"{server.url}/como-funciona")
    notice = page.get_by_role("status").filter(has_text=t("nav.tasks.actions.process-jobs.running"))
    expect(notice).to_be_visible()
    expect(notice.get_by_text(t("nav.tasks.counts", done=0, total=3))).to_be_visible()
    shot(page, "notice-running")

    # El agente dice que ha acabado: el aviso cambia solo, sin recargar.
    closed = cai(server, "agents", "finish-task", "--action", "process-jobs", "--outcome", "done")
    assert closed["closed"] is True
    finished = page.get_by_role("status").filter(has_text=t("nav.tasks.actions.process-jobs.done"))
    expect(finished).to_be_visible(timeout=25_000)
    shot(page, "notice-done")
    finished.get_by_role("button", name=t("nav.tasks.close")).click()
    expect(finished).to_have_count(0)


def test_a_question_is_answered_in_the_portal(page: Page, fresh_demo_app: AppServer) -> None:
    server = fresh_demo_app
    page.goto(f"{server.url}/como-funciona")
    asked = cai(server, "prompts", "ask", "--question", "¿Has trabajado con Airflow?")

    dialog = page.get_by_role("dialog")
    expect(dialog.get_by_text("¿Has trabajado con Airflow?")).to_be_visible(timeout=25_000)
    shot(page, "question")
    dialog.get_by_role("textbox", name=t("prompts.question.label")).fill("Dos años, en Akkodis")
    dialog.get_by_role("button", name=t("prompts.question.send")).click()
    expect(dialog).to_have_count(0)

    waited = cai(server, "prompts", "wait", str(asked["id"]), "--max-wait-seconds", "0")
    assert (waited["status"], waited["answer"]) == ("done", "Dos años, en Akkodis")


def test_a_correction_that_does_not_fit_is_not_published(fresh_demo_app: AppServer) -> None:
    server = fresh_demo_app
    job_id = job_ready_to_apply(server, "Una Página SL", "https://example.com/jobs/una-pagina")
    original = api(server, f"/jobs/{job_id}/cv")["cv"]["document_id"]
    versions = len(api(server, f"/jobs/{job_id}/cv/history")["versions"])

    created = httpx.post(
        f"{server.url}/jobs/{job_id}/cv/corrections",
        json={"instruction": "Quiero que ocupe solo 1 página"},
        headers={"Origin": server.url},
        timeout=30,
    )
    assert created.status_code == 201, created.text
    pending = cai(server, "cv", "correction", str(job_id))
    assert pending["max_pages"] == 1
    correction = pending["correction"]["id"]

    # Muchísimo contenido: con la plantilla real no cabe en una página.
    long_content = copy.deepcopy(demo_cv_content())
    long_content["summary"] = (long_content["summary"] + " ") * 12
    long_content["summary"] = long_content["summary"][:1190]
    for item in long_content["experience"]:
        item["bullets"] = copy.deepcopy((item["bullets"] * 12)[:12])
        for bullet in item["bullets"]:
            bullet["text"] = ((bullet["text"] + " ") * 12)[:395]
    payload = {"content": long_content, "correction_id": correction}

    check = cai(server, "cv", "check-fit", str(job_id), payload=payload)
    assert (check["fits"], check["max_pages"]) == (False, 1), check
    assert check["pages"] > 1

    outcome = _cai_error(server, job_id, payload)
    assert outcome["type"] == "too_long", outcome

    # Nada ha cambiado: ni versión nueva, ni corrección cerrada.
    assert api(server, f"/jobs/{job_id}/cv")["cv"]["document_id"] == original
    assert len(api(server, f"/jobs/{job_id}/cv/history")["versions"]) == versions
    still = cai(server, "cv", "correction", str(job_id))
    assert still["correction"]["status"] == "pending"


def _cai_error(server: AppServer, job_id: int, payload: object) -> dict[str, object]:
    path = server.data_dir / "tmp" / "too-long.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    done = run_cai(server.data_dir, "cv", "save", str(job_id), "--file", str(path), "--json")
    assert done.returncode != 0
    return json.loads(done.stdout)["error"]


def test_your_templates_are_renamed_and_deleted_in_the_list(
    page: Page, fresh_demo_app: AppServer
) -> None:
    server = fresh_demo_app
    builtin = Path(__file__).resolve().parents[3] / "templates" / "ats-simple"
    target = server.data_dir / "templates" / "de-prueba"
    shutil.copytree(builtin, target)
    meta = target / "template.yaml"
    text = meta.read_text(encoding="utf-8")
    text = re.sub(r"^id: .*$", "id: de-prueba", text, count=1, flags=re.M)
    text = re.sub(r"^name: .*$", "name: Plantilla de prueba", text, count=1, flags=re.M)
    meta.write_text(re.sub(r"^origin: .*$", "origin: user", text, count=1, flags=re.M), "utf-8")

    page.goto(f"{server.url}/perfil/plantillas")
    card = page.get_by_role("article", name="Plantilla de prueba")
    expect(card).to_be_visible()
    card.scroll_into_view_if_needed()
    expect(card.get_by_role("img").first).to_be_visible()
    shot(page, "templates")

    card.get_by_role(
        "button", name=t("templates.actions.rename", name="Plantilla de prueba")
    ).click()
    card.get_by_role("textbox", name=t("templates.actions.nameLabel")).fill("La definitiva")
    card.get_by_role("button", name=t("templates.actions.saveName")).click()
    renamed = page.get_by_role("article", name="La definitiva")
    expect(renamed).to_be_visible()
    assert "name: La definitiva" in meta.read_text(encoding="utf-8")

    renamed.get_by_role(
        "button", name=t("templates.actions.deleteAria", name="La definitiva")
    ).click()
    dialog = page.get_by_role("dialog")
    shot(page, "templates-delete")
    dialog.get_by_role("button", name=t("templates.actions.confirmDelete")).click()
    expect(dialog).to_have_count(0)
    expect(page.get_by_role("article", name="La definitiva")).to_have_count(0)
    assert not target.exists()

    # Las integradas no ofrecen ni renombrar ni eliminar.
    integrated = page.get_by_role("article").first
    expect(
        integrated.get_by_role("button", name=re.compile(t("templates.actions.delete")))
    ).to_have_count(0)


def test_a_job_ready_to_send_is_discarded_with_a_reason_and_reopened(
    page: Page, fresh_demo_app: AppServer
) -> None:
    server = fresh_demo_app
    job_id = job_ready_to_apply(server, "Cerrada SL", "https://example.com/jobs/cerrada")
    page.goto(f"{server.url}/jobs/{job_id}")
    page.get_by_role("button", name=t("job.decision.discard"), exact=True).click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("radio", name=re.compile(t("labels.discardReason.closed"))).click()
    shot(page, "discard")
    dialog.get_by_role("button", name=t("triage.discardDialog.discard"), exact=True).click()
    expect(dialog).to_have_count(0)
    expect(page.get_by_role("button", name=t("job.decision.reopen"))).to_be_visible()
    assert projected_stage(server, job_id) == "closed"

    page.get_by_role("button", name=t("job.decision.reopen")).click()
    expect(page.get_by_role("button", name=t("job.decision.discard"), exact=True)).to_be_visible()
    assert projected_stage(server, job_id) == "cv_ready"
