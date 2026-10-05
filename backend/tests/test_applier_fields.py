"""Candidatura asistida (fase 11): clasificación de campos, plan y plataformas, sin navegador."""

from pathlib import Path
from typing import Any

import pytest

from app.services.applier import fields, platforms
from app.services.applier.fields import FieldDescriptor, Option
from tests.applier_support import fill_data


def field(label: str, control: str = "text", **extra: Any) -> FieldDescriptor:
    return FieldDescriptor(marker="0", control=control, label=label, required=False, **extra)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("label", "extra", "kind"),
    [
        ("First Name*", {}, "first_name"),
        ("Nombre *", {}, "first_name"),
        ("Last Name*", {}, "last_name"),
        ("Apellidos", {}, "last_name"),
        ("Full name ✱", {}, "full_name"),
        ("Name *", {}, "full_name"),
        ("Nombre y apellidos *", {}, "full_name"),
        ("Preferred First Name", {}, "question"),
        ("Correo electrónico", {}, "email"),
        ("Contact", {"input_type": "email"}, "email"),
        ("Teléfono móvil", {}, "phone"),
        ("LinkedIn Profile", {}, "linkedin"),
        ("GitHub URL", {}, "github"),
        ("Ciudad de residencia", {}, "city"),
        ("Why do you want to work here?", {}, "question"),
        ("", {"placeholder": "Add a cover letter or anything else"}, "question"),
    ],
)
def test_classify_text_fields(label: str, extra: dict[str, Any], kind: str) -> None:
    assert fields.classify(field(label, **extra)) == kind


def test_classify_files_choices_and_sensitive() -> None:
    assert fields.classify(field("Resume/CV*", "file")) == "resume"
    assert fields.classify(field("Adjunta tu CV", "file")) == "resume"
    assert fields.classify(field("Cover Letter", "file")) == "cover_letter"
    assert fields.classify(field("Portfolio", "file")) == "other_file"
    lever_comments = field("", "textarea", placeholder="Add a cover letter or anything else")
    assert fields.classify(lever_comments) == "cover_letter"
    assert fields.classify(field("Carta de presentación", "textarea")) == "cover_letter"
    # Datos sensibles: nunca se rellenan, sea cual sea el control.
    for label in ("Gender", "Race / Ethnicity", "Veteran status", "¿Tienes discapacidad?"):
        assert fields.classify(field(label, "select")) == "sensitive"
    assert fields.classify(field("Acepto la política de privacidad", "checkbox")) == "consent"
    required = field("I confirm the above is true", "checkbox").model_copy(
        update={"required": True}
    )
    # Obligatoria pero no legal: no se marca sola al confirmar, la decides tú.
    relocate = field("Estoy dispuesto a reubicarme", "checkbox").model_copy(
        update={"required": True}
    )
    assert fields.classify(relocate) == "question"
    for label in (
        "Nationality",
        "Estado civil",
        "Do you have criminal convictions?",
        "Health conditions",
        "Afiliación sindical",
    ):
        assert fields.classify(field(label, "select")) == "sensitive", label
    assert fields.classify(required) == "consent"
    assert fields.classify(field("Quiero recibir novedades", "checkbox")) == "optional_checkbox"
    assert fields.classify(field("Do you need sponsorship?", "radio")) == "question"


def test_choose_option() -> None:
    labels = ["Select...", "Yes", "No"]
    assert fields.choose_option(labels, "Yes, I am an EU citizen.") == 1
    assert fields.choose_option(labels, "Sí") == 1
    assert fields.choose_option(labels, "No, I do not need it") == 2
    assert fields.choose_option(["--", "Remote", "Hybrid", "On-site"], "hybrid") == 2
    assert fields.choose_option(["Spain", "Portugal"], "I live in Spain") == 0
    assert fields.choose_option(labels, "Maybe later") is None


def test_match_answer_needs_similar_question(tmp_path: Path) -> None:
    answers = fill_data(tmp_path).answers
    found = fields.match_answer("Are you legally authorized to work in Spain?*", answers, 85)
    assert found is not None and found.answer.startswith("Yes")
    assert fields.match_answer("Do you have a driving licence?", answers, 85) is None
    assert fields.match_answer("", answers, 85) is None


def test_plan_assigns_sources_and_never_sensitive(tmp_path: Path) -> None:
    data = fill_data(tmp_path)
    descriptors = [
        field("First Name*"),
        field("Resume/CV*", "file"),
        field("Cover Letter", "file"),
        field(
            "Are you legally authorized to work in Spain?*",
            "select",
            options=[Option(label="Select..."), Option(label="Yes", value="1"), Option(label="No")],
        ),
        field("What are your salary expectations?*"),
        field("Gender", "select", options=[Option(label="Female")]),
        field("I agree to the privacy policy*", "checkbox").model_copy(update={"required": True}),
    ]
    plans = fields.plan(descriptors, data, 85)
    by_label = {p.field.label: p for p in plans}
    assert by_label["First Name*"].value == "Lucía"
    assert by_label["Resume/CV*"].file == data.resume
    assert by_label["Cover Letter"].file == data.letter_pdf
    auth = by_label["Are you legally authorized to work in Spain?*"]
    assert (auth.option, auth.value) == (1, "Yes")
    salary = by_label["What are your salary expectations?*"]
    assert salary.value is None and salary.needs_user_input
    gender = by_label["Gender"]
    assert gender.kind == "sensitive" and gender.value is None and gender.option is None
    consent = by_label["I agree to the privacy policy*"]
    assert consent.kind == "consent" and consent.value is None


def test_plan_without_letter_leaves_letter_empty(tmp_path: Path) -> None:
    data = fill_data(tmp_path, letter_pdf=None, letter_text=None)
    plans = fields.plan([field("Cover Letter", "file"), field("Carta", "textarea")], data, 85)
    assert all(p.file is None and p.value is None for p in plans)
    assert all(p.note == "No hay carta seleccionada para esta oferta." for p in plans)


def test_single_unlabelled_file_is_the_resume(tmp_path: Path) -> None:
    (p,) = fields.plan([field("Attach", "file")], fill_data(tmp_path), 85)
    assert p.kind == "resume" and p.file is not None


def test_split_name() -> None:
    assert fields.split_name("Lucía Varela Otero") == ("Lucía", "Varela Otero")
    assert fields.split_name("Lucía") == ("Lucía", "")


def test_platform_detection_and_application_url() -> None:
    gh = "https://job-boards.greenhouse.io/acme/jobs/123"
    lever = "https://jobs.lever.co/acme/6f1c2b9a-1111-2222-3333-444455556666"
    ashby = "https://jobs.ashbyhq.com/acme/6f1c2b9a-1111-2222-3333-444455556666"
    assert platforms.detect(gh) == "greenhouse"
    assert platforms.detect("https://boards.greenhouse.io/embed/job_app?token=1") == "greenhouse"
    assert platforms.detect(lever) == "lever"
    assert platforms.detect(ashby) == "ashby"
    assert platforms.detect("https://www.linkedin.com/jobs/view/1") == "linkedin"
    assert platforms.detect("https://empresa.example.com/empleo") is None
    assert platforms.detect("https://notgreenhouse.io.example.com") is None
    assert platforms.application_url("lever", lever) == lever + "/apply"
    assert platforms.application_url("lever", lever + "/apply") == lever + "/apply"
    assert platforms.application_url("ashby", ashby) == ashby + "/application"
    assert platforms.application_url("greenhouse", gh) == gh


def test_url_problem() -> None:
    assert platforms.url_problem("https://boards.greenhouse.io/acme/jobs/1") is None
    assert platforms.url_problem("ftp://example.com/x") is not None
    assert platforms.url_problem("http://localhost:8000/jobs") is not None
    assert platforms.url_problem("http://[::1]/x") is not None
