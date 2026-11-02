"""Corregir un CV ya generado: pedirlo desde la ficha, que lo aplique el agente (simulado), ver qué
cambió, volver a la versión anterior y editar el texto a mano."""

import copy
import re

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.agent import api, cai, demo_cv_content
from tests.e2e.flows import application_tab, job_ready_to_apply
from tests.e2e.harness import AppServer, t

pytestmark = pytest.mark.e2e

SHORTER = "Resumen corregido por el agente simulado."


def _current_document(server: AppServer, job_id: int) -> int:
    return int(api(server, f"/jobs/{job_id}/cv")["cv"]["document_id"])


def test_correct_go_back_and_edit(page: Page, fresh_demo_app: AppServer) -> None:
    server = fresh_demo_app
    job_id = job_ready_to_apply(server, "Correcciones SL", "https://example.com/jobs/correcciones")
    original = _current_document(server, job_id)
    application_tab(page, job_id)
    section = page.get_by_role("region", name=t("cv.title"), exact=True)

    # Lo pide en la ficha y lo deja para su próxima sesión; el texto no va en la orden del encargo.
    section.get_by_label(t("cv.correction.label")).fill("El resumen más corto")
    button = section.locator('[data-slot="agent-button"]').filter(
        has_text=t("cv.correction.submit")
    )
    button.get_by_role("button").nth(1).click()
    page.get_by_role("menuitem", name=re.compile(t("agentButton.later"))).click()
    expect(section.get_by_text(t("cv.correction.pending"))).to_be_visible()
    requests = cai(server, "requests", "list")["requests"]
    assert [r["action"] for r in requests if r["job_id"] == job_id] == ["correct-cv"]
    assert "resumen" not in requests[-1]["prompt"].lower()

    # El agente simulado lee lo pedido y guarda la versión corregida.
    pending = cai(server, "cv", "correction", str(job_id))
    assert pending["correction"]["instruction"] == "El resumen más corto"
    assert pending["document_id"] == original
    content = copy.deepcopy(demo_cv_content())
    content["summary"] = SHORTER
    saved = cai(
        server,
        "cv", "save", str(job_id),
        payload={"content": content, "correction_id": pending["correction"]["id"]},
    )  # fmt: skip

    # La ficha se entera sola: versión nueva vigente, qué cambió y la anterior conservada.
    versions = section.get_by_role("region", name=t("cv.history.title"), exact=True)
    expect(versions.get_by_text(t("cv.history.origin.correction"))).to_be_visible(timeout=15_000)
    expect(versions.get_by_text(SHORTER)).to_be_visible()
    assert _current_document(server, job_id) == saved["document_id"]

    # Volver no borra nada: la corregida sigue en la lista.
    versions.get_by_role("button", name=t("cv.history.restore")).click()
    expect(versions.get_by_role("listitem").filter(
        has_text=t("cv.history.origin.generated")
    ).get_by_text(t("cv.history.current"))).to_be_visible()  # fmt: skip
    assert _current_document(server, job_id) == original
    assert len(api(server, f"/jobs/{job_id}/cv/history")["versions"]) == 2

    # Edición directa: versión nueva, sin agente, sin verificar y avisando de la cifra nueva.
    section.get_by_role("button", name=t("cv.edit.open")).click()
    form = section.get_by_role("form", name=t("cv.edit.form"))
    form.get_by_label(t("cv.edit.summary")).fill("Resumen editado a mano: 987654 clientes.")
    form.get_by_role("button", name=t("cv.edit.save")).click()
    expect(section.get_by_text(t("cv.edit.warning.number", value="987654"))).to_be_visible(
        timeout=30_000
    )
    newest = api(server, f"/jobs/{job_id}/cv/history")["versions"][0]
    assert newest["origin"] == "edit" and newest["current"] and newest["verified"] is None
    expect(versions.get_by_text(t("cv.history.origin.edit"))).to_be_visible()
    expect(
        section.get_by_role("button", name=re.compile(t("cv.verification.verify")))
    ).to_be_visible()
