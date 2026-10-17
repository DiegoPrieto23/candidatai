"""freehire.me: búsqueda `GET freehire.me/api/v1/agent/jobs/search`.

Agregador de ofertas de tecnología con API pública documentada, sin claves. La búsqueda «agent»
trae la descripción completa (HTML). Pagina con `limit` (100 como mucho) y `offset`. La URL base
se puede cambiar con `CAI_FREEHIRE_BASE_URL` (p. ej. una instancia propia). Se busca en el título
(`q_fields=title`) y, si la búsqueda tiene varias palabras, todas tienen que estar (entre
comillas, para freehire). Documentación: https://freehire.me/docs/api
"""

from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.sources import FreehireConfig, SourceConfig
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
    unexpected,
)

PATH = "/agent/jobs/search"
PAGE_SIZE = 100
MAX_PAGES = 5


def search_url() -> str:
    return get_settings().freehire_base_url.rstrip("/") + PATH


def _query(query: str) -> str:
    query = query.strip()
    return f'"{query}"' if " " in query and '"' not in query else query


class FreehireConnector:
    kind = "freehire"
    label = "freehire"

    def fetch(self, name: str, config: SourceConfig, client: httpx.Client) -> FetchResult:
        assert isinstance(config, FreehireConfig)
        params: dict[str, Any] = {
            "q": _query(config.query),
            "q_fields": "title",
            "countries": config.country.upper(),
            "sort": "posted_at",
            "order": "desc",
            "limit": PAGE_SIZE,
        }
        if config.remote_only:
            params["work_mode"] = "remote"
        result = FetchResult()
        for page in range(MAX_PAGES):
            data = get_json(
                client,
                search_url(),
                params=params | {"offset": page * PAGE_SIZE},
                label=self.label,
            )
            if not isinstance(data, dict) or not isinstance(data.get("data"), list):
                raise unexpected(self.label, "falta la lista `data`")
            chunk = parse_items(data["data"], self.label, self._parse)
            result.jobs.extend(chunk.jobs)
            result.issues.extend(chunk.issues)
            meta = data.get("meta")
            total = meta.get("total") if isinstance(meta, dict) else None
            if len(data["data"]) < PAGE_SIZE or not isinstance(total, int):
                break
            if (page + 1) * PAGE_SIZE >= total:
                break
        return result

    def _parse(self, item: dict[str, Any]) -> RawJob | None:
        if item.get("closed_at"):
            return None
        description = item.get("description") if isinstance(item.get("description"), str) else ""
        location = optional_str(item.get("location"))
        return RawJob(
            external_id=require_str(item, "public_slug"),
            title=require_str(item, "title"),
            company=require_str(item, "company"),
            url=require_url(item, "url"),
            location=location,
            text=html_fragment_to_text(description),
            html=description or None,
            posted_at=parse_datetime(item.get("posted_at") or item.get("created_at")),
            remote=True if item.get("work_mode") == "remote" else looks_remote(location),
        )

    def complete(self, job: RawJob, client: httpx.Client) -> RawJob:
        return job
