"""Tu red de LinkedIn (fase 18): importar `Connections.csv` y cruzarla con tus ofertas.

La exportación oficial la descarga el usuario (LinkedIn → Ajustes → Privacidad de los datos →
Obtener una copia de tus datos → Contactos). Nada aquí navega LinkedIn ni busca perfiles.

- **Importar** sincroniza la tabla `network_contacts` con el fichero: añade los nuevos, actualiza
  los que cambian y borra los que ya no están. Los contactos de los procesos (`contacts`) no se
  tocan: solo pierden el enlace con la persona borrada. El email no se guarda aunque venga.
- **Cruce**: por la empresa normalizada (`normalize_company`, la de `companies.normalized_name`).
  Igual (o igual sin espacios) es `exact`; si un nombre es el principio del otro palabra a palabra
  («Brétema» ↔ «Brétema Analytics») es `probable`, salvo que el corto sea una sola palabra de
  menos de 5 letras o genérica («Banco», «Grupo»…), que daría falsos positivos.
- Las herramientas para agentes solo ven el nombre y el cargo de las personas que conoces en la
  empresa de **una** oferta: nunca la red entera, ni URLs ni emails (`POLICIES.md` §4).
"""

import csv
import io
import re
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Company, Contact, Job, NetworkContact
from app.models.base import utcnow
from app.services import context, events
from app.services.normalize import fold, normalize_company
from app.services.process import (
    ContactOut,
    ContactRelation,
    ReferralStatus,
    contact_out,
)

MatchKind = Literal["exact", "probable"]

MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_ROWS = 50_000  # LinkedIn admite hasta 30 000 contactos
DEFAULT_FILE = "Connections.csv"
# Primeras palabras que no bastan solas para decir que es la misma empresa.
GENERIC_WORDS = frozenset(
    {
        "banco", "bank", "caja", "grupo", "group", "the", "global", "international", "digital",
        "consulting", "consultores", "solutions", "soluciones", "services", "servicios",
        "systems", "sistemas", "technologies", "tecnologias", "software", "data", "datos",
        "ingenieria", "engineering", "universidad", "university", "instituto", "freelance",
        "autonomo", "self", "independent", "independiente", "stealth",
    }
)  # fmt: skip

# Cabeceras de la exportación (en inglés; las de la interfaz en español, por si acaso).
_HEADERS: dict[str, tuple[str, ...]] = {
    "first_name": ("first name", "nombre"),
    "last_name": ("last name", "apellidos", "apellido"),
    "url": ("url", "profile url", "url del perfil"),
    "company": ("company", "empresa"),
    "position": ("position", "cargo", "puesto"),
    "connected_on": ("connected on", "fecha de conexion", "conectado el", "conectado"),
}
_MONTHS = {
    "jan": 1, "ene": 1, "feb": 2, "mar": 3, "apr": 4, "abr": 4, "may": 5, "jun": 6, "jul": 7,
    "aug": 8, "ago": 8, "sep": 9, "sept": 9, "set": 9, "oct": 10, "nov": 11, "dec": 12, "dic": 12,
}  # fmt: skip
_DAY_MONTH_YEAR = re.compile(r"^(\d{1,2})\s+(?:de\s+)?([a-z]+)\s+(?:de\s+)?(\d{4})$")
_LINKEDIN_URL = re.compile(r"^https?://([a-z]{2,3}\.)?(www\.)?linkedin\.com/", re.IGNORECASE)


class NetworkImportError(ValueError):
    """El fichero no es la exportación de LinkedIn o no se puede leer."""


class NetworkContactNotFoundError(LookupError):
    pass


# --- Importación ----------------------------------------------------------------------------


class ParsedConnection(BaseModel):
    first_name: str
    last_name: str
    linkedin_url: str | None
    company: str | None
    company_key: str | None
    position: str | None
    connected_on: date | None


class ImportResult(BaseModel):
    ok: bool = True
    path: str
    total: int  # personas en la red tras importar
    added: int
    updated: int
    removed: int
    skipped: int  # filas sin nombre o repetidas
    without_company: int
    message: str


def default_path() -> Path:
    return context.documents_dir() / "linkedin" / DEFAULT_FILE


def _parse_date(value: str) -> date | None:
    text = fold(value)
    if not text:
        return None
    try:
        return date.fromisoformat(value.strip()[:10])
    except ValueError:
        pass
    found = _DAY_MONTH_YEAR.match(text)
    if found is None:
        return None
    day, month_name, year = found.groups()
    month = _MONTHS.get(month_name[:4]) or _MONTHS.get(month_name[:3])
    if month is None:
        return None
    try:
        return date(int(year), month, int(day))
    except ValueError:
        return None


def _header_index(row: list[str]) -> dict[str, int] | None:
    folded = [fold(cell) for cell in row]
    index: dict[str, int] = {}
    for field, aliases in _HEADERS.items():
        for position, cell in enumerate(folded):
            if cell in aliases:
                index[field] = position
                break
    if "first_name" in index and "last_name" in index:
        return index
    return None


def _cell(row: list[str], index: dict[str, int], field: str, limit: int) -> str | None:
    position = index.get(field)
    if position is None or position >= len(row):
        return None
    value = " ".join(row[position].split())[:limit]
    return value or None


def parse_connections(text: str) -> tuple[list[ParsedConnection], int]:
    """Filas válidas del CSV y cuántas se saltaron. Admite el preámbulo «Notes:» de LinkedIn."""
    reader = csv.reader(io.StringIO(text))
    index: dict[str, int] | None = None
    parsed: list[ParsedConnection] = []
    skipped = 0
    for row in reader:
        if index is None:
            index = _header_index(row)
            continue
        if not any(cell.strip() for cell in row):
            continue
        if len(parsed) + skipped >= MAX_ROWS:
            raise NetworkImportError(f"El fichero tiene más de {MAX_ROWS} filas.")
        first = _cell(row, index, "first_name", 200)
        last = _cell(row, index, "last_name", 200) or ""
        if first is None and not last:
            skipped += 1
            continue
        url = _cell(row, index, "url", 500)
        company = _cell(row, index, "company", 200)
        connected = _cell(row, index, "connected_on", 40)
        parsed.append(
            ParsedConnection(
                first_name=first or last,
                last_name=last if first else "",
                linkedin_url=url.rstrip("/") if url and _LINKEDIN_URL.match(url) else None,
                company=company,
                company_key=(normalize_company(company) or None) if company else None,
                position=_cell(row, index, "position", 300),
                connected_on=_parse_date(connected) if connected else None,
            )
        )
    if index is None:
        raise NetworkImportError(
            "No parece la exportación de contactos de LinkedIn: falta la cabecera «First Name, "
            "Last Name, URL, Email Address, Company, Position, Connected On»."
        )
    return parsed, skipped


def read_file(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise FileNotFoundError(f"No existe {path}.") from exc
    if size > MAX_FILE_BYTES:
        raise NetworkImportError(f"{path.name} pesa más de {MAX_FILE_BYTES // 1024 // 1024} MB.")
    try:
        return path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise NetworkImportError(f"{path.name} no está en UTF-8.") from exc


def _key(row: ParsedConnection | NetworkContact) -> tuple[str, ...]:
    if row.linkedin_url:
        return ("url", row.linkedin_url.lower())
    return ("name", fold(row.first_name), fold(row.last_name), row.company_key or "")


_FIELDS = ("first_name", "last_name", "linkedin_url", "company", "company_key", "position",
           "connected_on")  # fmt: skip


def import_connections(session: Session, path: Path | None = None) -> ImportResult:
    """Sincroniza la red con `Connections.csv` (por defecto, `data/documentos/linkedin/`)."""
    target = path or default_path()
    parsed, skipped = parse_connections(read_file(target))
    existing = {_key(row): row for row in session.scalars(select(NetworkContact))}
    if not parsed and existing:
        raise NetworkImportError(
            "El fichero no trae ningún contacto: no se borra la red que ya tenías."
        )
    now = utcnow()
    seen: set[tuple[str, ...]] = set()
    added = updated = 0
    for item in parsed:
        key = _key(item)
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        row = existing.get(key)
        values = item.model_dump(include=set(_FIELDS))
        if row is None:
            session.add(NetworkContact(**values, imported_at=now))
            added += 1
            continue
        if any(getattr(row, name) != value for name, value in values.items()):
            for name, value in values.items():
                setattr(row, name, value)
            updated += 1
        row.imported_at = now
    gone = [row.id for key, row in existing.items() if key not in seen]
    if gone:
        session.execute(
            update(Contact)
            .where(Contact.network_contact_id.in_(gone))
            .values(network_contact_id=None)
        )
        session.execute(delete(NetworkContact).where(NetworkContact.id.in_(gone)))
    session.flush()
    total = session.scalar(select(func.count()).select_from(NetworkContact)) or 0
    without_company = (
        session.scalar(
            select(func.count())
            .select_from(NetworkContact)
            .where(NetworkContact.company_key.is_(None))
        )
        or 0
    )
    try:
        shown = target.resolve().relative_to(get_settings().data_dir.resolve()).as_posix()
    except ValueError:
        shown = str(target)
    return ImportResult(
        path=shown,
        total=total,
        added=added,
        updated=updated,
        removed=len(gone),
        skipped=skipped,
        without_company=without_company,
        message=f"Red importada: {total} personas ({added} nuevas, {updated} actualizadas, "
        f"{len(gone)} quitadas).",
    )


# --- Cruce por empresa ----------------------------------------------------------------------


def match_kind(job_key: str, network_key: str) -> MatchKind | None:
    """¿Es la misma empresa? `exact`, `probable` o `None` (ver el docstring del módulo)."""
    if not job_key or not network_key:
        return None
    if job_key == network_key or job_key.replace(" ", "") == network_key.replace(" ", ""):
        return "exact"
    a, b = job_key.split(), network_key.split()
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    if long[: len(short)] != short:
        return None
    if len(short) == 1 and (len(short[0]) < 5 or short[0] in GENERIC_WORDS):
        return None
    return "probable"


class _KeyIndex:
    """Claves de empresa de la red agrupadas para cruzar muchas ofertas sin compararlas todas."""

    def __init__(self, keys: Iterable[str]) -> None:
        self.by_first: dict[str, list[str]] = defaultdict(list)
        self.by_compact: dict[str, list[str]] = defaultdict(list)
        for key in keys:
            self.by_first[key.split()[0]].append(key)
            self.by_compact[key.replace(" ", "")].append(key)

    def matches(self, job_key: str) -> dict[str, MatchKind]:
        if not job_key:
            return {}
        found: dict[str, MatchKind] = {}
        candidates = [*self.by_first.get(job_key.split()[0], ()),
                      *self.by_compact.get(job_key.replace(" ", ""), ())]  # fmt: skip
        for key in candidates:
            kind = match_kind(job_key, key)
            if kind is not None and found.get(key) != "exact":
                found[key] = kind
        return found


def _company_keys(session: Session, job_ids: list[int]) -> dict[int, tuple[str, str]]:
    rows = session.execute(
        select(Job.id, Company.normalized_name, Company.name)
        .join(Company, Company.id == Job.company_id)
        .where(Job.id.in_(job_ids))
    ).all()
    return {job_id: (key, name) for job_id, key, name in rows}


def known_counts(session: Session, job_ids: list[int]) -> dict[int, int]:
    """Cuántas personas de tu red trabajan en la empresa de cada oferta (solo las que tienen)."""
    if not job_ids:
        return {}
    counts = dict(
        session.execute(
            select(NetworkContact.company_key, func.count())
            .where(NetworkContact.company_key.is_not(None))
            .group_by(NetworkContact.company_key)
        ).all()
    )
    if not counts:
        return {}
    index = _KeyIndex(counts)
    out: dict[int, int] = {}
    for job_id, (key, _name) in _company_keys(session, job_ids).items():
        total = sum(counts[k] for k in index.matches(key))
        if total:
            out[job_id] = total
    return out


class NetworkPerson(BaseModel):
    """Una persona de tu red en la empresa de la oferta (vista de la UI)."""

    id: int
    name: str
    position: str | None
    company: str | None
    linkedin_url: str | None
    connected_on: date | None
    match: MatchKind
    contact_id: int | None  # ya es contacto de este proceso


class JobNetwork(BaseModel):
    job_id: int
    company: str
    network_size: int  # personas en tu red (0: aún no la has importado)
    imported_at: datetime | None
    people: list[NetworkPerson]  # primero las de coincidencia exacta


def _name(row: NetworkContact) -> str:
    return f"{row.first_name} {row.last_name}".strip()


def _people(session: Session, job_id: int) -> tuple[str, list[tuple[NetworkContact, MatchKind]]]:
    keys = _company_keys(session, [job_id])
    if job_id not in keys:
        raise events.JobNotFoundError(f"No existe la oferta {job_id}.")
    job_key, company = keys[job_id]
    network_keys = session.scalars(
        select(NetworkContact.company_key).where(NetworkContact.company_key.is_not(None)).distinct()
    )
    matched = _KeyIndex(k for k in network_keys if k).matches(job_key)
    if not matched:
        return company, []
    rows = session.scalars(
        select(NetworkContact).where(NetworkContact.company_key.in_(list(matched)))
    ).all()
    ranked = sorted(
        ((row, matched[row.company_key or ""]) for row in rows),
        key=lambda pair: (pair[1] != "exact", fold(_name(pair[0]))),
    )
    return company, ranked


def job_network(session: Session, job_id: int) -> JobNetwork:
    """Las personas de tu red en la empresa de la oferta, para la ficha."""
    company, people = _people(session, job_id)
    linked = dict(
        session.execute(
            select(Contact.network_contact_id, Contact.id).where(
                Contact.job_id == job_id, Contact.network_contact_id.is_not(None)
            )
        ).all()
    )
    return JobNetwork(
        job_id=job_id,
        company=company,
        network_size=session.scalar(select(func.count()).select_from(NetworkContact)) or 0,
        imported_at=session.scalar(select(func.max(NetworkContact.imported_at))),
        people=[
            NetworkPerson(
                id=row.id,
                name=_name(row),
                position=row.position,
                company=row.company,
                linkedin_url=row.linkedin_url,
                connected_on=row.connected_on,
                match=kind,
                contact_id=linked.get(row.id),
            )
            for row, kind in people
        ],
    )


class AddFromNetwork(BaseModel):
    network_contact_id: int = Field(ge=1)
    relation: ContactRelation = Field(
        description="Papel en el proceso: referencia, recruiter o responsable."
    )


def add_to_process(session: Session, job_id: int, data: AddFromNetwork) -> ContactOut:
    """«Añadir como contacto del proceso»: copia nombre, cargo y URL; el resto lo pones tú."""
    if session.get(Job, job_id) is None:
        raise events.JobNotFoundError(f"No existe la oferta {job_id}.")
    person = session.get(NetworkContact, data.network_contact_id)
    if person is None:
        raise NetworkContactNotFoundError(
            f"No existe la persona {data.network_contact_id} en tu red."
        )
    already = session.scalars(
        select(Contact).where(Contact.job_id == job_id, Contact.network_contact_id == person.id)
    ).first()
    if already is not None:
        already.relation = data.relation
        session.flush()
        return contact_out(already)
    row = Contact(
        job_id=job_id,
        name=_name(person)[:200],
        role=person.position[:200] if person.position else None,
        linkedin=person.linkedin_url,
        relation=data.relation,
        network_contact_id=person.id,
        created_at=utcnow(),
    )
    session.add(row)
    session.flush()
    return contact_out(row)


# --- Vista para agentes ---------------------------------------------------------------------


class AgentProcessContact(BaseModel):
    """Contacto del proceso sin email, teléfono, URL ni notas."""

    id: int
    name: str
    role: str | None  # cargo
    relation: ContactRelation | None
    referral: ReferralStatus | None


class AgentNetworkPerson(BaseModel):
    """Persona de tu red en la empresa: solo nombre y cargo."""

    id: int
    name: str
    position: str | None
    match: MatchKind
    in_process: bool  # ya es contacto de este proceso


class JobContacts(BaseModel):
    job_id: int
    company: str
    contacts: list[AgentProcessContact]
    network: list[AgentNetworkPerson]
    network_imported: bool  # False: el usuario aún no ha importado su red


def job_contacts(session: Session, job_id: int) -> JobContacts:
    """Contactos del proceso y personas de tu red en la empresa de la oferta (`get_job_contacts`).

    Sin datos de contacto: el agente solo necesita a quién se dirige y su cargo.
    """
    company, people = _people(session, job_id)
    contacts = session.scalars(select(Contact).where(Contact.job_id == job_id).order_by(Contact.id))
    contacts = list(contacts)
    linked = {c.network_contact_id for c in contacts if c.network_contact_id is not None}
    imported = session.scalar(select(NetworkContact.id).limit(1)) is not None
    return JobContacts(
        job_id=job_id,
        company=company,
        contacts=[
            AgentProcessContact(
                id=c.id,
                name=c.name,
                role=c.role,
                relation=c.relation,  # type: ignore[arg-type]
                referral=c.referral,  # type: ignore[arg-type]
            )
            for c in contacts
        ],
        network=[
            AgentNetworkPerson(
                id=row.id,
                name=_name(row),
                position=row.position,
                match=kind,
                in_process=row.id in linked,
            )
            for row, kind in people
        ],
        network_imported=imported,
    )


# --- Estado de la red (UI) ------------------------------------------------------------------


class NetworkStatus(BaseModel):
    size: int  # personas importadas
    without_company: int
    imported_at: datetime | None
    default_file: str  # relativo a la carpeta de datos
    default_file_exists: bool


def network_status(session: Session) -> NetworkStatus:
    path = default_path()
    return NetworkStatus(
        size=session.scalar(select(func.count()).select_from(NetworkContact)) or 0,
        without_company=session.scalar(
            select(func.count())
            .select_from(NetworkContact)
            .where(NetworkContact.company_key.is_(None))
        )
        or 0,
        imported_at=session.scalar(select(func.max(NetworkContact.imported_at))),
        default_file=path.relative_to(get_settings().data_dir).as_posix(),
        default_file_exists=path.is_file(),
    )
