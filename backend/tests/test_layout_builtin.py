"""Las plantillas integradas con el CV y la carta de la demo salen sin avisos de maquetación (fase
25.5). Con LibreOffice (o Word) y Chromium de verdad: se saltan si no están."""

from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from app.models import Job
from app.schemas.cover_letter import CoverLetterRenderOptions
from app.schemas.cv import CvRenderOptions
from app.services import events, extractions, profile
from app.services.documents import cover_letter, pdf, service
from tests.cv_support import demo_content, requires_chromium
from tests.matching_support import demo_extraction
from tests.test_cover_letter import content as letter_content


def _converter_available() -> bool:
    try:
        pdf.get_converter()
    except pdf.PdfConverterUnavailableError:
        return False
    return True


pytestmark = [
    pytest.mark.layout,
    requires_chromium,
    pytest.mark.skipif(not _converter_available(), reason="Sin LibreOffice ni Word"),
]

LAYOUT_CODES = {
    "orphan_heading",
    "large_gap",
    "footer_overlap",
    "nearly_empty_last_page",
    "text_layer",
}


@pytest.fixture
def approved_job(session: Session, make_job: Callable[..., Job]) -> Job:
    profile.import_profile(session, profile.EXAMPLE_PATH)
    job = make_job("Data Engineer")
    job.location_raw = "Santiago de Compostela"
    events.record(session, job.id, "found", "system")
    extractions.save_extraction(session, job.id, demo_extraction())
    events.record(session, job.id, "approved", "user")
    session.flush()
    return job


@pytest.mark.parametrize("template_id", ["ats-simple", "clasica-foto", "moderna-2col"])
def test_builtin_cv_templates_have_no_layout_warnings(
    session: Session, approved_job: Job, template_id: str
) -> None:
    saved = service.save_content(session, approved_job.id, demo_content())
    result = service.render(session, saved.document_id, CvRenderOptions(template_id=template_id))
    layout = [w for w in result.warnings if w.code in LAYOUT_CODES]
    assert layout == [], [w.message for w in layout]


@pytest.mark.parametrize("template_id", ["carta-simple", "clasica-foto", "moderna-2col"])
def test_builtin_letter_templates_have_no_layout_warnings(
    session: Session, approved_job: Job, template_id: str
) -> None:
    saved = cover_letter.save_cover_letter(
        session,
        approved_job.id,
        letter_content(),
        CoverLetterRenderOptions(template_id=template_id),
    )
    layout = [w for w in saved.render.warnings if w.code in LAYOUT_CODES]
    assert layout == [], [w.message for w in layout]
