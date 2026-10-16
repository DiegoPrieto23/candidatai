"""Recruitee Careers Site API: `GET {empresa}.recruitee.com/api/offers/`.

Pública y sin autenticación (la API del ATS, con token, es otra). Trae todas las ofertas
publicadas de una vez, con la descripción y los requisitos en HTML. Responde 404 si la empresa no
existe. Documentación: https://docs.recruitee.com/reference/offers
"""

from datetime import datetime
from typing import Any

import httpx

from app.schemas.sources import AtsConfig, SourceConfig
from app.services.ingestion.base import (
    FetchResult,
    RawJob,
    get_json,
    html_fragment_to_text,
    join_text,
    looks_remote,
    optional_str,
    parse_datetime,
    parse_items,
    require_str,
    require_url,
    unexpected,
)

API = "https://{slug}.recruitee.com/api/offers/"


def _date(value: Any) -> datetime | None:
    """Recruitee da las fechas como `2026-10-15 09:31:36 UTC`."""
    if isinstance(value, str) and value.endswith(" UTC"):
        value = value[: -len(" UTC")] + "+00:00"
    return parse_datetime(value)


class RecruiteeConnector:
    kind = "recruitee"
    label = "Recruitee"

    def fetch(self, name: str, config: SourceConfig, client: httpx.Client) -> FetchResult:
        assert isinstance(config, AtsConfig)
        data = get_json(
            client,
            API.format(slug=config.slug),
            label=self.label,
            not_found=(
                f"No existe la empresa «{config.slug}» en Recruitee (404). Revisa el slug: es lo "
                "que va antes de `.recruitee.com`."
            ),
        )
        if not isinstance(data, dict) or not isinstance(data.get("offers"), list):
            raise unexpected(self.label, "falta la lista `offers`")

        def parse(item: dict[str, Any]) -> RawJob | None:
            if item.get("status") not in (None, "published"):
                return None
            parts = [
                (heading, item[key])
                for key, heading in (("description", None), ("requirements", "Requisitos"))
                if isinstance(item.get(key), str) and item[key].strip()
            ]
            location = optional_str(item.get("location"))
            return RawJob(
                external_id=require_str(item, "id"),
                title=require_str(item, "title"),
                company=name,
                url=require_url(item, "careers_url"),
                location=location,
                text=join_text(*(join_text(h, html_fragment_to_text(v)) for h, v in parts)),
                html="".join(f"<h3>{h}</h3>{v}" if h else v for h, v in parts) or None,
                posted_at=_date(item.get("published_at") or item.get("created_at")),
                remote=True if item.get("remote") is True else looks_remote(location),
            )

        return parse_items(data["offers"], self.label, parse)

    def complete(self, job: RawJob, client: httpx.Client) -> RawJob:
        return job
