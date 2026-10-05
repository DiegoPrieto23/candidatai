"""Lo que obliga a parar y pasarte la pestaña (POLICIES §5.3), y el bloqueo del envío.

- **Captcha visible** (reCAPTCHA, hCaptcha, Turnstile): se para. Un reCAPTCHA invisible (v3 o
  Enterprise, habitual en Greenhouse) no se ve ni se resuelve: solo deja un aviso.
- **Anti-bot**: páginas de comprobación («Just a moment…», «Verify you are human») o un 403/429.
- **Login**: un campo de contraseña visible o una URL de inicio de sesión. Las cuentas las creas e
  introduces tú (POLICIES §5.6).

Nada de esto se esquiva: el navegador se lanza sin trucos para parecer humano.

`arm_submit_block` instala en la página, mientras se rellena, un bloqueo del evento `submit` y de
`form.submit()`/`requestSubmit()`. Se rearma antes de cada campo (una navegación lo quitaría).
Solo `submit.py` lo retira, justo antes de pulsar el envío confirmado, y «Lo termino yo»
(`release_submit_block`). Protege de accidentes, no de una web hostil: un script de la propia
página podría cambiar la marca de `window`.
"""

import re
from typing import Literal

from playwright.sync_api import Page, Response
from pydantic import BaseModel

BlockerKind = Literal["captcha", "antibot", "login", "no_form"]


class Blocker(BaseModel):
    kind: BlockerKind
    message: str


_CAPTCHA_JS = """() => {
  const selectors = [
    'iframe[src*="recaptcha/api2/anchor"]', 'iframe[src*="recaptcha/enterprise/anchor"]',
    'iframe[src*="recaptcha/api2/bframe"]', 'iframe[src*="recaptcha/enterprise/bframe"]',
    'iframe[src*="hcaptcha.com"]', 'iframe[src*="challenges.cloudflare.com"]',
    'iframe[title*="captcha" i]', '.g-recaptcha:not([data-size="invisible"])',
    '.h-captcha:not([data-size="invisible"])', '.cf-turnstile'];
  const visible = el => {
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden' || +style.opacity === 0) {
      return false;
    }
    const r = el.getBoundingClientRect();
    return r.width >= 30 && r.height >= 30;
  };
  const shown = selectors.some(s => [...document.querySelectorAll(s)].some(visible));
  const invisible = !!document.querySelector(
    '.grecaptcha-badge, script[src*="recaptcha"], script[src*="hcaptcha"], ' +
    'script[src*="challenges.cloudflare.com"]');
  const password = [...document.querySelectorAll('input[type=password]')].some(visible);
  const text = (document.body ? document.body.innerText : '').slice(0, 4000);
  return {shown, invisible, password, title: document.title || '', text,
          short: text.length < 1500};
}"""

_ANTIBOT = re.compile(
    r"just a moment|attention required|verify (that )?you are (a )?human|are you a robot|"
    r"unusual traffic|checking your browser|request (was )?blocked|access denied|"
    r"verifica que eres (un )?humano|no eres un robot",
    re.I,
)
_LOGIN_PATH = re.compile(r"/(login|log-in|signin|sign-in|sign_in|auth|sso)(/|$|\?)", re.I)


class PageCheck(BaseModel):
    blocker: Blocker | None
    invisible_captcha: bool


def check(page: Page, response: Response | None = None) -> PageCheck:
    """Si hay que parar y por qué. `response` es la de la navegación, si la hubo."""
    found = page.evaluate(_CAPTCHA_JS)
    invisible = bool(found["invisible"])
    if found["shown"]:
        return PageCheck(
            blocker=Blocker(
                kind="captcha",
                message="La página muestra un captcha. Resuélvelo tú en el navegador.",
            ),
            invisible_captcha=invisible,
        )
    status = response.status if response is not None else None
    title_hit = bool(_ANTIBOT.search(found["title"]))
    text_hit = bool(found["short"] and _ANTIBOT.search(found["text"]))
    if status in (403, 429) or title_hit or text_hit:
        return PageCheck(
            blocker=Blocker(
                kind="antibot",
                message="La web ha mostrado una comprobación anti-bot. Sigue tú en el navegador.",
            ),
            invisible_captcha=invisible,
        )
    if found["password"] or _LOGIN_PATH.search(page.url):
        return PageCheck(
            blocker=Blocker(
                kind="login",
                message="La web pide iniciar sesión. Entra tú en el navegador y vuelve a revisar.",
            ),
            invisible_captcha=invisible,
        )
    return PageCheck(blocker=None, invisible_captcha=invisible)


_ARM_JS = """() => {
  window.__jhAllowSubmit = false;
  if (window.__jhGuard) return;
  window.__jhGuard = true;
  window.__jhBlocked = 0;
  window.addEventListener('submit', e => {
    if (!window.__jhAllowSubmit) {
      e.preventDefault(); e.stopImmediatePropagation(); window.__jhBlocked++;
    }
  }, true);
  const submit = HTMLFormElement.prototype.submit;
  HTMLFormElement.prototype.submit = function () {
    if (!window.__jhAllowSubmit) { window.__jhBlocked++; return; }
    return submit.call(this);
  };
  const request = HTMLFormElement.prototype.requestSubmit;
  if (request) {
    HTMLFormElement.prototype.requestSubmit = function (...args) {
      if (!window.__jhAllowSubmit) { window.__jhBlocked++; return; }
      return request.apply(this, args);
    };
  }
}"""


def arm_submit_block(page: Page) -> None:
    """Bloquea cualquier envío del formulario en esta página hasta que se retire."""
    page.evaluate(_ARM_JS)


def blocked_submits(page: Page) -> int:
    """Cuántos envíos ha bloqueado (la página intentó enviar sola)."""
    return int(page.evaluate("() => window.__jhBlocked || 0"))


def release_submit_block(page: Page) -> None:
    """Deja enviar: lo usan `submit.py` (con confirmación) y «Lo termino yo»."""
    page.evaluate("() => { window.__jhAllowSubmit = true; }")
