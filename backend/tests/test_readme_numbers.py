"""Fase 28.1: las cifras del README salen de algo que se comprueba, o no están.

Los distintivos de tests y de versión son dinámicos (CI y release); las cifras del eval de matching
tienen que coincidir con `evals/REPORT.md` y el número de casos, con `evals/matching/seed.jsonl`."""

from __future__ import annotations

import re

import pytest

from app.core.config import REPO_ROOT

READMES = ("README.md", "README.es.md")


def _read(name: str) -> str:
    return (REPO_ROOT / name).read_text(encoding="utf-8")


def _report_default_row() -> tuple[str, str, str]:
    """Precision, recall y F1 del umbral por defecto (la fila en negrita de la curva)."""
    row = re.search(
        r"^\| \*\*\d+\*\* \| \*\*([\d.]+)\*\* \| \*\*([\d.]+)\*\* \| \*\*([\d.]+)\*\* \|$",
        _read("evals/REPORT.md"),
        re.MULTILINE,
    )
    assert row, "evals/REPORT.md no tiene la fila del umbral por defecto en negrita"
    return row.group(1), row.group(2), row.group(3)


@pytest.mark.parametrize("name", READMES)
def test_no_hardcoded_counts_that_go_stale(name: str) -> None:
    text = _read(name)
    assert "img.shields.io/badge/tests-" not in text
    assert "actions/workflows/ci.yml/badge.svg" in text
    assert "img.shields.io/github/v/release/DiegoPrieto23/candidatai" in text
    # Ni cuántos tests hay ni cuántos ADR: cambian en cada fase.
    assert not re.search(r"\d[\d.,]* (backend |frontend |de backend |de frontend )?tests", text)
    assert not re.search(r"\d+ ADRs?\b", text)


@pytest.mark.parametrize("name", READMES)
def test_matching_eval_numbers_match_the_report(name: str) -> None:
    text = re.sub(r"(\d),(\d)", r"\1.\2", _read(name))  # el README en español usa coma decimal
    precision, recall, f1 = _report_default_row()
    match = re.search(
        r"\((\d+) [^)]*\): precision \*\*([\d.]+)\*\*, "
        r"recall \*\*([\d.]+)\*\*,\s+F1 \*\*([\d.]+)\*\*",
        text,
    )
    assert match, f"{name} no tiene la línea del eval de matching"
    cases = sum(
        1
        for line in (REPO_ROOT / "evals/matching/seed.jsonl").read_text("utf-8").splitlines()
        if line.strip()
    )
    assert match.groups() == (str(cases), precision, recall, f1)
