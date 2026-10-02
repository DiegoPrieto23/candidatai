"""Greenhouse Job Board API:
`GET boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true`.

Pública y sin autenticación. Con `content=true` cada oferta trae la descripción en HTML, escapada
como entidades (`&lt;p&gt;`). Documentación: https://developers.greenhouse.io/job-board.html
"""

from typing import Any

import httpx

from app.schemas.sources import AtsConfig, SourceConfig
from app.services.ingestion.base import (
    FetchResult,
    RawJob,
    get_json,
    html_fragment_to_text,
    looks_remote,
    optional_str,
    parse_datetime,
    parse_items,
    require_str,
    require_url,
    unescape_html,
    unexpected,
)

API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


class GreenhouseConnector:
    kind = "greenhouse"
    label = "Greenhouse"

    def fetch(self, name: str, config: SourceConfig, client: httpx.Client) -> FetchResult:
        assert isinstance(config, AtsConfig)
        data = get_json(
            client,
            API.format(slug=config.slug),
            params={"content": "true"},
            label=self.label,
            not_found=f"No existe el tablero «{config.slug}» en Greenhouse (404). Revisa el slug.",
        )
        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            raise unexpected(self.label, "falta la lista `jobs`")

        def parse(item: dict[str, Any]) -> RawJob:
            location = item.get("location")
            place = optional_str(location.get("name")) if isinstance(location, dict) else None
            content = item.get("content")
            html = unescape_html(content) if isinstance(content, str) else ""
            return RawJob(
                external_id=require_str(item, "id"),
                title=require_str(item, "title"),
                company=name,
                url=require_url(item, "absolute_url"),
                location=place,
                text=html_fragment_to_text(html),
                html=html or None,
                posted_at=parse_datetime(item.get("first_published") or item.get("updated_at")),
                remote=looks_remote(place),
            )

        return parse_items(data["jobs"], self.label, parse)

    def complete(self, job: RawJob, client: httpx.Client) -> RawJob:
        return job
