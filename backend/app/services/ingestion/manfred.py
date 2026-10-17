"""Manfred: listado `GET getmanfred.com/api/v2/public/offers?lang=ES&onlyActive=true` y detalle
`GET getmanfred.com/api/v2/public/offers/{id}?lang=ES`.

Portal de tecnología en España. Su API pública da JSON sin claves, pero no está documentada: se
acepta porque no es HTML ni pide sesión (ADR-016, nota de la fase 25.1). No busca por palabras:
devuelve todas las ofertas activas (unas decenas) y aquí se quedan las que casan con la búsqueda
por el título. El listado no trae la descripción: se pide el detalle solo de las ofertas que
pasan el filtro previo. El detalle trae datos del «scout» de Manfred (nombre y correo), que nunca
se guardan.
"""

import re
from typing import Any

import httpx

from app.schemas.sources import ManfredConfig, SourceConfig
from app.services.ingestion.base import (
    FetchResult,
    RawJob,
    get_json,
    join_text,
    looks_remote,
    optional_str,
    parse_datetime,
    parse_items,
    require_str,
    unexpected,
)
from app.services.normalize import fold

LIST = "https://www.getmanfred.com/api/v2/public/offers"
DETAIL = "https://www.getmanfred.com/api/v2/public/offers/{id}"
JOB_URL = {
    "ES": "https://www.getmanfred.com/ofertas-empleo/{id}/{slug}",
    "EN": "https://www.getmanfred.com/en/job-offers/{id}/{slug}",
}
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,199}$")
# Secciones del detalle, en orden de lectura (texto en Markdown), con su encabezado en el idioma
# de las ofertas (`lang`).
_SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("introduction", "Introducción", "Introduction"),
    ("whatWillYouDo", "La empresa", "The company"),
    ("responsibilities", "Responsabilidades", "Responsibilities"),
    ("howWillYouDoIt", "Cómo lo harás", "How you will do it"),
    ("whoWillDoItWith", "Equipo", "Team"),
    ("whatTheyAskFor", "Qué piden", "What they ask for"),
    ("whereWillDoIt", "Dónde", "Where"),
    ("whenWillDoIt", "Horario", "Schedule"),
    ("whatOffering", "Qué ofrecen", "What they offer"),
    ("techs", "Tecnologías", "Technologies"),
)
_TECH_SECTIONS = {
    "ES": {"MUST": "imprescindible", "NICE": "deseable", "COULD": "deseable"},
    "EN": {"MUST": "required", "NICE": "nice to have", "COULD": "nice to have"},
}
_SALARY = {"ES": ("Salario", "hasta"), "EN": ("Salary", "up to")}


def matches(query: str, title: str) -> bool:
    """La búsqueda casa con el título: varias búsquedas separadas por comas; en cada una, todas
    sus palabras (sin tildes ni mayúsculas) tienen que estar en el título."""
    words = set(re.findall(r"[a-z0-9+#.]+", fold(title)))
    for alternative in query.split(","):
        terms = re.findall(r"[a-z0-9+#.]+", fold(alternative))
        if terms and all(term in words for term in terms):
            return True
    return False


def _section(value: Any) -> str | None:
    if isinstance(value, list):
        items = [f"- {v.strip()}" for v in value if isinstance(v, str) and v.strip()]
        return "\n".join(items) or None
    return optional_str(value)


def _techs(value: Any, lang: str) -> str | None:
    lines = []
    for tech in value if isinstance(value, list) else []:
        if not isinstance(tech, dict) or not optional_str(tech.get("name")):
            continue
        kind = _TECH_SECTIONS[lang].get(str(tech.get("section")), "")
        level = optional_str(tech.get("level"))
        extra = ", ".join(v for v in (kind, level.lower() if level else None) if v)
        lines.append(f"- {tech['name'].strip()}" + (f" ({extra})" if extra else ""))
    return "\n".join(lines) or None


def _salary(item: dict[str, Any], lang: str) -> str | None:
    low, high = item.get("salaryFrom"), item.get("salaryTo")
    currency = optional_str(item.get("currency")) or ""
    label, up_to = _SALARY[lang]
    if not isinstance(high, int | float) or high <= 0:
        return None
    if isinstance(low, int | float) and 0 < low < high:
        return f"{label}: {low:g}–{high:g} {currency}".strip()
    return f"{label}: {up_to} {high:g} {currency}".strip()


def _lang(url: str) -> str:
    return "EN" if url.endswith("lang=EN") else "ES"


class ManfredConnector:
    kind = "manfred"
    label = "Manfred"

    def fetch(self, name: str, config: SourceConfig, client: httpx.Client) -> FetchResult:
        assert isinstance(config, ManfredConfig)
        data = get_json(
            client,
            LIST,
            params={"lang": config.lang, "onlyActive": "true"},
            label=self.label,
        )
        if not isinstance(data, list):
            raise unexpected(self.label, "se esperaba una lista de ofertas")

        def parse(item: dict[str, Any]) -> RawJob | None:
            if item.get("status") not in (None, "ACTIVE"):
                return None
            title = require_str(item, "position")
            if not matches(config.query, title):
                return None
            offer_id = require_str(item, "id")
            if not offer_id.isdigit():
                raise ValueError("`id` no es numérico")
            slug = require_str(item, "slug")
            if not _SLUG.match(slug):
                raise ValueError("`slug` con caracteres no válidos")
            company = item.get("company")
            company_name = optional_str(company.get("name")) if isinstance(company, dict) else None
            if not company_name:
                raise ValueError("sin empresa (`company.name`)")
            places = [p.strip() for p in item.get("locations") or [] if isinstance(p, str)]
            location = "; ".join(p for p in places if p) or None
            remote = item.get("remotePercentage")
            return RawJob(
                external_id=offer_id,
                title=title,
                company=company_name,
                url=JOB_URL[config.lang].format(id=offer_id, slug=slug),
                location=location,
                text=join_text(_salary(item, config.lang)),
                # La API solo da `updatedAt`: una oferta editada parece más reciente.
                posted_at=parse_datetime(item.get("updatedAt")),
                remote=True if remote == 100 else looks_remote(location),
                needs_detail=True,
                detail_url=f"{DETAIL.format(id=offer_id)}?lang={config.lang}",
            )

        return parse_items(data, self.label, parse)

    def complete(self, job: RawJob, client: httpx.Client) -> RawJob:
        assert job.detail_url
        data = get_json(client, job.detail_url, label=self.label)
        if not isinstance(data, dict):
            raise unexpected(self.label, "el detalle de la oferta no es un objeto")
        lang = _lang(job.detail_url)
        parts = []
        for key, es, en in _SECTIONS:
            value = _techs(data.get(key), lang) if key == "techs" else _section(data.get(key))
            parts.append((es if lang == "ES" else en, value))
        # El salario del listado se conserva si el detalle no lo trae.
        listed = (line for line in job.text.splitlines() if line.startswith(_SALARY[lang][0]))
        salary = _salary(data, lang) or next(listed, None)
        job.text = join_text(*(join_text(f"## {h}", v) for h, v in parts if v), salary) or job.text
        job.needs_detail = False
        return job
