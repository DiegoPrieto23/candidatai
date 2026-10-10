"""Candidatura asistida (fase 11): intentos, token de un solo uso, envío y worker.

Los tests con navegador usan el del worker (`get_host`) en modo headless y un servidor local que
cuenta los envíos: sin la confirmación de la UI no llega ninguno, y con ella, exactamente uno.
"""

from collections.abc import Iterator
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import migrations
from app.core.config import get_settings
from app.core.db import session_scope
from app.core.policies import get_policies
from app.models import ApplicationAttempt, Event, Job, Task
from app.models.base import utcnow
from app.services import events, tasks
from app.services.applier import browser, service, tokens
from app.services.applier.service import ApplierError
from tests.applier_support import FormServer, cv_ready_job
from tests.cv_support import requires_chromium


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("JH_BROWSER_HEADLESS", "1")
    monkeypatch.setenv("JH_APPLIER_ALLOW_LOOPBACK", "1")  # el servidor de prueba es local
    get_settings.cache_clear()
    migrations.upgrade()
    yield
    browser.shutdown_host()


@pytest.fixture
def server() -> Iterator[FormServer]:
    with FormServer() as running:
        yield running


def queued(kind: str) -> list[Task]:
    with session_scope() as session:
        stmt = select(Task).where(Task.kind == kind, Task.status == "queued")
        return list(session.scalars(stmt))


def attempt(attempt_id: int) -> ApplicationAttempt:
    with session_scope() as session:
        row = session.get(ApplicationAttempt, attempt_id)
        assert row is not None
        return row


def event_types(job_id: int) -> list[str]:
    with session_scope() as session:
        return [e.type for e in session.scalars(select(Event).where(Event.job_id == job_id))]


def confirm(session: Session, attempt_id: int, company: str) -> service.AttemptView:
    """Confirma la versión vigente del intento, como hace la UI tras revisarla."""
    reviewed_at = service._get(session, attempt_id).updated_at
    return service.confirm_submission(session, attempt_id, company, reviewed_at)


def prepared(url: str) -> tuple[int, int]:
    with session_scope() as session:
        job_id = cv_ready_job(session, url)
        view = service.prepare(session, job_id)
    return job_id, view.id


# --- Con navegador --------------------------------------------------------------------------


@requires_chromium
def test_fill_then_submit_only_with_the_ui_token(db: None, server: FormServer) -> None:
    job_id, attempt_id = prepared(server.url("simple"))
    (task,) = queued("apply_fill")
    assert task.payload == {"attempt_id": attempt_id}

    result = service.run_fill(attempt_id)
    assert result["status"] == "ready" and result["missing_required"] == 0
    assert server.posts == []  # rellenar no envía
    with session_scope() as session:
        view = service.view(session, attempt(attempt_id))
        assert view.can_submit and view.platform == "generic"
        assert [c.label for c in view.consents] == ["Acepto la política de privacidad"]
        reviewed_at = view.updated_at
        assert service.screenshot_file(session, attempt_id, "review").is_file()
    assert "application_filled" in event_types(job_id)

    # Sin confirmación de la UI, ni un token inventado, el worker no envía.
    with pytest.raises(tokens.TokenError):
        service.run_submit(attempt_id, "token-inventado")
    assert server.posts == []

    with session_scope() as session, pytest.raises(ApplierError) as wrong:
        service.confirm_submission(session, attempt_id, "Otra Empresa", reviewed_at)
    assert wrong.value.code == "company_mismatch"
    assert queued("apply_submit") == []

    with session_scope() as session:
        service.confirm_submission(session, attempt_id, "  acme analytics ", reviewed_at)
    (submit_task,) = queued("apply_submit")
    token = submit_task.payload["token"]
    assert attempt(attempt_id).token_hash not in (None, token)  # solo el hash en la BD

    outcome = service.run_submit(attempt_id, token, submit_task.payload["consents"])
    assert outcome == {"attempt_id": attempt_id, "result": "confirmed", "applied": True}
    assert server.posts == ["/simple/submit"]  # exactamente un envío
    row = attempt(attempt_id)
    assert row.status == "submitted" and row.confirmation_path is not None
    assert (get_settings().data_dir / row.confirmation_path).is_file()
    with session_scope() as session:
        applied = session.scalars(
            select(Event).where(Event.job_id == job_id, Event.type == "applied")
        ).one()
        assert applied.actor == "user"
        assert applied.payload["channel"] == "ats_form"
        assert applied.payload["attempt_id"] == attempt_id
        assert applied.payload["evidence"] == row.confirmation_path
        assert "render_id" in applied.payload
        assert events.current_stage(session, job_id) == "applied"

    # La misma confirmación no vale dos veces.
    with pytest.raises(tokens.TokenError):
        service.run_submit(attempt_id, token)
    assert server.posts == ["/simple/submit"]


@requires_chromium
def test_unrecognised_confirmation_does_not_record_applied(
    db: None, server: FormServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_policies().applier, "confirm_wait_seconds", 2)
    job_id, attempt_id = prepared(server.url("silent"))
    service.run_fill(attempt_id)
    with session_scope() as session:
        confirm(session, attempt_id, "Acme Analytics")
    (task,) = queued("apply_submit")
    result = service.run_submit(attempt_id, task.payload["token"], task.payload["consents"])
    assert result["result"] == "unconfirmed" and not result["applied"]
    assert server.posts == ["/silent/submit"]
    assert attempt(attempt_id).status == "submit_unconfirmed"
    assert "applied" not in event_types(job_id)


@requires_chromium
def test_missing_required_blocks_confirmation(db: None, server: FormServer) -> None:
    _, attempt_id = prepared(server.url("generic"))
    service.run_fill(attempt_id)
    with session_scope() as session:
        view = service.view(session, attempt(attempt_id))
        assert not view.can_submit and view.missing_required == 1
        with pytest.raises(ApplierError) as info:
            confirm(session, attempt_id, "Acme Analytics")
    assert info.value.code == "missing_required"
    assert queued("apply_submit") == [] and server.posts == []


@requires_chromium
def test_captcha_leaves_attempt_for_the_user(db: None, server: FormServer) -> None:
    job_id, attempt_id = prepared(server.url("captcha"))
    result = service.run_fill(attempt_id)
    assert result["status"] == "needs_user"
    row = attempt(attempt_id)
    assert row.status == "needs_user" and row.error is not None and "captcha" in row.error
    with session_scope() as session, pytest.raises(ApplierError):
        confirm(session, attempt_id, "Acme Analytics")
    assert server.posts == []
    # «Lo termino yo»: la pestaña es tuya y después lo marcas como enviado.
    with session_scope() as session:
        service.focus(session, attempt_id)
    assert service.run_focus(attempt_id) == {"attempt_id": attempt_id, "reopened": False}
    with session_scope() as session:
        service.mark_manual_done(session, job_id)
        last = session.scalars(
            select(Event).where(Event.job_id == job_id).order_by(Event.id.desc())
        ).first()
        assert last is not None and last.type == "applied_manually"
        assert last.payload["channel"] == "ats_form"
    assert attempt(attempt_id).status == "manual_done"


# --- Sin navegador --------------------------------------------------------------------------


def ready_attempt(job_id: int, **changes: object) -> int:
    with session_scope() as session:
        row = ApplicationAttempt(
            job_id=job_id, platform="greenhouse", mode="fill", url="https://x", status="ready",
            fields=[], warnings=[],
        )  # fmt: skip
        for key, value in changes.items():
            setattr(row, key, value)
        session.add(row)
        session.flush()
        return row.id


def test_token_is_single_use_and_expires(db: None) -> None:
    with session_scope() as session:
        job_id = cv_ready_job(session, "https://boards.greenhouse.io/acme/jobs/1")
    attempt_id = ready_attempt(job_id)
    with session_scope() as session:
        row = session.get(ApplicationAttempt, attempt_id)
        assert row is not None
        token = tokens.issue(row, ttl_seconds=60)
    later = utcnow() + timedelta(seconds=61)
    with session_scope() as session, pytest.raises(tokens.TokenError, match="caducado"):
        tokens.consume(session, attempt_id, token, now=later)
    with session_scope() as session:
        confirmation = tokens.consume(session, attempt_id, token)
        assert confirmation.attempt_id == attempt_id
    with session_scope() as session, pytest.raises(tokens.TokenError, match="ya se usó"):
        tokens.consume(session, attempt_id, token)
    with pytest.raises(tokens.TokenError):
        tokens.SubmitConfirmation(attempt_id=attempt_id, consents=(), _issuer=object())


def test_confirmation_checks_review_and_stage(db: None) -> None:
    with session_scope() as session:
        job_id = cv_ready_job(session, "https://boards.greenhouse.io/acme/jobs/2")
    attempt_id = ready_attempt(job_id)
    old = utcnow() - timedelta(minutes=5)
    with session_scope() as session, pytest.raises(ApplierError) as stale:
        service.confirm_submission(session, attempt_id, "Acme Analytics", reviewed_at=old)
    assert stale.value.code == "stale"
    missing = [{"marker": "0", "label": "Salary", "control": "text", "kind": "question",
                "required": True, "status": "empty"}]  # fmt: skip
    other = ready_attempt(job_id, fields=missing)
    with session_scope() as session, pytest.raises(ApplierError) as info:
        confirm(session, other, "Acme Analytics")
    assert info.value.code == "missing_required"
    with session_scope() as session:
        events.add_user_event(session, job_id, "applied_manually")
    with session_scope() as session, pytest.raises(ApplierError) as closed:
        confirm(session, attempt_id, "Acme Analytics")
    assert closed.value.code == "invalid_stage"
    assert queued("apply_submit") == []


def test_prepare_rules(db: None) -> None:
    with session_scope() as session:
        job_id = cv_ready_job(
            session, "https://jobs.lever.co/acme/6f1c2b9a-1111-2222-3333-444455556666"
        )
        view = service.prepare(session, job_id)
        assert (view.platform, view.mode, view.status) == ("lever", "fill", "queued")
        assert view.url.endswith("/apply")
        with pytest.raises(ApplierError) as busy:
            service.prepare(session, job_id)
        assert busy.value.code == "busy"
        linkedin = cv_ready_job(session, "https://www.linkedin.com/jobs/view/1", "Beta")
        open_view = service.prepare(session, linkedin)
        assert (open_view.platform, open_view.mode) == ("linkedin", "open")
    assert [t.payload["attempt_id"] for t in queued("apply_open")] == [open_view.id]
    with session_scope() as session:
        job = session.scalars(select(Job).where(Job.id == job_id)).one()
        events.add_user_event(session, job.id, "applied_manually")
        with pytest.raises(ApplierError) as stage:
            service.prepare(session, job.id)
    assert stage.value.code == "invalid_stage"


def test_new_preparation_cancels_previous_review(db: None) -> None:
    with session_scope() as session:
        job_id = cv_ready_job(session, "https://boards.greenhouse.io/acme/jobs/3")
    old = ready_attempt(job_id, token_hash="abc")
    with session_scope() as session:
        service.prepare(session, job_id)
    row = attempt(old)
    assert row.status == "cancelled" and row.token_hash is None


def test_browser_tasks_are_never_retried_nor_requeued(db: None) -> None:
    with session_scope() as session:
        job_id = cv_ready_job(session, "https://boards.greenhouse.io/acme/jobs/4")
    attempt_id = ready_attempt(job_id, status="submitting")
    with session_scope() as session:
        submit_task = tasks.enqueue(
            session, "apply_submit", {"attempt_id": attempt_id, "token": "t"}
        )
        score = tasks.enqueue(session, "score_job", {"job_id": job_id})
        submit_task.status = score.status = "running"  # el worker se cerró a medias
        interrupted = tasks.fail_interrupted(session)
        assert [t.id for t in interrupted] == [submit_task.id]
        assert service.recover_interrupted(session, [attempt_id]) == 1
        assert tasks.requeue_running(session) == 1  # solo la de score
        assert (submit_task.status, score.status) == ("failed", "queued")
        fill = tasks.enqueue(session, "apply_fill", {"attempt_id": attempt_id})
        tasks.mark_failed(session, fill.id, "boom")
        assert fill.status == "failed"  # sin reintentos
    assert attempt(attempt_id).status == "submit_unconfirmed"


def test_worker_handler_rejects_forged_submit_task(db: None) -> None:
    from app.services import worker

    with session_scope() as session:
        job_id = cv_ready_job(session, "https://boards.greenhouse.io/acme/jobs/5")
    attempt_id = ready_attempt(
        job_id, token_hash="0" * 64, token_expires_at=utcnow() + timedelta(minutes=5)
    )
    with session_scope() as session:
        tasks.enqueue(session, "apply_submit", {"attempt_id": attempt_id, "token": "inventado"})
    run = worker.run_pending()
    (outcome,) = [o for o in run.outcomes if o.kind == "apply_submit"]
    assert not outcome.ok and "TokenError" in (outcome.error or "")
    assert attempt(attempt_id).status == "ready"  # el navegador ni se tocó
    with session_scope() as session:
        assert (
            session.scalars(select(Task).where(Task.kind == "apply_submit")).one().status
            == "failed"
        )


def test_missing_screenshot_is_not_found(db: None) -> None:
    with session_scope() as session:
        job_id = cv_ready_job(session, "https://boards.greenhouse.io/acme/jobs/6")
    attempt_id = ready_attempt(job_id)
    with session_scope() as session, pytest.raises(ApplierError) as info:
        service.screenshot_file(session, attempt_id, "confirmation")
    assert info.value.code == "not_found"


@requires_chromium
def test_after_a_click_the_attempt_never_goes_back_to_ready(
    db: None, server: FormServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_policies().applier, "confirm_wait_seconds", 2)
    job_id, attempt_id = prepared(server.url("silent"))
    service.run_fill(attempt_id)
    with session_scope() as session:
        confirm(session, attempt_id, "Acme Analytics")
    (task,) = queued("apply_submit")
    service.run_submit(attempt_id, task.payload["token"], task.payload["consents"])
    assert attempt(attempt_id).status == "submit_unconfirmed"
    with session_scope() as session:  # el token ya no queda en la cola
        assert "token" not in session.get(Task, task.id).payload  # type: ignore[union-attr]
    with session_scope() as session, pytest.raises(ApplierError, match="ya se pulsó"):
        service.rescan(session, attempt_id)
    # Un intento nuevo es una decisión explícita, y avisa del posible duplicado.
    with session_scope() as session:
        view = service.prepare(session, job_id)
    assert "possible_duplicate" in {w.code for w in view.warnings}
    service.run_fill(view.id)
    codes = {w.code for w in service.view_by_id(view.id).warnings}
    assert {"possible_duplicate", "submit_button"} <= codes
    assert server.posts == ["/silent/submit"]


def test_rejected_token_is_annotated_and_cleared(db: None) -> None:
    with session_scope() as session:
        job_id = cv_ready_job(session, "https://boards.greenhouse.io/acme/jobs/7")
    attempt_id = ready_attempt(job_id)
    with session_scope() as session:
        confirm(session, attempt_id, "Acme Analytics")
        with pytest.raises(ApplierError) as busy:  # ya hay una confirmación pendiente
            confirm(session, attempt_id, "Acme Analytics")
        assert busy.value.code == "busy"
    (task,) = queued("apply_submit")
    with pytest.raises(tokens.TokenError):
        service.run_submit(attempt_id, task.payload["token"] + "x")
    row = attempt(attempt_id)
    assert row.status == "ready" and row.token_hash is None
    assert row.error is not None and row.error.startswith("No se envió")
    with session_scope() as session:
        assert "token" not in session.get(Task, task.id).payload  # type: ignore[union-attr]


def test_prepare_refuses_non_web_and_local_urls(db: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JH_APPLIER_ALLOW_LOOPBACK", "0")
    get_settings.cache_clear()
    for url in ("file:///C:/Windows/win.ini", "javascript:alert(1)", "http://127.0.0.1:8000/"):
        with session_scope() as session:
            job_id = cv_ready_job(session, url, company=f"Empresa {len(url)}")
            with pytest.raises(ApplierError) as info:
                service.prepare(session, job_id)
        assert info.value.code == "invalid_url"


# --- Portales de empleo y «Rellenar esta página» --------------------------------------------

GLASSDOOR = "https://www.glassdoor.es/job-listing/data-engineer-acme-JV_IC2664239.htm?jl=1"


def test_job_board_offer_is_opened_not_filled(db: None) -> None:
    with session_scope() as session:
        job_id = cv_ready_job(session, GLASSDOOR)
        state = service.get_state(session, job_id)
        assert (state.mode, state.portal, state.can_prepare) == ("open", "Glassdoor", True)
        assert state.url == GLASSDOOR
        view = service.prepare(session, job_id)
        assert (view.platform, view.mode, view.url) == ("board", "open", GLASSDOOR)
    assert [t.payload["attempt_id"] for t in queued("apply_open")] == [view.id]
    assert queued("apply_fill") == []


def test_prepare_with_the_company_form_url(db: None) -> None:
    with session_scope() as session:
        job_id = cv_ready_job(session, GLASSDOOR)
        with pytest.raises(ApplierError) as board:
            service.prepare(session, job_id, form_url="https://es.indeed.com/viewjob?jk=1")
        assert board.value.code == "invalid_url" and "Indeed" in str(board.value)
        view = service.prepare(
            session, job_id, form_url=" https://boards.greenhouse.io/acme/jobs/7 "
        )
        assert (view.platform, view.mode) == ("greenhouse", "fill")
        assert view.url == "https://boards.greenhouse.io/acme/jobs/7"
    assert [t.payload["attempt_id"] for t in queued("apply_fill")] == [view.id]


def open_tabs(attempt_id: int, job_id: int, *urls: str) -> None:
    """La pestaña del intento con la primera URL y, como haría el portal, otras nuevas."""

    def _open(state: browser.BrowserState) -> None:
        page = state.new_page(attempt_id, job_id)
        page.goto(urls[0])
        for url in urls[1:]:
            state.ensure_context().new_page().goto(url)

    browser.get_host().call(_open)


def test_fill_page_rules(db: None) -> None:
    with session_scope() as session:
        job_id = cv_ready_job(session, GLASSDOOR)
    opened = ready_attempt(job_id, platform="board", mode="open", status="manual", url=GLASSDOOR)
    clicked = ready_attempt(
        job_id, platform="board", mode="open", status="manual", token_used_at=utcnow()
    )
    busy = ready_attempt(job_id, platform="board", mode="open", status="filling")
    with session_scope() as session:
        assert service.view(session, attempt(opened)).can_fill_page
        for attempt_id in (clicked, busy):
            assert not service.view(session, attempt(attempt_id)).can_fill_page
            with pytest.raises(ApplierError) as refused:
                service.fill_page(session, attempt_id)
            assert refused.value.code == "invalid_state"
        view = service.fill_page(session, opened)
        assert view.status == "queued"
    (task,) = queued("apply_fill_page")
    assert task.payload == {"attempt_id": opened, "previous": "manual"}


@requires_chromium
def test_fill_page_fills_the_company_form_reached_from_the_board(
    db: None, server: FormServer
) -> None:
    with session_scope() as session:
        job_id = cv_ready_job(session, GLASSDOOR)
    attempt_id = ready_attempt(
        job_id, platform="board", mode="open", status="manual", url=server.url("portal")
    )
    # El portal abre el formulario de la empresa en una pestaña nueva.
    open_tabs(attempt_id, job_id, server.url("portal"), server.url("generic"))
    with session_scope() as session:
        service.fill_page(session, attempt_id)
    result = service.run_fill_page(attempt_id, "manual")
    assert result["filled"] > 0
    assert server.posts == []  # rellenar no envía
    row = attempt(attempt_id)
    assert (row.mode, row.platform, row.url) == ("fill", "generic", server.url("generic"))
    assert row.status == "ready"
    assert "application_filled" in event_types(job_id)


@requires_chromium
def test_fill_page_never_fills_a_board_page(
    db: None, server: FormServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services.applier import platforms

    def board_page(url: str) -> str | None:
        return "Es la ficha del portal." if "portal" in url else None

    monkeypatch.setattr(platforms, "fill_problem", board_page)
    with session_scope() as session:
        job_id = cv_ready_job(session, GLASSDOOR)
    attempt_id = ready_attempt(
        job_id, platform="board", mode="open", status="manual", url=server.url("portal")
    )
    open_tabs(attempt_id, job_id, server.url("portal"))
    with session_scope() as session:
        service.fill_page(session, attempt_id)
    result = service.run_fill_page(attempt_id, "manual")
    assert result["wrong_page"] is True
    row = attempt(attempt_id)
    assert (row.status, row.mode, row.error) == ("manual", "open", "Es la ficha del portal.")
    assert row.fields == [] and "application_filled" not in event_types(job_id)


@requires_chromium
def test_open_browser_shows_the_start_page(db: None) -> None:
    assert service.run_browser_open() == {"opened": True}

    def _title(state: browser.BrowserState) -> str:
        return state.ensure_context().pages[0].title()

    assert browser.get_host().call(_title) == "Navegador de Job Hunter"
    # Si cierras la pestaña (o la ventana), volver a pulsar la abre de nuevo.
    browser.get_host().call(lambda state: state.ensure_context().pages[0].close())
    assert service.run_browser_open() == {"opened": True}
    assert browser.get_host().call(_title) == "Navegador de Job Hunter"
