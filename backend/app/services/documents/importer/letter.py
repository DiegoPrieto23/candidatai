"""`jh templates build-letter`: la carta a juego de una plantilla docx importada (fase 08c).

Parte de su `template.docx`: conserva los bloques de arriba (párrafos y tablas) que solo usan
variables de cabecera (`name`, `subtitle`, `contact`, `photo`), con los párrafos de control que
los cierran, y quita el resto. Debajo añade el cuerpo de la carta (fecha, destinatario, saludo,
párrafos, despedida y nombre) con el formato del primer párrafo de texto del cuerpo del CV.
Se comprueba con el contrato de la carta y renderizándola; si falla, no se toca la plantilla.
"""

import copy
import os
import re
import shutil
import tempfile
from pathlib import Path
from typing import Any

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.documents import templates
from app.services.documents.importer import ImportIssue, TemplateImportError, docx_xml
from app.services.documents.importer.build import TemplateExistsError

LETTER_DOCX = "letter.docx"
HEADER_VARIABLES = frozenset({"name", "subtitle", "contact", "photo"})
# Las del CV que no son de cabecera: un bloque que las usa ya es cuerpo (`show` incluido).
BODY_VARIABLES = templates.CONTRACT_VARIABLES - HEADER_VARIABLES - {"accent_color", "labels"}

_TAGS = re.compile(r"\{\{(.*?)\}\}|\{%(.*?)%\}", re.S)
_IDENT = re.compile(r"(?<![\w.])([A-Za-z_]\w*)")
_EMPHASIS = ("w:b", "w:bCs", "w:i", "w:iCs", "w:caps", "w:smallCaps", "w:u", "w:color",
             "w:highlight")  # fmt: skip
_CLOSING = re.compile(r"^\{%[pr]?\s*(endif|endfor|else|elif\b.*)\s*%\}$")


class BuildLetterResult(BaseModel):
    template_id: str
    path: str  # relativa a data/
    header_blocks: int  # bloques de la cabecera conservados (párrafos o tablas)
    body_style: bool  # el cuerpo copia el formato de un párrafo del CV
    warnings: list[str]


def _text(element: Any) -> str:
    return "".join(t.text or "" for t in element.iter(docx_xml.W_T))


def variables(element: Any) -> set[str]:
    """Variables del contrato que usa un bloque (párrafo o tabla), por sus marcadores."""
    found: set[str] = set()
    for match in _TAGS.finditer(_text(element)):
        expression = match.group(1) or match.group(2) or ""
        found |= set(_IDENT.findall(expression))
    return found & templates.CONTRACT_VARIABLES


def _is_closing_control(element: Any) -> bool:
    return element.tag == docx_xml.W_P and bool(_CLOSING.match(_text(element).strip()))


def header_cut(blocks: list[Any]) -> int:
    """Cuántos bloques del principio son la cabecera. 0 si no hay cabecera separable."""
    last = -1
    for i, block in enumerate(blocks):
        used = variables(block)
        if used & BODY_VARIABLES:
            break
        if used & HEADER_VARIABLES:
            last = i
    if last < 0:
        return 0
    cut = last + 1
    while cut < len(blocks) and _is_closing_control(blocks[cut]):
        cut += 1
    return cut


def _body_style(blocks: list[Any]) -> tuple[Any, Any] | None:
    """`pPr` y `rPr` del primer párrafo de contenido del cuerpo: sin marcadores de bloque ni
    títulos de sección (`labels.*`), que suelen ir en otro tamaño o en mayúsculas."""
    for block in blocks:
        if block.tag != docx_xml.W_P:
            continue
        text = _text(block).strip()
        if not text or text.startswith("{%") or "labels." in text:
            continue
        ppr = block.find(qn("w:pPr"))
        run = block.find(qn("w:r"))
        rpr = run.find(qn("w:rPr")) if run is not None else None
        return ppr, rpr
    return None


def _spacing(ppr: Any, before_pt: float | None, after_pt: float | None) -> None:
    # `get_or_add_*` de python-docx inserta cada hijo en el orden que exige OOXML (Word rechaza
    # un `pPr` o un `rPr` con los hijos desordenados; LibreOffice los tolera).
    spacing = ppr.get_or_add_spacing()
    if before_pt is not None:
        spacing.set(qn("w:before"), str(int(before_pt * 20)))
    if after_pt is not None:
        spacing.set(qn("w:after"), str(int(after_pt * 20)))


def _paragraph(
    text: str,
    style: tuple[Any, Any] | None,
    *,
    bold: bool = False,
    right: bool = False,
    before: float | None = None,
    after: float | None = 6,
) -> Any:
    """Un párrafo del cuerpo de la carta con el formato del CV (un solo fragmento)."""
    ppr_src, rpr_src = style or (None, None)
    p = OxmlElement("w:p")
    ppr = copy.deepcopy(ppr_src) if ppr_src is not None else OxmlElement("w:pPr")
    for tag in ("w:numPr", "w:jc", "w:pBdr", "w:ind"):  # sin viñetas, bordes ni sangría
        for child in ppr.findall(qn(tag)):
            ppr.remove(child)
    _spacing(ppr, before, after)
    if right:
        ppr.get_or_add_jc().set(qn("w:val"), "right")
    p.append(ppr)
    r = OxmlElement("w:r")
    rpr = copy.deepcopy(rpr_src) if rpr_src is not None else OxmlElement("w:rPr")
    # Del párrafo del CV se toma la letra (fuente, tamaño), no el énfasis de ese párrafo.
    for tag in _EMPHASIS:
        for child in rpr.findall(qn(tag)):
            rpr.remove(child)
    if bold:
        rpr.get_or_add_b()
    r.append(rpr)
    t = OxmlElement("w:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    p.append(r)
    return p


def _control(text: str) -> Any:
    p = OxmlElement("w:p")
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = text
    r.append(t)
    p.append(r)
    return p


def letter_body(style: tuple[Any, Any] | None) -> list[Any]:
    """Fecha, destinatario, saludo, párrafos, despedida y nombre (contrato de la carta)."""
    return [
        _paragraph("{{ [place, date]|select|join(', ') }}", style, right=True, before=18, after=14),
        _control("{%p if recipient %}"),
        _paragraph("{{ recipient }}", style, bold=True, after=10),
        _control("{%p endif %}"),
        _paragraph("{{ greeting }}", style, after=10),
        _control("{%p for paragraph in paragraphs %}"),
        _paragraph("{{ paragraph }}", style, after=9),
        _control("{%p endfor %}"),
        _paragraph("{{ sign_off }}", style, before=6, after=24),
        _paragraph("{{ name }}", style, bold=True),
    ]


def _meta_with_letter(meta_yaml: bytes) -> bytes:
    """`template.yaml` con `letter: {file: letter.docx}` al final, sin tocar el resto."""
    base = templates.without_letter_block(meta_yaml)
    newline = b"\r\n" if b"\r\n" in base else b"\n"
    if base and not base.endswith(newline):
        base += newline
    return base + b"letter:" + newline + b"  file: " + LETTER_DOCX.encode() + newline


def _fail(template_id: str, reason: str, field: str = "template.docx") -> TemplateImportError:
    return TemplateImportError(
        f"No se puede crear la carta de «{template_id}»: {reason}",
        [ImportIssue(field=field, received=None, reason=reason)],
    )


def build_letter(template_id: str, force: bool = False) -> BuildLetterResult:
    from app.services.documents.preview import check_letter_renders

    template = templates.get(template_id)
    user_dir = get_settings().user_templates_dir.resolve()
    if not template.path.resolve().is_relative_to(user_dir):
        raise _fail(template_id, "es una integrada: ya trae su carta o usa `carta-simple`.", "id")
    if template.meta.engine != "docx":
        raise _fail(
            template_id,
            "es html: escribe su `letter.html` a mano (ver el skill `importar-plantilla-cv`).",
            "engine",
        )
    if not template.meta.layout.header_paragraphs:
        raise _fail(
            template_id,
            "no tiene cabecera (`layout.header_paragraphs` vacío). Vuelve a crearla con "
            '`build-docx` marcando la cabecera con `"header": true`.',
            "layout.header_paragraphs",
        )
    if template.meta.letter is not None and not force:
        raise TemplateExistsError(
            f"«{template_id}» ya tiene diseño de carta ({template.meta.letter.file}). Usa "
            "`--force` para sustituirlo."
        )

    doc = Document(str(template.engine_file))
    body = doc.element.body
    blocks = [c for c in body if c.tag in (docx_xml.W_P, docx_xml.W_TBL)]
    cut = header_cut(blocks)
    if cut == 0:
        raise _fail(
            template_id,
            "no encuentro la cabecera (nombre, subtítulo, contacto o foto) antes del cuerpo del "
            "CV. Si está mezclada con el cuerpo (p. ej. en una tabla a dos columnas), la carta "
            "saldrá con `carta-simple`.",
        )
    style = _body_style(blocks[cut:])
    warnings = []
    if style is None:
        warnings.append("No hay párrafos de texto en el cuerpo: la carta usa el estilo Normal.")
    kept = set().union(*(variables(b) for b in blocks[:cut]))
    missing = [v for v in ("subtitle", "contact") if v not in kept]
    if missing:
        warnings.append(
            "La cabecera conservada no lleva " + " ni ".join(missing) + ": quizá estaba "
            "mezclado con el cuerpo. Revisa la preview."
        )
    for block in blocks[cut:]:
        body.remove(block)
    anchor = body.find(qn("w:sectPr"))
    cols = anchor.find(qn("w:cols")) if anchor is not None else None
    if cols is not None and int(cols.get(qn("w:num"), "1")) > 1:
        anchor.remove(cols)  # la carta va a una columna
        warnings.append("El CV acababa en varias columnas: la carta va a una.")
    for element in letter_body(style):
        if anchor is not None:
            anchor.addprevious(element)
        else:
            body.append(element)

    settings = get_settings()
    settings.tmp_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="jh-letter-", dir=settings.tmp_dir))
    try:
        target = staging / template_id
        shutil.copytree(template.path, target)
        doc.save(str(target / LETTER_DOCX))
        meta_file = target / templates.META_FILE
        meta_file.write_bytes(_meta_with_letter(meta_file.read_bytes()))
        staged = templates.Template(meta=templates.load_meta(target), path=target)
        assert staged.letter_file is not None
        unknown = sorted(
            templates.undeclared_variables(staged, staged.letter_file)
            - templates.LETTER_CONTRACT_VARIABLES
        )
        if unknown:
            names = ", ".join(unknown)
            reason = f"la cabecera usa variables fuera del contrato de la carta: {names}."
            raise _fail(template_id, reason, LETTER_DOCX)
        try:
            check_letter_renders(staged)
        except templates.TemplateInvalidError as exc:
            raise _fail(template_id, str(exc), LETTER_DOCX) from exc
        # Primero la carta y después el YAML que la declara, cada uno con `os.replace` (atómico):
        # si algo falla a medias, la plantilla sigue siendo válida.
        for name in (LETTER_DOCX, templates.META_FILE):
            shutil.copyfile(target / name, staging / name)
            os.replace(staging / name, template.path / name)
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    return BuildLetterResult(
        template_id=template_id,
        path=(template.path / LETTER_DOCX).relative_to(settings.data_dir).as_posix(),
        header_blocks=cut,
        body_style=style is not None,
        warnings=warnings,
    )
