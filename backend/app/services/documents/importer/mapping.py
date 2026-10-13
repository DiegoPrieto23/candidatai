"""Mapeo párrafo → marcador que decide el agente para `cai templates build-docx`.

```json
{"paragraphs": [
  {"index": 0, "action": "variable", "text": "{{ name }}", "header": true},
  {"index": 4, "action": "variable", "text": "{{ labels.experience|upper }}",
   "start": ["if show.experience"]},
  {"index": 5, "action": "variable", "runs": [{"text": "{{ e.role }}", "like": 0},
                                              {"text": " | {{ e.company }}", "like": 1}],
   "start": ["for e in experience"]},
  {"index": 6, "action": "variable", "text": "{{ b }}",
   "start": ["for b in e.bullets"], "end": ["endfor", "endfor", "endif"]},
  {"index": 7, "action": "delete"}
]}
```

- `action`: `static` (se queda tal cual; por defecto para los párrafos que no aparecen),
  `delete`, `variable` (el párrafo pasa a ser `text`, o `runs` para conservar formatos mezclados:
  cada parte copia el formato del fragmento `like` de `inspect`) o `photo` (la imagen del párrafo
  se sustituye por la foto).
- `start` / `end`: bloques que se abren antes del párrafo y se cierran después (`for x in y`,
  `if cond`; `endfor`, `endif`). Con `scope: row` el bloque repite o condiciona la fila de tabla
  entera (`{%tr … %}`); por defecto, párrafos (`{%p … %}`).
- `header`: el párrafo es parte de la cabecera (nombre, subtítulo, contacto, foto); la fase 08c la
  usa para crear la carta a juego.

Antes de tocar el fichero, todo el mapeo se monta como una plantilla Jinja de borrador y se
renderiza con el perfil demo: así salen juntos los bloques sin cerrar, las variables fuera del
contrato y los atributos que no existen (`e.rol`), cada uno con el índice de su párrafo.
"""

import re
from typing import Any, Literal, Self

import jinja2
from docx.oxml.ns import qn
from jinja2 import meta as jinja_meta
from jinja2.sandbox import SandboxedEnvironment
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.services.documents.importer import ImportIssue, TemplateImportError, docx_xml
from app.services.documents.preview import demo_context
from app.services.documents.templates import CONTRACT_VARIABLES

_SECTION_BREAK = f"{qn('w:pPr')}/{qn('w:sectPr')}"
_START = re.compile(r"^(for\s+\w+(\s*,\s*\w+)?\s+in\s+\S.*|if\s+\S.*)$")
SECTION_TOKENS = re.compile(
    r"\b(summary|experience|projects|education|certifications|extra_sections|skills|languages)\b"
)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunPart(_Strict):
    text: str
    like: int = Field(ge=0, description="Fragmento de `inspect` cuyo formato copia esta parte.")


class ParagraphMap(_Strict):
    index: int = Field(ge=0)
    action: Literal["static", "delete", "variable", "photo"] = "static"
    text: str | None = None
    runs: list[RunPart] | None = Field(default=None, min_length=1)
    start: list[str] = []
    end: list[Literal["endfor", "endif"]] = []
    scope: Literal["paragraph", "row"] = "paragraph"
    header: bool = False

    @model_validator(mode="after")
    def _coherent(self) -> Self:
        if self.action == "variable" and (self.text is None) == (self.runs is None):
            raise ValueError("Con `variable` hace falta `text` o `runs` (uno de los dos).")
        if self.action != "variable" and (self.text is not None or self.runs is not None):
            raise ValueError("`text` y `runs` solo valen con `action: variable`.")
        if self.action == "delete" and (self.start or self.end or self.header):
            raise ValueError("Un párrafo que se borra no puede abrir ni cerrar bloques.")
        for piece in [self.text or "", *(p.text for p in self.runs or []), *self.start]:
            if "__" in piece or "{#" in piece:
                raise ValueError(
                    "No se admiten `__` ni comentarios `{#`: usa solo variables del contrato."
                )
        for tag in self.start:
            if not _START.match(tag.strip()) or "%}" in tag or "{%" in tag:
                raise ValueError(
                    f"`start` no válido: «{tag}». Usa `for x in lista` o `if condición`."
                )
        return self

    @property
    def content(self) -> str:
        if self.action == "photo":
            return "{{ photo }}"
        if self.runs is not None:
            return "".join(part.text for part in self.runs)
        return self.text or ""


class DocxMapping(_Strict):
    paragraphs: list[ParagraphMap] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> Self:
        indexes = [p.index for p in self.paragraphs]
        repeated = sorted({i for i in indexes if indexes.count(i) > 1})
        if repeated:
            raise ValueError(f"Párrafos repetidos en el mapeo: {repeated}.")
        return self

    def by_index(self) -> dict[int, ParagraphMap]:
        return {p.index: p for p in self.paragraphs}


# --- Comprobación previa --------------------------------------------------------------------


def _issue(index: int | None, reason: str, received: str | None = None) -> ImportIssue:
    field = f"paragraphs[index={index}]" if index is not None else "mapping"
    return ImportIssue(field=field, received=received, reason=reason)


def _template_line(exc: BaseException) -> int | None:
    """Línea de la plantilla de borrador donde falló el render (Jinja reescribe la traza)."""
    tb = exc.__traceback__
    line = None
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == "<template>":
            line = tb.tb_lineno
        tb = tb.tb_next
    return line


def draft_template(
    paragraphs: list[docx_xml.Paragraph], mapping: DocxMapping
) -> tuple[str, list[int]]:
    """El mapeo como una plantilla Jinja (una línea por pieza) y el párrafo de cada línea."""
    lines: list[str] = []
    owners: list[int] = []
    entries = mapping.by_index()
    # Un bloque de fila (`scope: row`) se cierra después de la fila entera, no del párrafo.
    # Guardar la fila mantiene vivo su proxy de lxml: si no, `id()` no es estable.
    last_in_row: dict[int, tuple[Any, int]] = {}
    for p in paragraphs:
        tr = next(p.element.iterancestors(docx_xml.W_TR), None)
        if tr is not None:
            last_in_row[id(tr)] = (tr, p.index)
    deferred: dict[int, list[str]] = {}

    def emit(owner: int, line: str) -> None:
        lines.append(line)
        owners.append(owner)

    for p in paragraphs:
        entry = entries.get(p.index)
        if entry is not None and entry.action != "delete":
            for tag in entry.start:
                emit(p.index, f"{{% {tag.strip()} %}}")
            emit(p.index, entry.content if entry.action in ("variable", "photo") else "")
            ends = [f"{{% {tag} %}}" for tag in entry.end]
            if entry.scope == "row" and ends:
                tr = next(p.element.iterancestors(docx_xml.W_TR))
                deferred.setdefault(last_in_row[id(tr)][1], []).extend(ends)
            else:
                for line in ends:
                    emit(p.index, line)
        for line in deferred.pop(p.index, []):
            emit(p.index, line)
    return "\n".join(lines), owners


def check(paragraphs: list[docx_xml.Paragraph], mapping: DocxMapping) -> None:
    """Lanza `TemplateImportError` con todos los problemas del mapeo, o no hace nada."""
    issues: list[ImportIssue] = []
    by_index = {p.index: p for p in paragraphs}
    for entry in mapping.paragraphs:
        p = by_index.get(entry.index)
        if p is None:
            issues.append(
                _issue(entry.index, f"No existe: el documento tiene {len(paragraphs)} párrafos.")
            )
            continue
        if entry.scope == "row" and p.row is None:
            issues.append(_issue(entry.index, "`scope: row` solo vale en párrafos de una tabla."))
        if entry.action == "photo" and not p.images:
            issues.append(_issue(entry.index, "`photo` en un párrafo sin imagen."))
        if entry.runs is not None:
            for part in entry.runs:
                if part.like >= max(len(p.runs), 1):
                    issues.append(
                        _issue(
                            entry.index,
                            f"`like` fuera de rango: el párrafo tiene {len(p.runs)} fragmentos.",
                            str(part.like),
                        )
                    )
        if entry.action == "delete" and p.element.find(_SECTION_BREAK) is not None:
            issues.append(
                _issue(entry.index, "Lleva un salto de sección: no se puede borrar (déjalo vacío).")
            )
    entries = mapping.by_index()
    for p in paragraphs:
        entry = entries.get(p.index)
        if (entry is None or entry.action == "static") and any(
            mark in p.text for mark in ("{{", "{%", "{#")
        ):
            issues.append(
                _issue(p.index, "Texto con `{{`, `{%` o `{#` que se quedaría así: mapéalo.", p.text)
            )
    if issues:
        raise TemplateImportError(_summary(issues), issues)

    source, owners = draft_template(paragraphs, mapping)
    env = SandboxedEnvironment(undefined=jinja2.StrictUndefined, autoescape=False)
    try:
        ast = env.parse(source)
    except jinja2.TemplateSyntaxError as exc:
        owner = owners[exc.lineno - 1] if 0 < exc.lineno <= len(owners) else None
        issue = _issue(owner, f"Bloques o marcadores mal formados: {exc.message}.")
        raise TemplateImportError(_summary([issue]), [issue]) from exc
    unknown = sorted(jinja_meta.find_undeclared_variables(ast) - CONTRACT_VARIABLES)
    if unknown:
        issue = _issue(
            None,
            f"Variables fuera del contrato: {', '.join(unknown)}. Usa solo las de "
            "docs/CV_TEMPLATES.md §Contrato de variables.",
            ", ".join(unknown),
        )
        raise TemplateImportError(_summary([issue]), [issue])
    try:
        env.from_string(source).render(demo_context())
    except jinja2.TemplateError as exc:
        line = _template_line(exc)
        owner = owners[line - 1] if line and 0 < line <= len(owners) else None
        issue = _issue(owner, f"No se puede renderizar con el perfil demo: {exc}.")
        raise TemplateImportError(_summary([issue]), [issue]) from exc


def used_sections(paragraphs: list[docx_xml.Paragraph], mapping: DocxMapping) -> list[str]:
    """Secciones del contrato en el orden en que las usa la plantilla (el del original)."""
    source, _owners = draft_template(paragraphs, mapping)
    seen: list[str] = []
    for match in SECTION_TOKENS.finditer(source):
        if match.group(1) not in seen:
            seen.append(match.group(1))
    return seen


def _summary(issues: list[ImportIssue]) -> str:
    count = len(issues)
    noun = "problema" if count == 1 else "problemas"
    return f"El mapeo no es válido ({count} {noun}): " + ", ".join(i.field for i in issues) + "."
