"""Pasos que comparten los recorridos de las E2E: los de la UI (dar de alta, abrir una pestaña de la
ficha, leer su etapa) y los que dejan una oferta en un punto del embudo como lo harían tu agente y
tú, para empezar el recorrido desde ahí.

El reloj del equipo no se toca: lo que tiene que haber pasado hace días se atrasa en la base
temporal (`days_ago`, `milestone_days_ago`).
"""

import sqlite3
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import httpx
from playwright.sync_api import Locator, Page, expect

from app.services import pipeline
from app.services.documents import pdf
from tests.e2e.agent import api, cai, demo_cv_content, demo_extras, extraction, find_job, text_of
from tests.e2e.harness import AppServer, t


def new_job_by_text(page: Page, title: str, company: str, text: str, url: str = "") -> None:
    page.goto("/nueva")
    page.get_by_role("tab", name=t("newJob.pasteText")).click()
    page.get_by_label(t("newJob.text.title")).fill(title)
    page.get_by_label(t("newJob.text.company")).fill(company)
    if url:
        page.get_by_label(t("newJob.text.url")).fill(url)
    page.get_by_label(t("newJob.text.text")).fill(text)
    page.get_by_role("button", name=t("newJob.text.submit")).click()
    expect(page.get_by_text(t("job.added.created"))).to_be_visible()


# --- Ficha ------------------------------------------------------------------------------------


def job_tab(page: Page, job_id: int, tab: str) -> Locator:
    """Abre la ficha en una pestaña (`overview`, `application`, `process`, `company`, `history`)
    y devuelve su panel."""
    page.goto(f"/jobs/{job_id}")
    page.get_by_role("tab", name=t(f"job.tabs.{tab}")).click()
    return page.get_by_role("tabpanel")


def timeline(page: Page, job_id: int) -> Locator:
    return job_tab(page, job_id, "history")


def application_tab(page: Page, job_id: int) -> None:
    job_tab(page, job_id, "application")


def stage_badge(page: Page) -> Locator:
    """La etapa que enseña la cabecera de la ficha abierta (la del título de la oferta)."""
    return page.locator("header").filter(has=page.get_by_role("heading", level=1))


def projected_stage(server: AppServer, job_id: int) -> str:
    """La etapa que da la proyección de `DATA_MODEL.md` (`pipeline.stage_for`) con los eventos de
    la oferta tal como los devuelve la interfaz para agentes."""
    timeline_out = cai(server, "events", "list", str(job_id))
    events = [
        SimpleNamespace(
            type=e["type"],
            payload=e["payload"],
            occurred_at=datetime.fromisoformat(e["occurred_at"]),
        )
        for e in timeline_out["events"]
    ]
    return pipeline.stage_for(events).value


def record_event(server: AppServer, job_id: int, event: str, **body: Any) -> dict[str, Any]:
    """Un evento como lo registra la UI (actor `user`)."""
    response = httpx.post(
        f"{server.url}/jobs/{job_id}/events",
        json={"type": event, **body},
        timeout=30,
        trust_env=False,
    )
    assert response.is_success, response.text
    out: dict[str, Any] = response.json()
    return out


def wait_for_stage(page: Page, server: AppServer, job_id: int, stage: str) -> None:
    """La etapa la cambia el worker: se espera a que llegue, sin `sleep` (con el reloj de la
    página, que no bloquea el navegador)."""
    for _ in range(120):
        if api(server, f"/jobs/{job_id}")["stage"] == stage:
            return
        page.wait_for_timeout(500)
    raise AssertionError(f"la oferta {job_id} no llegó a «{stage}»")


# --- La base temporal -------------------------------------------------------------------------


def _db(server: AppServer) -> sqlite3.Connection:
    return sqlite3.connect(server.data_dir / "candidatai.db", timeout=30)


def shift_job(server: AppServer, job_id: int, *, days: int = 0, minutes: int = 0) -> None:
    """Atrasa la oferta: sus eventos y su proyección pasan a haber ocurrido antes."""
    shift = f"-{days * 24 * 60 + minutes} minutes"
    with _db(server) as db:
        db.execute(
            "UPDATE events SET occurred_at = strftime('%Y-%m-%d %H:%M:%f', occurred_at, ?) "
            "WHERE job_id = ?",
            (shift, job_id),
        )
        db.execute(
            "UPDATE applications SET "
            "applied_at = strftime('%Y-%m-%d %H:%M:%f', applied_at, ?), "
            "last_event_at = strftime('%Y-%m-%d %H:%M:%f', last_event_at, ?) WHERE job_id = ?",
            (shift, shift, job_id),
        )


def days_ago(server: AppServer, job_id: int, days: int) -> None:
    """La candidatura, enviada hace `days` días: el seguimiento vence sin esperar."""
    shift_job(server, job_id, days=days)


def milestone_days_ago(server: AppServer, milestone_id: int, days: int) -> None:
    """Pasa un hito a hace `days` días: la entrevista ya ha sido, sin esperar a su fecha."""
    shift = f"-{days} days"
    with _db(server) as db:
        db.execute(
            "UPDATE milestones SET "
            "starts_at = strftime('%Y-%m-%d %H:%M:%f', starts_at, ?), "
            "ends_at = strftime('%Y-%m-%d %H:%M:%f', ends_at, ?) WHERE id = ?",
            (shift, shift, milestone_id),
        )


# --- Ofertas preparadas por el agente --------------------------------------------------------


def templates() -> tuple[str, str | None]:
    """La plantilla del CV y otra a la que cambiar. Como la demo: Word si hay con qué pasarlo a
    PDF (LibreOffice o Word); si no (la CI), la HTML, que lo hace Chromium, y no hay otra."""
    if pdf.converter_name() is not None:
        return "ats-simple", "clasica-foto"
    return "moderna-2col", None


def add_job(server: AppServer, title: str, company: str, url: str) -> int:
    """Una oferta pegada por texto, como la deja el agente (`add_job_from_text`)."""
    tmp = server.data_dir / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    posting = tmp / "e2e-oferta.txt"
    posting.write_text(text_of("oferta-texto.txt"), encoding="utf-8")
    added = cai(
        server,
        "jobs", "add-text", "--title", title, "--company", company, "--url", url,
        "--file", str(posting),
    )  # fmt: skip
    return int(added["job_id"])


def save_verified_cv(server: AppServer, job_id: int) -> None:
    template, _ = templates()
    saved = cai(
        server,
        "cv", "save", str(job_id),
        payload={"content": demo_cv_content(), "render_options": {"template_id": template}},
    )  # fmt: skip
    cai(server, "cv", "save-verification", str(saved["document_id"]), payload={"passed": True})


def job_ready_to_apply(
    server: AppServer, company: str, url: str, *, title: str = "Analytics Engineer"
) -> int:
    """Una oferta con su extracción, aprobada y con el CV verificado y las respuestas de screening:
    lista para enviar."""
    job_id = add_job(server, title, company, url)
    cai(server, "jobs", "save-extraction", str(job_id), payload=extraction())
    record_event(server, job_id, "approved")
    save_verified_cv(server, job_id)
    answers = {"answers": demo_extras()["application_answers"]}
    cai(server, "applications", "save-answers", str(job_id), payload=answers)
    assert api(server, f"/jobs/{job_id}")["stage"] == "cv_ready"
    return job_id


def applied_job(
    server: AppServer, company: str, url: str, *, title: str = "Analytics Engineer"
) -> int:
    """Una candidatura que enviaste por tu cuenta (`applied_manually`) hace un rato: lo que la UI
    registre después, con la hora en minutos, queda detrás."""
    job_id = job_ready_to_apply(server, company, url, title=title)
    record_event(server, job_id, "applied_manually", channel="email")
    shift_job(server, job_id, minutes=30)
    assert api(server, f"/jobs/{job_id}")["stage"] == "applied"
    assert find_job(server, company)["id"] == job_id
    return job_id
