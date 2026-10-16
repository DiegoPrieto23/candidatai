"""Personio, feed XML de ofertas: `GET {empresa}.jobs.personio.de/xml?language={idioma}`.

Público y sin autenticación; es el feed oficial que Personio ofrece para publicar ofertas en otras
webs. Responde 404 si la empresa no existe o no tiene el feed activo. La descripción
(`jobDescriptions`) solo viene en el idioma que se pide: sin idioma configurado se prueba `es` y,
si ninguna oferta trae descripción, `en`. Documentación:
https://developer.personio.de/docs/retrieving-open-job-positions
"""

from html import escape
from typing import Any

import httpx
from lxml import etree

from app.schemas.sources import AtsConfig, SourceConfig
from app.services.ingestion.base import (
    FetchResult,
    RawJob,
    get_xml,
    html_fragment_to_text,
    join_text,
    looks_remote,
    parse_datetime,
    parse_items,
    require_str,
    unexpected,
    xml_text,
)

FEED = "https://{slug}.jobs.personio.de/xml"
JOB_URL = "https://{slug}.jobs.personio.de/job/{id}"
DEFAULT_LANGUAGES = ("es", "en")


def _position(node: etree._Element) -> dict[str, Any]:
    """Una `<position>` como diccionario, para validarla como las ofertas de las APIs JSON."""
    offices = [xml_text(node, "office")]
    offices += ["".join(o.itertext()).strip() for o in node.findall("additionalOffices/office")]
    sections = []
    for desc in node.findall("jobDescriptions/jobDescription"):
        sections.append((xml_text(desc, "name") or "", xml_text(desc, "value") or ""))
    return {
        "id": xml_text(node, "id"),
        "name": xml_text(node, "name"),
        "offices": [o for o in offices if o],
        "department": xml_text(node, "department"),
        "employment": [xml_text(node, k) for k in ("employmentType", "schedule", "seniority")],
        "years": xml_text(node, "yearsOfExperience"),
        "createdAt": xml_text(node, "createdAt"),
        "sections": [(h, v) for h, v in sections if v.strip()],
    }


def _positions(root: etree._Element, label: str) -> list[dict[str, Any]]:
    if root.tag != "workzag-jobs":
        raise unexpected(label, "falta el elemento `workzag-jobs`")
    return [_position(node) for node in root.findall("position")]


class PersonioConnector:
    kind = "personio"
    label = "Personio"

    def fetch(self, name: str, config: SourceConfig, client: httpx.Client) -> FetchResult:
        assert isinstance(config, AtsConfig)
        languages = (config.language,) if config.language else DEFAULT_LANGUAGES
        items: list[dict[str, Any]] = []
        for language in languages:
            root = get_xml(
                client,
                FEED.format(slug=config.slug),
                params={"language": language},
                label=self.label,
                not_found=(
                    f"No existe la empresa «{config.slug}» en Personio o no publica su feed "
                    "(404). Revisa el slug: es lo que va antes de `.jobs.personio.de`."
                ),
            )
            items = _positions(root, self.label)
            if any(item["sections"] for item in items):
                break

        def parse(item: dict[str, Any]) -> RawJob:
            external_id = require_str(item, "id")
            if not external_id.isdigit():
                raise ValueError("`id` no es numérico")
            title = require_str(item, "name")
            html = "".join(f"<h3>{escape(h)}</h3>{v}" for h, v in item["sections"])
            details = ", ".join(v for v in item["employment"] if v)
            if item["years"]:
                details += f" ({item['years']} años de experiencia)"
            text = join_text(
                *(join_text(h, html_fragment_to_text(v)) for h, v in item["sections"]),
                f"Departamento: {item['department']}" if item["department"] else None,
                f"Contrato: {details}" if details else None,
            )
            location = ", ".join(item["offices"]) or None
            return RawJob(
                external_id=external_id,
                title=title,
                company=name,
                url=JOB_URL.format(slug=config.slug, id=external_id),
                location=location,
                text=text,
                html=html or None,
                posted_at=parse_datetime(item["createdAt"]),
                remote=looks_remote(location, title),
            )

        return parse_items(items, self.label, parse)

    def complete(self, job: RawJob, client: httpx.Client) -> RawJob:
        return job
