"""Descubrir los tableros de ATS de tus empresas (fase 16): `cai sources discover --file F`.

Para cada empresa de la lista prueba unos pocos slugs candidatos en las mismas APIs y feeds
públicos que usan los conectores (sin agente, sin tokens, sin scraping): Greenhouse, Lever (global
y UE), Ashby y, desde la fase 25.1, Personio, Teamtailor, Workable, SmartRecruiters y Recruitee.
Todos responden 404 a un tablero que no existe salvo SmartRecruiters, que devuelve una lista
vacía: ahí solo cuenta si tiene alguna oferta.

- Greenhouse y Workable dan el nombre del tablero, y SmartRecruiters el de la empresa en cada
  oferta: si casa con la empresa, `confirmed`; si no, `doubtful`.
- El resto no lo da: `probable` si el slug sale del nombre completo y `doubtful` si solo de su
  primera palabra. Se enseñan el número de ofertas y algunos títulos para comprobarlo.

Solo propone. Con `add=True` da de alta las `confirmed` y `probable` que aún no son fuente
(`service.add_source`, que marca la empresa como objetivo). Las `doubtful`, nunca: se añaden a
mano con el comando que se sugiere.

Formato del fichero: una empresa por línea; `#` empieza un comentario. `Nombre | slug` prueba solo
ese slug (para corregir uno que no se adivina).
"""

import logging
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

import httpx
from lxml import etree
from pydantic import BaseModel
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.policies import get_policies
from app.models import Source
from app.schemas.sources import KIND_LABELS, SourceInput
from app.services.ingestion import service
from app.services.ingestion.base import make_client
from app.services.normalize import normalize_company

logger = logging.getLogger(__name__)

MAX_COMPANIES = 200
MAX_SAMPLES = 3
DELAY_SECONDS = 0.3  # entre peticiones: son APIs públicas, sin prisa
# `ratio` entre el nombre del tablero (Greenhouse) y la empresa, ya normalizados. No
# `token_set_ratio`: daría 100 a «Capital» frente a «Capital Energy».
NAME_MATCH = 90
MAX_TEXT = 120  # lo que se enseña de un nombre o un título de la API (dato no confiable)
_SLUG = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,99}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")

GREENHOUSE_BOARD = "https://boards-api.greenhouse.io/v1/boards/{slug}"
GREENHOUSE_JOBS = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
LEVER = {
    "global": "https://api.lever.co/v0/postings/{slug}",
    "eu": "https://api.eu.lever.co/v0/postings/{slug}",
}
ASHBY = "https://api.ashbyhq.com/posting-api/job-board/{slug}"
PERSONIO = "https://{slug}.jobs.personio.de/xml"
TEAMTAILOR = "https://{slug}.teamtailor.com/jobs.rss"
WORKABLE = "https://apply.workable.com/api/v1/widget/accounts/{slug}"
SMARTRECRUITERS = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
RECRUITEE = "https://{slug}.recruitee.com/api/offers/"
DISCOVER_KINDS = (
    "greenhouse",
    "lever",
    "ashby",
    "personio",
    "teamtailor",
    "workable",
    "smartrecruiters",
    "recruitee",
)

Confidence = Literal["confirmed", "probable", "doubtful"]


class DiscoverError(ValueError):
    """El fichero de empresas no se puede leer o está vacío."""


class BoardHit(BaseModel):
    kind: str  # uno de `DISCOVER_KINDS`
    slug: str
    region: str = "global"
    board_name: str | None  # solo Greenhouse y Workable
    jobs_count: int
    sample_titles: list[str]
    confidence: Confidence
    existing_source_id: int | None  # ya es una fuente
    add_command: str


class CompanyDiscovery(BaseModel):
    company: str
    tried: list[str]  # slugs probados
    hits: list[BoardHit]
    errors: list[str]
    added_source_ids: list[int]


class DiscoverResult(BaseModel):
    companies: list[CompanyDiscovery]
    found: int  # empresas con algún tablero
    added: int
    message: str


# --- Entrada -----------------------------------------------------------------------------------


def parse_companies(text: str) -> list[tuple[str, list[str]]]:
    """Empresas del fichero, con sus slugs forzados (`Nombre | slug`) si los hay."""
    companies: list[tuple[str, list[str]]] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        name, _, forced = line.partition("|")
        name = " ".join(name.split())
        key = normalize_company(name)
        if not key or key in seen:
            continue
        seen.add(key)
        slugs = [s.strip().lower() for s in forced.split(",") if _valid_slug(s.strip().lower())]
        companies.append((name, slugs))
    return companies


def read_companies(path: Path) -> list[tuple[str, list[str]]]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise DiscoverError(f"No se pudo leer {path}: {exc}") from exc
    companies = parse_companies(text)
    if not companies:
        raise DiscoverError(f"{path} no tiene ninguna empresa (una por línea).")
    if len(companies) > MAX_COMPANIES:
        raise DiscoverError(
            f"{path} tiene {len(companies)} empresas; como mucho {MAX_COMPANIES} por vez."
        )
    return companies


def _valid_slug(slug: str) -> bool:
    return bool(_SLUG.match(slug)) and ".." not in slug


def _clean(value: object) -> str:
    """Texto de la API en una línea, sin caracteres de control (secuencias ANSI) y recortado."""
    return " ".join(_CONTROL.sub(" ", str(value)).split())[:MAX_TEXT]


def candidate_slugs(name: str) -> list[tuple[str, bool]]:
    """Slugs que probar y si salen del nombre completo: «Acme Data S.L.» -> `acmedata`,
    `acme-data` y `acme` (este, solo si tiene 4 letras o más; no es del nombre completo)."""
    tokens = normalize_company(name).split()
    if not tokens:
        return []
    candidates = [("".join(tokens), True)]
    if len(tokens) > 1:
        candidates.append(("-".join(tokens), True))
        if len(tokens[0]) >= 4:
            candidates.append((tokens[0], False))
    unique: dict[str, bool] = {}
    for slug, full in candidates:
        if _valid_slug(slug) and slug not in unique:
            unique[slug] = full
    return list(unique.items())


# --- Red ---------------------------------------------------------------------------------------


class _Probe:
    """Peticiones con pausa entre ellas. `None` = no existe (404); lanza `httpx.HTTPError` o
    `ValueError` si la API falla de otra forma."""

    def __init__(self, client: httpx.Client, sleep: Callable[[float], None]) -> None:
        self.client = client
        self.sleep = sleep
        self.calls = 0

    def get(self, url: str, params: dict[str, str] | None = None) -> Any:
        if self.calls:
            self.sleep(DELAY_SECONDS)
        self.calls += 1
        response = self.client.get(url, params=params)
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise ValueError(f"HTTP {response.status_code}")
        return response.json()

    def get_xml(self, url: str) -> Any:
        """Como `get`, para los feeds XML (Personio, Teamtailor): sin entidades ni red."""
        if self.calls:
            self.sleep(DELAY_SECONDS)
        self.calls += 1
        response = self.client.get(url, headers={"Accept": "application/xml, text/xml"})
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise ValueError(f"HTTP {response.status_code}")
        parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
        try:
            return etree.fromstring(response.content, parser)
        except etree.XMLSyntaxError as exc:
            raise ValueError("no es XML") from exc


def _titles(items: list[Any], key: str) -> list[str]:
    """Hasta `MAX_SAMPLES` títulos distintos, en el orden de la API."""
    titles = (_clean(i[key]) for i in items if isinstance(i, dict) and i.get(key))
    return list(dict.fromkeys(titles))[:MAX_SAMPLES]


def _greenhouse(probe: _Probe, slug: str, company: str, full_name: bool) -> dict[str, Any] | None:
    board = probe.get(GREENHOUSE_BOARD.format(slug=slug))
    if board is None:
        return None
    jobs = probe.get(GREENHOUSE_JOBS.format(slug=slug)) or {}
    items = jobs.get("jobs") if isinstance(jobs, dict) else None
    items = items if isinstance(items, list) else []
    name = _board_name(board)
    return {
        "board_name": name,
        "jobs_count": len(items),
        "sample_titles": _titles(items, "title"),
        "confidence": _named_confidence(name, company, full_name),
    }


def _board_name(data: Any) -> str | None:
    name = data.get("name") if isinstance(data, dict) else None
    return _clean(name) if isinstance(name, str) and name.strip() else None


def _named_confidence(name: str | None, company: str, full_name: bool) -> Confidence:
    """«Confirmada» exige que el nombre del tablero case y que el slug salga del nombre
    completo."""
    score = fuzz.ratio(normalize_company(name or ""), normalize_company(company))
    return "confirmed" if name is not None and score >= NAME_MATCH and full_name else "doubtful"


def _lever(probe: _Probe, slug: str) -> dict[str, Any] | None:
    for region in ("global", "eu"):
        items = probe.get(LEVER[region].format(slug=slug), params={"mode": "json"})
        if items is not None:
            items = items if isinstance(items, list) else []
            return {
                "region": region,
                "jobs_count": len(items),
                "sample_titles": _titles(items, "text"),
            }
    return None


def _ashby(probe: _Probe, slug: str) -> dict[str, Any] | None:
    data = probe.get(ASHBY.format(slug=slug))
    if data is None:
        return None
    jobs = data.get("jobs") if isinstance(data, dict) else None
    listed = jobs if isinstance(jobs, list) else []
    items = [i for i in listed if isinstance(i, dict) and i.get("isListed") is not False]
    return {"jobs_count": len(items), "sample_titles": _titles(items, "title")}


def _xml_titles(nodes: list[Any], tag: str) -> list[str]:
    titles = (_clean(n.findtext(tag) or "") for n in nodes)
    return list(dict.fromkeys(t for t in titles if t))[:MAX_SAMPLES]


def _personio(probe: _Probe, slug: str) -> dict[str, Any] | None:
    root = probe.get_xml(PERSONIO.format(slug=slug))
    if root is None:
        return None
    if root.tag != "workzag-jobs":
        raise ValueError("formato inesperado")
    positions = root.findall("position")
    return {"jobs_count": len(positions), "sample_titles": _xml_titles(positions, "name")}


def _teamtailor(probe: _Probe, slug: str) -> dict[str, Any] | None:
    root = probe.get_xml(TEAMTAILOR.format(slug=slug))
    if root is None:
        return None
    channel = root.find("channel")
    if root.tag != "rss" or channel is None:
        raise ValueError("formato inesperado")
    items = channel.findall("item")
    return {"jobs_count": len(items), "sample_titles": _xml_titles(items, "title")}


def _workable(probe: _Probe, slug: str, company: str, full_name: bool) -> dict[str, Any] | None:
    data = probe.get(WORKABLE.format(slug=slug))
    if data is None:
        return None
    jobs = data.get("jobs") if isinstance(data, dict) else None
    items = jobs if isinstance(jobs, list) else []
    name = _board_name(data)
    return {
        "board_name": name,
        "jobs_count": len(items),
        "sample_titles": _titles(items, "title"),
        "confidence": _named_confidence(name, company, full_name),
    }


def _smartrecruiters(
    probe: _Probe, slug: str, company: str, full_name: bool
) -> dict[str, Any] | None:
    data = probe.get(SMARTRECRUITERS.format(slug=slug), params={"limit": "10"})
    if not isinstance(data, dict) or not isinstance(data.get("content"), list):
        return None
    total = data.get("totalFound")
    if not isinstance(total, int) or total == 0:  # no distingue «no existe» de «sin ofertas»
        return None
    # Cada oferta trae el nombre de la empresa: sirve para confirmar el slug, como en Greenhouse.
    first = data["content"][0] if data["content"] else None
    name = _board_name(first.get("company")) if isinstance(first, dict) else None
    return {
        "board_name": name,
        "jobs_count": total,
        "sample_titles": _titles(data["content"], "name"),
        "confidence": _named_confidence(name, company, full_name),
    }


def _recruitee(probe: _Probe, slug: str) -> dict[str, Any] | None:
    data = probe.get(RECRUITEE.format(slug=slug))
    if data is None:
        return None
    offers = data.get("offers") if isinstance(data, dict) else None
    items = offers if isinstance(offers, list) else []
    return {"jobs_count": len(items), "sample_titles": _titles(items, "title")}


_PROBES: dict[str, Callable[[_Probe, str], dict[str, Any] | None]] = {
    "lever": _lever,
    "ashby": _ashby,
    "personio": _personio,
    "teamtailor": _teamtailor,
    "recruitee": _recruitee,
}
# Los que dan el nombre del tablero (o de la empresa) y pueden confirmar el slug.
_NAMED_PROBES: dict[str, Callable[[_Probe, str, str, bool], dict[str, Any] | None]] = {
    "greenhouse": _greenhouse,
    "workable": _workable,
    "smartrecruiters": _smartrecruiters,
}


def _probe_kind(
    probe: _Probe, kind: str, slug: str, company: str, full_name: bool
) -> dict[str, Any] | None:
    if kind in _NAMED_PROBES:
        return _NAMED_PROBES[kind](probe, slug, company, full_name)
    return _PROBES[kind](probe, slug)


def _existing(session: Session) -> dict[tuple[str, str], int]:
    rows = session.scalars(select(Source).where(Source.kind.in_(DISCOVER_KINDS)))
    return {(row.kind, str((row.config or {}).get("slug") or "").lower()): row.id for row in rows}


def _command(company: str, kind: str, slug: str, region: str) -> str:
    extra = " --region eu" if region == "eu" else ""
    # Se pega en PowerShell: fuera comillas, acentos graves y `$`.
    name = re.sub(r'["`$]', "", company)
    return f'cai sources add --kind {kind} --name "{name}" --slug {slug}{extra}'


def _discover_one(
    probe: _Probe,
    company: str,
    forced: list[str],
    existing: dict[tuple[str, str], int],
) -> CompanyDiscovery:
    slugs = [(s, True) for s in forced] if forced else candidate_slugs(company)
    result = CompanyDiscovery(
        company=company, tried=[s for s, _ in slugs], hits=[], errors=[], added_source_ids=[]
    )
    for kind in DISCOVER_KINDS:
        for slug, full_name in slugs:
            try:
                found = _probe_kind(probe, kind, slug, company, full_name)
            except (httpx.HTTPError, ValueError) as exc:
                label = KIND_LABELS[kind]
                reason = type(exc).__name__ if isinstance(exc, httpx.HTTPError) else str(exc)
                result.errors.append(f"{label} · {slug}: {reason}")
                continue
            if found is None:
                continue
            region = found.pop("region", "global")
            confidence = found.pop("confidence", "probable" if full_name else "doubtful")
            result.hits.append(
                BoardHit(
                    kind=kind,
                    slug=slug,
                    region=region,
                    board_name=found.pop("board_name", None),
                    confidence=confidence,
                    existing_source_id=existing.get((kind, slug)),
                    add_command=_command(company, kind, slug, region),
                    **found,
                )
            )
            break  # un tablero por ATS basta
    return result


def discover(
    session: Session,
    companies: list[tuple[str, list[str]]],
    *,
    add: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    transport: httpx.BaseTransport | None = None,
) -> DiscoverResult:
    """Busca el tablero de cada empresa y, con `add`, da de alta las fiables que faltan."""
    existing = _existing(session)
    results: list[CompanyDiscovery] = []
    with make_client(get_policies().connectors.timeout_seconds, transport) as client:
        probe = _Probe(client, sleep)
        for company, forced in companies:
            results.append(_discover_one(probe, company, forced, existing))
    added = 0
    if add:
        for item in results:
            for hit in item.hits:
                if hit.confidence == "doubtful" or hit.existing_source_id is not None:
                    continue
                data = SourceInput(
                    kind=hit.kind,  # type: ignore[arg-type]
                    name=item.company,
                    slug=hit.slug,
                    region=hit.region,  # type: ignore[arg-type]
                )
                try:
                    with session.begin_nested():
                        view = service.add_source(session, data)
                except (service.SourceExistsError, ValueError) as exc:
                    item.errors.append(str(exc))
                    continue
                hit.existing_source_id = view.id
                item.added_source_ids.append(view.id)
                added += 1
    found = sum(1 for r in results if r.hits)
    message = f"{found} de {len(results)} empresas con tablero en algún ATS"
    message += f"; {added} añadidas como fuente." if add else "."
    return DiscoverResult(companies=results, found=found, added=added, message=message)
