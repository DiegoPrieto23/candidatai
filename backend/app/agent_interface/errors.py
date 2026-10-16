"""Formato de error común de la interfaz para agentes, idéntico por MCP y por CLI.

```json
{"ok": false, "error": {"type": "validation_error", "message": "…",
                        "details": [{"field": "extraction.seniority", "received": "sr",
                                     "reason": "Debe ser uno de: intern, junior, …",
                                     "expected": "uno de: intern, junior, …",
                                     "hint": "¿Querías decir `senior`?"}]}}
```

Fase 24.2: `field` es siempre un path con puntos (`content.experience.2.bullets.0.evidence.1`),
`expected` dice en pocas palabras qué se esperaba y `hint`, cómo arreglarlo, para que un modelo
pequeño acierte al segundo intento. Ningún texto de la entrada de más de 80 caracteres vuelve en el
error (`scrub`): puede ser contenido no confiable que el agente volvería a leer.
"""

import re
from typing import Any, get_args, get_origin

from pydantic import BaseModel, ValidationError

from app.core.validation import MAX_RECEIVED_CHARS, describe_error, expected_of, quoted, similar


class ErrorDetail(BaseModel):
    field: str  # path con puntos desde la raíz de la entrada
    received: str | None  # siempre como texto: por CLI todo llega como texto (paridad)
    reason: str
    expected: str | None = None  # tipo, valores permitidos o longitud
    hint: str | None = None  # cómo corregirlo


class ErrorInfo(BaseModel):
    type: str
    message: str
    details: list[ErrorDetail] = []


class ToolError(Exception):
    """Error esperable de una herramienta: se devuelve al agente para que corrija y reintente."""

    def __init__(self, type: str, message: str, details: list[ErrorDetail] | None = None) -> None:
        super().__init__(message)
        self.info = ErrorInfo(type=type, message=message, details=details or [])

    def payload(self) -> dict[str, Any]:
        return {"ok": False, "error": self.info.model_dump(mode="json")}


_BRACKET = re.compile(r"\[(\d+)\]")


def dotted(field: str, root: str | None = None) -> str:
    """`experience[2].bullets[0]` → `experience.2.bullets.0`, con `root.` delante si se da."""
    path = _BRACKET.sub(r".\1", field).lstrip(".")
    return f"{root}.{path}" if root else path


def _unwrap(annotation: Any) -> type[BaseModel] | None:
    """El modelo dentro de una anotación (`X | None`, `list[X]`, `dict[str, X]`…), si lo hay."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    origin = get_origin(annotation)
    if origin is not None:
        for arg in get_args(annotation):
            found = _unwrap(arg)
            if found is not None:
                return found
    return None


def model_at(model: type[BaseModel] | None, loc: tuple[Any, ...]) -> type[BaseModel] | None:
    """El modelo que valida el objeto en `loc` (los índices de listas se saltan)."""
    current = model
    for part in loc:
        if current is None:
            return None
        if isinstance(part, int):
            continue
        info = current.model_fields.get(str(part))
        if info is None:
            return None
        current = _unwrap(info.annotation)
    return current


def _hint(error: Any, model: type[BaseModel] | None, schema: str | None) -> str | None:
    kind = error["type"]
    loc = tuple(error["loc"])
    name = str(loc[-1]) if loc else ""
    see = f" Esquema: `cai schema {schema} --json` (MCP: `get_schema`)." if schema else ""
    ctx = dict(error.get("ctx") or {})
    if kind == "missing":
        return f"Añade `{name}`: es obligatorio.{see}"
    if kind == "extra_forbidden":
        parent = model_at(model, loc[:-1])
        if parent is None:
            return f"Quita `{name}`.{see}"
        valid = list(parent.model_fields)
        if not valid:
            return f"Quita `{name}`: aquí no hay ningún campo."
        close = similar(name, valid, n=1, cutoff=0.6)
        guess = f"¿Querías decir `{close[0]}`? " if close else ""
        return f"{guess}Campos válidos aquí: {quoted(valid)}."
    if kind in ("literal_error", "enum"):
        allowed = [v.strip() for v in str(ctx.get("expected", "")).replace("'", "").split(",")]
        allowed = [p for v in allowed for p in v.split(" or ") if p.strip()]
        if name.endswith("language") and "es" in allowed and "en" in allowed:
            return (
                "Usa el código de dos letras del idioma de la oferta (`posting_language` de la "
                "extracción): `es` o `en`, no el nombre del idioma."
            )
        received = error.get("input")
        if isinstance(received, str) and allowed:
            close = similar(received, allowed, n=1, cutoff=0.5)
            if close:
                return f"¿Querías decir `{close[0]}`? Escríbelo tal cual."
        return None
    if kind == "string_too_short" and ctx.get("min_length") == 1:
        return "No lo dejes vacío: si no tienes el dato y el campo es opcional, quítalo."
    return None


def from_validation_error(
    exc: ValidationError,
    model: type[BaseModel] | None = None,
    schema: str | None = None,
) -> ToolError:
    """`model` (el de la entrada) y `schema` (su nombre en `cai schema`) mejoran las pistas."""
    details: list[ErrorDetail] = []
    for error in exc.errors(include_url=False):
        received, reason = describe_error(error)
        field = ".".join(str(part) for part in error["loc"]) or "(entrada)"
        details.append(
            ErrorDetail(
                field=field,
                received=received,
                reason=reason,
                expected=expected_of(error),
                hint=_hint(error, model, schema),
            )
        )
    count = len(details)
    noun = "error" if count == 1 else "errores"
    fields = ", ".join(d.field for d in details)
    return ToolError("validation_error", f"Entrada no válida ({count} {noun}): {fields}.", details)


# --- Nada largo de la entrada vuelve en el error --------------------------------------------------


def _long_texts(value: Any, found: set[str]) -> set[str]:
    if isinstance(value, str):
        if len(value) > MAX_RECEIVED_CHARS:
            found.add(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            _long_texts(key, found)
            _long_texts(item, found)
    elif isinstance(value, list | tuple):
        for item in value:
            _long_texts(item, found)
    return found


def _cut(text: str, long_texts: set[str]) -> str:
    """Cada tramo de `text` de más de 80 caracteres copiado de la entrada (entero o en parte) se
    queda en sus 79 primeros y «…». Los textos del error son cortos: basta una ventana
    deslizante."""
    window = MAX_RECEIVED_CHARS + 1

    def copied(piece: str) -> bool:
        return any(piece in long_text for long_text in long_texts)

    out: list[str] = []
    i = 0
    while i < len(text):
        if i + window <= len(text) and copied(text[i : i + window]):
            end = i + window
            while end < len(text) and copied(text[i : end + 1]):
                end += 1
            out.append(text[i : i + MAX_RECEIVED_CHARS - 1] + "…")
            i = end
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def scrub(error: ToolError, raw: Any) -> ToolError:
    """Recorta en el error cualquier texto de la entrada de más de 80 caracteres (también en el
    path, si es una clave larga, y en motivos que citan el valor). Límite conocido: no reconoce un
    texto que un servicio haya normalizado (minúsculas, espacios) antes de citarlo."""
    long_texts = _long_texts(raw, set())
    if not long_texts:
        return error
    info = error.info
    info.message = _cut(info.message, long_texts)
    for detail in info.details:
        detail.field = _cut(detail.field, long_texts)
        detail.reason = _cut(detail.reason, long_texts)
        if detail.received is not None:
            detail.received = _cut(detail.received, long_texts)
        if detail.hint is not None:
            detail.hint = _cut(detail.hint, long_texts)
    return error
