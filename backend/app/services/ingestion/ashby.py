"""Ashby Job Posting API: `GET api.ashbyhq.com/posting-api/job-board/{job_board_name}`.

Pública y sin autenticación. La documentación no garantiza un `id` por oferta: se usa si viene y,
si no, el último tramo de `jobUrl`. Las ofertas con `isListed: false` se ignoran. Documentación:
https://developers.ashbyhq.com/docs/public-job-posting-api
"""

from typing import Any
from urllib.parse import urlsplit

import httpx

from app.schemas.sources import AtsConfig, SourceConfig
from app.services.ingestion.base import (
    FetchResult,
    RawJob,
    get_json,
    html_fragment_to_text,
    optional_str,
    parse_datetime,
    parse_items,
    require_str,
    require_url,
    unexpected,
)

API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def _external_id(item: dict[str, Any], url: str) -> str:
    if isinstance(item.get("id"), str) and item["id"].strip():
        return item["id"].strip()
    tail = urlsplit(url).path.rstrip("/").rsplit("/", 1)[-1]
    if not tail:
        raise ValueError("sin `id` ni `jobUrl` con identificador")
    return tail


class AshbyConnector:
    kind = "ashby"
    label = "Ashby"

    def fetch(self, name: str, config: SourceConfig, client: httpx.Client) -> FetchResult:
        assert isinstance(config, AtsConfig)
        data = get_json(
            client,
            API.format(slug=config.slug),
            label=self.label,
            not_found=f"No existe el tablero «{config.slug}» en Ashby (404). Revisa el nombre.",
        )
        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            raise unexpected(self.label, "falta la lista `jobs`")

        def parse(item: dict[str, Any]) -> RawJob | None:
            if item.get("isListed") is False:
                return None
            url = require_url(item, "jobUrl")
            description = item.get("descriptionHtml")
            html = description if isinstance(description, str) else ""
            workplace = (optional_str(item.get("workplaceType")) or "").lower()
            return RawJob(
                external_id=_external_id(item, url),
                title=require_str(item, "title"),
                company=name,
                url=url,
                location=optional_str(item.get("location")),
                text=optional_str(item.get("descriptionPlain")) or html_fragment_to_text(html),
                html=html or None,
                posted_at=parse_datetime(item.get("publishedAt")),
                remote=True if item.get("isRemote") is True or workplace == "remote" else None,
            )

        return parse_items(data["jobs"], self.label, parse)

    def complete(self, job: RawJob, client: httpx.Client) -> RawJob:
        return job
