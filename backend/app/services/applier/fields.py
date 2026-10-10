"""Campos de un formulario de candidatura: localizarlos, decidir qué va en cada uno y rellenarlos.

1. `discover` recorre el formulario en la página y marca cada control con `data-jh-field`. Cada
   campo se identifica por su **etiqueta accesible** (`aria-labelledby`, `<label>`, `aria-label`,
   `legend` del grupo y, si no hay, la etiqueta visible más cercana), nunca por su posición.
2. `plan` (sin navegador) clasifica cada campo por su etiqueta y le asigna un valor del perfil, el
   CV, la carta o una respuesta del paquete. Nunca rellena datos sensibles (género, origen,
   discapacidad…) ni marca casillas: los consentimientos obligatorios los aceptas tú al confirmar
   el envío.
3. `apply` rellena: primero los adjuntos (Lever rellena campos al subir el CV), luego el resto.
   No pulsa teclas: un Enter en un campo podría enviar el formulario. Los clics pasan por
   `safe_click`, que rechaza cualquier control de envío.
4. `read_state` lee de la página qué tiene valor de verdad (también lo que rellenes tú a mano) y
   devuelve el informe de la pantalla de revisión.
"""

import contextlib
import re
import unicodedata
from pathlib import Path
from typing import Any, Literal

from playwright.sync_api import Locator, Page
from pydantic import BaseModel
from rapidfuzz import fuzz

from app.services.applier import guard
from app.services.applier.log import AttemptLog

Control = Literal["text", "textarea", "select", "file", "checkbox", "checkboxes", "radio",
                  "buttons", "combobox"]  # fmt: skip
FieldKind = Literal[
    "first_name",
    "last_name",
    "full_name",
    "email",
    "phone",
    "linkedin",
    "github",
    "city",
    "resume",
    "cover_letter",
    "question",
    "sensitive",
    "consent",
    "optional_checkbox",
    "other_file",
]
FieldStatus = Literal["filled", "empty", "needs_user_input", "sensitive", "consent", "skipped",
                      "error"]  # fmt: skip


class SubmitControlError(RuntimeError):
    """Se intentó pulsar un control de envío fuera de `submit.py`. No debería pasar nunca."""


# --- Entradas -------------------------------------------------------------------------------


class Applicant(BaseModel):
    full_name: str
    first_name: str
    last_name: str
    email: str | None = None
    phone: str | None = None
    linkedin: str | None = None
    github: str | None = None
    city: str | None = None


class PackageAnswer(BaseModel):
    question: str
    answer: str
    needs_user_input: bool


class FillData(BaseModel):
    """Lo que se puede poner en el formulario: perfil, CV elegido, carta y respuestas."""

    applicant: Applicant
    resume: Path
    letter_pdf: Path | None = None
    letter_text: str | None = None
    answers: list[PackageAnswer] = []


def split_name(full_name: str) -> tuple[str, str]:
    """Nombre de pila y apellidos: el primer término y el resto."""
    parts = full_name.split()
    if len(parts) < 2:
        return full_name.strip(), ""
    return parts[0], " ".join(parts[1:])


# --- Descubrimiento -------------------------------------------------------------------------


class Option(BaseModel):
    marker: str = ""  # vacío en las opciones de un <select>
    label: str
    value: str = ""


class FieldDescriptor(BaseModel):
    marker: str
    control: Control
    input_type: str = ""
    label: str
    required: bool
    name: str = ""
    id: str = ""
    autocomplete: str = ""
    placeholder: str = ""
    options: list[Option] = []


_DISCOVER_JS = r"""() => {
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const textOf = el => clean(el ? (el.innerText || el.textContent) : '');
  const byIds = ids => clean((ids || '').split(/\s+/)
    .map(id => textOf(document.getElementById(id))).join(' '));
  const shown = el => {
    if (!el) return false;
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') return false;
    return el.getClientRects().length > 0;
  };
  // El formulario: el que tiene más campos, con más peso si pide correo o un adjunto.
  let root = null, best = -1;
  for (const form of document.querySelectorAll('form')) {
    const score = form.querySelectorAll('input, textarea, select').length +
      5 * !!form.querySelector('input[type=file]') + 5 * !!form.querySelector('input[type=email]');
    if (score > best) { best = score; root = form; }
  }
  if (!root || best <= 0) root = document.querySelector('main') || document.body;
  document.querySelectorAll('[data-jh-field]').forEach(el => el.removeAttribute('data-jh-field'));
  let n = 0;
  const mark = el => { const id = String(n++); el.setAttribute('data-jh-field', id); return id; };
  const ownLabel = el => {
    if (el.getAttribute('aria-labelledby')) return byIds(el.getAttribute('aria-labelledby'));
    if (el.labels && el.labels.length) return clean([...el.labels].map(textOf).join(' '));
    if (el.getAttribute('aria-label')) return clean(el.getAttribute('aria-label'));
    return '';
  };
  const groupLabel = g => {
    if (!g) return '';
    if (g.getAttribute('aria-labelledby')) return byIds(g.getAttribute('aria-labelledby'));
    if (g.getAttribute('aria-label')) return clean(g.getAttribute('aria-label'));
    const legend = g.querySelector('legend');
    return legend ? textOf(legend) : '';
  };
  // La etiqueta visible más cercana del bloque, para controles sin etiqueta propia.
  const nearbyLabel = el => {
    let box = el.parentElement;
    for (let i = 0; box && i < 4; box = box.parentElement, i++) {
      for (const cand of box.querySelectorAll('label, legend, [class*=label], [class*=heading]')) {
        if (!cand.contains(el) && textOf(cand)) return textOf(cand);
      }
      if (box === root) break;
    }
    return '';
  };
  const isRequired = (el, label) => !!(el && (el.required ||
    el.getAttribute('aria-required') === 'true')) || /[*✱]/.test(label) ||
    /\((required|obligatori[oa])\)/i.test(label);
  const out = [];
  const groups = new Set();
  for (const el of root.querySelectorAll('input, textarea, select')) {
    const type = (el.tagName === 'INPUT' ? (el.getAttribute('type') || 'text')
      : el.tagName.toLowerCase()).toLowerCase();
    if (['hidden', 'submit', 'button', 'reset', 'image', 'password', 'search'].includes(type)) {
      continue;
    }
    if (el.disabled) continue;
    const visible = shown(el) || (el.labels && [...el.labels].some(shown));
    if (type !== 'file' && !visible) continue;
    const base = {name: el.name || '', id: el.id || '',
      autocomplete: el.getAttribute('autocomplete') || '',
      placeholder: clean(el.getAttribute('placeholder')), input_type: type, options: []};
    const siblings = el.name ? [...root.querySelectorAll(
      `input[type=${type}][name="${CSS.escape(el.name)}"]`)] : [el];
    if (type === 'radio' || (type === 'checkbox' && siblings.length > 1)) {
      const key = type + ':' + (el.name || el.id);
      if (groups.has(key)) continue;
      groups.add(key);
      const g = el.closest('fieldset, [role=radiogroup], [role=group]');
      const label = groupLabel(g) || nearbyLabel(g || el);
      out.push({...base, marker: 'g' + out.length, label,
        control: type === 'radio' ? 'radio' : 'checkboxes',
        required: siblings.some(m => m.required) || isRequired(g, label),
        options: siblings.map(m => ({marker: mark(m), label: ownLabel(m) || clean(m.value),
                                     value: m.value || ''}))});
      continue;
    }
    const control = el.tagName === 'SELECT' ? 'select' : el.tagName === 'TEXTAREA' ? 'textarea'
      : type === 'file' ? 'file' : type === 'checkbox' ? 'checkbox'
      : el.getAttribute('role') === 'combobox' ? 'combobox' : 'text';
    let label = ownLabel(el);
    if (!label && control !== 'file') label = base.placeholder || clean(el.title);
    if (!label) label = nearbyLabel(el);
    const options = control === 'select'
      ? [...el.options].map(o => ({marker: '', label: textOf(o), value: o.value})) : [];
    out.push({...base, marker: mark(el), control, label, required: isRequired(el, label),
              options});
  }
  // Preguntas de sí/no con botones (Ashby). Nunca un botón que enviaría el formulario.
  const yesNo = /^(yes|no|si|sí)$/i;
  const seen = new Set();
  for (const b of root.querySelectorAll('button')) {
    if (!yesNo.test(textOf(b)) || (b.type === 'submit' && b.form) || seen.has(b.parentElement)) {
      continue;
    }
    const box = b.parentElement;
    const opts = [...box.children].filter(x => x.tagName === 'BUTTON' && yesNo.test(textOf(x))
      && !(x.type === 'submit' && x.form));
    if (opts.length < 2) continue;
    seen.add(box);
    const label = nearbyLabel(box);
    out.push({name: '', id: '', autocomplete: '', placeholder: '', input_type: 'button',
      marker: 'b' + out.length, control: 'buttons', label, required: isRequired(null, label),
      options: opts.map(o => ({marker: mark(o), label: textOf(o), value: ''}))});
  }
  return out;
}"""


def discover(page: Page) -> list[FieldDescriptor]:
    """Los campos del formulario de la página, marcados con `data-jh-field`."""
    return [FieldDescriptor.model_validate(item) for item in page.evaluate(_DISCOVER_JS)]


# --- Clasificación y plan -------------------------------------------------------------------


def norm(text: str) -> str:
    """Minúsculas, sin acentos, sin asteriscos ni «(required)» y con un espacio entre palabras."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = re.sub(r"\((required|obligatori[oa])\)", " ", text)
    text = re.sub(r"[*✱_\[\]\-:?¿!¡()/.,;]", " ", text)
    return " ".join(text.split())


def display_label(label: str) -> str:
    """La etiqueta para la pantalla de revisión: sin asterisco final."""
    return re.sub(r"\s*[*✱]\s*$", "", " ".join(label.split())) or "(sin etiqueta)"


def _has(text: str, *patterns: str) -> bool:
    return any(re.search(rf"(^|\s){p}($|\s)", text) for p in patterns)


_SENSITIVE = (
    r"gender", r"genero", r"sexo", r"race", r"raza", r"ethnic\w*", r"etnia", r"etnico",
    r"hispanic", r"latino", r"veteran\w*", r"disabilit\w*", r"disabled", r"discapacidad",
    r"sexual orientation", r"orientacion sexual", r"pronouns?", r"pronombres?", r"religion",
    r"date of birth", r"fecha de nacimiento", r"age", r"edad", r"self identification",
    r"nationality", r"nacionalidad", r"citizenship", r"ciudadania", r"marital", r"estado civil",
    r"lgbt\w*", r"transgender", r"trans", r"criminal", r"convictions?", r"antecedentes",
    r"health", r"salud", r"medical", r"medica", r"union membership", r"afiliacion sindical",
    r"sindicato", r"political", r"afiliacion politica", r"ideologia", r"embarazo",
    r"pregnan\w*", r"hijos", r"children",
)  # fmt: skip
_CONSENT = (
    r"privacy", r"privacidad", r"consent\w*", r"consentimiento", r"acepto", r"i agree",
    r"agree", r"terms", r"condiciones", r"gdpr", r"rgpd", r"data protection",
    r"proteccion de datos", r"acknowledge\w*", r"certify", r"declaro", r"confirmo",
    r"i confirm", r"politica de privacidad",
)  # fmt: skip
_RESUME = (r"resume", r"cv", r"curriculum", r"curriculum vitae", r"curriculo")
_LETTER = (
    r"cover letter", r"carta", r"carta de presentacion", r"carta de motivacion",
    r"motivation letter", r"motivational letter", r"letter of motivation",
)  # fmt: skip


def classify(field: FieldDescriptor) -> FieldKind:
    """Qué es el campo, por su etiqueta y, de apoyo, su placeholder, `name`, `id` y
    `autocomplete`."""
    label = norm(field.label)
    text = norm(" ".join([field.label, field.placeholder, field.name, field.id]))
    auto = field.autocomplete.lower()
    if _has(text, *_SENSITIVE):
        return "sensitive"
    if field.control == "file":
        if _has(text, *_LETTER):
            return "cover_letter"
        return "resume" if _has(text, *_RESUME) else "other_file"
    if field.control == "checkbox":
        if _has(text, *_CONSENT):
            return "consent"
        # Una casilla obligatoria que no es un aviso legal («Puedo reubicarme») la decides tú.
        return "question" if field.required else "optional_checkbox"
    if field.control in ("radio", "checkboxes", "buttons", "select"):
        return "question"
    if _has(text, r"preferred", r"preferido", r"preferida"):
        return "question"
    if field.input_type == "email" or auto == "email" or _has(text, r"e mail", r"email",
                                                               r"correo"):  # fmt: skip
        return "email"
    if (
        field.input_type == "tel"
        or auto.startswith("tel")
        or _has(text, r"phone", r"telefono", r"movil", r"mobile", r"celular")
    ):
        return "phone"
    if _has(text, r"linkedin"):
        return "linkedin"
    if _has(text, r"github"):
        return "github"
    if (
        auto == "name"
        or label in ("name", "nombre y apellidos", "nombre y apellido")
        or _has(text, r"full name", r"nombre completo", r"your name", r"legal name")
    ):
        return "full_name"
    if (
        auto == "given-name"
        or label == "nombre"
        or _has(text, r"first name", r"given name", r"nombre de pila", r"forename", r"firstname")
    ):
        return "first_name"
    if auto == "family-name" or _has(
        text, r"last name", r"surname", r"family name", r"apellidos?", r"lastname"
    ):
        return "last_name"
    if field.control == "textarea" and _has(text, *_LETTER):
        return "cover_letter"
    if field.control in ("text", "combobox") and _has(
        text, r"city", r"ciudad", r"location", r"ubicacion", r"localidad", r"residencia",
        r"where are you (based|located)",
    ):  # fmt: skip
        return "city"
    return "question"


class FieldPlan(BaseModel):
    """Lo que se va a poner en un campo. `value` vacío: se deja como está."""

    field: FieldDescriptor
    kind: FieldKind
    value: str | None = None
    file: Path | None = None
    option: int | None = None  # índice en `field.options`
    source: str | None = None
    needs_user_input: bool = False
    note: str | None = None


_PLACEHOLDER = re.compile(r"^(|-+|select.*|selecciona.*|choose.*|elige.*|please select.*)$")


def choose_option(labels: list[str], answer: str) -> int | None:
    """La opción que corresponde a la respuesta: igual, sí/no por el comienzo de la respuesta o,
    si no, la más parecida (mínimo 85)."""
    target = norm(answer)
    options = [(i, norm(label)) for i, label in enumerate(labels)]
    options = [(i, label) for i, label in options if not _PLACEHOLDER.match(label)]
    for i, label in options:
        if label == target:
            return i
    if re.match(r"^(yes|si)\b", target):
        return next((i for i, label in options if re.match(r"^(yes|si)\b", label)), None)
    if re.match(r"^no\b", target):
        return next((i for i, label in options if re.match(r"^no\b", label)), None)
    best: tuple[float, int] | None = None
    for i, label in options:
        score = fuzz.token_sort_ratio(label, target)
        if len(label) >= 3 and re.search(rf"(^|\s){re.escape(label)}($|\s)", target):
            score = max(score, 90)
        if score >= 85 and (best is None or score > best[0]):
            best = (score, i)
    return best[1] if best else None


def match_answer(
    label: str, answers: list[PackageAnswer], min_similarity: int
) -> PackageAnswer | None:
    """La respuesta del paquete cuya pregunta se parece más a la etiqueta del campo."""
    target = norm(label)
    if not target:
        return None
    scored = [(fuzz.token_sort_ratio(target, norm(a.question)), a) for a in answers]
    scored = [(score, a) for score, a in scored if score >= min_similarity]
    return max(scored, key=lambda pair: pair[0])[1] if scored else None


_PROFILE_SOURCES: dict[str, tuple[str, str]] = {
    "first_name": ("first_name", "Perfil: nombre"),
    "last_name": ("last_name", "Perfil: apellidos"),
    "full_name": ("full_name", "Perfil: nombre completo"),
    "email": ("email", "Perfil: correo"),
    "phone": ("phone", "Perfil: teléfono"),
    "linkedin": ("linkedin", "Perfil: LinkedIn"),
    "github": ("github", "Perfil: GitHub"),
    "city": ("city", "Perfil: ciudad"),
}


def plan(fields: list[FieldDescriptor], data: FillData, min_similarity: int) -> list[FieldPlan]:
    """Qué va en cada campo. No toca la página."""
    plans = [FieldPlan(field=f, kind=classify(f)) for f in fields]
    # Un único adjunto sin etiqueta clara es el CV.
    if not any(p.kind == "resume" for p in plans):
        spare = next((p for p in plans if p.kind == "other_file"), None)
        if spare is not None:
            spare.kind = "resume"
    resume_done = False
    for p in plans:
        field = p.field
        if p.kind in _PROFILE_SOURCES:
            attr, source = _PROFILE_SOURCES[p.kind]
            value = getattr(data.applicant, attr)
            if value:
                p.value, p.source = value, source
        elif p.kind == "resume" and not resume_done:
            p.file, p.source = data.resume, "CV (PDF del render elegido)"
            resume_done = True
        elif p.kind == "cover_letter":
            if field.control == "file" and data.letter_pdf is not None:
                p.file, p.source = data.letter_pdf, "Carta (PDF)"
            elif field.control != "file" and data.letter_text:
                p.value, p.source = data.letter_text, "Carta (texto)"
            else:
                p.note = "No hay carta seleccionada para esta oferta."
        elif p.kind == "question":
            _plan_question(p, data.answers, min_similarity)
        elif p.kind == "sensitive":
            p.note = "Dato sensible: nunca se rellena solo. Decides tú."
        elif p.kind == "consent":
            p.note = (
                "Se marcará al confirmar el envío."
                if field.required
                else "Opcional: márcala tú si quieres."
            )
    return plans


def _plan_question(p: FieldPlan, answers: list[PackageAnswer], min_similarity: int) -> None:
    found = match_answer(p.field.label, answers, min_similarity)
    if found is None:
        return
    source = f"Respuesta del paquete: «{found.question}»"
    if not found.answer.strip():
        p.needs_user_input, p.source = True, source
        p.note = "La respuesta espera un dato tuyo."
        return
    if p.field.options:
        index = choose_option([o.label for o in p.field.options], found.answer)
        if index is None:
            p.note = "Ninguna opción encaja con la respuesta del paquete."
            p.source = source
            return
        p.option, p.value = index, p.field.options[index].label
    elif p.field.control == "checkboxes":
        p.note = "Varias casillas: elige tú."
        return
    else:
        p.value = found.answer
    p.source = source


# --- Rellenado ------------------------------------------------------------------------------

_SUBMIT_CHECK_JS = r"""el => {
  const submitText = /(submit|send|enviar|apply|aplicar|solicitar|postular|inscrib)/i;
  const isSubmit = (el.tagName === 'BUTTON' && el.type === 'submit' && !!el.form) ||
    (el.tagName === 'INPUT' && ['submit', 'image'].includes(el.type)) ||
    (['BUTTON', 'A'].includes(el.tagName) && submitText.test(el.innerText || el.value || ''));
  return isSubmit;
}"""


def field_locator(page: Page, marker: str) -> Locator:
    return page.locator(f'[data-jh-field="{marker}"]')


def safe_click(locator: Locator) -> None:
    """Clic que nunca pulsa un control de envío (ese clic solo lo hace `submit.py`)."""
    if locator.evaluate(_SUBMIT_CHECK_JS):
        raise SubmitControlError("Se ha evitado pulsar un control de envío al rellenar.")
    locator.click()


# El botón que abre el formulario («Enviar solicitud», «Apply now»…) suele tener texto de envío,
# así que `safe_click` no lo pulsa. Este clic solo vale fuera de cualquier formulario y nunca en
# un control de envío; se usa cuando la página aún no tiene formulario (no hay datos que enviar).
_OPEN_FORM_CHECK_JS = r"""el => el.closest('form') === null &&
  !(el.tagName === 'INPUT' && ['submit', 'image'].includes(el.type)) &&
  !(el.tagName === 'BUTTON' && el.type === 'submit' && !!el.form)"""


def open_form_click(locator: Locator) -> None:
    """Pulsa el botón que abre el formulario de candidatura (ver `_OPEN_FORM_CHECK_JS`)."""
    if not locator.evaluate(_OPEN_FORM_CHECK_JS):
        raise SubmitControlError("Se ha evitado pulsar un control de envío al abrir el formulario.")
    locator.click()


def check_box(locator: Locator) -> None:
    """Marca una casilla o una opción; si está oculta tras un diseño propio, con un clic de JS."""
    if locator.evaluate(_SUBMIT_CHECK_JS):
        raise SubmitControlError("Se ha evitado pulsar un control de envío al rellenar.")
    try:
        locator.check(timeout=3000)
    except Exception:
        locator.evaluate("el => { if (!el.checked) el.click(); }")


def _fill_combobox(page: Page, locator: Locator, value: str) -> str | None:
    """Escribe y elige la sugerencia que encaja. Devuelve una nota si no hubo sugerencia."""
    safe_click(locator)
    locator.fill(value)
    options = page.locator("[role=option]:visible")
    try:
        options.first.wait_for(timeout=3000)
    except Exception:
        return "Sin sugerencias para el texto escrito: revísalo."
    labels = options.all_inner_texts()
    index = choose_option(labels, value)
    if index is None:
        return "Ninguna sugerencia encaja: revísalo."
    safe_click(options.nth(index))
    return None


def _order(p: FieldPlan) -> int:
    return 0 if p.file is not None else 1


def apply(page: Page, plans: list[FieldPlan], log: AttemptLog) -> dict[str, str]:
    """Rellena lo planeado. Devuelve `marker -> error` de los campos que fallaron."""
    errors: dict[str, str] = {}
    for p in sorted(plans, key=_order):
        if p.file is None and p.value is None:
            continue
        # Si la página navegó o se recargó (p. ej. al subir el CV), el bloqueo se habría perdido.
        guard.arm_submit_block(page)
        field = p.field
        try:
            label = display_label(field.label)
            with log.step("fill", label=label, kind=p.kind, control=field.control):
                note = _apply_one(page, p)
            if note:
                p.note = note
        except SubmitControlError:
            raise
        except Exception as exc:
            errors[field.marker] = f"{type(exc).__name__}: {str(exc).splitlines()[0]}"[:300]
    return errors


def _apply_one(page: Page, p: FieldPlan) -> str | None:
    field = p.field
    if p.file is not None:
        field_locator(page, field.marker).set_input_files(str(p.file))
        # Algunas webs suben el fichero al elegirlo (Lever lo lee para rellenar campos).
        with contextlib.suppress(Exception):
            page.wait_for_load_state("networkidle", timeout=5000)
        return None
    assert p.value is not None
    if field.control in ("radio", "buttons"):
        assert p.option is not None
        target = field_locator(page, field.options[p.option].marker)
        if field.control == "radio":
            check_box(target)
        else:
            safe_click(target)
        return None
    locator = field_locator(page, field.marker)
    if field.control == "select":
        assert p.option is not None
        option = field.options[p.option]
        if option.value:
            locator.select_option(value=option.value)
        else:
            locator.select_option(label=option.label)
        return None
    if field.control == "combobox":
        return _fill_combobox(page, locator, p.value)
    locator.fill(p.value)
    return None


# --- Estado e informe -----------------------------------------------------------------------

_STATE_JS = r"""(fields) => {
  const clean = s => (s || '').replace(/\s+/g, ' ').trim();
  const q = m => document.querySelector(`[data-jh-field="${m}"]`);
  const optionLabel = el => clean(el.labels && el.labels[0] ? el.labels[0].innerText : el.value);
  const pressed = el => el.getAttribute('aria-pressed') === 'true' ||
    el.getAttribute('aria-checked') === 'true' ||
    /(^|[\s_-])(active|selected|checked|pressed)/i.test(el.className || '');
  return fields.map(f => {
    if (f.control === 'radio' || f.control === 'checkboxes' || f.control === 'buttons') {
      const els = f.options.map(o => q(o.marker)).filter(Boolean);
      if (!els.length) return {present: false, has_value: false, value: null};
      const sel = f.control === 'buttons' ? els.filter(pressed) : els.filter(e => e.checked);
      return {present: true, has_value: sel.length > 0,
              value: sel.map(e => f.control === 'buttons' ? clean(e.innerText)
                                                            : optionLabel(e)).join(', ') || null};
    }
    const el = q(f.marker);
    if (!el) return {present: false, has_value: false, value: null};
    if (f.control === 'file') {
      const names = [...(el.files || [])].map(x => x.name);
      if (!names.length && f.uploaded) {
        let box = el.parentElement;
        for (let i = 0; box && i < 4; box = box.parentElement, i++) {
          if ((box.innerText || '').includes(f.uploaded)) return {present: true, has_value: true,
                                                                  value: f.uploaded};
        }
      }
      return {present: true, has_value: names.length > 0, value: names.join(', ') || null};
    }
    if (f.control === 'checkbox') {
      return {present: true, has_value: el.checked, value: el.checked ? 'Marcada' : null};
    }
    if (f.control === 'select') {
      const o = el.selectedOptions[0];
      const label = o ? clean(o.textContent) : '';
      const empty = !el.value || /^(-+|select.*|selecciona.*|choose.*|elige.*)$/i.test(label);
      return {present: true, has_value: !empty, value: empty ? null : label};
    }
    if (f.control === 'combobox' && !clean(el.value)) {
      const box = el.closest('[class*=control], [class*=container], [class*=select]');
      const chosen = box && box.querySelector(
        '[class*=single-value], [class*=singleValue], [class*=multi-value], [class*=multiValue]');
      return {present: true, has_value: !!chosen, value: chosen ? clean(chosen.innerText) : null};
    }
    return {present: true, has_value: clean(el.value) !== '', value: clean(el.value) || null};
  });
}"""


class FieldReport(BaseModel):
    """Una fila de la tabla de revisión."""

    marker: str
    label: str
    control: Control
    kind: FieldKind
    required: bool
    status: FieldStatus
    source: str | None = None
    value: str | None = None
    note: str | None = None

    @property
    def missing(self) -> bool:
        """Obligatorio y sin valor. Los consentimientos los aceptas al confirmar."""
        return self.required and self.status not in ("filled", "consent")


def _preview(value: str | None) -> str | None:
    if value is None:
        return None
    value = " ".join(value.split())
    return value if len(value) <= 160 else value[:157] + "…"


def read_state(page: Page, plans: list[FieldPlan], errors: dict[str, str]) -> list[FieldReport]:
    """El informe de cada campo según lo que hay ahora en la página."""
    payload: list[dict[str, Any]] = [
        {
            "marker": p.field.marker,
            "control": p.field.control,
            "options": [o.model_dump() for o in p.field.options],
            "uploaded": p.file.name if p.file is not None else None,
        }
        for p in plans
    ]
    states = page.evaluate(_STATE_JS, payload)
    reports = []
    for p, state in zip(plans, states, strict=True):
        status: FieldStatus
        source, note = p.source, p.note
        if state["has_value"]:
            status = "filled"
            if p.value is None and p.file is None:
                source = "En el navegador"
        elif p.field.marker in errors:
            status, note = "error", errors[p.field.marker]
        elif p.kind == "sensitive":
            status = "sensitive"
        elif p.kind == "consent":
            status = "consent"
        elif p.needs_user_input:
            status = "needs_user_input"
        elif p.kind == "optional_checkbox":
            status = "skipped"
        else:
            status = "empty"
        if not state["present"]:
            note = "El campo ya no está en la página."
        reports.append(
            FieldReport(
                marker=p.field.marker,
                label=display_label(p.field.label),
                control=p.field.control,
                kind=p.kind,
                required=p.field.required,
                status=status,
                source=source,
                value=_preview(state["value"]),
                note=note,
            )
        )
    return reports
