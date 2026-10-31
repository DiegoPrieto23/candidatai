"""Títulos para `broaden-search` (`services/search_titles.py`)."""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models import Job
from app.models.base import utcnow
from app.services import events, ingest, profile, search_titles

TEXT = "Buscamos perfil de datos con Python y SQL para el equipo. " * 10


def _job(session: Session, title: str, company: str = "Acme Datos", location: str = "Vigo") -> int:
    return ingest.add_from_text(session, title, company, TEXT, location=location).job_id


def _approve(session: Session, job_id: int) -> None:
    events.record(session, job_id, "extracted", "agent")
    events.record(session, job_id, "approved", "user")


def _discard(session: Session, job_id: int, reason: str) -> None:
    events.add_user_event(
        session, job_id, "discarded", reason=reason, note="x" if reason == "other" else None
    )


def test_groups_positive_and_negative_by_last_decision(session: Session) -> None:
    profile.import_profile(session, profile.EXAMPLE_PATH)
    a = _job(session, "Data Engineer")
    b = _job(session, "Ingeniero de datos (m/f)", company="Otra")
    c = _job(session, "BI Engineer", company="Tercera")
    d = _job(session, "Sales Executive", company="Cuarta")
    e = _job(session, "Data Analyst", company="Quinta")
    gone = _job(session, "Analytics Engineer", company="Sexta")
    changed = _job(session, "Data Scientist", company="Séptima")
    for job_id in (a, b, c, changed):
        _approve(session, job_id)
    _discard(session, d, "skills")
    _discard(session, e, "salary")
    _discard(session, gone, "closed")  # cerrada: no dice nada del puesto
    _discard(session, changed, "company")  # aprobada y luego descartada: cuenta como negativa

    view = search_titles.search_titles(session)
    assert view.roles  # los del perfil de demo
    positive = {g.key: g for g in view.positive}
    assert positive["data engineer"].count == 2
    assert set(positive["data engineer"].job_ids) == {a, b}
    assert positive["data engineer"].title in {"Data Engineer", "Ingeniero de datos (m/f)"}
    assert "bi engineer" in positive
    negative = {g.key: g for g in view.negative}
    assert negative["sales executive"].reasons == {"skills": 1}
    assert negative["data scientist"].reasons == {"company": 1}
    assert "analytics engineer" not in negative and "analytics engineer" not in positive
    assert all(g.reasons == {} for g in view.positive)
    assert view.profile_missing is False
    assert positive["data engineer"].matches_roles is True


def test_matches_roles_flags_titles_the_prefilter_drops(session: Session) -> None:
    profile.import_profile(session, profile.EXAMPLE_PATH)
    roles = profile.current(session).profile.preferences.roles
    job_id = _job(session, "Ingeniero de Telecomunicaciones")
    _approve(session, job_id)
    [group] = search_titles.search_titles(session).positive
    assert group.matches_roles is False, roles


def test_without_profile_and_old_jobs(session: Session) -> None:
    recent = _job(session, "Data Engineer")
    old = _job(session, "Platform Engineer", company="Antigua")
    _approve(session, recent)
    _approve(session, old)
    job = session.get(Job, old)
    assert job is not None
    job.first_seen_at = utcnow() - timedelta(days=200)
    session.flush()

    view = search_titles.search_titles(session, days=90)
    assert view.profile_missing and view.roles == []
    assert [g.key for g in view.positive] == ["data engineer"]
    assert view.positive[0].matches_roles is None


def test_candidates_say_what_adding_a_role_would_let_in(session: Session) -> None:
    profile.import_profile(session, profile.EXAMPLE_PATH)  # Data Engineer, Analytics…, Data Analyst
    for title, company in (("BI Analyst", "Una"), ("Analista BI", "Dos")):
        _approve(session, _job(session, title, company=company))
    _discard(session, _job(session, "BI Sales Analyst", company="Tres"), "skills")
    _discard(session, _job(session, "Data Analyst Sr", company="Cuatro"), "salary")

    view = search_titles.search_titles(
        session, candidates=["Analista BI", "Senior Data Engineer", " ", "Analista BI"]
    )

    assert view.aliases["data engineer"][0] == "ingeniero de datos"
    bi, senior = view.candidates  # sin vacíos ni repetidos, en su orden
    assert bi.title == "Analista BI" and bi.compared_as == ["analista bi", "bi analyst"]
    assert bi.covered_by == []  # «Data Analyst» pide «data»
    assert len(bi.lets_in) == 1  # un solo grupo: «Analista BI» se lee como «BI Analyst»
    # Lo que colaría: el descartado que hoy no pasa. «Data Analyst Sr» ya pasa: no cuenta.
    assert bi.also_lets_in == ["BI Sales Analyst"]
    assert senior.compared_as == ["data engineer"]
    assert senior.covered_by == ["Data Engineer"] and senior.lets_in == []


def test_candidate_the_prefilter_cannot_read(session: Session) -> None:
    profile.import_profile(session, profile.EXAMPLE_PATH)
    (check,) = search_titles.search_titles(session, candidates=["Senior (m/f/d)"]).candidates
    assert check.compared_as == [] and check.covered_by == [] and check.lets_in == []


def test_candidates_need_a_profile(session: Session) -> None:
    view = search_titles.search_titles(session, candidates=["BI Analyst"])
    assert view.profile_missing and view.candidates == []
