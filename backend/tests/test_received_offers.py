"""Fase 21: ofertas recibidas, comparación con el mínimo y vista para el agente.

Criterios: la comparación (mínimo de `private` y rango publicado) solo la calcula el servicio para
la UI; el agente ve la oferta sin el mínimo ni las diferencias, y sin importes si son privados.
Guardar datos registra `offer_received` si falta y las notas del historial no llevan cifras.
"""

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, Job, JobExtraction, ProfileVersion
from app.services import events, profile, received_offers
from app.services.pipeline import InvalidTransitionError
from app.services.received_offers import ReceivedOfferFields, ReceivedOfferNotFoundError
from tests.replies_support import add_applied_job

FLOOR = 41_000


def _profile(session: Session, floor: object = FLOOR) -> None:
    data = profile.load_from_yaml(profile.EXAMPLE_PATH).model_dump(mode="json")
    data["private"] = {"salary_floor_eur": floor}
    session.add(ProfileVersion(data=data, content_hash="ofertas"))
    session.flush()


def _published(session: Session, job: Job, **salary: object) -> None:
    session.add(JobExtraction(job_id=job.id, schema_version=1, data={"salary": salary}))
    session.flush()


def _types(session: Session, job_id: int) -> list[str]:
    return list(
        session.scalars(select(Event.type).where(Event.job_id == job_id).order_by(Event.id))
    )


def _notes(session: Session, job_id: int) -> list[str]:
    rows = session.scalars(select(Event).where(Event.job_id == job_id, Event.type == "note"))
    return [e.payload["note"] for e in rows]


def test_saving_registers_offer_received_once_and_notes_changes_without_figures(
    session: Session,
) -> None:
    job = add_applied_job(session, "Brétema Analytics")
    saved = received_offers.save_received_offer(
        session, job.id, ReceivedOfferFields(base_salary=45_000, variable=4_000)
    )
    assert saved.amounts_private is True and saved.currency == "EUR"
    assert _types(session, job.id)[-1] == "offer_received"

    received_offers.save_received_offer(
        session, job.id, ReceivedOfferFields(base_salary=47_500, variable=4_000)
    )
    assert _types(session, job.id).count("offer_received") == 1
    assert _notes(session, job.id) == ["Oferta recibida actualizada (fijo)."]
    assert "47" not in _notes(session, job.id)[0]

    # Guardar lo mismo no deja otra nota.
    received_offers.save_received_offer(
        session, job.id, ReceivedOfferFields(base_salary=47_500, variable=4_000)
    )
    assert len(_notes(session, job.id)) == 1


def test_existing_offer_received_is_not_duplicated(session: Session) -> None:
    job = add_applied_job(session, "Néboa Data")
    events.record(session, job.id, "offer_received", "user")
    received_offers.save_received_offer(session, job.id, ReceivedOfferFields(base_salary=1))
    assert _types(session, job.id).count("offer_received") == 1


def test_saving_needs_a_stage_that_admits_an_offer(session: Session, make_job) -> None:
    job = make_job()
    with pytest.raises(InvalidTransitionError):
        received_offers.save_received_offer(session, job.id, ReceivedOfferFields(base_salary=1))
    assert received_offers.get_received_offer(session, job.id) is None


def test_fields_are_validated() -> None:
    with pytest.raises(ValidationError):
        ReceivedOfferFields(base_salary=-1)
    with pytest.raises(ValidationError):
        ReceivedOfferFields(currency="euros")
    with pytest.raises(ValidationError):
        ReceivedOfferFields(period="hour")  # type: ignore[arg-type]
    assert ReceivedOfferFields(currency="usd", notes="  ").model_dump()["currency"] == "USD"
    assert ReceivedOfferFields(notes="  ").notes is None


def test_agent_view_hides_private_amounts(session: Session) -> None:
    job = add_applied_job(session, "Brétema Analytics")
    data = ReceivedOfferFields(base_salary=45_000, variable=4_000, benefits="Seguro médico")
    received_offers.save_received_offer(session, job.id, data)

    view = received_offers.agent_view(session, job.id)
    assert view.amounts_private is True
    assert view.base_salary is None and view.variable is None and view.currency is None
    assert view.benefits == "Seguro médico"

    received_offers.save_received_offer(
        session, job.id, data.model_copy(update={"amounts_private": False})
    )
    shown = received_offers.agent_view(session, job.id)
    assert shown.base_salary == 45_000 and shown.variable == 4_000 and shown.period == "year"


def test_agent_view_without_data_is_not_found(session: Session) -> None:
    job = add_applied_job(session, "Brétema Analytics")
    with pytest.raises(ReceivedOfferNotFoundError):
        received_offers.agent_view(session, job.id)
    with pytest.raises(events.JobNotFoundError):
        received_offers.agent_view(session, 999)


def test_compare_against_floor_and_published_range(session: Session) -> None:
    _profile(session)
    job = add_applied_job(session, "Brétema Analytics")
    _published(session, job, min=40_000, max=48_000, currency="EUR", period="year")
    received_offers.save_received_offer(
        session, job.id, ReceivedOfferFields(base_salary=45_000, variable=3_000)
    )

    view = received_offers.compare(session)

    assert view.floor_eur == FLOOR
    [offer] = view.offers
    assert offer.company == "Brétema Analytics" and offer.stage == "in_process"
    assert (offer.annual_base, offer.annual_total) == (45_000, 48_000)
    assert (offer.floor_diff_base, offer.floor_diff_total) == (4_000, 7_000)
    assert (offer.published_diff_min, offer.published_diff_max) == (5_000, -3_000)
    assert offer.remarks == [] and offer.approximate is False


def test_compare_monthly_amounts_are_approximate(session: Session) -> None:
    _profile(session)
    job = add_applied_job(session, "Brétema Analytics")
    _published(session, job, min=3_000, max=3_500, currency="EUR", period="month")
    received_offers.save_received_offer(
        session, job.id, ReceivedOfferFields(base_salary=3_200, period="month")
    )
    [offer] = received_offers.compare(session).offers
    assert offer.annual_base == 38_400 and offer.approximate
    assert offer.floor_diff_base == 38_400 - FLOOR
    assert (offer.published_annual_min, offer.published_annual_max) == (36_000, 42_000)
    assert any("×12" in r for r in offer.remarks)


def test_compare_skips_what_is_not_comparable(session: Session) -> None:
    job = add_applied_job(session, "Brétema Analytics")
    _published(session, job, min=60_000, max=70_000, currency="USD", period="year")
    received_offers.save_received_offer(
        session, job.id, ReceivedOfferFields(base_salary=50_000, currency="GBP")
    )
    view = received_offers.compare(session)
    [offer] = view.offers
    assert view.floor_eur is None
    assert offer.floor_diff_base is None and offer.published_diff_min is None
    assert len(offer.remarks) == 2

    _profile(session)
    [offer] = received_offers.compare(session).offers
    assert offer.floor_diff_base is None
    assert any("euros" in r for r in offer.remarks)


@pytest.mark.parametrize("floor", [None, "cuarenta mil", True, -5])
def test_invalid_floor_is_ignored(session: Session, floor: object) -> None:
    _profile(session, floor)
    assert received_offers.compare(session).floor_eur is None


def test_compare_orders_by_respond_by(session: Session) -> None:
    from datetime import date

    first = add_applied_job(session, "Brétema Analytics")
    second = add_applied_job(session, "Néboa Data")
    third = add_applied_job(session, "Ardora Labs")
    received_offers.save_received_offer(session, first.id, ReceivedOfferFields())
    received_offers.save_received_offer(
        session, second.id, ReceivedOfferFields(respond_by=date(2026, 10, 20))
    )
    received_offers.save_received_offer(
        session, third.id, ReceivedOfferFields(respond_by=date(2026, 10, 15))
    )
    jobs = [o.job_id for o in received_offers.compare(session).offers]
    assert jobs == [third.id, second.id, first.id]


def test_delete_keeps_the_event(session: Session) -> None:
    job = add_applied_job(session, "Brétema Analytics")
    received_offers.save_received_offer(session, job.id, ReceivedOfferFields(base_salary=1))
    received_offers.delete_received_offer(session, job.id)
    assert received_offers.get_received_offer(session, job.id) is None
    assert "offer_received" in _types(session, job.id)
    with pytest.raises(ReceivedOfferNotFoundError):
        received_offers.delete_received_offer(session, job.id)


def test_variable_is_annual_and_needs_a_base_for_the_total(session: Session) -> None:
    _profile(session)
    job = add_applied_job(session, "Brétema Analytics")
    received_offers.save_received_offer(
        session, job.id, ReceivedOfferFields(base_salary=3_000, variable=5_000, period="month")
    )
    [offer] = received_offers.compare(session).offers
    assert (offer.annual_base, offer.annual_total) == (36_000, 41_000)

    received_offers.save_received_offer(session, job.id, ReceivedOfferFields(variable=5_000))
    [offer] = received_offers.compare(session).offers
    assert offer.annual_total is None and offer.floor_diff_total is None
    assert any("no hay total" in r for r in offer.remarks)


@pytest.mark.parametrize(
    ("salary", "remark"),
    [
        ({"min": 40_000, "max": 50_000, "currency": None, "period": "year"}, "no indica moneda"),
        ({"min": 40_000, "max": 50_000, "currency": "EUR", "period": None}, "no indica periodo"),
        ({"min": 50_000, "max": 40_000, "currency": "EUR", "period": "year"}, "no indica salario"),
    ],
)
def test_published_range_that_cannot_be_compared_says_why(
    session: Session, salary: dict, remark: str
) -> None:
    job = add_applied_job(session, "Brétema Analytics")
    _published(session, job, **salary)  # el último es inválido (min > max): no rompe la tabla
    received_offers.save_received_offer(session, job.id, ReceivedOfferFields(base_salary=45_000))
    [offer] = received_offers.compare(session).offers
    assert offer.published_diff_min is None
    assert any(remark in r for r in offer.remarks)


def test_privacy_change_and_recreate_leave_no_figures_nor_duplicates(session: Session) -> None:
    job = add_applied_job(session, "Brétema Analytics")
    data = ReceivedOfferFields(base_salary=45_000)
    received_offers.save_received_offer(session, job.id, data)
    received_offers.save_received_offer(
        session, job.id, data.model_copy(update={"amounts_private": False})
    )
    assert _notes(session, job.id) == ["Oferta recibida actualizada (privacidad de los importes)."]
    received_offers.delete_received_offer(session, job.id)
    received_offers.save_received_offer(session, job.id, data)
    assert _types(session, job.id).count("offer_received") == 1
    assert not [n for n in _notes(session, job.id) if "45" in n]
