"""Utilidades compartidas por los tests del CV: plantillas de prueba y contenido demo."""

import copy
import functools
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.schemas.cv import CvContent

BASE_META: dict[str, Any] = {
    "name": "Prueba",
    "engine": "docx",
    "origin": "user",
    "ats_friendly": True,
    "sections": [
        "summary",
        "experience",
        "projects",
        "education",
        "certifications",
        "skills",
        "languages",
    ],
}


def write_template(
    root: Path, template_id: str, docx: Path | bytes | None = None, **meta: Any
) -> Path:
    """Crea `root/<id>/` con su `template.yaml` y un `template.docx` (vacío si no se da)."""
    folder = root / template_id
    folder.mkdir(parents=True, exist_ok=True)
    data = {**copy.deepcopy(BASE_META), "id": template_id, **meta}
    (folder / "template.yaml").write_text(yaml.safe_dump(data), encoding="utf-8")
    if isinstance(docx, Path):
        (folder / "template.docx").write_bytes(docx.read_bytes())
    else:
        (folder / "template.docx").write_bytes(docx or b"")
    return folder


DEMO_CONTENT: dict[str, Any] = {
    "language": "es",
    "subtitle": "Data Engineer · Python · SQL · Snowflake",
    "summary": (
        "Data Engineer con tres años construyendo pipelines ETL y modelos analíticos sobre "
        "Snowflake para clientes de retail y banca."
    ),
    "experience": [
        {
            "experience_id": "exp-norteconsulting",
            "bullets": [
                {
                    "text": "Migré 40 procesos ETL de SSIS a Python sobre Snowflake (-35 % en "
                    "tiempo de carga nocturna).",
                    "evidence": ["exp-norteconsulting/a1"],
                },
                {
                    "text": "Diseñé el modelo dimensional de ventas y stock usado por 3 equipos.",
                    "evidence": ["exp-norteconsulting/a2"],
                },
            ],
        },
        {
            "experience_id": "exp-datagal",
            "bullets": [
                {
                    "text": "Automaticé informes semanales en Power BI (6 h/semana ahorradas).",
                    "evidence": ["exp-datagal/a1"],
                }
            ],
        },
    ],
    "projects": [
        {
            "project_id": "prj-tfg",
            "bullets": [
                {
                    "text": "Detección de anomalías en series temporales de 500 hogares.",
                    "evidence": ["prj-tfg"],
                }
            ],
        }
    ],
    "skills": [
        {"group": "Lenguajes", "items": ["Python", "SQL"]},
        {"group": "Datos", "items": ["Snowflake", "ETL", "Modelado dimensional"]},
    ],
    "education_ids": ["edu-grado"],
    "certification_ids": ["cert-aws-ccp"],
    "languages": [
        {"language": "Español", "level": "Nativo"},
        {"language": "Inglés", "level": "B2"},
    ],
    "include_regional_language": False,
    "keywords_targeted": ["Python", "SQL", "Snowflake"],
}


def demo_content_data(**changes: Any) -> dict[str, Any]:
    data = copy.deepcopy(DEMO_CONTENT)
    data.update(changes)
    return data


def demo_content(**changes: Any) -> CvContent:
    return CvContent.model_validate(demo_content_data(**changes))


# Carta del perfil demo para la oferta demo (fase 08c).
LETTER: dict[str, Any] = {
    "language": "es",
    "recipient": "Equipo de datos de Acme",
    "greeting": "Hola, equipo de Acme:",
    "paragraphs": [
        {
            "text": "Os escribo por el puesto de Data Engineer: buscáis a alguien con Python y "
            "SQL para mantener vuestras cargas en Snowflake.",
            "evidence": ["extraction"],
        },
        {
            "text": "En Norteconsulting migré las cargas nocturnas de SSIS a Python y reduje el "
            "tiempo de carga un 35 %, sin incidencias en el cambio.",
            "evidence": ["exp-norteconsulting/a1", "st-migracion"],
        },
        {"text": "¿Hablamos en una llamada breve esta semana?", "evidence": ["user"]},
    ],
    "sign_off": "Un saludo,",
    "keywords_targeted": ["Python", "SQL", "Snowflake"],
}


# --- PDF sin LibreOffice --------------------------------------------------------------------

LINES_PER_PAGE = 45


def make_pdf(
    pages: list[list[str]], font: str = "Calibri", extra_fonts: tuple[str, ...] = ()
) -> bytes:
    """PDF mínimo y válido con una línea de texto por elemento (fuente `font`, WinAnsi).

    `extra_fonts` solo se declaran en los recursos de cada página (como las de los títulos).
    """
    objects: list[bytes] = []
    n_pages = len(pages)
    page_ids = [4 + 2 * i for i in range(n_pages)]
    extra_ids = [4 + 2 * n_pages + i for i in range(len(extra_fonts))]
    font_refs = "".join(f" /F{i + 2} {ref} 0 R" for i, ref in enumerate(extra_ids))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    objects.append(
        f"<< /Type /Font /Subtype /TrueType /BaseFont /ABCDEF+{font} "
        "/Encoding /WinAnsiEncoding >>".encode()
    )
    for i, lines in enumerate(pages):
        content_id = page_ids[i] + 1
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {content_id} 0 R "
            f"/Resources << /Font << /F1 3 0 R{font_refs} >> >> >>".encode()
        )
        ops = [b"BT /F1 10 Tf 40 800 Td 12 TL"]
        for line in lines:
            text = line.encode("cp1252", "replace")
            text = text.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
            ops.append(b"(" + text + b") Tj T*")
        ops.append(b"ET")
        stream = b"\n".join(ops)
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    for extra in extra_fonts:
        objects.append(
            f"<< /Type /Font /Subtype /TrueType /BaseFont /ABCDEF+{extra}-Bold "
            "/Encoding /WinAnsiEncoding >>".encode()
        )

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


def fake_converter(  # noqa: ANN201
    font: str = "Calibri",
    lines_per_page: int = LINES_PER_PAGE,
    extra_fonts: tuple[str, ...] = ("Cambria",),
):
    """Conversor DOCX → PDF sin LibreOffice: una línea por párrafo, `lines_per_page` por página.

    Declara también Cambria (títulos de `clasica-foto`): así las integradas no dan
    `font_substituted`. Los párrafos dentro de tablas (la cabecera con foto) no se cuentan.
    """
    from docx import Document

    def convert(docx: Path, pdf: Path, _timeout: int) -> None:
        lines = [p.text for p in Document(str(docx)).paragraphs if p.text.strip()]
        pages = [lines[i : i + lines_per_page] for i in range(0, len(lines), lines_per_page)]
        pdf.parent.mkdir(parents=True, exist_ok=True)
        pdf.write_bytes(make_pdf(pages or [[]], font=font, extra_fonts=extra_fonts))

    return convert


@functools.cache
def chromium_available() -> bool:
    """¿Tiene Playwright su Chromium instalado? (`uv run playwright install chromium`)."""
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            return Path(pw.chromium.executable_path).is_file()
    except Exception:
        return False


# Los tests del motor html imprimen con Chromium de verdad: se saltan si no está instalado.
requires_chromium = pytest.mark.skipif(
    not chromium_available(), reason="Chromium de Playwright no instalado"
)


# --- PDFs con texto colocado (fase 25.5, maquetación) -------------------------------------------

Placed = tuple[float, float, str]  # x e y desde arriba a la izquierda (pt) y el texto


def make_layout_pdf(
    pages: list[list[Placed]], size: float = 10, width: float = 595, height: float = 842
) -> bytes:
    """PDF con cada línea donde se le dice (Helvetica, WinAnsi), para probar la maquetación."""
    objects: list[bytes] = []
    n_pages = len(pages)
    page_ids = [4 + 2 * i for i in range(n_pages)]
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    for i, lines in enumerate(pages):
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
            f"/Contents {page_ids[i] + 1} 0 R /Resources << /Font << /F1 3 0 R >> >> >>".encode()
        )
        ops = []
        for x, y, line in lines:
            text = line.encode("cp1252", "replace")
            text = text.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
            baseline = height - y - size
            ops.append(b"BT /F1 %g Tf %g %g Td (" % (size, x, baseline) + text + b") Tj ET")
        stream = b"\n".join(ops)
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)
