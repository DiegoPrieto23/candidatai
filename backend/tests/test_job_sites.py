"""Fase 48.4: en qué web se abre una oferta, por el dominio de su URL (sin visitar nada)."""

import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.core import migrations
from app.core.db import session_scope
from app.models import Company, Job, Source
from app.services.job_sites import site_of


@pytest.mark.parametrize(
    ("url", "kind", "name", "host"),
    [
        ("https://www.linkedin.com/jobs/view/1234567/", "portal", "LinkedIn", "linkedin.com"),
        ("https://lnkd.in/abc", "portal", "LinkedIn", "lnkd.in"),
        ("https://www.infojobs.net/madrid/data/of-i0123", "portal", "InfoJobs", "infojobs.net"),
        ("https://es.indeed.com/viewjob?jk=1", "portal", "Indeed", "es.indeed.com"),
        ("https://www.tecnoempleo.com/x/rf-0123456789", "portal", "Tecnoempleo", "tecnoempleo.com"),
        ("https://www.getmanfred.com/ofertas-empleo/1", "portal", "Manfred", "getmanfred.com"),
        (
            "https://job-boards.greenhouse.io/acme/jobs/1",
            "ats",
            "Greenhouse",
            "job-boards.greenhouse.io",
        ),
        ("https://jobs.lever.co/acme/9", "ats", "Lever", "jobs.lever.co"),
        ("https://jobs.ashbyhq.com/acme/1", "ats", "Ashby", "jobs.ashbyhq.com"),
        ("https://acme.wd3.myworkdayjobs.com/x", "ats", "Workday", "acme.wd3.myworkdayjobs.com"),
        ("https://www.acme.com/careers/42", "web", None, "acme.com"),
        # Un dominio que acaba igual no es el portal.
        ("https://notlinkedin.com/jobs", "web", None, "notlinkedin.com"),
        ("https://linkedin.com.example.org/x", "web", None, "linkedin.com.example.org"),
        ("HTTPS://WWW.LinkedIn.COM/jobs/view/1", "portal", "LinkedIn", "linkedin.com"),
    ],
)
def test_site_of_known_and_unknown_webs(url: str, kind: str, name: str | None, host: str) -> None:
    site = site_of(url)
    assert site is not None
    assert (site.kind, site.name, site.host) == (kind, name, host)


@pytest.mark.parametrize(
    "url", [None, "", "nada", "ftp://acme.com/x", "javascript:alert(1)", "https://"]
)
def test_no_site_without_an_http_url(url: str | None) -> None:
    assert site_of(url) is None


@pytest.mark.parametrize(
    ("url", "kind", "host"),
    [
        ("https://user:pw@www.linkedin.com:443/x", "portal", "linkedin.com"),
        ("https://linkedin.com@evil.example/", "web", "evil.example"),  # credenciales, no el host
        ("https://www.linkedin.com./a", "portal", "linkedin.com"),
        ("http://192.168.1.10:8080/oferta", "web", "192.168.1.10"),
        ("https://lınkedin.com/jobs", "web", "xn--lnkedin-rfb.com"),  # se ve que no es LinkedIn
    ],
)
def test_odd_urls(url: str, kind: str, host: str) -> None:
    site = site_of(url)
    assert site is not None
    assert (site.kind, site.host) == (kind, host)


@pytest.mark.parametrize("url", ["https://" + "a" * 300 + ".com/x", "https://a b.com/x"])
def test_no_site_for_hosts_that_are_not_server_names(url: str) -> None:
    assert site_of(url) is None


def test_the_job_page_says_where_it_opens() -> None:
    migrations.upgrade()
    with session_scope() as session:
        source = Source(kind="manual", name="m", active=True, config={})
        company = Company(name="Acme", normalized_name="acme")
        session.add_all([source, company])
        session.flush()
        job = Job(
            source_id=source.id,
            company_id=company.id,
            title="Data Engineer",
            url="https://job-boards.greenhouse.io/acme/jobs/1",
            raw_text="x",
            fingerprint="f",
        )
        session.add(job)
        session.flush()
        job_id = job.id
    with TestClient(create_app()) as client:
        body = client.get(f"/jobs/{job_id}").json()
    assert body["site"] == {"kind": "ats", "name": "Greenhouse", "host": "job-boards.greenhouse.io"}
