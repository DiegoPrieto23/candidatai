"""Lectura del XML de un `.docx`: párrafos numerados y fragmentos fusionados.

Word parte el texto en fragmentos (`w:r`) por motivos invisibles (revisiones, corrector, idioma).
Aquí se fusionan los consecutivos con el mismo formato, que es lo que ve una persona. La
numeración recorre, en orden: el cuerpo (incluidas tablas, también anidadas, y cuadros de texto)
y después las cabeceras y los pies. Las copias de compatibilidad de los cuadros de texto
(`mc:Fallback`) no cuentan.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

from docx.document import Document as DocxDocument
from docx.oxml.ns import qn
from lxml import etree

MC_NS = "http://schemas.openxmlformats.org/markup-compatibility/2006"
FALLBACK = f"{{{MC_NS}}}Fallback"
ALTERNATE_CONTENT = f"{{{MC_NS}}}AlternateContent"
W_P, W_R, W_T, W_TBL, W_TR, W_TC = (qn(t) for t in ("w:p", "w:r", "w:t", "w:tbl", "w:tr", "w:tc"))
W_TXBX = qn("w:txbxContent")
W_DRAWING, W_PICT = qn("w:drawing"), qn("w:pict")

Location = Literal["body", "table", "textbox", "header", "footer"]


@dataclass
class Run:
    """Fragmentos consecutivos con el mismo formato, ya fusionados."""

    text: str
    elements: list[Any]
    bold: bool = False
    italic: bool = False
    size: float | None = None
    color: str | None = None
    font: str | None = None


@dataclass
class Paragraph:
    index: int
    element: Any
    location: Location
    table: int | None = None
    row: int | None = None
    cell: int | None = None
    style: str | None = None
    runs: list[Run] = field(default_factory=list)
    images: int = 0
    is_list: bool = False

    @property
    def text(self) -> str:
        return "".join(r.text for r in self.runs)


def _under_fallback(element: Any) -> bool:
    return any(a.tag == FALLBACK for a in element.iterancestors())


def _own_runs(p: Any) -> Iterator[Any]:
    """Fragmentos del párrafo (también dentro de hipervínculos), sin los de cuadros anidados."""
    for r in p.iter(W_R):
        if next(r.iterancestors(W_P)) is p:
            yield r


def _run_text(r: Any) -> str:
    parts = []
    for child in r:
        tag = etree.QName(child).localname
        if tag == "t":
            parts.append(child.text or "")
        elif tag == "tab":
            parts.append("\t")
        elif tag in ("br", "cr"):
            parts.append("\n")
        elif tag == "noBreakHyphen":
            parts.append("-")
    return "".join(parts)


def has_image(r: Any) -> bool:
    return r.find(W_DRAWING) is not None or r.find(W_PICT) is not None


def _on(rpr: Any, tag: str) -> bool:
    el = rpr.find(qn(tag)) if rpr is not None else None
    return el is not None and el.get(qn("w:val"), "true") not in ("false", "0", "off")


def _format_key(r: Any) -> bytes:
    rpr = r.find(qn("w:rPr"))
    return b"" if rpr is None else etree.tostring(rpr, method="c14n")


def _make_run(r: Any) -> Run:
    rpr = r.find(qn("w:rPr"))
    run = Run(text=_run_text(r), elements=[r], bold=_on(rpr, "w:b"), italic=_on(rpr, "w:i"))
    if rpr is not None:
        size = rpr.find(qn("w:sz"))
        if size is not None and size.get(qn("w:val"), "").isdigit():
            run.size = int(size.get(qn("w:val"))) / 2
        color = rpr.find(qn("w:color"))
        if color is not None and color.get(qn("w:val"), "auto") != "auto":
            run.color = "#" + color.get(qn("w:val")).upper()
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is not None:
            run.font = fonts.get(qn("w:ascii")) or fonts.get(qn("w:hAnsi"))
    return run


def merged_runs(p: Any) -> list[Run]:
    runs: list[Run] = []
    last_key: bytes | None = None
    for r in _own_runs(p):
        if has_image(r):
            runs.append(_make_run(r))
            last_key = None  # una imagen no se fusiona con nada
            continue
        key = _format_key(r)
        if runs and key == last_key:
            runs[-1].text += _run_text(r)
            runs[-1].elements.append(r)
        else:
            runs.append(_make_run(r))
            last_key = key
    return [r for r in runs if r.text or any(has_image(e) for e in r.elements)]


def _style_id(p: Any) -> str | None:
    style = p.find(f"{qn('w:pPr')}/{qn('w:pStyle')}")
    return style.get(qn("w:val")) if style is not None else None


def _is_list(p: Any, style_name: str | None) -> bool:
    if p.find(f"{qn('w:pPr')}/{qn('w:numPr')}") is not None:
        return True
    name = (style_name or "").casefold()
    return any(word in name for word in ("list", "lista", "viñeta", "vineta", "bullet"))


def header_footer_parts(doc: DocxDocument) -> list[tuple[Location, Any]]:
    """Elementos raíz de cabeceras y pies, en orden estable (por nombre de parte)."""
    parts = []
    for rel in doc.part.rels.values():
        kind = rel.reltype.rsplit("/", 1)[-1]
        if kind in ("header", "footer") and not rel.is_external:
            parts.append((str(rel.target_part.partname), kind, rel.target_part.element))
    return [(kind, element) for _name, kind, element in sorted(parts, key=lambda p: p[0])]


def style_names(doc: DocxDocument) -> dict[str, str]:
    return {s.style_id: s.name for s in doc.styles if s.style_id and s.name}


def tables_in_order(doc: DocxDocument) -> list[Any]:
    return [t for t in doc.element.body.iter(W_TBL) if not _under_fallback(t)]


def paragraphs(doc: DocxDocument) -> list[Paragraph]:
    names = style_names(doc)
    tables = tables_in_order(doc)  # la lista mantiene vivos los proxies: `id()` estable
    table_index = {id(t): i for i, t in enumerate(tables)}
    roots: list[tuple[Location, Any]] = [("body", doc.element.body), *header_footer_parts(doc)]
    result: list[Paragraph] = []
    for root_location, root in roots:
        for p in root.iter(W_P):
            if _under_fallback(p):
                continue
            location: Location = root_location
            info: dict[str, int | None] = {"table": None, "row": None, "cell": None}
            for ancestor in p.iterancestors():
                if ancestor.tag == W_TXBX:
                    location = "textbox" if root_location == "body" else root_location
                    break
                if ancestor.tag == W_TC:
                    tr = ancestor.getparent()
                    tbl = tr.getparent()
                    info = {
                        "table": table_index.get(id(tbl)),
                        "row": tbl.findall(W_TR).index(tr),
                        "cell": tr.findall(W_TC).index(ancestor),
                    }
                    if root_location == "body":
                        location = "table"
                    break
            style_id = _style_id(p)
            style = names.get(style_id, style_id) if style_id else None
            runs = merged_runs(p)
            result.append(
                Paragraph(
                    index=len(result),
                    element=p,
                    location=location,
                    style=style,
                    runs=runs,
                    images=sum(1 for r in _own_runs(p) if has_image(r)),
                    is_list=_is_list(p, style),
                    **info,
                )
            )
    return result
