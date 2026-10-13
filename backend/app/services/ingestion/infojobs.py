"""InfoJobs API (opcional): búsqueda `GET api.infojobs.net/api/9/offer` y detalle
`GET api.infojobs.net/api/7/offer/{id}`.

Necesita las claves de una aplicación de InfoJobs (`CAI_INFOJOBS_CLIENT_ID` y
`CAI_INFOJOBS_CLIENT_SECRET` en `.env`), por autenticación HTTP básica. El listado no trae la
descripción: se pide el detalle solo de las ofertas que pasan el filtro previo y no se tenían.
Documentación: https://developer.infojobs.net/documentation/operation-list/index.xhtml
"""

from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.sources import InfoJobsConfig, SourceConfig
from app.services.ingestion.base import (
    FetchResult,
    MissingKeysError,
    RawJob,
    get_json,
    html_fragment_to_text,
    join_text,
    optional_str,
    parse_datetime,
    parse_items,
    require_str,
    require_url,
    safe_id,
    unexpected,
)

SEARCH_API = "https://api.infojobs.net/api/9/offer"
DETAIL_API = "https://api.infojobs.net/api/7/offer/{id}"
PAGE_SIZE = 50
MAX_PAGES = 4


def _auth() -> tuple[str, str]:
    settings = get_settings()
    if not settings.infojobs_client_id or not settings.infojobs_client_secret:
        raise MissingKeysError(
            "InfoJobs necesita CAI_INFOJOBS_CLIENT_ID y CAI_INFOJOBS_CLIENT_SECRET en `.env` "
            "(se registran en developer.infojobs.net)."
        )
    return settings.infojobs_client_id, settings.infojobs_client_secret


def _value(field: Any) -> str | None:
    """Los diccionarios de InfoJobs llegan como `{id, value}`."""
    return optional_str(field.get("value")) if isinstance(field, dict) else None


def _location(city: str | None, province: str | None) -> str | None:
    if city and province and city.lower() != province.lower():
        return f"{city}, {province}"
    return city or province


class InfoJobsConnector:
    kind = "infojobs"
    label = "InfoJobs"

    def fetch(self, name: str, config: SourceConfig, client: httpx.Client) -> FetchResult:
        assert isinstance(config, InfoJobsConfig)
        auth = _auth()
        params: dict[str, Any] = {
            "q": config.query,
            "maxResults": PAGE_SIZE,
            "sinceDate": config.since,
        }
        if config.province:
            params["province"] = config.province
        result = FetchResult()
        for page in range(1, MAX_PAGES + 1):
            data = get_json(
                client, SEARCH_API, params=params | {"page": page}, auth=auth, label=self.label
            )
            if not isinstance(data, dict) or not isinstance(data.get("offers"), list):
                raise unexpected(self.label, "falta la lista `offers`")
            chunk = parse_items(data["offers"], self.label, self._parse)
            result.jobs.extend(chunk.jobs)
            result.issues.extend(chunk.issues)
            total_pages = data.get("totalPages")
            if not isinstance(total_pages, int) or page >= total_pages:
                break
        return result

    def _parse(self, item: dict[str, Any]) -> RawJob:
        author = item.get("author")
        company = optional_str(author.get("name")) if isinstance(author, dict) else None
        if not company:
            raise ValueError("sin empresa (`author.name`)")
        teleworking = (_value(item.get("teleworking")) or "").lower()
        return RawJob(
            external_id=safe_id(require_str(item, "id")),
            title=require_str(item, "title"),
            company=company,
            url=require_url(item, "link"),
            location=_location(optional_str(item.get("city")), _value(item.get("province"))),
            text=join_text(optional_str(item.get("requirementMin"))),
            posted_at=parse_datetime(item.get("published")),
            remote=True if "solo teletrabajo" in teleworking else None,
            needs_detail=True,
        )

    def complete(self, job: RawJob, client: httpx.Client) -> RawJob:
        data = get_json(
            client,
            DETAIL_API.format(id=job.external_id),
            auth=_auth(),
            label=self.label,
            not_found=f"La oferta {job.external_id} ya no está en InfoJobs (404).",
        )
        if not isinstance(data, dict):
            raise unexpected(self.label, "el detalle de la oferta no es un objeto")
        parts = {
            key: data.get(key) if isinstance(data.get(key), str) else ""
            for key in ("description", "minRequirements", "desiredRequirements")
        }
        job.html = "".join(parts.values()) or None
        job.text = join_text(*(html_fragment_to_text(v) for v in parts.values())) or job.text
        job.needs_detail = False
        return job
