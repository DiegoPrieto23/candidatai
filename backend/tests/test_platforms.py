"""Identidad por plataforma a partir de la URL. URLs inventadas con la forma de las reales."""

import pytest

from app.services.platforms import PlatformId, can_fetch, canonical_url, detect, platform_of_host


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.linkedin.com/jobs/view/4012345678/", ("linkedin", "4012345678")),
        ("https://es.linkedin.com/jobs/view/4012345678", ("linkedin", "4012345678")),
        (
            "https://www.linkedin.com/jobs/view/data-engineer-at-acme-demo-4012345678?trk=x",
            ("linkedin", "4012345678"),
        ),
        (
            "https://www.linkedin.com/comm/jobs/view/4012345678/?trackingId=abc%3D%3D&refId=1",
            ("linkedin", "4012345678"),
        ),
        (
            "https://www.linkedin.com/jobs/search/?currentJobId=4012345678&keywords=data",
            ("linkedin", "4012345678"),
        ),
        (
            "https://www.infojobs.net/vigo/data-engineer/of-i0123456789abcdef0123456789abcd",
            ("infojobs", "0123456789abcdef0123456789abcd"),
        ),
        (
            "https://www.infojobs.net/vigo/data-engineer/of-i0123456789ABCDEF0123456789ABCD?applicationOrigin=x",
            ("infojobs", "0123456789abcdef0123456789abcd"),
        ),
        ("https://es.indeed.com/viewjob?jk=0123456789abcdef", ("indeed", "0123456789abcdef")),
        (
            "https://es.indeed.com/rc/clk?jk=0123456789abcdef&from=ja",
            ("indeed", "0123456789abcdef"),
        ),
        ("https://www.indeed.es/jobs?q=data&vjk=0123456789abcdef", ("indeed", "0123456789abcdef")),
        ("https://uk.indeed.co.uk/viewjob?jk=0123456789abcdef", ("indeed", "0123456789abcdef")),
        (
            "https://www.tecnoempleo.com/data-engineer-vigo/python-sql/rf-0123456789abcdef0123",
            ("tecnoempleo", "0123456789abcdef0123"),
        ),
    ],
)
def test_detect(url: str, expected: tuple[str, str]) -> None:
    assert detect(url) == PlatformId(*expected)


@pytest.mark.parametrize(
    "url",
    [
        None,
        "",
        "no es una url",
        "ftp://www.linkedin.com/jobs/view/4012345678/",
        "https://www.linkedin.com/jobs/search/?keywords=data",
        "https://www.linkedin.com/jobs/search/?currentJobId=abc",
        "https://www.linkedin.com/in/alguien/",
        "https://linkedin.com.evil.example/jobs/view/4012345678/",
        "https://www.infojobs.net/ofertas-trabajo/data-engineer",
        "https://es.indeed.com/viewjob?jk=nohex",
        "https://indeed.evil.example/viewjob?jk=0123456789abcdef",
        "https://www.tecnoempleo.com/ofertas-trabajo/programador",
        "https://boards.greenhouse.io/acme/jobs/123456",
    ],
)
def test_detect_rejects(url: str | None) -> None:
    assert detect(url) is None


def test_platform_of_host() -> None:
    assert platform_of_host("es.linkedin.com") == "linkedin"
    assert platform_of_host("mail.infojobs.net") == "infojobs"
    assert platform_of_host("notlinkedin.com") is None
    assert platform_of_host(None) is None


def test_can_fetch_never_linkedin() -> None:
    assert not can_fetch("linkedin")
    assert can_fetch("infojobs") and can_fetch(None)


def test_canonical_url() -> None:
    assert (
        canonical_url(PlatformId("linkedin", "4012345678"))
        == "https://www.linkedin.com/jobs/view/4012345678/"
    )
    assert canonical_url(PlatformId("infojobs", "x")) is None
