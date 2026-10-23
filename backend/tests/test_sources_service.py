"""Servicio de fuentes con conector (`ingestion/service.py`): alta, prueba y ejecución."""

import httpx
import pytest
import respx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Company, Event, Job, SourceRun
from app.schemas.sources import SourceInput
from app.services import profile
from app.services.events import current_stage
from app.services.ingestion import service, smartrecruiters
from app.services.pipeline import Stage
from tests.sources_support import (
    GREENHOUSE_URL,
    INFOJOBS_DETAIL_URL,
    INFOJOBS_SEARCH_URL,
    load,
    mock_greenhouse,
    mock_lever,
    mock_personio,
    mock_smartrecruiters,
)

GREENHOUSE = SourceInput(kind="greenhouse", name="Acme Datos", slug="acmedatos")


@pytest.fixture
def with_profile(session: Session) -> None:
    profile.import_profile(session, profile.EXAMPLE_PATH)
    session.flush()


def _count(session: Session, model: type) -> int:
    return session.scalar(select(func.count()).select_from(model)) or 0


# --- Alta ------------------------------------------------------------------------------------


def test_add_source_marks_the_company_as_target(session: Session) -> None:
    view = service.add_source(session, GREENHOUSE)

    assert (view.kind, view.kind_label, view.name, view.active) == (
        "greenhouse",
        "Greenhouse",
        "Acme Datos",
        True,
    )
    assert view.config == {"slug": "acmedatos", "region": "global", "title_keywords": []}
    assert view.last_run is None and view.keys_missing is False
    company = session.scalars(select(Company)).one()
    assert (company.watchlist, company.ats_kind, company.ats_slug) == (
        True,
        "greenhouse",
        "acmedatos",
    )


def test_add_source_twice_is_rejected(session: Session) -> None:
    service.add_source(session, GREENHOUSE)
    with pytest.raises(service.SourceExistsError, match="Ya existe"):
        service.add_source(
            session, GREENHOUSE.model_copy(update={"name": "Otra", "slug": "ACMEDATOS"})
        )
    # Otro ATS con el mismo slug sí es otra fuente.
    service.add_source(session, SourceInput(kind="lever", name="Acme Datos", slug="acmedatos"))


def test_portal_without_keys_is_flagged(session: Session) -> None:
    view = service.add_source(
        session, SourceInput(kind="adzuna", name="Adzuna datos", query="data")
    )
    assert view.keys_missing is True
    assert view.config["country"] == "es"
    # Un portal no marca ninguna empresa como objetivo.
    assert _count(session, Company) == 0


def test_set_active_pauses_the_company_too(session: Session) -> None:
    view = service.add_source(session, GREENHOUSE)
    paused = service.set_active(session, view.id, False)
    assert paused.active is False
    assert session.scalars(select(Company)).one().watchlist is False
    with pytest.raises(service.SourceNotFoundError):
        service.set_active(session, 999, True)


def test_website_given_by_the_user_is_kept_as_its_origin(session: Session) -> None:
    view = service.add_source(
        session, GREENHOUSE.model_copy(update={"website": "Acme-Datos.example/empleo"})
    )
    assert view.config["website"] == "https://acme-datos.example"
    assert view.website == "https://acme-datos.example"

    cleared = service.set_website(session, view.id, None)
    assert "website" not in cleared.config and cleared.website is None
    changed = service.set_website(session, view.id, "https://www.acme.example/")
    assert changed.website == "https://www.acme.example"

    with pytest.raises(ValueError, match="Web no válida"):
        service.set_website(session, view.id, "javascript:alert(1)")
    portal = service.add_source(session, SourceInput(kind="manfred", name="Manfred", query="data"))
    assert portal.website == "https://www.getmanfred.com"
    with pytest.raises(service.NotAConnectorError, match="empresas objetivo"):
        service.set_website(session, portal.id, "acme.example")
    with pytest.raises(ValueError, match="solo se usa en las empresas objetivo"):
        SourceInput(kind="manfred", name="Manfred", query="data", website="acme.example")


@respx.mock
def test_website_comes_from_offers_outside_the_ats(session: Session, with_profile: None) -> None:
    mock_greenhouse()
    source = service.add_source(session, GREENHOUSE)
    service.run_source(session, source.id)
    assert service.get_source(session, source.id).website is None  # ofertas en greenhouse.io

    job = session.scalars(select(Job).order_by(Job.id.desc())).first()
    assert job is not None
    job.url = "https://careers.acme-datos.example/jobs/1001-data-engineer"
    session.flush()
    assert service.get_source(session, source.id).website == "https://careers.acme-datos.example"


# --- Prueba sin guardar ----------------------------------------------------------------------


@respx.mock
def test_preview_counts_found_and_after_filters(session: Session, with_profile: None) -> None:
    mock_greenhouse()
    result = service.preview_source(session, GREENHOUSE)

    assert (result.found, result.after_filters) == (5, 3)
    assert result.message == "5 ofertas encontradas, 3 tras filtros"
    assert result.filters_applied is True
    rejected = {j.title: j.reason for j in result.jobs if not j.passed}
    assert set(rejected) == {"Account Executive", "Data Analyst"}
    assert "Fuera de zona" in (rejected["Data Analyst"] or "")
    assert [i.item for i in result.errors] == ["1005"]
    assert _count(session, Job) == 0  # no guarda nada


@respx.mock
def test_preview_without_profile_does_not_filter(session: Session) -> None:
    mock_greenhouse()
    result = service.preview_source(session, GREENHOUSE)
    assert (result.found, result.after_filters, result.filters_applied) == (5, 5, False)
    assert "sin perfil" in result.message


@respx.mock
def test_preview_reports_a_failing_source(session: Session) -> None:
    respx.get(GREENHOUSE_URL).mock(return_value=httpx.Response(404, json={}))
    result = service.preview_source(session, GREENHOUSE)
    assert result.found == 0
    assert [e.code for e in result.errors] == ["not_found"]
    assert "Revisa el slug" in result.message


# --- Ejecución -------------------------------------------------------------------------------


@respx.mock
def test_run_stores_new_jobs_in_pending_extraction(session: Session, with_profile: None) -> None:
    mock_greenhouse()
    source = service.add_source(session, GREENHOUSE)
    result = service.run_source(session, source.id, actor="system")

    assert (result.found, result.after_filters, result.created, result.existing) == (5, 3, 3, 0)
    assert result.message == (
        "Greenhouse · Acme Datos: 5 ofertas encontradas, 3 tras filtros, 3 nuevas; 1 avisos"
    )
    jobs = session.scalars(select(Job).order_by(Job.id)).all()
    assert [j.external_id for j in jobs] == ["1001", "1002", "1006"]
    assert all(j.source_id == source.id for j in jobs)
    assert all(current_stage(session, j.id) == Stage.PENDING_EXTRACTION for j in jobs)
    found = session.scalars(select(Event).where(Event.type == "found")).first()
    assert found is not None
    assert found.payload == {"source": "greenhouse", "source_id": source.id}
    # La detección de riesgo también corre para los conectores.
    assert "hidden_text" in jobs[2].risk_flags or "injection_phrase" in jobs[2].risk_flags

    run = session.scalars(select(SourceRun)).one()
    assert (run.actor, run.found, run.after_filters, run.created) == ("system", 5, 3, 3)
    assert run.finished_at is not None and run.errors[0]["item"] == "1005"
    view = service.get_source(session, source.id)
    assert view.last_run_at is not None and view.last_run is not None


@respx.mock
def test_running_twice_does_not_duplicate_anything(session: Session, with_profile: None) -> None:
    mock_greenhouse()
    source = service.add_source(session, GREENHOUSE)
    service.run_source(session, source.id)
    jobs, events = _count(session, Job), _count(session, Event)

    again = service.run_source(session, source.id)

    assert (again.created, again.existing) == (0, 3)
    assert "3 ya estaban" in again.message
    assert (_count(session, Job), _count(session, Event)) == (jobs, events)
    assert _count(session, SourceRun) == 2


@respx.mock
def test_job_already_added_by_hand_is_not_duplicated(session: Session, with_profile: None) -> None:
    """La misma oferta dada de alta antes por texto (misma huella) cuenta como ya existente."""
    from app.services import ingest

    ingest.add_from_text(
        session, "Data Engineer", "Acme Datos", "Pegada a mano.", location="Vigo, Spain"
    )
    mock_greenhouse()
    source = service.add_source(session, GREENHOUSE)
    result = service.run_source(session, source.id)
    assert (result.created, result.existing) == (2, 1)


@respx.mock
def test_failing_source_is_recorded_and_does_not_raise(session: Session) -> None:
    respx.get(GREENHOUSE_URL).mock(return_value=httpx.Response(503))
    source = service.add_source(session, GREENHOUSE)
    result = service.run_source(session, source.id)

    assert result.created == 0
    assert [e.code for e in result.errors] == ["http_error"]
    assert "error" in result.message
    assert service.retryable_error(result) is not None
    run = session.scalars(select(SourceRun)).one()
    assert run.errors[0]["code"] == "http_error"


@respx.mock
def test_not_found_is_not_retried(session: Session) -> None:
    respx.get(GREENHOUSE_URL).mock(return_value=httpx.Response(404))
    source = service.add_source(session, GREENHOUSE)
    assert service.retryable_error(service.run_source(session, source.id)) is None


def test_portal_without_keys_is_skipped_without_a_run(session: Session) -> None:
    source = service.add_source(session, SourceInput(kind="infojobs", name="IJ", query="data"))
    result = service.run_source(session, source.id)
    assert result.skipped and "CAI_INFOJOBS_CLIENT_ID" in result.skipped
    assert result.run_id is None and _count(session, SourceRun) == 0
    assert service.retryable_error(result) is None


@respx.mock
def test_infojobs_fetches_detail_only_for_new_jobs_that_pass(
    session: Session, with_profile: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("CAI_INFOJOBS_CLIENT_ID", "id-demo")
    monkeypatch.setenv("CAI_INFOJOBS_CLIENT_SECRET", "secreto-demo")
    get_settings.cache_clear()
    respx.get(INFOJOBS_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=load("infojobs_search.json"))
    )
    detail = respx.get(INFOJOBS_DETAIL_URL).mock(
        return_value=httpx.Response(200, json=load("infojobs_offer.json"))
    )
    source = service.add_source(session, SourceInput(kind="infojobs", name="IJ", query="data"))

    first = service.run_source(session, source.id)
    assert (first.found, first.after_filters, first.created) == (2, 1, 1)
    job = session.get(Job, first.job_ids[0])
    assert job is not None and "Experiencia con dbt." in job.raw_text
    assert job.external_id == "ab12cd34ef56ab12cd34ef56ab12cd"

    service.run_source(session, source.id)
    assert detail.call_count == 1  # la segunda vez ya estaba: no se pide el detalle


@respx.mock
def test_detail_failure_skips_only_that_job(
    session: Session, with_profile: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("CAI_INFOJOBS_CLIENT_ID", "id-demo")
    monkeypatch.setenv("CAI_INFOJOBS_CLIENT_SECRET", "secreto-demo")
    get_settings.cache_clear()
    respx.get(INFOJOBS_SEARCH_URL).mock(
        return_value=httpx.Response(200, json=load("infojobs_search.json"))
    )
    respx.get(INFOJOBS_DETAIL_URL).mock(return_value=httpx.Response(500))
    source = service.add_source(session, SourceInput(kind="infojobs", name="IJ", query="data"))
    result = service.run_source(session, source.id)
    assert result.created == 0
    assert [(e.code, e.item) for e in result.errors] == [
        ("http_error", "ab12cd34ef56ab12cd34ef56ab12cd")
    ]
    assert service.retryable_error(result) is None  # la fuente respondió


@respx.mock
def test_truncates_to_max_jobs_per_source(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.policies import get_policies

    monkeypatch.setattr(get_policies().connectors, "max_jobs_per_source", 2)
    mock_lever()
    source = service.add_source(
        session, SourceInput(kind="lever", name="Acme Datos", slug="acmedatos")
    )
    result = service.run_source(session, source.id)
    assert result.found == 2
    assert "truncated" in [e.code for e in result.errors]


def test_manual_sources_cannot_run(session: Session) -> None:
    from app.services import ingest

    created = ingest.add_from_text(session, "Data Engineer", "Acme", "Texto.")
    job = session.get(Job, created.job_id)
    assert job is not None
    with pytest.raises(service.NotAConnectorError):
        service.run_source(session, job.source_id)
    listed = service.list_sources(session)
    assert [s.kind_label for s in listed.sources] == ["Alta manual por texto"]


@respx.mock
def test_fuzzy_duplicates_across_sources_still_count(session: Session, with_profile: None) -> None:
    """Dentro de una fuente, ids distintos no son duplicados difusos; frente a otra fuente, sí."""
    from app.services import ingest

    ingest.add_from_text(session, "Data Engineer", "Acme Datos", "Pegada.", location="Ourense")
    mock_greenhouse()
    source = service.add_source(session, GREENHOUSE)
    result = service.run_source(session, source.id)
    assert result.created == 3
    # «Data Engineer» y «Senior Data Engineer» de Greenhouse se parecen a la de Ourense.
    assert result.duplicates == 2
    assert "cerradas como duplicadas" in result.message


# --- Robustez (revisión de la fase) ----------------------------------------------------------


@respx.mock
def test_offer_with_a_non_http_url_is_ignored(session: Session, with_profile: None) -> None:
    data = load("greenhouse_jobs.json")
    data["jobs"][0]["absolute_url"] = "javascript:alert(1)"
    mock_greenhouse(data=data)
    source = service.add_source(session, GREENHOUSE)
    result = service.run_source(session, source.id)
    assert ("invalid_item", "1001") in [(e.code, e.item) for e in result.errors]
    assert all(not j.url.startswith("javascript") for j in session.scalars(select(Job)))


@respx.mock
def test_redirects_are_not_followed(session: Session) -> None:
    respx.get(GREENHOUSE_URL).mock(
        return_value=httpx.Response(302, headers={"Location": "https://example.com/"})
    )
    source = service.add_source(session, GREENHOUSE)
    result = service.run_source(session, source.id)
    assert [e.code for e in result.errors] == ["http_error"]
    assert "redirección" in result.errors[0].message


@respx.mock
def test_failed_source_does_not_advance_last_run_at(session: Session) -> None:
    respx.get(GREENHOUSE_URL).mock(return_value=httpx.Response(500))
    source = service.add_source(session, GREENHOUSE)
    service.run_source(session, source.id)
    view = service.get_source(session, source.id)
    assert view.last_run_at is None  # el worker la volverá a encolar al arrancar
    assert view.last_run is not None and view.last_run.errors[0].code == "http_error"


@respx.mock
def test_unexpected_error_is_recorded_without_raising(
    session: Session, with_profile: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import ingest

    def boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("fallo raro")

    monkeypatch.setattr(ingest, "store_job", boom)
    mock_greenhouse()
    source = service.add_source(session, GREENHOUSE)
    result = service.run_source(session, source.id)

    assert result.created == 0
    assert result.errors[-1].code == "internal_error"
    assert "RuntimeError" in result.message
    assert service.retryable_error(result) is None  # encontró ofertas: no se reintenta
    assert session.scalars(select(Job)).all() == []  # el guardado se deshizo entero
    run = session.scalars(select(SourceRun)).one()
    assert run.errors[-1]["code"] == "internal_error"
    assert service.get_source(session, source.id).last_run_at is None


@respx.mock
def test_detail_401_stops_asking_for_more_details(
    session: Session, with_profile: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("CAI_INFOJOBS_CLIENT_ID", "id-demo")
    monkeypatch.setenv("CAI_INFOJOBS_CLIENT_SECRET", "secreto-demo")
    get_settings.cache_clear()
    data = load("infojobs_search.json")
    second = dict(data["offers"][0], id="cd34ef56ab12cd34ef56ab12cd34ef", city="Vigo")
    second["link"] = "https://www.infojobs.net/vigo/data-engineer/of-icd34"
    data["offers"].append(second)
    respx.get(INFOJOBS_SEARCH_URL).mock(return_value=httpx.Response(200, json=data))
    detail = respx.get(INFOJOBS_DETAIL_URL).mock(return_value=httpx.Response(401))
    source = service.add_source(session, SourceInput(kind="infojobs", name="IJ", query="data"))

    result = service.run_source(session, source.id)

    assert detail.call_count == 1  # la segunda oferta ni se pide
    assert [e.code for e in result.errors] == ["unauthorized", "details_skipped"]
    assert result.created == 0


@respx.mock
def test_infojobs_id_with_path_characters_is_rejected(
    session: Session, with_profile: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setenv("CAI_INFOJOBS_CLIENT_ID", "id-demo")
    monkeypatch.setenv("CAI_INFOJOBS_CLIENT_SECRET", "secreto-demo")
    get_settings.cache_clear()
    data = load("infojobs_search.json")
    data["offers"][0]["id"] = "../../candidate"
    respx.get(INFOJOBS_SEARCH_URL).mock(return_value=httpx.Response(200, json=data))
    source = service.add_source(session, SourceInput(kind="infojobs", name="IJ", query="data"))
    result = service.run_source(session, source.id)
    assert ("invalid_item", "../../candidate") in [(e.code, e.item) for e in result.errors]


def test_pausing_one_of_two_sources_keeps_the_company_as_target(session: Session) -> None:
    gh = service.add_source(session, GREENHOUSE)
    service.add_source(session, SourceInput(kind="lever", name="Acme Datos", slug="acmedatos"))
    company = session.scalars(select(Company)).one()
    assert company.ats_kind == "greenhouse"  # la segunda fuente no pisa el ATS

    service.set_active(session, gh.id, False)
    assert company.watchlist is True  # le queda Lever
    lever = service.list_sources(session, "lever").sources[0]
    service.set_active(session, lever.id, False)
    assert company.watchlist is False


def test_invalid_company_name_leaves_nothing(session: Session) -> None:
    from app.models import Source

    with pytest.raises(ValueError, match="no válido"):
        service.add_source(session, SourceInput(kind="greenhouse", name="¿?", slug="x"))
    assert session.scalars(select(Source)).all() == []


# --- Fase 25.1: ATS nuevos de extremo a extremo -------------------------------------------------


@respx.mock
def test_personio_and_smartrecruiters_companies_produce_jobs(
    session: Session, with_profile: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Una empresa en Personio y otra en SmartRecruiters, dadas de alta con el perfil de la demo,
    dejan ofertas nuevas en `pending_extraction`; SmartRecruiters pide el detalle solo de las que
    pasan el filtro previo."""
    monkeypatch.setattr(smartrecruiters, "PAGE_SIZE", 2)
    mock_personio()
    list_route = mock_smartrecruiters()
    personio = service.add_source(
        session, SourceInput(kind="personio", name="Acme Datos", slug="acmedatos")
    )
    smart = service.add_source(
        session, SourceInput(kind="smartrecruiters", name="Beta Datos", slug="acmedatos")
    )
    assert personio.config == {"slug": "acmedatos", "region": "global", "title_keywords": []}

    first = service.run_source(session, personio.id, actor="system")
    second = service.run_source(session, smart.id, actor="system")

    assert (first.found, first.created) == (2, first.after_filters)
    assert first.created >= 1 and first.message.startswith("Personio · Acme Datos: 2 ofertas")
    assert (second.found, second.created) == (3, second.after_filters)
    assert second.created >= 1
    details = [c for c in respx.calls if "/postings/" in c.request.url.path]
    assert len(details) == second.after_filters  # «Office Manager» no pasa: sin detalle
    assert len(list_route.calls) == 2

    jobs = session.scalars(select(Job).order_by(Job.id)).all()
    assert {j.source_id for j in jobs} == {personio.id, smart.id}
    assert all(current_stage(session, j.id) == Stage.PENDING_EXTRACTION for j in jobs)
    for source_id in (personio.id, smart.id):
        texts = [j.raw_text for j in jobs if j.source_id == source_id]
        assert any("pipelines de datos" in t for t in texts)
    companies = {c.name: c for c in session.scalars(select(Company))}
    assert companies["Acme Datos"].ats_kind == "personio" and companies["Acme Datos"].watchlist
    assert companies["Beta Datos"].ats_kind == "smartrecruiters"

    again = service.run_source(session, smart.id)
    assert again.created == 0 and again.existing == second.created


def test_new_kinds_validate_their_fields() -> None:
    with pytest.raises(ValueError, match="slug"):
        SourceInput(kind="workable", name="Acme")
    with pytest.raises(ValueError, match="Personio"):
        SourceInput(kind="recruitee", name="Acme", slug="acme", language="en")
    with pytest.raises(ValueError, match="query"):
        SourceInput(kind="manfred", name="Manfred")
    config = SourceInput(kind="freehire", name="freehire", query=" python ", remote_only=True)
    assert config.to_config().model_dump() == {
        "query": "python",
        "country": "es",
        "remote_only": True,
        "title_keywords": [],
    }
    personio = SourceInput(kind="personio", name="Acme", slug="acme", language="en")
    assert personio.to_config().language == "en"  # type: ignore[union-attr]


def test_same_portal_search_with_another_option_is_another_source(session: Session) -> None:
    service.add_source(session, SourceInput(kind="manfred", name="Manfred", query="python"))
    service.add_source(
        session, SourceInput(kind="manfred", name="Manfred EN", query="python", lang="EN")
    )
    with pytest.raises(service.SourceExistsError):
        service.add_source(session, SourceInput(kind="manfred", name="Otra", query="Python"))


def test_options_of_another_kind_are_rejected() -> None:
    with pytest.raises(ValueError, match="Manfred"):
        SourceInput(kind="freehire", name="x", query="python", lang="EN")
    with pytest.raises(ValueError, match="freehire"):
        SourceInput(kind="greenhouse", name="Acme", slug="acme", remote_only=True)
