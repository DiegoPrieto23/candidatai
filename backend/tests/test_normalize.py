import hashlib

import pytest

from app.services.normalize import (
    fingerprint,
    normalize_company,
    normalize_location,
    normalize_title,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Acme S.L.", "acme"),
        ("ACME, S.A.", "acme"),
        ("Acme SLU", "acme"),
        ("Acme S.L.U.", "acme"),
        ("Globex GmbH", "globex"),
        ("Initech, Inc.", "initech"),
        ("Hooli Co., Ltd.", "hooli"),
        ("Telefónica España", "telefonica espana"),
        ("  Stark   Industries  ", "stark industries"),
        ("Grupo Sa Plus", "grupo sa plus"),  # la forma jurídica solo se quita al final
        ("AG", "ag"),  # nunca deja el nombre vacío
    ],
)
def test_normalize_company(raw: str, expected: str) -> None:
    assert normalize_company(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Data Engineer (m/f/d)", "data engineer"),
        ("Sr. Data Engineer – Remote", "senior data engineer"),
        ("Senior Data Engineer", "senior data engineer"),
        ("Data Engineer (H/M)", "data engineer"),
        ("Data Engineer [f/m/x]", "data engineer"),
        ("Data Engineer (all genders)", "data engineer"),
        ("Data Engineer (Senior)", "data engineer"),
        ("Data Engineer (Remote)", "data engineer"),
        ("Data Engineer - 100% remoto", "data engineer"),
        ("Data Engineer | Híbrido", "data engineer"),
        ("Jr Data Analyst", "junior data analyst"),
        ("🚀 Data   Engineer 🚀", "data engineer"),
        ("Ingeniero/a de Datos", "ingeniero a de datos"),
        ("C++ Developer", "c++ developer"),
        ("C# Developer", "c# developer"),
        ("Remote Sensing Engineer", "remote sensing engineer"),  # «remote» no es sufijo aquí
    ],
)
def test_normalize_title(raw: str, expected: str) -> None:
    assert normalize_title(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, ""),
        ("", ""),
        ("Madrid, España", "madrid espana"),
        ("Remoto", "remote"),
        ("Remote - Spain", "remote spain"),
        ("A Coruña (Galicia)", "a coruna galicia"),
    ],
)
def test_normalize_location(raw: str | None, expected: str) -> None:
    assert normalize_location(raw) == expected


def test_fingerprint_is_sha256_of_normalized_parts() -> None:
    expected = hashlib.sha256(b"acme|data engineer|madrid").hexdigest()
    assert fingerprint("Acme S.L.", "Data Engineer (m/f/d)", "Madrid") == expected


def test_fingerprint_equal_for_formatting_variants() -> None:
    a = fingerprint("ACME, S.A.", "Sr. Data Engineer – Remote", "Remoto")
    b = fingerprint("Acme S.L.", "Senior Data Engineer (m/f/d)", "remote")
    assert a == b


def test_fingerprint_differs_on_meaningful_changes() -> None:
    base = fingerprint("Acme", "Data Engineer", "Madrid")
    assert fingerprint("Globex", "Data Engineer", "Madrid") != base
    assert fingerprint("Acme", "Senior Data Engineer", "Madrid") != base
    assert fingerprint("Acme", "Data Engineer", "Barcelona") != base
    assert fingerprint("Acme", "Data Engineer", None) != base
