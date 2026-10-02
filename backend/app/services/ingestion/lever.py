"""Lever Postings API: `GET api.lever.co/v0/postings/{site}?mode=json`
(en la UE, `api.eu.lever.co`).

Pública y sin autenticación; solo devuelve las ofertas publicadas. Documentación:
https://github.com/lever/postings-api
"""

from typing import Any

import httpx

from app.schemas.sources import AtsConfig, SourceConfig
from app.services.ingestion.base import (
    FetchResult,
    RawJob,
    get_json,
    html_fragment_to_text,
    join_text,
    optional_str,
    parse_datetime,
    parse_items,
    require_str,
    require_url,
    unexpected,
)

API = {
    "global": "https://api.lever.co/v0/postings/{slug}",
    "eu": "https://api.eu.lever.co/v0/postings/{slug}",
}


def _lists(item: dict[str, Any]) -> tuple[str, str]:
    """Secciones extra («Requirements»…): texto plano y HTML (para la detección de riesgo)."""
    texts, htmls = [], []
    for section in item.get("lists") or []:
        if not isinstance(section, dict):
            continue
        heading = optional_str(section.get("text")) or ""
        content = section.get("content") if isinstance(section.get("content"), str) else ""
        texts.append(join_text(heading, html_fragment_to_text(content)))
        htmls.append(f"<h3>{heading}</h3>{content}")
    return "\n\n".join(texts), "".join(htmls)


class LeverConnector:
    kind = "lever"
    label = "Lever"

    def fetch(self, name: str, config: SourceConfig, client: httpx.Client) -> FetchResult:
        assert isinstance(config, AtsConfig)
        data = get_json(
            client,
            API[config.region].format(slug=config.slug),
            params={"mode": "json"},
            label=self.label,
            not_found=(
                f"No existe la empresa «{config.slug}» en Lever (404). Revisa el slug o prueba "
                "la región `eu`."
            ),
        )
        if not isinstance(data, list):
            raise unexpected(self.label, "se esperaba una lista de ofertas")

        def parse(item: dict[str, Any]) -> RawJob:
            categories = item.get("categories")
            location = (
                optional_str(categories.get("location")) if isinstance(categories, dict) else None
            )
            lists_text, lists_html = _lists(item)
            html_parts = (item.get("description"), lists_html, item.get("additional"))
            return RawJob(
                external_id=require_str(item, "id"),
                title=require_str(item, "text"),
                company=name,
                url=require_url(item, "hostedUrl"),
                location=location,
                text=join_text(
                    optional_str(item.get("descriptionPlain")),
                    lists_text,
                    optional_str(item.get("additionalPlain")),
                ),
                html="".join(v for v in html_parts if isinstance(v, str)) or None,
                posted_at=parse_datetime(item.get("createdAt")),
                remote=True if item.get("workplaceType") == "remote" else None,
            )

        return parse_items(data, self.label, parse)

    def complete(self, job: RawJob, client: httpx.Client) -> RawJob:
        return job
