"""Workable: listado `GET apply.workable.com/api/v1/widget/accounts/{cuenta}` y detalle
`GET apply.workable.com/api/v2/accounts/{cuenta}/jobs/{shortcode}`.

Los dos son públicos y sin autenticación. El listado es la API del widget de empleo que Workable
documenta para montar páginas de empleo propias; responde 404 si la cuenta no existe. No trae la
descripción (con `?details=true` redirige a otro dominio, que bloquea las peticiones sin
navegador), así que se pide el detalle solo de las ofertas que pasan el filtro previo. El detalle
es el JSON que usa la propia página de empleo de Workable (`apply.workable.com/{cuenta}`): no
está documentado, pero es JSON público, no HTML (ADR-016). Documentación del widget:
https://help.workable.com/hc/en-us/articles/115012771647
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
    looks_remote,
    optional_str,
    parse_datetime,
    parse_items,
    require_str,
    require_url,
    safe_id,
    unexpected,
)

WIDGET = "https://apply.workable.com/api/v1/widget/accounts/{slug}"
DETAIL = "https://apply.workable.com/api/v2/accounts/{slug}/jobs/{shortcode}"
_SECTIONS = (("description", None), ("requirements", "Requisitos"), ("benefits", "Beneficios"))


def _location(item: dict[str, Any]) -> str | None:
    places = []
    for loc in item.get("locations") or []:
        if not isinstance(loc, dict) or loc.get("hidden") is True:
            continue
        city, country = optional_str(loc.get("city")), optional_str(loc.get("country"))
        place = ", ".join(v for v in (city, country) if v)
        if place and place not in places:
            places.append(place)
    if not places:
        city, country = optional_str(item.get("city")), optional_str(item.get("country"))
        places = [", ".join(v for v in (city, country) if v)]
    return "; ".join(p for p in places if p) or None


class WorkableConnector:
    kind = "workable"
    label = "Workable"

    def fetch(self, name: str, config: SourceConfig, client: httpx.Client) -> FetchResult:
        assert isinstance(config, AtsConfig)
        data = get_json(
            client,
            WIDGET.format(slug=config.slug),
            label=self.label,
            not_found=(
                f"No existe la cuenta «{config.slug}» en Workable (404). Revisa el slug: es lo "
                "que va tras `apply.workable.com/`."
            ),
        )
        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            raise unexpected(self.label, "falta la lista `jobs`")

        def parse(item: dict[str, Any]) -> RawJob:
            shortcode = safe_id(require_str(item, "shortcode"))
            location = _location(item)
            title = require_str(item, "title")
            return RawJob(
                external_id=shortcode,
                title=title,
                company=name,
                url=require_url(item, "url"),
                location=location,
                posted_at=parse_datetime(item.get("published_on") or item.get("created_at")),
                remote=True if item.get("telecommuting") is True else looks_remote(location),
                needs_detail=True,
                detail_url=DETAIL.format(slug=config.slug, shortcode=shortcode),
            )

        return parse_items(data["jobs"], self.label, parse)

    def complete(self, job: RawJob, client: httpx.Client) -> RawJob:
        assert job.detail_url
        data = get_json(
            client,
            job.detail_url,
            label=self.label,
            not_found=f"La oferta {job.external_id} ya no está en Workable (404).",
        )
        if not isinstance(data, dict):
            raise unexpected(self.label, "el detalle de la oferta no es un objeto")
        parts = [
            (heading, data[key])
            for key, heading in _SECTIONS
            if isinstance(data.get(key), str) and data[key].strip()
        ]
        job.html = "".join(f"<h3>{h}</h3>{v}" if h else v for h, v in parts) or None
        job.text = (
            join_text(*(join_text(h, html_fragment_to_text(v)) for h, v in parts)) or job.text
        )
        if data.get("remote") is True or data.get("workplace") == "remote":
            job.remote = True
        job.needs_detail = False
        return job
