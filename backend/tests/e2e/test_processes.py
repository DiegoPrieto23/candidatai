"""Procesos y después, con la demo: entrevistas, contactos y mensajes,
oferta recibida, seguimientos y agradecimientos, el embudo frente a `get_funnel_stats`, los huecos
de skills y la proyección de etapas de una oferta de principio a fin.

El agente se simula con los comandos `cai … --json` (`tests/e2e/agent.py`).
"""

import re
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta
from email.utils import format_datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from playwright.sync_api import Locator, Page, Request, Response, expect

from tests.e2e.agent import api, cai, extraction, find_job, text_of
from tests.e2e.flows import (
    applied_job,
    days_ago,
    job_ready_to_apply,
    job_tab,
    milestone_days_ago,
    new_job_by_text,
    projected_stage,
    record_event,
    save_verified_cv,
    stage_badge,
    timeline,
)
from tests.e2e.harness import AppServer, t
from tests.e2e.sites import FIXTURES

pytestmark = pytest.mark.e2e

MADRID = ZoneInfo("Europe/Madrid")
COMPANY = "Nordés Datos"
COMPANY_URL = "https://nordesdatos.es/empleo/analytics-engineer"


def _today() -> date:
    return datetime.now(MADRID).date()


def _stage_label(stage: str) -> str:
    return t(f"labels.stage.{stage}")


def _starts(text: str) -> re.Pattern[str]:
    """Un nombre accesible que empieza por el texto (el de una opción del diálogo de mover lleva
    detrás la etapa a la que va y una pista)."""
    return re.compile(rf"^{re.escape(text)}")


def _move(page: Page, button: Locator, event: str) -> None:
    """«¿Qué ha pasado?»: elige el evento en el diálogo y lo registra."""
    button.click()
    dialog = page.get_by_role("dialog", name=t("move.title"))
    dialog.get_by_role("radio", name=_starts(t(f"labels.event.{event}"))).click()
    dialog.get_by_role("button", name=t("move.register")).click()
    expect(dialog).to_be_hidden()


def _status_step(page: Page, server: AppServer, job_id: int, step: str) -> None:
    """Registra un paso desde «¿Qué ha pasado con esta candidatura?» de la ficha."""
    panel = job_tab(page, job_id, "process")
    status = panel.get_by_role("region", name=t("status.label"))
    _move(page, status.get_by_role("button", name=t(f"status.steps.{step}")), step)


def _process_section(page: Page) -> Locator:
    return page.get_by_role("region", name=t("process.title"), exact=True)


def _process_section_of(page: Page, job_id: int) -> Locator:
    job_tab(page, job_id, "process")
    return _process_section(page)


def _add_interview(page: Page, job_id: int, title: str, when: datetime) -> int:
    """Programa una entrevista desde la ficha y devuelve su id."""
    section = _process_section_of(page, job_id)
    section.get_by_role("button", name=t("process.milestones.add")).first.click()
    section.get_by_label(t("process.milestoneForm.kind"), exact=True).select_option("interview")
    section.get_by_label(t("process.milestoneForm.interviewType")).select_option("technical")
    section.get_by_label(t("process.milestoneForm.title")).fill(title)
    section.get_by_label(t("process.milestoneForm.dateTime")).fill(when.strftime("%Y-%m-%dT%H:%M"))
    section.get_by_role("button", name=t("process.milestoneForm.save")).click()
    expect(section.get_by_text(title)).to_be_visible()
    return _milestone_id(page, title)


def _milestone_id(page: Page, title: str) -> int:
    href = page.get_by_role("link", name=t("process.milestone.ics", title=title)).get_attribute(
        "href"
    )
    assert href is not None
    found = re.search(r"/milestones/(\d+)/", href)
    assert found is not None, href
    return int(found.group(1))


# --- Entrevistas ------------------------------------------------------------------------------

GUIDE = {
    "language": "es",
    "title": "Analytics Engineer",
    "subtitle": "Entrevista técnica con el equipo de datos",
    "sections": [
        {"title": "El rol", "blocks": [{"type": "paragraph", "text": "Modelado con dbt."}]},
        {"title": "Tu encaje", "blocks": [{"type": "paragraph", "text": "SQL y Snowflake."}]},
        {"title": "Preguntas", "blocks": [{"type": "paragraph", "text": "¿Cómo pruebas dbt?"}]},
    ],
}


def test_an_interview_is_scheduled_prepared_and_debriefed(
    page: Page, fresh_demo_app: AppServer
) -> None:
    server = fresh_demo_app
    job_id = applied_job(server, COMPANY, COMPANY_URL)
    when = datetime.combine(_today() + timedelta(days=3), datetime.min.time()).replace(hour=10)
    title = "Entrevista técnica con Nordés"
    milestone_id = _add_interview(page, job_id, title, when)
    assert api(server, f"/jobs/{job_id}")["stage"] == "in_process"

    # En el Calendario (agenda de ese día) y en los próximos 7 días de Inicio.
    page.goto(f"/calendario?view=agenda&date={when.date().isoformat()}")
    agenda = page.get_by_role("button", name=_starts(f"10:00 {title} · "))
    expect(agenda).to_contain_text(COMPANY)
    page.goto("/")
    next7 = page.locator("section").filter(
        has=page.get_by_role("heading", name=t("home.panels.next7"))
    )
    expect(next7.get_by_text(title)).to_be_visible()
    upcoming = cai(server, "upcoming")["items"]
    assert any(i["milestone_id"] == milestone_id for i in upcoming)

    # El plan y la guía de tu agente, en la ficha; la guía se descarga en PDF.
    plan = {"blocks": [{"date": _today().isoformat(), "minutes": 45, "topic": "SQL y dbt"}]}
    cai(server, "interviews", "plan", str(milestone_id), payload=plan)
    cai(server, "interviews", "guide", str(milestone_id), payload=GUIDE)
    section = _process_section_of(page, job_id)
    expect(section.get_by_text(t("status.interview.plan_one", count=1, minutes=45))).to_be_visible()
    guide = section.get_by_role("link", name=t("status.interview.guide"))
    href = guide.get_attribute("href")
    assert href is not None
    response = page.request.get(href)
    assert response.ok and response.body().startswith(b"%PDF"), href

    # Una guía nueva conserva la anterior: se ve qué cambió, se vuelve a ella y se puede deshacer.
    changed = deepcopy(GUIDE)
    changed["sections"][0]["blocks"] = [{"type": "paragraph", "text": "Un rol más corto."}]
    cai(server, "interviews", "guide", str(milestone_id), payload=changed)
    section = _process_section_of(page, job_id)
    older = t("status.interview.versions.older.title", date="").split(" ·")[0]
    section.get_by_role("button", name=_starts(older)).click()
    expect(section.get_by_text("Un rol más corto.")).to_be_visible()
    section.get_by_role("button", name=t("status.interview.versions.older.restore")).click()
    # El bloque sigue abierto, y ahora ofrece deshacerlo.
    section.get_by_role("button", name=t("status.interview.versions.newer.restore")).click()
    expect(
        section.get_by_role("button", name=t("status.interview.versions.older.restore"))
    ).to_be_visible()

    # Antes de su día no se puede dar por hecha; después, sí, y el repaso queda en la ficha.
    done = section.get_by_role("button", name=t("process.milestone.doneLater"))
    expect(done).to_be_disabled()
    milestone_days_ago(server, milestone_id, 4)  # ya ha sido, sin tocar el reloj
    section = _process_section_of(page, job_id)
    section.get_by_role("button", name=t("process.milestone.done", title=title)).click()
    expect(section.get_by_text(t("labels.milestoneStatus.done"))).to_be_visible()
    notes = {
        "notes": "Preguntaron por tests en dbt.",
        "next_steps": "Caso práctico la semana próxima.",
    }
    cai(server, "interviews", "notes", str(milestone_id), payload=notes)
    section = _process_section_of(page, job_id)
    expect(section.get_by_text("Preguntaron por tests en dbt.")).to_be_visible()
    expect(section.get_by_text("Caso práctico la semana próxima.")).to_be_visible()

    expect(stage_badge(page)).to_contain_text(_stage_label("in_process"))
    assert projected_stage(server, job_id) == "in_process"
    history = timeline(page, job_id)
    for event in ("applied_manually", "interview_scheduled", "interview_done"):
        expect(history.get_by_text(t(f"labels.event.{event}"), exact=True)).to_be_visible()


# --- Contactos y mensajes ---------------------------------------------------------------------


def test_contacts_and_a_message_that_is_only_copied(page: Page, fresh_demo_app: AppServer) -> None:
    server = fresh_demo_app
    job_id = applied_job(server, COMPANY, COMPANY_URL)
    section = _process_section_of(page, job_id)
    contacts = section.locator("div.space-y-3").filter(
        has=page.get_by_role("heading", name=t("process.contacts.title"))
    )
    contacts.get_by_role("button", name=t("process.contacts.add")).click()
    contacts.get_by_label(t("process.contactForm.name")).fill("Uxía Castro")
    contacts.get_by_label(t("process.contactForm.role")).fill("Talent Partner")
    contacts.get_by_label(t("process.contactForm.relation")).select_option("recruiter")
    contacts.get_by_role("button", name=t("process.contactForm.save")).click()
    expect(contacts.get_by_text("Uxía Castro", exact=True)).to_be_visible()

    # La referencia: pedida y, después, dada.
    referral = contacts.get_by_label(t("process.referral.of", name="Uxía Castro"))
    referral.select_option("requested")
    expect(referral).to_have_value("requested")
    referral.select_option("given")
    expect(referral).to_have_value("given")
    listed = cai(server, "contacts", "list", str(job_id))
    contact = next(c for c in listed["contacts"] if c["name"] == "Uxía Castro")
    assert contact["relation"] == "recruiter"
    assert contact["referral"] == "given"

    # El borrador de tu agente: se copia, y nada sale de la app.
    body = "Hola, Uxía: gracias por tu tiempo. Quedo atenta a los próximos pasos del proceso."
    cai(
        server,
        "drafts", "save", str(job_id),
        payload={
            "kind": "linkedin",
            "body": body,
            "recipient_role": "recruiter",
            "contact_id": contact["id"],
        },
    )  # fmt: skip
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    job_tab(page, job_id, "process")
    drafts = page.get_by_role("region", name=t("drafts.title"))
    expect(drafts.get_by_text(body)).to_be_visible()
    to = t("drafts.toNamed", name="Uxía Castro", role=t("drafts.role.recruiter"))
    expect(drafts.get_by_text(to)).to_be_visible()
    events_before = cai(server, "events", "list", str(job_id))["events"]
    writes: list[str] = []

    def on_request(request: Request) -> None:
        if request.method != "GET":
            writes.append(f"{request.method} {request.url}")

    page.on("request", on_request)
    drafts.get_by_role("button", name=t("drafts.copyText")).click()
    expect(drafts.get_by_role("button", name=t("common.copy.copied"))).to_be_visible()
    assert page.evaluate("navigator.clipboard.readText()") == body
    assert writes == [], "copiar no llama a la app ni a nadie"
    # No hay ningún «Enviar»: solo copiar, marcarlo enviado o descartarlo.
    expect(drafts.get_by_role("button", name=re.compile(r"^Enviar"))).to_have_count(0)

    # «Ya lo he enviado» solo cambia el borrador: no registra eventos ni llama fuera.
    drafts.get_by_role("button", name=t("drafts.sent")).click()
    expect(drafts.get_by_text(body)).to_be_hidden()
    page.remove_listener("request", on_request)
    assert all(w.startswith(f"POST {server.url}/") for w in writes), writes
    assert cai(server, "events", "list", str(job_id))["events"] == events_before


# --- Oferta recibida --------------------------------------------------------------------------


def _amounts(text: str) -> set[int]:
    """Las cifras en euros de un texto («42.000 €», «-3.000 €»), en valor absoluto."""
    return {int(m.replace(".", "")) for m in re.findall(r"(\d{1,3}(?:\.\d{3})+|\d+)\s*€", text)}


def _note_offer(page: Page, job_id: int, *, base: str, variable: str, benefits: str) -> Locator:
    """«Anotar oferta» en la ficha, con sus condiciones."""
    job_tab(page, job_id, "process")
    offer = page.get_by_role("region", name=t("offers.received.title"))
    offer.get_by_role("button", name=t("offers.received.add")).click()
    offer.get_by_label(t("offers.received.form.base")).fill(base)
    offer.get_by_label(t("offers.received.form.variable")).fill(variable)
    offer.get_by_label(t("offers.received.form.mode")).select_option("hybrid")
    offer.get_by_label(t("offers.received.form.location")).fill("A Coruña")
    offer.get_by_label(t("offers.received.form.benefits")).fill(benefits)
    offer.get_by_role("button", name=t("offers.received.form.save")).click()
    expect(offer.get_by_text(benefits)).to_be_visible()
    return offer


def test_a_received_offer_is_noted_compared_and_closes_the_process(
    page: Page, fresh_demo_app: AppServer
) -> None:
    server = fresh_demo_app
    job_id = applied_job(server, COMPANY, COMPANY_URL)
    _status_step(page, server, job_id, "reply_received")
    assert api(server, f"/jobs/{job_id}")["stage"] == "in_process"

    # Anotarla con sus condiciones registra `offer_received`.
    offer = _note_offer(page, job_id, base="42000", variable="3000", benefits="Seguro médico")
    expect(offer.get_by_text(t("offers.received.private"))).to_be_visible()
    events = [e["type"] for e in cai(server, "events", "list", str(job_id))["events"]]
    assert "offer_received" in events

    # Tu agente no ve los importes (privados por defecto) ni tu mínimo.
    shown = cai(server, "received-offers", "show", str(job_id))
    assert shown["base_salary"] is None and shown["variable"] is None
    assert not any("floor" in key or "minimum" in key for key in shown)

    # En Procesos, al lado de la de la demo. Ninguna cifra que no hayas puesto tú o que no salga
    # de restar: la app no propone ninguna.
    page.goto("/procesos")
    comparison = page.get_by_role("region", name=t("offers.comparison.label"))
    expect(comparison.get_by_text(COMPANY)).to_be_visible()
    offers = api(server, "/received-offers")
    allowed: set[int] = set()
    for row in offers["offers"]:
        o = row["offer"]
        values = [o["base_salary"], o["variable"], row["annual_base"], row["annual_total"]]
        values += [row["floor_diff_base"], row["floor_diff_total"], offers["floor_eur"]]
        values += [
            row[f"published_{k}"] for k in ("annual_min", "annual_max", "diff_min", "diff_max")
        ]
        values += [(row["published"] or {}).get(k) for k in ("min", "max")]
        allowed |= {abs(int(v)) for v in values if isinstance(v, int | float)}
    assert _amounts(comparison.inner_text()) <= allowed

    # Aceptarla cierra el proceso con su evento.
    board = page.get_by_role("region", name=_stage_label("in_process"), exact=True)
    card = board.locator("li").filter(has_text=COMPANY)
    _move(
        page,
        card.get_by_role("button", name=t("processes.card.updateAria", title="Analytics Engineer")),
        "accepted",
    )
    assert api(server, f"/jobs/{job_id}")["stage"] == "closed"
    page.goto(f"/jobs/{job_id}")
    expect(stage_badge(page)).to_contain_text(_stage_label("closed"))
    history = timeline(page, job_id)
    expect(history.get_by_text(t("labels.event.accepted"), exact=True)).to_be_visible()

    # Otra oferta rechazada también cierra.
    other = applied_job(server, "Faro Métricas", "https://farometricas.es/empleo/bi")
    _status_step(page, server, other, "rejected")
    assert api(server, f"/jobs/{other}")["stage"] == "closed"
    assert [e["type"] for e in cai(server, "events", "list", str(other))["events"]][-1] == (
        "rejected"
    )


def test_a_step_in_the_same_minute_as_the_last_event(page: Page, fresh_demo_app: AppServer) -> None:
    """Pegas una oferta a la que ya te presentaste, la marcas enviada y enseguida te responden (o
    anotas la respuesta que ya tenías): todo en el mismo minuto."""
    server = fresh_demo_app
    job_id = job_ready_to_apply(server, COMPANY, COMPANY_URL)
    record_event(server, job_id, "applied_manually")
    # El minuto del envío, como lo propone el diálogo mientras no cambia el minuto: así no depende
    # de cuánto tarde el clic.
    applied_at = cai(server, "events", "list", str(job_id))["events"][-1]["occurred_at"]
    minute = datetime.fromisoformat(applied_at).astimezone(MADRID).strftime("%Y-%m-%dT%H:%M")
    panel = job_tab(page, job_id, "process")
    status = panel.get_by_role("region", name=t("status.label"))
    status.get_by_role("button", name=t("status.steps.reply_received")).click()
    dialog = page.get_by_role("dialog", name=t("move.title"))
    dialog.get_by_label(t("move.when")).fill(minute)
    dialog.get_by_role("button", name=t("move.register")).click()
    expect(dialog).to_be_hidden()
    assert api(server, f"/jobs/{job_id}")["stage"] == "in_process"


# --- Seguimientos y agradecimientos -----------------------------------------------------------


def test_follow_up_and_thank_you_drafts_are_marked_sent(
    page: Page, fresh_demo_app: AppServer
) -> None:
    server = fresh_demo_app

    # Un silencio de 10 días: toca seguimiento.
    quiet = applied_job(server, COMPANY, COMPANY_URL)
    days_ago(server, quiet, 10)
    due = cai(server, "followups")
    assert any(f["job_id"] == quiet and f["days_waiting"] >= 10 for f in due["followups"])
    cai(
        server,
        "drafts", "save", str(quiet),
        payload={
            "kind": "followup",
            "subject": "Mi candidatura a Analytics Engineer",
            "body": "Hola: os escribo para saber si hay novedades sobre mi candidatura.",
        },
    )  # fmt: skip

    # Una entrevista hecha: toca agradecer.
    interviewed = applied_job(server, "Faro Métricas", "https://farometricas.es/empleo/bi")
    when = datetime.combine(_today() + timedelta(days=2), datetime.min.time()).replace(hour=12)
    milestone_id = _add_interview(page, interviewed, "Entrevista con Faro", when)
    milestone_days_ago(server, milestone_id, 3)
    section = _process_section_of(page, interviewed)
    section.get_by_role(
        "button", name=t("process.milestone.done", title="Entrevista con Faro")
    ).click()
    expect(section.get_by_text(t("labels.milestoneStatus.done"))).to_be_visible()
    due = cai(server, "followups")
    assert any(th["milestone_id"] == milestone_id for th in due["thanks_due"])
    cai(
        server,
        "drafts", "save", str(interviewed),
        payload={
            "kind": "thank_you",
            "subject": "Gracias por la entrevista",
            "body": "Gracias por la conversación de ayer.",
            "milestone_id": milestone_id,
        },
    )  # fmt: skip

    page.goto("/procesos")
    followups = len(due["followups"])
    thanks = len(due["thanks_due"])
    for key, count in (("followups", followups), ("thanks", thanks)):
        plural = "one" if count == 1 else "other"
        expect(page.get_by_text(t(f"processes.{key}_{plural}", count=count))).to_be_visible()

    # Marcar el seguimiento enviado registra `followup_sent` y lo quita de los pendientes.
    job_tab(page, quiet, "process")
    drafts = page.get_by_role("region", name=t("drafts.title"))
    drafts.get_by_role("button", name=t("drafts.sent")).click()
    expect(drafts.get_by_text("os escribo para saber si hay novedades")).to_be_hidden()
    assert "followup_sent" in [
        e["type"] for e in cai(server, "events", "list", str(quiet))["events"]
    ]
    due = cai(server, "followups")
    assert all(f["job_id"] != quiet for f in due["followups"])

    # Y el agradecimiento, igual: ya no se pide.
    job_tab(page, interviewed, "process")
    drafts.get_by_role("button", name=t("drafts.sent")).click()
    expect(drafts.get_by_text("Gracias por la conversación de ayer.")).to_be_hidden()
    due = cai(server, "followups")
    assert all(th["milestone_id"] != milestone_id for th in due["thanks_due"])


# --- Embudo y analítica -----------------------------------------------------------------------


def _numbers(text: str) -> list[int]:
    return [int(n.replace(".", "")) for n in re.findall(r"\d{1,3}(?:\.\d{3})+|\d+", text)]


def _table(page: Page, caption: str) -> list[list[str]]:
    """Las filas (sin cabecera) de la tabla accesible con ese `caption`."""
    table = page.locator("table").filter(has=page.locator("caption", has_text=caption))
    expect(table).to_have_count(1)
    rows: list[list[str]] = table.locator("tbody tr").evaluate_all(
        "rows => rows.map(r => [...r.children].map(c => c.textContent.trim()))"
    )
    return rows


def _funnel_since(page: Page, preset: str) -> str | None:
    """Pulsa un periodo y devuelve el `since` que pidió la página a la API."""

    def asks_funnel(response: Response) -> bool:
        return "/stats/funnel" in response.url

    button = page.get_by_role("group", name=t("funnel.period")).get_by_role(
        "button", name=t(f"funnel.presets.{preset}"), exact=True
    )
    with page.expect_response(asks_funnel) as asked:
        if button.get_attribute("aria-pressed") == "true":
            page.reload()
        else:
            button.click()
    found = re.search(r"since=([\d-]+)", asked.value.url)
    return found.group(1) if found else None


def _check_against_agent_interface(page: Page, server: AppServer, since: str | None) -> list[int]:
    stats = cai(server, "stats", "funnel", *(["--since", since] if since else []))
    # Las cifras van plegadas en «Tu embudo»; cada periodo o recarga las puede volver a plegar.
    numbers = page.get_by_role("button", name=t("funnel.flow.numbers"))
    expect(numbers).to_be_visible()
    if numbers.get_attribute("aria-expanded") == "false":
        numbers.click()
    # Se espera a que la página pinte las cifras de ese periodo (las del anterior siguen hasta
    # que llega la respuesta).
    funnel = page.locator("table").filter(
        has=page.locator("caption", has_text=t("funnel.funnel.caption"))
    )
    expect(funnel.locator("tbody tr")).to_have_count(len(stats["steps"]))
    expect(funnel.locator("tbody td:first-of-type")).to_have_text(
        [re.compile(rf"^{s['count']}(\D|$)") for s in stats["steps"]]
    )
    # El gráfico dice las mismas cifras, y un paso con candidaturas se dibuja con su alto.
    by_step = {s["step"]: s["count"] for s in stats["steps"]}
    if by_step["applied"]:
        chart = page.locator("section[aria-labelledby=funnel-flow] svg[role=img]")
        expect(chart).to_have_attribute(
            "aria-label",
            t(
                "funnel.flow.chartLabel",
                applied=by_step["applied"],
                replied=by_step["replied"],
                interview=by_step["interview"],
                offer=by_step["offer"],
                accepted=by_step["accepted"],
            ),
        )
        first = chart.locator("rect").first.bounding_box()
        assert first is not None
        assert first["height"] > 0
    steps = _table(page, t("funnel.funnel.caption"))
    assert [row[0] for row in steps] == [t(f"funnel.steps.{s['step']}") for s in stats["steps"]]
    assert [_numbers(row[1])[0] for row in steps] == [s["count"] for s in stats["steps"]]
    sources = _table(page, t("funnel.bySource.caption"))
    assert [_numbers(" ".join(row[1:6])) for row in sources] == [
        [s["found"], s["approved"], s["applied"], s["replied"], s["interview"]]
        for s in stats["by_source"]
    ]
    if stats["by_week"]:
        weeks = _table(page, t("funnel.week.caption"))
        assert [_numbers(" ".join(row[1:])) for row in weeks] == [
            [w["found"], w["approved"], w["applied"], w["replied"], w["interview"]]
            for w in stats["by_week"]
        ]
    if stats["discard_reasons"]:
        reasons = _table(page, t("funnel.reasons.byYouCaption"))
        assert [_numbers(row[1])[0] for row in reasons] == [
            r["count"] for r in stats["discard_reasons"]
        ]
    response = stats["response_time"]
    if response["applied"]:
        replied = t(
            "funnel.response.repliedOf", replied=response["replied"], applied=response["applied"]
        )
        expect(page.get_by_text(replied, exact=True)).to_be_visible()
    return [s["count"] for s in stats["steps"]]


@pytest.mark.smoke
def test_the_funnel_counts_the_same_as_the_agent_interface(page: Page, demo_app: AppServer) -> None:
    """La UI y `get_funnel_stats` cuentan lo mismo, periodo a periodo."""
    page.goto("/embudo")
    expect(page.get_by_role("heading", name=t("funnel.title"), level=1)).to_be_visible()
    expect(page.locator(".recharts-surface").first).to_be_visible()  # las gráficas pintan
    expect(page.locator(".recharts-rectangle").first).to_be_visible()

    counts: dict[str, list[int]] = {}
    for preset in ("all", "30", "90", "365"):
        since = _funnel_since(page, preset)
        assert (since is None) == (preset == "all")
        counts[preset] = _check_against_agent_interface(page, demo_app, since)
    # 8 semanas de historial: 30 días deja fuera parte; 90 días y 12 meses, nada.
    assert counts["30"][0] < counts["all"][0]
    assert counts["90"] == counts["365"] == counts["all"]


# --- Skills ---------------------------------------------------------------------------------


def test_a_skill_marked_as_a_gap_reaches_the_agent(page: Page, demo_app: AppServer) -> None:
    unmarked = cai(demo_app, "skills", "gaps", "--status", "unmarked")["gaps"]
    assert unmarked, "la demo tiene skills sin decidir"
    skill = unmarked[0]["skill"]
    page.goto("/perfil/skills")
    actions = page.get_by_role("group", name=t("skills.row.actions", skill=skill))
    actions.get_by_role("button", name=t("skills.row.gap")).click()
    expect(actions.get_by_role("button", name=t("skills.row.gap"))).to_have_attribute(
        "aria-pressed", "true"
    )
    gaps = cai(demo_app, "skills", "gaps", "--status", "gap")["gaps"]
    assert skill in [g["skill"] for g in gaps]


# --- Proyección de etapas ---------------------------------------------------------------------


def test_the_stage_shown_follows_the_projection_from_new_to_accepted(
    page: Page, fresh_demo_app: AppServer
) -> None:
    """Todos los eventos de una oferta, de nueva a aceptada, por la UI donde se puede (el agente
    extrae y redacta el CV). En cada paso, la etapa de la ficha es la de la proyección."""
    server = fresh_demo_app

    def check(job_id: int, stage: str) -> None:
        assert projected_stage(server, job_id) == stage
        assert api(server, f"/jobs/{job_id}")["stage"] == stage
        page.goto(f"/jobs/{job_id}")
        expect(stage_badge(page)).to_contain_text(_stage_label(stage))

    new_job_by_text(page, "Analytics Engineer", COMPANY, text_of("oferta-texto.txt"), COMPANY_URL)
    job_id = find_job(server, COMPANY)["id"]
    check(job_id, "pending_extraction")

    cai(server, "jobs", "save-extraction", str(job_id), payload=extraction())
    check(job_id, "pending_triage")

    page.get_by_role("button", name=t("job.decision.approve"), exact=True).click()
    expect(stage_badge(page)).to_contain_text(_stage_label("approved"))
    check(job_id, "approved")

    save_verified_cv(server, job_id)
    check(job_id, "cv_ready")

    # Enviada por tu cuenta, desde Procesos.
    page.goto("/procesos")
    column = page.get_by_role("region", name=_stage_label("cv_ready"), exact=True)
    card = column.locator("li").filter(has_text=COMPANY)
    update = card.get_by_role(
        "button", name=t("processes.card.updateAria", title="Analytics Engineer")
    )
    _move(page, update, "applied_manually")
    check(job_id, "applied")

    _status_step(page, server, job_id, "reply_received")
    check(job_id, "in_process")

    when = datetime.combine(_today() + timedelta(days=2), datetime.min.time()).replace(hour=9)
    milestone_id = _add_interview(page, job_id, "Entrevista final", when)
    check(job_id, "in_process")
    milestone_days_ago(server, milestone_id, 3)
    section = _process_section_of(page, job_id)
    section.get_by_role(
        "button", name=t("process.milestone.done", title="Entrevista final")
    ).click()
    expect(section.get_by_text(t("labels.milestoneStatus.done"))).to_be_visible()
    check(job_id, "in_process")

    # En «En proceso», «¿Qué ha pasado?» también registra lo que no cambia de etapa: otra
    # prueba y la oferta. «Acepto la oferta» solo sale con una oferta registrada.
    status = job_tab(page, job_id, "process").get_by_role("region", name=t("status.label"))
    expect(status.get_by_role("button", name=t("status.steps.accepted"))).to_have_count(0)
    _status_step(page, server, job_id, "test_assigned")
    check(job_id, "in_process")
    _status_step(page, server, job_id, "offer_received")
    check(job_id, "in_process")
    _status_step(page, server, job_id, "accepted")
    check(job_id, "closed")

    events = [e["type"] for e in cai(server, "events", "list", str(job_id))["events"]]
    for event in (
        "found", "extracted", "approved", "cv_verified", "applied_manually", "reply_received",
        "interview_scheduled", "interview_done", "test_assigned", "offer_received", "accepted",
    ):  # fmt: skip
        assert event in events, events


def _replies(server: AppServer) -> list[dict[str, Any]]:
    """Los correos guardados, como los ve «Respuestas» (con asunto y ofertas candidatas)."""
    out: list[dict[str, Any]] = api(server, "/replies", limit=500)["replies"]
    return out


def _drop_mail(server: AppServer, name: str, when: datetime) -> None:
    """Deja un correo exportado en `data/inbox/respuestas/`, con su fecha."""
    inbox = server.data_dir / "inbox" / "respuestas"
    inbox.mkdir(parents=True, exist_ok=True)
    raw = (FIXTURES / name).read_text(encoding="utf-8").replace("{date}", format_datetime(when))
    (inbox / name).write_bytes(raw.replace("\n", "\r\n").encode("utf-8"))


def test_replies_are_proposed_by_the_agent_and_decided_by_you(
    page: Page, fresh_demo_app: AppServer
) -> None:
    server = fresh_demo_app
    job_id = applied_job(server, COMPANY, COMPANY_URL)
    before = {r["reply_id"] for r in _replies(server)}
    sent_at = datetime.now(UTC) + timedelta(minutes=1)  # posterior al envío
    for name in ("respuesta-entrevista.eml", "respuesta-otra.eml", "correo-ajeno.eml"):
        _drop_mail(server, name, sent_at)

    page.goto("/respuestas")
    page.get_by_role("button", name=t("replies.page.poll")).click()
    expect(page.get_by_role("status").filter(has_text=t("replies.page.title"))).to_be_visible()
    new = [r for r in _replies(server) if r["reply_id"] not in before]
    # Solo los de la empresa: el boletín la nombra, pero su remitente no es de ella.
    assert sorted(r["subject"] for r in new) == [
        "Novedades de tu candidatura",
        "Tu candidatura a Analytics Engineer: primera entrevista",
    ]
    assert all(r["candidates"][0]["job_id"] == job_id for r in new)
    assert not any("noticias-ejemplo.test" in r["sender"] for r in _replies(server))
    interview_reply = next(r for r in new if "entrevista" in r["subject"])
    other_reply = next(r for r in new if r["reply_id"] != interview_reply["reply_id"])

    # El rol `classifier` guarda sus propuestas: no registran nada.
    when = datetime.combine(_today() + timedelta(days=4), datetime.min.time(), MADRID).replace(
        hour=10
    )
    cai(
        server,
        "replies", "propose", str(interview_reply["reply_id"]),
        payload={
            "job_id": job_id,
            "event_type": "interview_scheduled",
            "milestone": {"title": "Primera entrevista", "starts_at": when.isoformat()},
            "summary": "Te invitan a una primera entrevista por videollamada.",
            "confidence": "high",
        },
    )  # fmt: skip
    cai(
        server,
        "replies", "propose", str(other_reply["reply_id"]),
        payload={
            "job_id": job_id,
            "event_type": "rejected",
            "summary": "Siguen revisando candidaturas.",
            "confidence": "low",
        },
    )  # fmt: skip
    assert api(server, f"/jobs/{job_id}")["stage"] == "applied"

    # La UI enseña la propuesta; aceptarla registra la entrevista y la oferta pasa a «En proceso».
    page.reload()
    replies = page.get_by_role("list", name=t("replies.page.list"))
    replies.get_by_role("button").filter(has_text="primera entrevista").click()
    email = page.get_by_role("article", name=t("replies.page.email"))
    proposal = email.get_by_role("region", name=t("replies.page.proposal"))
    expect(proposal.get_by_text("Te invitan a una primera entrevista")).to_be_visible()
    proposal.get_by_role("button", name=t("replies.card.accept")).click()
    # Un aviso dice dónde ha quedado, con enlace a la oferta; el correo sale de «Pendientes».
    notice = page.get_by_role("status").filter(has_text=f"Analytics Engineer · {COMPANY}")
    expect(notice.get_by_role("link", name=f"Analytics Engineer · {COMPANY}")).to_have_attribute(
        "href", f"/jobs/{job_id}"
    )
    expect(replies.get_by_role("button").filter(has_text="primera entrevista")).to_have_count(0)
    filters = page.get_by_role("radiogroup", name=t("replies.page.filterAria"))
    filters.get_by_role("radio", name=re.compile(t("replies.page.filters.accepted"))).click()
    replies.get_by_role("button").filter(has_text="primera entrevista").click()
    expect(proposal.get_by_text(t("replies.card.accepted"))).to_be_visible()
    assert api(server, f"/jobs/{job_id}")["stage"] == "in_process"
    events = [e["type"] for e in cai(server, "events", "list", str(job_id))["events"]]
    assert events.count("interview_scheduled") == 1
    section = _process_section_of(page, job_id)
    expect(section.get_by_text("Primera entrevista")).to_be_visible()

    # Ignorar la otra no cambia nada.
    page.goto("/respuestas")
    replies.get_by_role("button").filter(has_text="Novedades de tu candidatura").click()
    proposal.get_by_role("button", name=t("replies.card.ignore")).click()
    expect(replies.get_by_role("button").filter(has_text="Novedades")).to_have_count(0)
    # «Deshacer» la devuelve a pendientes; se vuelve a ignorar.
    ignored = page.get_by_role("status").filter(has_text=t("replies.page.resolved.ignored"))
    ignored.get_by_role("button", name=t("replies.page.resolved.undo")).click()
    expect(replies.get_by_role("button").filter(has_text="Novedades")).to_have_count(1)
    proposal.get_by_role("button", name=t("replies.card.ignore")).click()
    expect(replies.get_by_role("button").filter(has_text="Novedades")).to_have_count(0)
    filters.get_by_role("radio", name=re.compile(t("replies.page.filters.ignored"))).click()
    replies.get_by_role("button").filter(has_text="Novedades de tu candidatura").click()
    expect(proposal.get_by_text(t("replies.card.ignored"))).to_be_visible()
    after = [e["type"] for e in cai(server, "events", "list", str(job_id))["events"]]
    assert after == events
    assert api(server, f"/jobs/{job_id}")["stage"] == "in_process"
    page.goto(f"/jobs/{job_id}")
    expect(stage_badge(page)).to_contain_text(_stage_label("in_process"))


def _drag(page: Page, card: Locator, target: Locator) -> None:
    """Con el ratón de verdad, por pasos: `dnd-kit` no arranca hasta que se mueve 6 px."""
    start, end = card.bounding_box(), target.bounding_box()
    assert start and end
    page.mouse.move(start["x"] + start["width"] / 2, start["y"] + 8)
    page.mouse.down()
    page.mouse.move(start["x"] + start["width"] / 2 + 12, start["y"] + 8, steps=4)
    page.mouse.move(end["x"] + end["width"] / 2, end["y"] + 40, steps=12)
    page.mouse.up()


def test_a_card_is_dragged_only_to_the_right(page: Page, fresh_demo_app: AppServer) -> None:
    server = fresh_demo_app
    job_id = applied_job(server, COMPANY, COMPANY_URL)
    title = api(server, f"/jobs/{job_id}")["title"]
    page.goto("/procesos")

    def column(stage: str) -> Locator:
        return page.get_by_role("region", name=_stage_label(stage), exact=True)

    # La tarjeta entera es arrastrable, y `dnd-kit` le da el papel de botón.
    def card_in(stage: str) -> Locator:
        return column(stage).get_by_role("button").filter(has_text=title).filter(has_text=COMPANY)

    card = card_in("applied")
    expect(card).to_be_visible()

    # Hacia la izquierda no se puede: se queda donde estaba y lo dice.
    _drag(page, card, column("cv_ready"))
    expect(page.get_by_role("alert").filter(has_text=t("processes.onlyForward"))).to_be_visible()
    expect(page.get_by_role("dialog")).to_have_count(0)
    assert api(server, f"/jobs/{job_id}")["stage"] == "applied"

    # Hacia la derecha abre el diálogo de siempre y, al confirmar, la tarjeta cambia de columna.
    _drag(page, card, column("in_process"))
    dialog = page.get_by_role("dialog", name=t("move.title"))
    expect(dialog).to_be_visible()
    dialog.get_by_role("radio", name=_starts(t("labels.event.reply_received"))).click()
    dialog.get_by_role("button", name=t("move.register")).click()
    expect(dialog).to_be_hidden()
    expect(card_in("in_process")).to_be_visible()
    assert api(server, f"/jobs/{job_id}")["stage"] == "in_process"
