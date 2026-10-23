"""Señales de oferta dudosa (`services/doubtful.py`, fase 25.3): cada una con ofertas inventadas que
la disparan y otras que no, que no cambian el score y el filtro duro opcional."""

from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.models import Company, Job, JobSighting
from app.schemas.llm_io import JobExtraction
from app.services import doubtful, events, ingest
from app.services.extractions import save_extraction
from app.services.matching import scorer
from app.services.matching.hard_filters import evaluate
from app.services.signals import read
from tests.agent_support import extraction
from tests.matching_support import FakeEmbedder, demo_extraction, demo_profile

TEXT = "Buscamos Data Engineer con Python y SQL para el equipo de datos. " * 10


def _ext(**changes: Any) -> JobExtraction:
    return JobExtraction.model_validate(extraction(**changes))


def _salary(lo: int, hi: int) -> dict[str, Any]:
    return {"min": lo, "max": hi, "currency": "EUR", "period": "year"}


# --- salary_range_wide -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("salary", "fires"),
    [
        (_salary(30000, 60000), True),  # +100 %
        (_salary(30000, 48001), True),  # justo por encima del 60 %
        (_salary(30000, 48000), False),  # 60 % exacto: no
        (_salary(40000, 48000), False),
        ({"min": 40000, "max": None, "currency": "EUR", "period": "year"}, False),
        (None, False),
    ],
)
def test_salary_range_wide(salary: dict[str, Any] | None, fires: bool) -> None:
    signal = doubtful.salary_range_wide(_ext(salary=salary))
    assert (signal is not None) == fires
    if signal:
        assert signal.threshold_pct == get_policies().doubtful.salary_range_max_pct


def test_salary_range_threshold_is_configurable(monkeypatch: pytest.MonkeyPatch) -> None:
    policies = get_policies()
    looser = policies.model_copy(
        update={"doubtful": policies.doubtful.model_copy(update={"salary_range_max_pct": 150})}
    )
    monkeypatch.setattr(doubtful, "get_policies", lambda: looser)
    assert doubtful.salary_range_wide(_ext(salary=_salary(30000, 60000))) is None


# --- employer_hidden ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("company", "changes", "reason"),
    [
        ("Hays", {}, "agency"),  # agencia por el nombre
        ("Michael Page International", {}, "agency"),
        ("Talento Norte", {"is_agency": True}, "agency"),  # agencia según la extracción
        ("Talento Norte", {"is_agency": True, "hiring_entity": "Acme Datos"}, "agency_for_client"),
        ("Empresa confidencial", {}, "unnamed"),
        ("Importante empresa del sector", {}, "unnamed"),
        ("Acme Datos", {}, None),
        ("Acme Datos", {"is_agency": False, "hiring_entity": "Acme Datos"}, None),
        ("Haystack Analytics", {}, None),  # «hays» solo como palabra completa
        ("Acme Sociedad Anónima", {}, None),
    ],
)
def test_employer_hidden(company: str, changes: dict[str, Any], reason: str | None) -> None:
    signal = doubtful.employer_hidden(_ext(**changes), company)
    assert (signal.reason if signal else None) == reason
    if reason == "agency_for_client":
        assert signal is not None and signal.client == "Acme Datos"


def test_employer_hidden_without_extraction_uses_the_name() -> None:
    assert doubtful.employer_hidden(None, "Randstad") is not None
    assert doubtful.employer_hidden(None, "Acme Datos") is None


# --- fixed_term y ai_screening -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("contract_type", "fires"),
    [("fixed_term", True), ("permanent", False), ("freelance", False), ("unknown", False)],
)
def test_fixed_term(contract_type: str, fires: bool) -> None:
    assert (doubtful.fixed_term(_ext(contract_type=contract_type)) is not None) == fires


def test_fixed_term_needs_the_new_field() -> None:
    assert doubtful.fixed_term(_ext()) is None  # extracción anterior a la fase
    assert doubtful.fixed_term(None) is None


@pytest.mark.parametrize(
    ("changes", "text", "origin"),
    [
        ({"mentions_ai_screening": True}, TEXT, "extraction"),
        ({}, TEXT + " El primer paso es una entrevista en vídeo grabada con HireVue.", "text"),
        ({}, TEXT + " Tus candidaturas pasarán un AI-powered screening.", "text"),
        ({}, TEXT + " Experiencia en test automático con Selenium.", None),  # QA: una skill
        ({"mentions_ai_screening": False}, TEXT, None),
    ],
)
def test_ai_screening(changes: dict[str, Any], text: str, origin: str | None) -> None:
    signal = doubtful.ai_screening(_ext(**changes), text)
    assert (signal.origin if signal else None) == origin


# --- stale_repost ------------------------------------------------------------------------------


def _infojobs(n: int) -> str:
    return f"https://www.infojobs.net/vigo/data-engineer/of-i{n:030x}"


def _add(session: Session, url: str) -> int:
    return ingest.add_from_text(
        session, "Data Engineer", "Acme Datos", TEXT, url=url, location="Vigo"
    ).job_id


def _age(session: Session, days: int) -> None:
    for sighting in session.scalars(select(JobSighting)):
        sighting.seen_at -= timedelta(days=days)
    session.flush()


def _stale(session: Session, job_id: int) -> Any:
    job = session.get(Job, job_id)
    assert job is not None
    return read(job).stale_repost


def test_stale_repost_by_count(session: Session) -> None:
    first = _add(session, _infojobs(1))
    for n in range(2, 4):
        _age(session, 3)
        _add(session, _infojobs(n))
    assert _stale(session, first) is None  # 3 días: «Republicada ×3», aún no dudosa
    _age(session, 3)
    _add(session, _infojobs(4))
    signal = _stale(session, first)
    assert signal is not None and signal.count == 4 and signal.channel == "infojobs"


def test_stale_repost_by_span_even_outside_the_repost_window(session: Session) -> None:
    first = _add(session, _infojobs(1))
    _age(session, 200)  # fuera de `reposts.window_days`
    _add(session, _infojobs(2))
    job = session.get(Job, first)
    assert job is not None
    assert read(job).reposted is None  # la ventana de 90 días no la ve
    signal = _stale(session, first)
    assert signal is not None and signal.span_days >= 200


def test_one_posting_is_not_stale(session: Session) -> None:
    first = _add(session, _infojobs(1))
    _age(session, 365)  # vista una vez hace un año: no hay historia de republicación
    assert _stale(session, first) is None


# --- Al extraer, recalcular y en `get_match` ---------------------------------------------------


@pytest.fixture
def found_job(session: Session, make_job: Callable[..., Job]) -> Job:
    job = make_job()
    events.record(session, job.id, "found", "system")
    return job


def test_signals_are_computed_on_extraction_and_cleared_when_gone(
    session: Session, found_job: Job
) -> None:
    ext = _ext(salary=_salary(20000, 60000), contract_type="fixed_term", is_agency=True)
    save_extraction(session, found_job.id, ext)
    signals = read(found_job)
    assert doubtful.active_codes(signals) == ["salary_range_wide", "employer_hidden", "fixed_term"]
    texts = {n.code: n.text for n in doubtful.notes(signals)}
    assert "20.000 EUR – 60.000 EUR" in texts["salary_range_wide"]
    assert "no dice para quién" in texts["employer_hidden"]

    found_job.raw_text = TEXT  # el texto no cambia nada
    save_extraction(session, found_job.id, _ext(contract_type="permanent", is_agency=False))
    assert doubtful.active_codes(read(found_job)) == []
    assert read(found_job).model_dump(exclude_none=True) == {}


def test_recompute_all_picks_up_pattern_changes(session: Session, found_job: Job) -> None:
    save_extraction(session, found_job.id, _ext())
    assert doubtful.active_codes(read(found_job)) == []
    company = session.get(Company, found_job.company_id)
    assert company is not None
    company.name = "Empresa confidencial"
    result = doubtful.recompute_all(session)
    assert result.jobs == 1 and result.with_signals == 1
    assert result.counts["employer_hidden"] == 1
    assert doubtful.active_codes(read(found_job)) == ["employer_hidden"]


def test_old_extractions_still_validate_and_dump_the_same() -> None:
    data = extraction()
    assert JobExtraction.model_validate(data).model_dump(mode="json") == data


# --- No cambian el score; filtran solo si lo pides ---------------------------------------------


def test_signals_never_change_the_score() -> None:
    profile = demo_profile()
    policy = get_policies().scoring
    plain = demo_extraction()
    doubtful_ext = demo_extraction(
        contract_type="fixed_term",
        is_agency=True,
        hiring_entity=None,
        mentions_ai_screening=True,
        salary=_salary(20000, 90000),
    )
    assert doubtful.salary_range_wide(doubtful_ext) is not None
    for embedder in (None, FakeEmbedder()):
        before = scorer.score("Data Engineer", plain, profile, policy, embedder)
        after = scorer.score("Data Engineer", doubtful_ext, profile, policy, embedder)
        assert after.score == before.score
        assert (
            after.breakdown.model_dump()["components"]
            == before.breakdown.model_dump()["components"]
        )


def test_signals_are_not_a_hard_filter_unless_you_ask() -> None:
    policy = get_policies().hard_filters
    ext = demo_extraction(contract_type="fixed_term", is_agency=True)
    # Sin los filtros de contrato y tipo de empresa de la fase 27.5 (el perfil demo los trae).
    loose = {"contract_types": [], "employment_types": [], "excluded_employer_kinds": []}
    assert evaluate("Data Engineer", ext, demo_profile(**loose), policy, "Hays").passed

    # Fase 27.5: `fixed_term` es «no acepto contrato temporal», en el filtro `contract`.
    strict = demo_profile(exclude_signals=["fixed_term"], **loose)
    result = evaluate("Data Engineer", ext, strict, policy, "Hays")
    assert [f.filter for f in result.failures] == ["contract"]
    assert "contrato temporal" in result.failures[0].reason

    both = demo_profile(exclude_signals=["employer_hidden", "fixed_term"], **loose)
    failures = evaluate("Data Engineer", ext, both, policy, "Hays").failures
    assert [f.filter for f in failures] == ["signal", "contract"]
    assert "empresa oculta o agencia" in failures[0].reason
    assert evaluate("Data Engineer", demo_extraction(), both, policy, "Acme Datos").passed


def test_exclude_signals_empty_is_not_dumped() -> None:
    assert "exclude_signals" not in demo_profile().model_dump()["preferences"]
    assert demo_profile(exclude_signals=["fixed_term"]).model_dump()["preferences"][
        "exclude_signals"
    ] == ["fixed_term"]


# --- Revisión de la fase: más casos ------------------------------------------------------------


def test_ai_screening_matches_whole_words_only() -> None:
    assert doubtful.ai_screening(_ext(), TEXT + " Thai screening of samples.") is None
    assert doubtful.ai_screening(_ext(), TEXT + " We use HireVue.") is not None


def test_stale_repost_span_counts_one_channel_only(session: Session) -> None:
    # La misma oferta en InfoJobs y, 90 días después, en otro portal no es republicarla.
    first = _add(session, _infojobs(1))
    _age(session, 90)
    _add(session, "https://es.indeed.com/viewjob?jk=0123456789abcdef")
    assert _stale(session, first) is None


def test_recompute_all_without_extraction_and_with_a_broken_one(
    session: Session, make_job: Callable[..., Job]
) -> None:
    from app.models import JobExtraction as JobExtractionRow

    bare = make_job()  # sin extracción: solo el nombre de la empresa
    company = session.get(Company, bare.company_id)
    assert company is not None
    company.name = "Randstad"
    broken = make_job()
    session.add(JobExtractionRow(job_id=broken.id, schema_version=1, data={"nope": True}))
    session.flush()
    result = doubtful.recompute_all(session)
    assert result.jobs == 2 and result.counts["employer_hidden"] == 1
    assert doubtful.active_codes(read(bare)) == ["employer_hidden"]
    assert doubtful.active_codes(read(broken)) == []


def test_cli_signals_recompute(isolated_env: Any) -> None:
    from typer.testing import CliRunner

    from app import cli

    runner = CliRunner()
    assert runner.invoke(cli.app, ["db", "upgrade"]).exit_code == 0
    missing = runner.invoke(cli.app, ["jobs", "signals", "--json"])
    assert missing.exit_code == 1 and "--recompute" in missing.stdout
    done = runner.invoke(cli.app, ["jobs", "signals", "--recompute", "--json"])
    assert done.exit_code == 0, done.output
    assert '"jobs": 0' in done.stdout or '"jobs":0' in done.stdout
    text = runner.invoke(cli.app, ["jobs", "signals", "--recompute"])
    assert "0 ofertas revisadas" in text.stdout
