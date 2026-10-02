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
