"""Adzuna API (opcional): `GET api.adzuna.com/v1/api/jobs/{country}/search/{page}`.

Necesita `JH_ADZUNA_APP_ID` y `JH_ADZUNA_APP_KEY` en `.env` (registro en developer.adzuna.com).
Adzuna solo da un extracto de la descripción: la oferta entra con ese extracto y la extracción
saldrá más pobre (en la fase 09b podrá entrar como oferta «resumen» y completarse).
Documentación: https://developer.adzuna.com/docs/search
"""

from typing import Any

import httpx

from app.core.config import get_settings
from app.schemas.sources import AdzunaConfig, SourceConfig
from app.services.ingestion.base import (
    FetchResult,
    MissingKeysError,
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

API = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
PAGE_SIZE = 50
MAX_PAGES = 4


def _keys() -> dict[str, str]:
    settings = get_settings()
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        raise MissingKeysError(
            "Adzuna necesita JH_ADZUNA_APP_ID y JH_ADZUNA_APP_KEY en `.env` "
            "(se registran en developer.adzuna.com)."
        )
    return {"app_id": settings.adzuna_app_id, "app_key": settings.adzuna_app_key}


def _name(field: Any) -> str | None:
    return optional_str(field.get("display_name")) if isinstance(field, dict) else None


class AdzunaConnector:
    kind = "adzuna"
    label = "Adzuna"

    def fetch(self, name: str, config: SourceConfig, client: httpx.Client) -> FetchResult:
        assert isinstance(config, AdzunaConfig)
        params: dict[str, Any] = _keys() | {
            "what": config.query,
            "results_per_page": PAGE_SIZE,
            "max_days_old": config.max_days_old,
            "content-type": "application/json",
        }
        if config.where:
            params["where"] = config.where
        result = FetchResult()
        for page in range(1, MAX_PAGES + 1):
            data = get_json(
                client,
                API.format(country=config.country, page=page),
                params=params,
                label=self.label,
                not_found=f"Adzuna no tiene el país «{config.country}» (404).",
            )
            if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                raise unexpected(self.label, "falta la lista `results`")
            chunk = parse_items(data["results"], self.label, self._parse)
            result.jobs.extend(chunk.jobs)
            result.issues.extend(chunk.issues)
            count = data.get("count")
            if len(data["results"]) < PAGE_SIZE or not isinstance(count, int):
                break
            if page * PAGE_SIZE >= count:
                break
        return result

    def _parse(self, item: dict[str, Any]) -> RawJob:
        company = _name(item.get("company"))
        if not company:
            raise ValueError("sin empresa (`company.display_name`)")
        location = _name(item.get("location"))
        description = item.get("description") if isinstance(item.get("description"), str) else ""
        return RawJob(
            external_id=require_str(item, "id"),
            title=html_fragment_to_text(require_str(item, "title")),  # trae <strong> en la búsqueda
            company=company,
            url=require_url(item, "redirect_url"),
            location=location,
            text=html_fragment_to_text(description),
            html=description or None,
            posted_at=parse_datetime(item.get("created")),
            remote=looks_remote(location),
        )

    def complete(self, job: RawJob, client: httpx.Client) -> RawJob:
        return job
