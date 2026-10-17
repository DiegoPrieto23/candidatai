"""SmartRecruiters Posting API: listado
`GET api.smartrecruiters.com/v1/companies/{empresa}/postings` y detalle
`GET .../postings/{id}`.

Pública y sin autenticación; solo devuelve las ofertas públicas. El listado va paginado (`limit`
de 100 como mucho y `offset`) y no trae la descripción: se pide el detalle solo de las ofertas que
pasan el filtro previo. Una empresa que no existe **no da 404**: devuelve `totalFound: 0`, igual
que una que hoy no publica nada, así que se avisa sin poder distinguirlas. Documentación:
https://developers.smartrecruiters.com/docs/posting-api
"""

from typing import Any

import httpx

from app.schemas.sources import AtsConfig, Issue, SourceConfig
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
    safe_id,
    unexpected,
)

LIST = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
DETAIL = "https://api.smartrecruiters.com/v1/companies/{slug}/postings/{id}"
JOB_URL = "https://jobs.smartrecruiters.com/{slug}/{id}"
PAGE_SIZE = 100
MAX_PAGES = 5
_SECTIONS = ("jobDescription", "qualifications", "additionalInformation", "companyDescription")


def _location(item: dict[str, Any]) -> tuple[str | None, bool | None]:
    loc = item.get("location")
    if not isinstance(loc, dict):
        return None, None
    city, country = optional_str(loc.get("city")), optional_str(loc.get("country"))
    place = ", ".join(v for v in (city, country.upper() if country else None) if v) or None
    remote = True if loc.get("remote") is True else looks_remote(place)
    return place, remote


class SmartRecruitersConnector:
    kind = "smartrecruiters"
    label = "SmartRecruiters"

    def fetch(self, name: str, config: SourceConfig, client: httpx.Client) -> FetchResult:
        assert isinstance(config, AtsConfig)
        result = FetchResult()

        def parse(item: dict[str, Any]) -> RawJob:
            posting_id = safe_id(require_str(item, "id"))
            place, remote = _location(item)
            return RawJob(
                external_id=posting_id,
                title=require_str(item, "name"),
                company=name,
                url=JOB_URL.format(slug=config.slug, id=posting_id),
                location=place,
                posted_at=parse_datetime(item.get("releasedDate")),
                remote=remote,
                needs_detail=True,
                detail_url=DETAIL.format(slug=config.slug, id=posting_id),
            )

        for page in range(MAX_PAGES):
            data = get_json(
                client,
                LIST.format(slug=config.slug),
                params={"limit": PAGE_SIZE, "offset": page * PAGE_SIZE},
                label=self.label,
                not_found=f"No existe la empresa «{config.slug}» en SmartRecruiters (404).",
            )
            if not isinstance(data, dict) or not isinstance(data.get("content"), list):
                raise unexpected(self.label, "falta la lista `content`")
            chunk = parse_items(data["content"], self.label, parse)
            result.jobs.extend(chunk.jobs)
            result.issues.extend(chunk.issues)
            total = data.get("totalFound")
            if page == 0 and total == 0:
                result.issues.append(
                    Issue(
                        code="empty",
                        message=(
                            f"SmartRecruiters no devuelve ninguna oferta para «{config.slug}»: o "
                            "no publica nada ahora o el identificador no es ese (SmartRecruiters "
                            "no los distingue). Es lo que va tras `jobs.smartrecruiters.com/`."
                        ),
                    )
                )
            if len(data["content"]) < PAGE_SIZE or not isinstance(total, int):
                break
            if (page + 1) * PAGE_SIZE >= total:
                break
        return result

    def complete(self, job: RawJob, client: httpx.Client) -> RawJob:
        assert job.detail_url
        data = get_json(
            client,
            job.detail_url,
            label=self.label,
            not_found=f"La oferta {job.external_id} ya no está en SmartRecruiters (404).",
        )
        if not isinstance(data, dict):
            raise unexpected(self.label, "el detalle de la oferta no es un objeto")
        ad = data.get("jobAd")
        sections = ad.get("sections") if isinstance(ad, dict) else None
        sections = sections if isinstance(sections, dict) else {}
        parts = []
        for key in _SECTIONS:
            section = sections.get(key)
            if not isinstance(section, dict):
                continue
            text = section.get("text")
            if isinstance(text, str) and text.strip():
                parts.append((optional_str(section.get("title")) or "", text))
        job.html = "".join(f"<h3>{h}</h3>{v}" for h, v in parts) or None
        job.text = (
            join_text(*(join_text(h, html_fragment_to_text(v)) for h, v in parts)) or job.text
        )
        job.needs_detail = False
        return job
