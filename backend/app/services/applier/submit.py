"""El único módulo que pulsa el botón de envío de un formulario (POLICIES §5.1).

`click_submit` exige una `SubmitConfirmation`, que solo crea `tokens.consume` al validar la
confirmación que diste en la UI. Antes de pulsar vuelve a mirar si hay captcha (si lo hay, para y
la pestaña es tuya), marca los consentimientos obligatorios que aceptaste y retira el bloqueo del
envío. Después espera la página de confirmación y la captura. Sin reintentos (POLICIES §5.4).

Un test comprueba que ningún otro módulo de la app pulsa el envío ni retira el bloqueo.
"""

import re
import time
from typing import Literal

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page
from pydantic import BaseModel

from app.services.applier import guard
from app.services.applier.fields import check_box, field_locator
from app.services.applier.guard import Blocker
from app.services.applier.log import AttemptLog
from app.services.applier.tokens import SubmitConfirmation, TokenError

SubmitResult = Literal["confirmed", "unconfirmed", "blocked", "failed"]

CONFIRM_TEXT = re.compile(
    r"thank(s| you) for (applying|your application|submitting|your interest in)|"
    r"application (has been |was )?(submitted|received|sent)|"
    r"we('ve| have) received your application|your application is (in|complete)|"
    r"gracias por (tu|su) (candidatura|solicitud|inter[eé]s)|"
    r"hemos recibido (tu|su) (candidatura|solicitud)|"
    r"(candidatura|solicitud) (ha sido )?(enviada|recibida)",
    re.I,
)
CONFIRM_URL = re.compile(
    r"/(thanks|thank-you|thank_you|confirmation|confirmed|success|submitted|gracias)(/|$|\?|#)",
    re.I,
)

_FIND_SUBMIT_JS = r"""() => {
  const shown = el => el.getClientRects().length > 0 &&
    getComputedStyle(el).visibility !== 'hidden';
  const marked = document.querySelector('[data-jh-field]');
  const form = marked ? (marked.closest('form') || document.body) : document.body;
  const text = el => (el.innerText || el.value || '').replace(/\s+/g, ' ').trim();
  const words = /(submit|send application|enviar|apply|aplicar|solicitar|postular|inscrib)/i;
  const typed = [...form.querySelectorAll('button[type=submit], input[type=submit]')]
    .filter(shown);
  const named = [...form.querySelectorAll('button, [role=button]')]
    .filter(el => shown(el) && words.test(text(el)));
  const pick = typed.find(el => words.test(text(el))) || typed[0] || named[named.length - 1];
  document.querySelectorAll('[data-jh-submit]').forEach(el => el.removeAttribute('data-jh-submit'));
  if (!pick) return null;
  pick.setAttribute('data-jh-submit', '1');
  return text(pick) || '(sin texto)';
}"""

_ERRORS_JS = r"""() => {
  const shown = el => el.getClientRects().length > 0;
  const texts = [...document.querySelectorAll(
    '[role=alert], [aria-invalid=true], .error, .errors, [class*=error-message], [class*=Error]')]
    .filter(shown).map(el => (el.innerText || '').replace(/\s+/g, ' ').trim()).filter(Boolean);
  return [...new Set(texts)].slice(0, 10);
}"""


class SubmitOutcome(BaseModel):
    result: SubmitResult
    message: str
    blocker: Blocker | None = None
    errors: list[str] = []


def _body_text(page: Page) -> str:
    try:
        return str(page.evaluate("() => document.body ? document.body.innerText : ''"))
    except PlaywrightError:  # navegando: el contexto de la página aún no existe
        return ""


def click_submit(
    page: Page,
    confirmation: SubmitConfirmation,
    attempt_id: int,
    log: AttemptLog,
    wait_seconds: float,
) -> SubmitOutcome:
    """Pulsa el envío del intento confirmado y espera la confirmación de la web."""
    if not isinstance(confirmation, SubmitConfirmation) or confirmation.attempt_id != attempt_id:
        raise TokenError("Hace falta la confirmación de envío de este intento.")
    with log.step("submit_check"):
        found = guard.check(page)
    if found.blocker is not None:
        return SubmitOutcome(result="blocked", message=found.blocker.message, blocker=found.blocker)
    for marker in confirmation.consents:
        with log.step("consent"):
            check_box(field_locator(page, marker))
    with log.step("find_submit"):
        label = page.evaluate(_FIND_SUBMIT_JS)
    if label is None:
        return SubmitOutcome(result="failed", message="No se encuentra el botón de envío.")
    before_url, before_text = page.url, _body_text(page)
    already = bool(CONFIRM_TEXT.search(before_text))
    # A partir de aquí el clic puede haberse dado: cualquier fallo es «sin confirmar», nunca
    # «fallido», para que nadie lo repita creyendo que no salió (POLICIES §5.4).
    try:
        with log.step("click_submit", button=label):
            guard.release_submit_block(page)
            page.locator('[data-jh-submit="1"]').click()
        return _wait_confirmation(page, before_url, already, log, wait_seconds)
    except Exception as exc:
        log.write("after_click_error", ok=False, error=f"{type(exc).__name__}"[:200])
        return SubmitOutcome(result="unconfirmed", message=UNCONFIRMED)


UNCONFIRMED = (
    "No se ha reconocido la página de confirmación. Mira la pestaña: si la web muestra errores, "
    "corrígelos y termina tú; si se envió, márcala como enviada. No se vuelve a enviar sola."
)


def _wait_confirmation(
    page: Page, before_url: str, already: bool, log: AttemptLog, wait_seconds: float
) -> SubmitOutcome:
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        page.wait_for_timeout(500)
        url = page.url
        if url != before_url and CONFIRM_URL.search(url):
            log.write("confirmed", by="url")
            return SubmitOutcome(result="confirmed", message="La web ha confirmado el envío.")
        if not already and CONFIRM_TEXT.search(_body_text(page)):
            log.write("confirmed", by="text")
            return SubmitOutcome(result="confirmed", message="La web ha confirmado el envío.")
        try:
            after = guard.check(page)
        except PlaywrightError:
            continue
        if after.blocker is not None and after.blocker.kind == "captcha":
            log.write("blocked", ok=False, kind="captcha")
            return SubmitOutcome(
                result="blocked",
                message="Tras pulsar «Enviar» ha aparecido un captcha. Resuélvelo tú y termina "
                "en la web; no se vuelve a enviar sola.",
                blocker=after.blocker,
            )
    try:
        errors = [str(e) for e in page.evaluate(_ERRORS_JS)]
    except PlaywrightError:
        errors = []
    log.write("unconfirmed", ok=False, errors=len(errors))
    return SubmitOutcome(result="unconfirmed", message=UNCONFIRMED, errors=errors)


def submit_button_label(page: Page) -> str | None:
    """El texto del botón que se pulsaría al confirmar (para la pantalla de revisión). Lo marca,
    pero no lo pulsa."""
    label = page.evaluate(_FIND_SUBMIT_JS)
    return str(label) if label is not None else None
