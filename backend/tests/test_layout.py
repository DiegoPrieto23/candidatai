"""Maquetación del PDF (fase 25.5, `documents/layout.py`): un PDF de prueba por aviso que lo dispara
y un CV correcto que no dispara ninguno."""

from pathlib import Path

import pytest

from app.services.documents import layout
from app.services.documents.layout import Expected
from tests.cv_support import Placed, make_layout_pdf

pytestmark = pytest.mark.layout

H = 842
EXPECTED = Expected(
    name="Lucía Varela",
    email="lucia.varela@example.com",
    phone="+34 600 000 000",
    headings=["Experiencia", "Formación", "Data Engineer"],
)


def header() -> list[Placed]:
    return [
        (50, 50, "Lucía Varela"),
        (50, 66, "lucia.varela@example.com · +34 600 000 000"),
        (50, 100, "Experiencia"),
    ]


def body(start: float, end: float, step: float = 14, prefix: str = "Viñeta") -> list[Placed]:
    lines: list[Placed] = []
    y, n = start, 1
    while y <= end:
        lines.append((60, y, f"{prefix} {n} con un logro concreto"))
        y += step
        n += 1
    return lines


def codes(tmp_path: Path, pages: list[list[Placed]], expected: Expected = EXPECTED) -> dict:
    path = tmp_path / "cv.pdf"
    path.write_bytes(make_layout_pdf(pages, height=H))
    return {w.code: w for w in layout.analyze(path, expected)}


def test_a_correct_cv_has_no_warnings(tmp_path: Path) -> None:
    page = [*header(), (50, 116, "Data Engineer · Acme"), *body(132, 700)]
    assert codes(tmp_path, [page]) == {}


def test_a_correct_two_page_cv_has_no_warnings(tmp_path: Path) -> None:
    first = [*header(), (50, 116, "Data Engineer · Acme"), *body(132, 760)]
    second = [(50, 50, "Formación"), *body(66, 300)]
    assert codes(tmp_path, [first, second]) == {}


def test_orphan_heading(tmp_path: Path) -> None:
    first = [*header(), *body(116, 740), (50, 780, "Data Engineer · Acme")]
    second = body(50, 400)
    found = codes(tmp_path, [first, second])
    assert set(found) == {"orphan_heading"}
    warning = found["orphan_heading"]
    assert warning.page == 1 and warning.fix == "content"
    assert "Data Engineer" in warning.message


def test_a_heading_at_the_bottom_of_the_last_page_is_not_an_orphan(tmp_path: Path) -> None:
    page = [*header(), *body(116, 740), (50, 780, "Formación")]
    assert "orphan_heading" not in codes(tmp_path, [page])


def test_large_gap(tmp_path: Path) -> None:
    page = [*header(), *body(116, 300), *body(500, 700, prefix="Después")]
    found = codes(tmp_path, [page])
    assert set(found) == {"large_gap"}
    assert found["large_gap"].page == 1 and found["large_gap"].fix == "template"


def test_footer_overlap(tmp_path: Path) -> None:
    page = [*header(), *body(116, 700), (50, 825, "Pie pisado por el texto")]
    found = codes(tmp_path, [page])
    assert "footer_overlap" in found and "Pie pisado" in found["footer_overlap"].message


def test_out_of_the_margin(tmp_path: Path) -> None:
    page = [*header(), *body(116, 700), (4, 400, "Se sale por la izquierda")]
    assert "footer_overlap" in codes(tmp_path, [page])


def test_nearly_empty_last_page(tmp_path: Path) -> None:
    first = [*header(), (50, 116, "Data Engineer · Acme"), *body(132, 760)]
    second = [(60, 50, "Una línea suelta"), (60, 64, "y otra")]
    found = codes(tmp_path, [first, second])
    assert set(found) == {"nearly_empty_last_page"}
    assert found["nearly_empty_last_page"].page == 2


@pytest.mark.parametrize(
    ("contact", "missing"),
    [
        ("✉ ✆", "el correo, el teléfono"),  # iconos en vez del texto
        ("lucia.varela@example.com", "el teléfono"),
    ],
)
def test_text_layer_missing_contact(tmp_path: Path, contact: str, missing: str) -> None:
    page = [(50, 50, "Lucía Varela"), (50, 66, contact), (50, 100, "Experiencia"), *body(116, 700)]
    found = codes(tmp_path, [page])
    assert set(found) == {"text_layer"} and missing in found["text_layer"].message


def test_text_layer_reading_order(tmp_path: Path) -> None:
    # En pantalla el nombre va arriba, pero en el texto del PDF sale después de los títulos.
    page = [
        (50, 100, "Experiencia"),
        *body(116, 700),
        (50, 50, "Lucía Varela"),
        (50, 66, "lucia.varela@example.com · +34 600 000 000"),
    ]
    found = codes(tmp_path, [page])
    assert "text_layer" in found and "orden de lectura" in found["text_layer"].message


def _cv_with_contact(contact: str) -> list[Placed]:
    return [(50, 50, "Lucía Varela"), (50, 66, contact), (50, 100, "Experiencia"), *body(116, 700)]


def test_phone_is_compared_by_digits(tmp_path: Path) -> None:
    other_format = _cv_with_contact("lucia.varela@example.com · (+34) 600-000-000")
    assert codes(tmp_path, [other_format]) == {}  # mismos dígitos, otro formato
    reordered = _cv_with_contact("lucia.varela@example.com · 600-000-000 (+34)")
    assert "text_layer" in codes(tmp_path, [reordered])  # «600000000 34» no es «34600000000»


def test_spaced_name_and_split_email_are_still_there(tmp_path: Path) -> None:
    page = [
        (50, 50, "L U C Í A  V A R E L A"),  # `letter-spacing` en el nombre
        (50, 66, "lucia.varela@"),
        (50, 78, "example.com · +34 600 000 000"),  # el correo, partido en dos líneas
        (50, 100, "E X P E R I E N C I A"),
        *body(116, 700),
    ]
    assert codes(tmp_path, [page]) == {}


def test_a_spaced_heading_at_the_bottom_is_an_orphan(tmp_path: Path) -> None:
    first = [*header(), *body(116, 740), (50, 780, "F O R M A C I Ó N")]
    assert "orphan_heading" in codes(tmp_path, [first, body(50, 400)])


def test_a_sentence_that_starts_like_a_heading_is_not_an_orphan(tmp_path: Path) -> None:
    first = [*header(), *body(116, 740), (50, 780, "Data Engineer con cinco años en plataformas")]
    assert "orphan_heading" not in codes(tmp_path, [first, body(50, 400)])


def test_large_gap_at_the_bottom_of_a_page_that_is_not_the_last(tmp_path: Path) -> None:
    first = [*header(), *body(116, 400)]  # la mitad de abajo, vacía, y sigue en la siguiente
    second = [(50, 50, "Formación"), *body(66, 400)]
    found = codes(tmp_path, [first, second])
    assert "large_gap" in found and found["large_gap"].page == 1


def test_thresholds_come_from_policies(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.policies import get_policies

    policies = get_policies()
    loose = policies.layout.model_copy(update={"large_gap_pct": 40})
    monkeypatch.setattr(
        layout, "get_policies", lambda: policies.model_copy(update={"layout": loose})
    )
    page = [*header(), *body(116, 300), *body(500, 700, prefix="Después")]
    assert codes(tmp_path, [page]) == {}


def test_expected_from_context() -> None:
    ctx = {
        "name": "Lucía Varela",
        "contact": {"email": "a@b.es", "phone": ""},
        "labels": {"experience": "Experiencia", "skills": "Habilidades", "projects": "Proyectos"},
        "experience": [{"role": "Data Engineer"}],
        "skills": [],
        "projects": [{"name": "TFG"}],
    }
    expected = layout.expected_from_context(ctx)
    assert expected.phone is None and expected.email == "a@b.es"
    assert expected.headings == ["Experiencia", "Proyectos", "Data Engineer"]  # sin skills: vacía


def test_off_by_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.policies import get_policies

    policies = get_policies()
    off = policies.model_copy(
        update={"layout": policies.layout.model_copy(update={"enabled": False})}
    )
    monkeypatch.setattr(layout, "get_policies", lambda: off)
    page = [*header(), *body(116, 300), *body(500, 700)]
    assert codes(tmp_path, [page]) == {}
