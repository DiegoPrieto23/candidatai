"""Candidatura asistida (fase 11): rellenadores contra formularios HTML locales, con Chromium.

Cada formulario se sirve en `127.0.0.1` y el servidor cuenta los envíos: rellenar nunca envía.
"""

import itertools
from collections.abc import Iterator
from pathlib import Path

import pytest

from app.services.applier import fields, service
from app.services.applier.browser import BrowserHost, BrowserState
from app.services.applier.fields import FieldReport, FillData
from app.services.applier.log import AttemptLog
from tests.applier_support import FormServer, fill_data
from tests.cv_support import requires_chromium

pytestmark = requires_chromium

_ids = itertools.count(1000)


@pytest.fixture(scope="module")
def host(tmp_path_factory: pytest.TempPathFactory) -> Iterator[BrowserHost]:
    browser = BrowserHost(tmp_path_factory.mktemp("profile"), headless=True, channel=None)
    yield browser
    browser.close()


@pytest.fixture(scope="module")
def server() -> Iterator[FormServer]:
    with FormServer() as running:
        yield running


def fill(
    host: BrowserHost, server: FormServer, path: str, data: FillData
) -> tuple[int, service._BrowserOutcome]:  # noqa: E501
    attempt_id = next(_ids)
    log = AttemptLog(attempt_id)
    outcome = host.call(
        lambda state: service._fill_in_browser(
            state, attempt_id, attempt_id, server.url(path), "generic", data, log, 85
        )
    )
    return attempt_id, outcome


def by_label(reports: list[FieldReport]) -> dict[str, FieldReport]:
    return {r.label: r for r in reports}


def value(host: BrowserHost, attempt_id: int, selector: str) -> str:
    def read(state: BrowserState) -> str:
        page = state.page_for(attempt_id)
        assert page is not None
        return page.locator(selector).input_value()

    return host.call(read)


def test_greenhouse_form_is_filled_and_stops(
    host: BrowserHost, server: FormServer, tmp_path: Path
) -> None:
    before = len(server.posts)
    attempt_id, outcome = fill(host, server, "greenhouse", fill_data(tmp_path))
    assert outcome.status == "ready" and outcome.blocker is None
    rows = by_label(outcome.fields)
    assert rows["First Name"].status == "filled" and rows["First Name"].value == "Lucía"
    assert rows["Last Name"].value == "Varela Otero"
    assert rows["Email"].value == "lucia.varela@example.com"
    assert rows["Phone"].source == "Perfil: teléfono"
    assert rows["Resume/CV"].value == "CV-Lucia-Varela.pdf"
    assert rows["Cover Letter"].value == "Carta-Lucia-Varela.pdf"
    assert rows["LinkedIn Profile"].value == "https://www.linkedin.com/in/lucia-varela-demo"
    assert rows["Are you legally authorized to work in Spain?"].value == "Yes"
    assert rows["Why do you want to work at Acme?"].status == "filled"
    salary = rows["What are your salary expectations?"]
    assert salary.status == "needs_user_input" and salary.required and salary.missing
    assert rows["Gender"].status == "sensitive" and rows["Gender"].value is None
    consent = rows["I agree to the privacy policy"]
    assert consent.status == "consent" and not consent.missing
    codes = {w.code for w in outcome.warnings}
    assert {"invisible_captcha", "missing_required"} <= codes
    assert value(host, attempt_id, "#gender") == ""
    assert outcome.screenshot is not None
    assert server.posts[before:] == []  # nada enviado


def test_lever_form(host: BrowserHost, server: FormServer, tmp_path: Path) -> None:
    before = len(server.posts)
    attempt_id, outcome = fill(host, server, "lever", fill_data(tmp_path))
    rows = by_label(outcome.fields)
    assert rows["Full name"].value == "Lucía Varela Otero" and rows["Full name"].required
    assert rows["Resume/CV"].status == "filled"
    assert rows["GitHub URL"].value == "https://github.com/lucia-varela-demo"
    assert rows["Current company"].status == "empty"
    sponsor = rows["Will you now or in the future require visa sponsorship?"]
    assert (sponsor.control, sponsor.value, sponsor.required) == ("radio", "No", True)
    letter = next(r for r in outcome.fields if r.kind == "cover_letter")
    assert letter.source == "Carta (texto)"
    assert value(host, attempt_id, "textarea[name=comments]").startswith("Estimado equipo:")
    assert not any(r.missing for r in outcome.fields)
    assert server.posts[before:] == []


def test_ashby_form_with_yes_no_buttons(
    host: BrowserHost, server: FormServer, tmp_path: Path
) -> None:
    before = len(server.posts)
    _, outcome = fill(host, server, "ashby", fill_data(tmp_path))
    rows = by_label(outcome.fields)
    assert rows["Name"].value == "Lucía Varela Otero"
    assert rows["Resume"].value == "CV-Lucia-Varela.pdf"  # input oculto
    office = rows["Are you willing to work from our Vigo office?"]
    assert (office.control, office.value, office.required) == ("buttons", "Yes", True)
    assert not any(r.missing for r in outcome.fields)
    assert server.posts[before:] == []


def test_generic_spanish_form(host: BrowserHost, server: FormServer, tmp_path: Path) -> None:
    before = len(server.posts)
    _, outcome = fill(host, server, "generic", fill_data(tmp_path))
    rows = by_label(outcome.fields)
    assert (rows["Nombre"].value, rows["Apellidos"].value) == ("Lucía", "Varela Otero")
    assert rows["Correo electrónico"].status == "filled"
    assert rows["Teléfono móvil"].value == "+34 600 000 000"
    assert rows["Ciudad de residencia"].value == "Vigo"
    assert rows["Adjunta tu CV"].status == "filled"
    assert rows["Carta de presentación"].source == "Carta (texto)"
    start = rows["¿Cuándo podrías incorporarte?"]
    assert start.status == "empty" and start.missing
    assert rows["Quiero recibir novedades"].status == "skipped"
    assert server.posts[before:] == []


def test_visible_captcha_stops_before_filling(
    host: BrowserHost, server: FormServer, tmp_path: Path
) -> None:
    before = len(server.posts)
    attempt_id, outcome = fill(host, server, "captcha", fill_data(tmp_path))
    assert outcome.status == "needs_user"
    assert outcome.blocker is not None and outcome.blocker.kind == "captcha"
    assert outcome.fields == []
    assert value(host, attempt_id, "#email") == ""
    assert outcome.screenshot is not None
    assert server.posts[before:] == []


def test_login_page_stops(host: BrowserHost, server: FormServer, tmp_path: Path) -> None:
    _, outcome = fill(host, server, "signin", fill_data(tmp_path))
    assert outcome.status == "needs_user"
    assert outcome.blocker is not None and outcome.blocker.kind == "login"


def test_page_without_form_is_unknown(
    host: BrowserHost, server: FormServer, tmp_path: Path
) -> None:
    _, outcome = fill(host, server, "nothing-here", fill_data(tmp_path))
    assert outcome.status == "needs_user" and outcome.platform == "unknown"
    assert outcome.blocker is not None and outcome.blocker.kind == "no_form"


def test_page_cannot_submit_itself_while_filling(
    host: BrowserHost, server: FormServer, tmp_path: Path
) -> None:
    before = len(server.posts)
    _, outcome = fill(host, server, "autosubmit", fill_data(tmp_path))
    assert outcome.status == "ready"
    assert "submit_blocked" in {w.code for w in outcome.warnings}
    assert server.posts[before:] == []


def test_safe_click_refuses_submit_controls(host: BrowserHost, server: FormServer) -> None:
    before = len(server.posts)

    def click(state: BrowserState) -> None:
        page = state.new_page(next(_ids), next(_ids))
        page.goto(server.url("simple"))
        with pytest.raises(fields.SubmitControlError):
            fields.safe_click(page.locator("button[type=submit]"))
        with pytest.raises(fields.SubmitControlError):
            fields.check_box(page.locator("button[type=submit]"))

    host.call(click)
    assert server.posts[before:] == []
