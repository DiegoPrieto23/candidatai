"""Teamtailor, feed RSS de la página de empleo: `GET {empresa}.teamtailor.com/jobs.rss`.

Público y sin autenticación; Teamtailor lo ofrece en todas las páginas de empleo para publicar las
ofertas en otros sitios. Trae la descripción en HTML, la modalidad (`remoteStatus`) y las sedes
(`tt:locations`). Responde 404 si la empresa no existe. Da 100 ofertas por página por defecto:
se pagina con `per_page` y `offset` (si una página no trae nada nuevo, se para: así un feed que
ignore la paginación no repite ofertas). Las páginas con dominio propio (`careers.empresa.com`)
también sirven `/jobs.rss`, pero aquí solo se admite el subdominio de Teamtailor. Documentación:
https://support.teamtailor.com/en/articles/11171756-rss-feed-how-to-guide
"""

from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

import httpx
from lxml import etree

from app.schemas.sources import AtsConfig, SourceConfig
from app.services.ingestion.base import (
    FetchResult,
    RawJob,
    get_xml,
    html_fragment_to_text,
    looks_remote,
    parse_items,
    require_str,
    require_url,
    unexpected,
    xml_text,
)

FEED = "https://{slug}.teamtailor.com/jobs.rss"
TT = "https://teamtailor.com/locations"
PAGE_SIZE = 100
MAX_PAGES = 5


def _date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None


def _item(node: etree._Element) -> dict[str, Any]:
    places = []
    for loc in node.iterfind(f"{{{TT}}}locations/{{{TT}}}location"):
        city = xml_text(loc, f"{{{TT}}}city") or xml_text(loc, f"{{{TT}}}name")
        country = xml_text(loc, f"{{{TT}}}country")
        place = ", ".join(v for v in (city, country) if v)
        if place and place not in places:
            places.append(place)
    return {
        "id": xml_text(node, "guid"),
        "title": xml_text(node, "title"),
        "link": xml_text(node, "link"),
        "description": xml_text(node, "description") or "",
        "pubDate": xml_text(node, "pubDate"),
        "remoteStatus": (xml_text(node, "remoteStatus") or "").lower(),
        "places": places,
        "department": xml_text(node, f"{{{TT}}}department"),
    }


class TeamtailorConnector:
    kind = "teamtailor"
    label = "Teamtailor"

    def fetch(self, name: str, config: SourceConfig, client: httpx.Client) -> FetchResult:
        assert isinstance(config, AtsConfig)
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in range(MAX_PAGES):
            root = get_xml(
                client,
                FEED.format(slug=config.slug),
                params={"per_page": PAGE_SIZE, "offset": page * PAGE_SIZE},
                label=self.label,
                not_found=(
                    f"No existe la página de empleo «{config.slug}» en Teamtailor (404). Revisa "
                    "el slug: es lo que va antes de `.teamtailor.com`."
                ),
            )
            channel = root.find("channel")
            if root.tag != "rss" or channel is None:
                raise unexpected(self.label, "no es un RSS con `channel`")
            chunk = [_item(node) for node in channel.findall("item")]
            fresh = [i for i in chunk if i["id"] is None or i["id"] not in seen]
            seen.update(i["id"] for i in fresh if i["id"])
            items.extend(fresh)
            if len(chunk) < PAGE_SIZE or not fresh:
                break

        def parse(item: dict[str, Any]) -> RawJob:
            html = item["description"]  # el RSS trae el HTML escapado: `itertext` lo deja en claro
            location = "; ".join(item["places"]) or None
            status = item["remoteStatus"]
            return RawJob(
                external_id=require_str(item, "id"),
                title=require_str(item, "title"),
                company=name,
                url=require_url(item, "link"),
                location=location,
                text=html_fragment_to_text(html),
                html=html or None,
                posted_at=_date(item["pubDate"]),
                remote=True if status == "fully" else looks_remote(location),
            )

        return parse_items(items, self.label, parse)

    def complete(self, job: RawJob, client: httpx.Client) -> RawJob:
        return job
