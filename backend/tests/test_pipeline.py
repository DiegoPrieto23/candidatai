"""Proyección de etapas: cada evento del catálogo desde cada etapa, válido o no."""

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.services.pipeline import (
    EventType,
    InvalidTransitionError,
    Stage,
    project,
    stage_for,
)

T0 = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)

PD = Stage.PENDING_DETAIL
PE = Stage.PENDING_EXTRACTION
PT = Stage.PENDING_TRIAGE
AP = Stage.APPROVED
CR = Stage.CV_READY
AD = Stage.APPLIED
IP = Stage.IN_PROCESS
CL = Stage.CLOSED
WORK = (PE, PT, AP, CR, AD, IP)  # abiertas, salvo los resúmenes
OPEN = (PD, *WORK)


@dataclass
class Ev:
    type: str
    payload: dict[str, Any] | None = field(default=None)
    occurred_at: datetime = T0


def seq(*types: str | Ev) -> list[Ev]:
    """Eventos separados por un minuto, en el orden dado."""
    return [
        replace(t if isinstance(t, Ev) else Ev(t), occurred_at=T0 + timedelta(minutes=i))
        for i, t in enumerate(types)
    ]


RENDERED = Ev("cv_rendered", {"document_id": 1, "render_id": 1, "too_long": False})
TOO_LONG = Ev("cv_rendered", {"document_id": 1, "render_id": 2, "too_long": True})
VERIFIED = Ev("cv_verified", {"document_id": 1, "passed": True})
SUMMARY = Ev("found", {"detail_level": "summary"})

# Una secuencia mínima para llegar a cada etapa. El cierre se hace desde `pending_triage`.
PATHS: dict[Stage, list[str | Ev]] = {
    PD: [SUMMARY],
    PE: ["found"],
    PT: ["found", "extracted"],
    AP: ["found", "extracted", "approved"],
    CR: ["found", "extracted", "approved", RENDERED, VERIFIED],
    AD: ["found", "extracted", "approved", RENDERED, VERIFIED, "applied"],
    IP: ["found", "extracted", "approved", RENDERED, VERIFIED, "applied", "reply_received"],
    CL: ["found", "extracted", "discarded"],
}


def _same(stages: tuple[Stage, ...]) -> dict[Stage, Stage]:
    return {s: s for s in stages}


def _to(target: Stage, stages: tuple[Stage, ...]) -> dict[Stage, Stage]:
    return dict.fromkeys(stages, target)


# Especificación escrita a mano (no derivada de TRANSITIONS): etapa de origen -> etapa final.
# Una etapa ausente significa que el evento es inválido ahí.
EXPECTED: dict[EventType, dict[Stage, Stage]] = {
    EventType.FOUND: {},
    EventType.DETAIL_CAPTURED: _to(PE, (PD,)),
    EventType.DUPLICATE_DETECTED: _to(CL, (PD, PE, PT)),
    EventType.EXTRACTED: _to(PT, (PE, PT)),
    EventType.EXTRACTION_FAILED: _same((PE,)),
    EventType.HARD_FILTER_FAILED: _to(CL, (PT,)),
    EventType.INJECTION_SUSPECTED: _same(OPEN),
    EventType.SCORED: _same(WORK),
    EventType.FIT_ASSESSED: _same(WORK),
    EventType.APPROVED: _to(AP, (PT,)),
    EventType.DISCARDED: _to(CL, (PD, PE, PT, AP, CR)),
    EventType.CV_GENERATED: _same((AP, CR)),
    EventType.CV_RENDERED: _same((AP, CR)),  # sin payload; con documento verificado, aparte
    EventType.CV_VERIFIED: _same((AP, CR)),  # sin `passed`; con `passed` se prueba aparte
    EventType.CV_REJECTED: _same((AP, CR)),
    EventType.APPLICATION_PREPARED: _same(WORK),
    EventType.APPLIED: _to(AD, (CR,)),
    EventType.APPLIED_MANUALLY: _to(AD, (PE, PT, AP, CR)),
    EventType.REPLY_RECEIVED: _to(IP, (AD, IP)),
    EventType.INTERVIEW_SCHEDULED: _to(IP, (AD, IP)),
    EventType.INTERVIEW_DONE: _to(IP, (AD, IP)),
    EventType.TEST_ASSIGNED: _to(IP, (AD, IP)),
    EventType.OFFER_RECEIVED: _to(IP, (AD, IP)),
    EventType.FOLLOWUP_SENT: _same((AD, IP)),
    EventType.REJECTED: _to(CL, WORK),
    EventType.WITHDRAWN: _to(CL, WORK),
    EventType.EXPIRED: _to(CL, OPEN),
    EventType.ACCEPTED: _to(CL, (IP,)),
    EventType.REOPENED: {CL: PT},  # vuelve a la etapa previa al cierre
    EventType.NOTE: _same((*OPEN, CL)),
}

CASES = [(ev, stage) for ev in EventType for stage in Stage]


def test_expected_covers_whole_catalog() -> None:
    assert set(EXPECTED) == set(EventType)


def test_paths_reach_their_stage() -> None:
    for stage, path in PATHS.items():
        assert stage_for(seq(*path)) == stage


@pytest.mark.parametrize(("event_type", "from_stage"), CASES, ids=lambda v: str(v))
def test_transition(event_type: EventType, from_stage: Stage) -> None:
    events = [*seq(*PATHS[from_stage]), Ev(event_type.value, occurred_at=T0 + timedelta(days=1))]
    expected = EXPECTED[event_type].get(from_stage)
    if expected is None:
        with pytest.raises(InvalidTransitionError, match=f"«{event_type}» no es válido"):
            stage_for(events)
    else:
        assert stage_for(events) == expected


def test_first_event_must_be_found() -> None:
    with pytest.raises(InvalidTransitionError, match="primer evento .* debe ser «found»"):
        stage_for(seq("extracted"))


def test_no_events_has_no_stage() -> None:
    with pytest.raises(ValueError, match="No hay eventos"):
        stage_for([])


def test_unknown_event_type_rejected() -> None:
    with pytest.raises(ValueError):
        stage_for(seq("found", "teleported"))


def test_cv_verified_only_advances_when_passed() -> None:
    base = ["found", "extracted", "approved", RENDERED]
    assert stage_for(seq(*base, Ev("cv_verified", {"document_id": 1, "passed": False}))) == AP
    assert stage_for(seq(*base, Ev("cv_verified", {"document_id": 1}))) == AP
    assert stage_for(seq(*base, VERIFIED)) == CR
    # Una verificación fallida posterior no retrocede: el CV ya verificado sigue listo.
    failed = Ev("cv_verified", {"document_id": 1, "passed": False})
    assert stage_for(seq(*base, VERIFIED, failed)) == CR


def test_cv_verified_needs_a_render_that_fits() -> None:
    base = ["found", "extracted", "approved"]
    assert stage_for(seq(*base, VERIFIED)) == AP
    assert stage_for(seq(*base, TOO_LONG, VERIFIED)) == AP
    # Sin `document_id` no se sabe de qué documento es: no avanza.
    assert stage_for(seq(*base, RENDERED, Ev("cv_verified", {"passed": True}))) == AP


def test_cv_verified_and_render_must_be_same_document() -> None:
    other = Ev("cv_rendered", {"document_id": 2, "render_id": 3, "too_long": False})
    assert stage_for(seq("found", "extracted", "approved", other, VERIFIED)) == AP


def test_render_that_fits_after_verification_reaches_cv_ready() -> None:
    base = ["found", "extracted", "approved", TOO_LONG, VERIFIED]
    assert stage_for(seq(*base)) == AP
    assert stage_for(seq(*base, RENDERED)) == CR
    # Un render de otro documento, o sin `too_long` explícito, no basta.
    other = Ev("cv_rendered", {"document_id": 2, "render_id": 3, "too_long": False})
    assert stage_for(seq(*base, other)) == AP
    assert stage_for(seq(*base, Ev("cv_rendered", {"document_id": 1}))) == AP


def test_applied_without_cv_ready_explains_alternative() -> None:
    with pytest.raises(InvalidTransitionError, match="applied_manually"):
        stage_for(seq("found", "extracted", "approved", "applied"))


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (["found", "duplicate_detected"], PE),
        (["found", "extracted", "hard_filter_failed"], PT),
        (["found", "extracted", "approved", "discarded"], AP),
        (["found", "extracted", "approved", RENDERED, VERIFIED, "applied", "rejected"], AD),
        (["found", "extracted", "applied_manually", "offer_received", "withdrawn"], IP),
    ],
)
def test_reopened_returns_to_stage_before_close(path: list[str | Ev], expected: Stage) -> None:
    assert stage_for(seq(*path, "reopened")) == expected


def test_reopen_close_reopen_uses_latest_close() -> None:
    events = seq("found", "discarded", "reopened", "extracted", "expired", "reopened")
    assert stage_for(events) == PT


def test_projection_tracks_application_fields() -> None:
    events = seq(
        "found",
        "extracted",
        Ev("applied_manually", {"channel": "portal_manual", "render_id": 7}),
        "reply_received",
    )
    state = project(events)
    assert state.stage == IP
    assert state.channel == "portal_manual"
    assert state.render_id == 7
    assert state.applied_at == events[2].occurred_at
    assert state.last_event_at == events[3].occurred_at


def test_events_are_replayed_by_occurred_at() -> None:
    found = Ev("found", occurred_at=T0)
    approved = Ev("approved", occurred_at=T0 + timedelta(hours=2))
    extracted = Ev("extracted", occurred_at=T0 + timedelta(hours=1))  # llega tarde, pasó antes
    assert stage_for([found, approved, extracted]) == AP


def test_ties_keep_input_order() -> None:
    same = [Ev("found"), Ev("extracted"), Ev("approved")]
    assert stage_for(same) == AP
    with pytest.raises(InvalidTransitionError):
        stage_for([Ev("found"), Ev("approved"), Ev("extracted")])


def test_summary_found_goes_to_pending_detail_and_capture_completes_it() -> None:
    assert stage_for(seq(SUMMARY)) == PD
    assert stage_for(seq(Ev("found", {"detail_level": "full"}))) == PE
    assert stage_for(seq(SUMMARY, "detail_captured", "extracted")) == PT


def test_expired_summary_reopens_as_summary() -> None:
    assert stage_for(seq(SUMMARY, "expired", "reopened")) == PD
