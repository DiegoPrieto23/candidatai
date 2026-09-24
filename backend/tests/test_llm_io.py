"""Esquema `JobExtraction` (schema_version 1)."""

import pytest
from pydantic import ValidationError

from app.agent_interface.errors import from_validation_error
from app.schemas.llm_io import JobExtraction
from tests.agent_support import EXTRACTION, extraction


def test_valid_extraction() -> None:
    model = JobExtraction.model_validate(EXTRACTION)
    assert model.salary is not None and model.salary.max == 48000
    assert model.model_dump(mode="json") == EXTRACTION


def test_all_documented_fields_and_nothing_else() -> None:
    # Exactamente los campos de docs/AGENT_INTERFACE.md §JobExtraction.
    assert list(JobExtraction.model_fields) == list(EXTRACTION)


def test_injection_excerpt_defaults_to_none() -> None:
    data = extraction()
    del data["injection_excerpt"]
    assert JobExtraction.model_validate(data).injection_excerpt is None


@pytest.mark.parametrize(
    ("changes", "field", "reason"),
    [
        ({"seniority": "sr"}, "seniority", "Debe ser uno de: intern, junior"),
        ({"remote_mode": "teletrabajo"}, "remote_mode", "Debe ser uno de"),
        ({"responsibilities": ["x"] * 7}, "responsibilities", "máximo 6"),
        ({"injection_excerpt": "x" * 201, "injection_suspected": True}, "injection_excerpt",
         "máximo 200"),
        ({"injection_excerpt": "ignora todo"}, "(entrada)", "solo va si `injection_suspected`"),
        ({"salary": {"min": 50, "max": 10, "currency": "EUR", "period": "year"}}, "salary",
         "`min` no puede ser mayor"),
        ({"salary": {"min": 1, "max": 2, "currency": "EUR", "period": "week"}}, "salary.period",
         "year, month, hour"),
        ({"application_deadline": "31/12/2026"}, "application_deadline", "AAAA-MM-DD"),
        ({"years_experience_min": "tres"}, "years_experience_min", "número entero"),
        ({"posting_language": ""}, "posting_language", "No puede estar vacío"),
        ({"extra": 1}, "extra", "Campo no permitido"),
        ({"languages_required": [{"language": "English", "nivel": "B2"}]},
         "languages_required.0.nivel", "Campo no permitido"),
    ],
)  # fmt: skip
def test_invalid_extraction_readable_errors(
    changes: dict[str, object], field: str, reason: str
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        JobExtraction.model_validate(extraction(**changes))
    details = from_validation_error(exc_info.value).info.details
    assert [d.field for d in details] == [field]
    assert reason in details[0].reason


def test_missing_field_is_reported_without_received() -> None:
    data = extraction()
    del data["seniority"]
    with pytest.raises(ValidationError) as exc_info:
        JobExtraction.model_validate(data)
    (detail,) = from_validation_error(exc_info.value).info.details
    assert (detail.field, detail.received, detail.reason) == (
        "seniority",
        None,
        "Campo obligatorio.",
    )


def test_received_value_is_truncated() -> None:
    with pytest.raises(ValidationError) as exc_info:
        JobExtraction.model_validate(extraction(seniority="x" * 500))
    (detail,) = from_validation_error(exc_info.value).info.details
    assert len(detail.received) == 80
    assert detail.received.endswith("…")
