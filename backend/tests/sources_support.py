"""Respuestas grabadas (inventadas) de los conectores y ayudas para mockearlas con respx."""

import json
from pathlib import Path
from typing import Any

import httpx
import respx

FIXTURES = Path(__file__).parent / "fixtures" / "connectors"

GREENHOUSE_URL = "https://boards-api.greenhouse.io/v1/boards/acmedatos/jobs"
LEVER_URL = "https://api.lever.co/v0/postings/acmedatos"
LEVER_EU_URL = "https://api.eu.lever.co/v0/postings/acmedatos"
ASHBY_URL = "https://api.ashbyhq.com/posting-api/job-board/acmedatos"
INFOJOBS_SEARCH_URL = "https://api.infojobs.net/api/9/offer"
INFOJOBS_DETAIL_URL = "https://api.infojobs.net/api/7/offer/ab12cd34ef56ab12cd34ef56ab12cd"
ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/es/search/1"


def load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def mock_greenhouse(data: Any = None, status: int = 200) -> respx.Route:
    return respx.get(GREENHOUSE_URL).mock(
        return_value=httpx.Response(
            status, json=load("greenhouse_jobs.json") if data is None else data
        )
    )


def mock_lever(data: Any = None, status: int = 200, url: str = LEVER_URL) -> respx.Route:
    return respx.get(url).mock(
        return_value=httpx.Response(
            status, json=load("lever_postings.json") if data is None else data
        )
    )


def mock_ashby(data: Any = None, status: int = 200) -> respx.Route:
    return respx.get(ASHBY_URL).mock(
        return_value=httpx.Response(status, json=load("ashby_board.json") if data is None else data)
    )


# --- Fase 25.1: forma de respuestas reales grabadas el 2026-10-16, con contenido inventado ------

PERSONIO_URL = "https://acmedatos.jobs.personio.de/xml"
TEAMTAILOR_URL = "https://acmedatos.teamtailor.com/jobs.rss"
WORKABLE_URL = "https://apply.workable.com/api/v1/widget/accounts/acmedatos"
WORKABLE_JOB_URL = "https://apply.workable.com/api/v2/accounts/acmedatos/jobs/186545F8C1"
SMARTRECRUITERS_URL = "https://api.smartrecruiters.com/v1/companies/acmedatos/postings"
SMARTRECRUITERS_JOB_URL = f"{SMARTRECRUITERS_URL}/744000156074001"
RECRUITEE_URL = "https://acmedatos.recruitee.com/api/offers/"
MANFRED_URL = "https://www.getmanfred.com/api/v2/public/offers"
MANFRED_JOB_URL = f"{MANFRED_URL}/8510"
FREEHIRE_URL = "https://freehire.me/api/v1/agent/jobs/search"


def load_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def mock_personio(name: str = "personio_feed.xml", status: int = 200) -> respx.Route:
    return respx.get(PERSONIO_URL).mock(
        return_value=httpx.Response(
            status, text=load_text(name), headers={"Content-Type": "text/xml"}
        )
    )


def mock_teamtailor(status: int = 200) -> respx.Route:
    return respx.get(TEAMTAILOR_URL).mock(
        return_value=httpx.Response(
            status,
            text=load_text("teamtailor_jobs.rss"),
            headers={"Content-Type": "application/rss+xml"},
        )
    )


def mock_smartrecruiters() -> respx.Route:
    """Dos páginas de dos ofertas (con `PAGE_SIZE` a 2 en el test) y el detalle de cualquiera."""
    pages = {
        "0": load("smartrecruiters_postings_1.json"),
        "2": load("smartrecruiters_postings_2.json"),
    }

    def page(request: httpx.Request) -> httpx.Response:
        offset = request.url.params.get("offset", "0")
        empty = {"offset": int(offset), "limit": 2, "totalFound": 4, "content": []}
        return httpx.Response(200, json=pages.get(offset, empty))

    def detail(request: httpx.Request) -> httpx.Response:
        data = load("smartrecruiters_posting.json")
        data["id"] = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=data)

    respx.get(url__regex=rf"^{SMARTRECRUITERS_URL}/\d+$").mock(side_effect=detail)
    return respx.get(SMARTRECRUITERS_URL).mock(side_effect=page)
