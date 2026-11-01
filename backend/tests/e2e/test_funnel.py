"""El embudo principal con la demo: dar de alta ofertas (texto, URL y extensión), la extracción y la
valoración de tu agente, la bandeja y el triaje, el CV y la carta, la candidatura asistida contra un
formulario local y el seguimiento.

El agente se simula con los comandos `cai … --json` (`tests/e2e/agent.py`). Las webs de terceros
(el ATS de la oferta y el formulario) las sirve `tests/e2e/sites.py` en 127.0.0.1.
"""

import re
from collections.abc import Iterator

import httpx
import pytest
from playwright.sync_api import Locator, Page, expect

from tests.e2e.agent import api, cai, demo_cv_content, demo_extras, extraction, find_job, text_of
from tests.e2e.flows import (
    application_tab,
    days_ago,
    job_ready_to_apply,
    new_job_by_text,
    templates,
    timeline,
    wait_for_stage,
)
from tests.e2e.harness import AppServer, t
from tests.e2e.sites import SUBMIT_PATH, Sites

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def sites() -> Iterator[Sites]:
    with Sites() as running:
        yield running


@pytest.fixture(scope="module")
def app_extra_env(sites: Sites) -> dict[str, str]:
    return sites.app_env()


# --- Alta -------------------------------------------------------------------------------------


def test_a_pasted_job_waits_for_extraction_with_its_risk_flag(
    page: Page, demo_app: AppServer
) -> None:
    new_job_by_text(page, "Data Platform Engineer", "Ría Analítica", text_of("oferta-texto.txt"))
    job = find_job(demo_app, "Ría Analítica")
    assert job["stage"] == "pending_extraction"
    assert "injection_phrase" in job["risk_flags"]

    page.goto("/bandeja")
    page.get_by_role("searchbox", name=t("inbox.search")).fill("Ría Analítica")
    row = page.get_by_role("row").filter(has_text="Data Platform Engineer")
    expect(row).to_have_count(1)
    expect(row.get_by_text(t("inbox.notExtracted"))).to_be_visible()
    expect(row.get_by_label(t("inbox.risk"))).to_be_visible()

    page.goto(f"/jobs/{job['id']}")
    expect(page.get_by_role("heading", level=1)).to_have_text("Data Platform Engineer")
    expect(page.get_by_text(t("job.injection.title"))).to_be_visible()
    expect(page.get_by_role("heading", name=t("job.fitSteps.title"))).to_be_visible()


def test_a_job_by_url_is_downloaded_once_and_not_duplicated(
    page: Page, demo_app: AppServer, sites: Sites
) -> None:
    downloads_before = sites.job_downloads
    for attempt in range(2):
        page.goto("/nueva")
        page.get_by_label(t("newJob.url.label")).fill(sites.job_url)
        page.get_by_role("button", name=t("newJob.url.submit")).click()
        added = t("job.added.created") if attempt == 0 else t("job.added.exists")
        expect(page.get_by_text(added)).to_be_visible()
    job = find_job(demo_app, "Lumbre Datos")
    assert job["title"] == "Analytics Engineer"
    assert job["url"] == sites.job_url
    # La segunda vez reconoce la URL sin volver a descargarla.
    assert sites.job_downloads - downloads_before == 1, "la oferta pasa por el proxy local"


def test_the_extension_endpoint_needs_its_origin_and_token(demo_app: AppServer) -> None:
    client = httpx.Client(base_url=demo_app.url, timeout=15, trust_env=False)
    # «Conectar» en la UI: un token nuevo.
    pairing = client.post("/capture/pair", json={})
    pairing.raise_for_status()
    token, extension_id = pairing.json()["token"], pairing.json()["extension_id"]
    origin = f"chrome-extension://{extension_id}"
    body = {
        "url": "https://empleo.ejemplo.test/ofertas/bi-developer-77",
        "title": "BI Developer",
        "company": "Faro Métricas",
        "location": "Lugo",
        "text": text_of("oferta-texto.txt").replace("Data Platform Engineer", "BI Developer"),
    }
    without_token = client.post("/capture", json=body, headers={"Origin": origin})
    assert without_token.status_code == 401
    other_origin = client.post(
        "/capture",
        json=body,
        headers={"Origin": "https://web-cualquiera.test", "Authorization": f"Bearer {token}"},
    )
    assert other_origin.status_code == 403
    sent = client.post(
        "/capture", json=body, headers={"Origin": origin, "Authorization": f"Bearer {token}"}
    )
    assert sent.status_code == 200, sent.text
    again = client.post(
        "/capture", json=body, headers={"Origin": origin, "Authorization": f"Bearer {token}"}
    )
    assert again.json()["status"] != sent.json()["status"]
    assert find_job(demo_app, "Faro Métricas")["title"] == "BI Developer"


# --- Extracción y valoración ----------------------------------------------------------------


def test_the_agents_extraction_and_assessment_show_in_the_job(
    page: Page, fresh_demo_app: AppServer, sites: Sites
) -> None:
    demo_app = fresh_demo_app  # su propia oferta, sin depender del orden de los tests
    added = httpx.post(
        f"{demo_app.url}/jobs/url", json={"url": sites.job_url}, timeout=30, trust_env=False
    )
    added.raise_for_status()
    job = api(demo_app, f"/jobs/{added.json()['job_id']}")
    saved = cai(demo_app, "jobs", "save-extraction", str(job["id"]), payload=extraction())
    assert saved["stage"] == "pending_triage"
    match = api(demo_app, f"/jobs/{job['id']}/match")
    assert match["score"] is not None
    assessment = {
        "verdict": "strong",
        "rationale": "Pide dbt, Snowflake y SQL, que están en tu perfil con logros que lo prueban.",
        "risks": ["El inglés B2 que piden es justo tu nivel."],
        "questions_for_user": ["¿Te encaja ir dos días a la oficina de A Coruña?"],
    }
    cai(demo_app, "match", "save-assessment", str(job["id"]), payload=assessment)

    page.goto(f"/jobs/{job['id']}")
    expect(page.get_by_label(t("match.scoreAria", score=match["score"])).first).to_be_visible()
    expect(page.get_by_text(t("labels.verdict.strong")).first).to_be_visible()
    expect(page.get_by_text(assessment["rationale"])).to_be_visible()
    expect(page.get_by_text("¿Te encaja ir dos días a la oficina de A Coruña?")).to_be_visible()


# --- Bandeja y triaje -------------------------------------------------------------------------


def _starts(text: str) -> "re.Pattern[str]":
    """El nombre de un botón que lleva dentro su atajo de teclado («Aprobar A»)."""
    return re.compile(rf"^{re.escape(text)}")


def _total(server: AppServer, **params: str) -> int:
    return int(api(server, "/jobs", limit=1, **params)["total"])


def _selected_job_id(page: Page) -> int:
    selected = page.get_by_role("article", name=t("triage.selected"))
    href = selected.get_by_role("link", name=t("triage.detail")).get_attribute("href")
    assert href is not None
    return int(href.rstrip("/").rsplit("/", 1)[-1])


def _discard_with_reason(page: Page, reason: str, note: str = "") -> None:
    dialog = page.get_by_role("dialog", name=t("triage.discardDialog.title"))
    dialog.get_by_role("radio", name=t(f"labels.discardReason.{reason}")).click()
    if note:
        dialog.get_by_label(t("triage.discardDialog.note"), exact=False).fill(note)
    dialog.get_by_role("button", name=t("triage.discardDialog.discard"), exact=True).click()
    expect(dialog).to_be_hidden()


def test_triage_approves_discards_with_reason_and_undoes(
    page: Page, fresh_demo_app: AppServer
) -> None:
    server = fresh_demo_app
    pending = _total(server, stage="pending_triage")
    assert pending >= 3, "la demo trae ofertas por revisar"
    page.goto("/por-revisar")
    count = page.get_by_text(t("triage.count_other", count=pending))
    expect(count).to_be_visible()
    selected = page.get_by_role("article", name=t("triage.selected"))

    # Descartar con motivo y deshacer (aprobar no se deshace: se reabre desde la ficha).
    discarded_id = _selected_job_id(page)
    selected.get_by_role("button", name=_starts(t("triage.discard"))).click()
    _discard_with_reason(page, "salary", "Pide más presencialidad de la que busco.")
    notice = page.get_by_role("status").filter(has_text=t("triage.done.discarded"))
    expect(notice).to_contain_text(t("labels.discardReason.salary"))
    expect(page.get_by_text(t("triage.count_other", count=pending - 1))).to_be_visible()
    assert api(server, f"/jobs/{discarded_id}")["stage"] == "closed"
    notice.get_by_role("button", name=t("triage.done.undo")).click()
    expect(count).to_be_visible()
    assert api(server, f"/jobs/{discarded_id}")["stage"] == "pending_triage"
    history = timeline(page, discarded_id)
    expect(history.get_by_text(t("labels.event.discarded"), exact=True)).to_be_visible()
    reason = t("job.events.reason", reason=t("labels.discardReason.salary"))
    expect(history.get_by_text(reason)).to_be_visible()
    expect(history.get_by_text(t("labels.event.reopened"), exact=True)).to_be_visible()

    # Descartar de verdad: el contador baja.
    page.goto("/por-revisar")
    discarded_id = _selected_job_id(page)
    selected.get_by_role("button", name=_starts(t("triage.discard"))).click()
    _discard_with_reason(page, "seniority")
    expect(page.get_by_text(t("triage.count_other", count=pending - 1))).to_be_visible()
    assert api(server, f"/jobs/{discarded_id}")["stage"] == "closed"

    # Aprobar: sale de la cola y queda como evento.
    approved_id = _selected_job_id(page)
    assert approved_id != discarded_id
    selected.get_by_role("button", name=_starts(t("triage.approve"))).click()
    notice = page.get_by_role("status").filter(has_text=t("triage.done.approved"))
    expect(notice).to_be_visible()
    expect(page.get_by_text(t("triage.count_other", count=pending - 2))).to_be_visible()
    assert api(server, f"/jobs/{approved_id}")["stage"] == "approved"
    history = timeline(page, approved_id)
    expect(history.get_by_text(t("labels.event.approved"), exact=True)).to_be_visible()


def test_inbox_filters_searches_pages_and_discards(page: Page, fresh_demo_app: AppServer) -> None:
    server = fresh_demo_app
    total = _total(server)
    assert total > 50, "la demo llena más de dos páginas de 25"
    page.goto("/bandeja")
    expect(page.get_by_text(t("inbox.count_other", count=total))).to_be_visible()
    table = page.get_by_role("table")
    expect(table.get_by_role("row")).to_have_count(25 + 1)  # y la cabecera
    pager = page.get_by_role("navigation", name=t("common.pager.label"))
    expect(pager.get_by_text(t("common.pager.range", **{"from": 1, "to": 25, "total": total})))
    pager.get_by_role("button", name=t("common.pager.next")).click()
    expect(
        pager.get_by_text(t("common.pager.range", **{"from": 26, "to": 50, "total": total}))
    ).to_be_visible()

    # Filtro por etapa.
    approved = _total(server, stage="approved")
    stages = page.get_by_role("radiogroup", name=t("inbox.filterStage"))
    stages.get_by_role("radio", name=t("labels.stage.approved")).click()
    expect(page.get_by_text(t("inbox.count_other", count=approved))).to_be_visible()
    stages.get_by_role("radio", name=t("inbox.allStages")).click()

    # Las que están por extraer se quitan desde la fila (con otro motivo) y se deshace.
    job = api(server, "/jobs", stage="pending_extraction", limit=1)["items"][0]
    stages.get_by_role("radio", name=t("labels.stage.pending_extraction")).click()
    page.get_by_role("searchbox", name=t("inbox.search")).fill(job["company"])
    row = table.get_by_role("row").filter(has_text=job["title"])
    expect(row).to_have_count(1)
    row.get_by_role("button", name=t("inbox.quick.moreReasons", title=job["title"])).click()
    page.get_by_role("menuitem", name=t("inbox.quick.otherReason")).click()
    _discard_with_reason(page, "company")
    notice = page.get_by_role("status").filter(has_text=t("inbox.quick.discarded"))
    expect(notice).to_contain_text(t("labels.discardReason.company"))
    expect(row).to_have_count(0)
    assert api(server, f"/jobs/{job['id']}")["stage"] == "closed"
    notice.get_by_role("button", name=t("inbox.quick.undo")).click()
    expect(row).to_have_count(1)
    assert api(server, f"/jobs/{job['id']}")["stage"] == "pending_extraction"

    # Aprobar, desde la ficha.
    job = api(server, "/jobs", stage="pending_triage", limit=1)["items"][0]
    page.goto(f"/jobs/{job['id']}")
    page.get_by_role("button", name=t("job.decision.approve"), exact=True).click()
    expect(page.get_by_text(t("labels.stage.approved")).first).to_be_visible()
    assert api(server, f"/jobs/{job['id']}")["stage"] == "approved"


# --- CV y carta -------------------------------------------------------------------------------


def _check_pdf(page: Page, link: Locator) -> None:
    href = link.get_attribute("href")
    assert href is not None
    response = page.request.get(href)
    assert response.ok and response.body().startswith(b"%PDF"), href


def _check_docx(page: Page, link: Locator) -> None:
    with page.expect_download() as download:
        link.click()
    path = download.value.path()
    assert path.read_bytes().startswith(b"PK"), "un .docx es un zip"


@pytest.mark.smoke
def test_pasted_approved_and_cv_ready_to_download(page: Page, fresh_demo_app: AppServer) -> None:
    """El recorrido corto del humo: pegar una oferta, que tu agente la lea, aprobarla y descargar
    el CV que redacta."""
    server = fresh_demo_app
    new_job_by_text(page, "Data Platform Engineer", "Ría Analítica", text_of("oferta-texto.txt"))
    job_id = find_job(server, "Ría Analítica")["id"]
    cai(server, "jobs", "save-extraction", str(job_id), payload=extraction())

    page.goto(f"/jobs/{job_id}")
    page.get_by_role("button", name=t("job.decision.approve"), exact=True).click()
    expect(page.get_by_role("tab", name=t("job.tabs.application"))).to_be_visible()
    assert api(server, f"/jobs/{job_id}")["stage"] == "approved"

    template, _ = templates()
    saved = cai(
        server,
        "cv", "save", str(job_id),
        payload={"content": demo_cv_content(), "render_options": {"template_id": template}},
    )  # fmt: skip
    application_tab(page, job_id)
    cv = page.get_by_role("region", name=t("cv.title"), exact=True)
    expect(cv.get_by_text(t("cv.verification.pending"))).to_be_visible()
    cai(server, "cv", "save-verification", str(saved["document_id"]), payload={"passed": True})
    page.reload()
    expect(cv.get_by_text(t("cv.verification.passed"))).to_be_visible()
    assert api(server, f"/jobs/{job_id}")["stage"] == "cv_ready"
    _check_pdf(page, cv.get_by_role("link", name=t("cv.viewPdf")).first)
    if saved["render"]["docx_path"]:
        _check_docx(page, cv.get_by_role("link", name="DOCX").first)


def test_cv_changes_template_and_the_letter_is_verified_and_downloads(
    page: Page, demo_app: AppServer
) -> None:
    job = api(demo_app, "/jobs", stage="cv_ready", limit=1)["items"][0]
    template, other = templates()
    application_tab(page, job["id"])
    cv = page.get_by_role("region", name=t("cv.title"), exact=True)
    expect(cv.get_by_text(t("cv.verification.passed"))).to_be_visible()

    if other is not None:  # sin conversor a PDF solo hay una plantilla que lo saque
        cv.get_by_text(t("cv.changeDesign")).click()
        form = cv.get_by_role("form", name=t("cv.renderForm"))
        form.locator(f'input[name="template"][value="{other}"]').check(force=True)
        form.get_by_role("button", name=t("cv.render"), exact=True).click()
        expect(form.get_by_role("button", name=t("cv.render"), exact=True)).to_be_enabled(
            timeout=120_000
        )
        cv_view = api(demo_app, f"/jobs/{job['id']}/cv")["cv"]
        renders = [r["template_id"] for r in cv_view["renders"]]
        assert other in renders and template in renders

    # La carta: sin verificar al guardarla; verificada y descargable después.
    letter_content = demo_extras()["cover_letter"]["content"]
    saved = cai(demo_app, "letter", "save", str(job["id"]), payload={"content": letter_content})
    page.reload()
    letter = page.get_by_role("region", name=t("letter.title"), exact=True)
    expect(letter.get_by_text(t("letter.status.notVerified"))).to_be_visible()
    cai(
        demo_app,
        "letter", "save-verification", str(saved["document_id"]),
        payload={"passed": True},
    )  # fmt: skip
    page.reload()
    expect(letter.get_by_text(t("letter.status.verified"))).to_be_visible()
    _check_pdf(page, letter.get_by_role("link", name=t("letter.render.downloadPdf")).first)


# --- Candidatura asistida y seguimiento --------------------------------------------------------

FORM_COMPANY = "Lumbre Datos"


def test_assisted_application_sends_only_after_confirming_and_then_follow_up(
    page: Page, fresh_demo_app: AppServer, sites: Sites
) -> None:
    server = fresh_demo_app
    job_id = job_ready_to_apply(server, FORM_COMPANY, sites.form_url)
    posts_before = len(sites.posts)

    # Preparar: rellena en el navegador de la app y se para antes de enviar.
    application_tab(page, job_id)
    apply = page.get_by_role("region", name=t("apply.title"), exact=True)
    apply.get_by_role("button", name=t("apply.prepare.prepare")).click()
    expect(apply.get_by_text(t("apply.attemptStatus.ready"))).to_be_visible(timeout=120_000)
    fields = apply.get_by_role("table", name=t("apply.fields.caption"))
    for label in ("Nombre", "Correo electrónico", "Adjunta tu CV"):
        row = fields.get_by_role("row").filter(has_text=label)
        expect(row.get_by_text(t("apply.fieldStatus.filled"))).to_be_visible()
    for question in ("modelado dimensional", "años de experiencia tienes con Python"):
        row = fields.get_by_role("row").filter(has_text=question)
        expect(row.get_by_text(t("apply.fieldStatus.filled"))).to_be_visible()
    assert len(sites.posts) == posts_before, "rellenar no envía nada"

    # Sin confirmar, nada: cancelar el diálogo no envía.
    apply.get_by_role("button", name=t("apply.review.send"), exact=True).click()
    dialog = page.get_by_role("dialog", name=t("apply.submit.title", company=FORM_COMPANY))
    send = dialog.get_by_role("button", name=t("apply.submit.send"))
    expect(send).to_be_disabled()
    dialog.get_by_label(t("apply.submit.typeCompany")).fill("Otra Empresa")
    expect(send).to_be_disabled()
    dialog.get_by_role("button", name=t("apply.submit.cancel")).click()
    expect(dialog).to_be_hidden()
    assert len(sites.posts) == posts_before
    assert api(server, f"/jobs/{job_id}")["stage"] == "cv_ready"

    # Con tu confirmación, un solo envío y la oferta pasa a «Enviada» con su evento.
    apply.get_by_role("button", name=t("apply.review.send"), exact=True).click()
    dialog.get_by_label(t("apply.submit.typeCompany")).fill(FORM_COMPANY)
    send.click()
    expect(page.get_by_role("tab", name=t("job.tabs.process"))).to_be_visible(timeout=120_000)
    wait_for_stage(page, server, job_id, "applied")
    assert sites.posts[posts_before:] == [SUBMIT_PATH]
    history = timeline(page, job_id)
    expect(history.get_by_text(t("labels.event.applied"), exact=True)).to_be_visible()

    # En Procesos, esperando respuesta y aún sin seguimiento.
    page.goto("/procesos")
    applied = page.get_by_role("region", name=t("labels.stage.applied"), exact=True)
    card = applied.locator("li").filter(has_text=FORM_COMPANY)
    expect(card).to_be_visible()
    followup = re.compile(re.escape(t("processes.card.followup", count=0).split("·")[0]))
    expect(card.get_by_text(followup)).to_have_count(0)

    # Diez días después, toca el seguimiento; marcarlo hecho lo quita.
    days_ago(server, job_id, 10)
    page.reload()
    expect(card.get_by_text(t("processes.card.followup", count=10))).to_be_visible()
    page.goto(f"/jobs/{job_id}")
    page.get_by_role("tab", name=t("job.tabs.process")).click()
    panel = page.get_by_role("tabpanel")
    expect(panel.get_by_text(t("process.sending.followupDue", count=10))).to_be_visible()
    panel.get_by_role("button", name=t("process.sending.followupSent")).click()
    expect(panel.get_by_text(t("process.sending.followupDue", count=10))).to_be_hidden()
    page.goto("/procesos")
    expect(card).to_be_visible()
    expect(card.get_by_text(t("processes.card.followup", count=10))).to_have_count(0)
    history = timeline(page, job_id)
    expect(history.get_by_text(t("labels.event.followup_sent"), exact=True)).to_be_visible()
