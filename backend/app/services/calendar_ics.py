"""Calendario iCalendar (RFC 5545) de los hitos de los procesos (fase 10), sin dependencias.

- Un `.ics` por hito (para descargar e importar) y un feed con todos los hitos futuros y los
  plazos de las ofertas (para suscribirse desde un cliente de escritorio por URL local, o
  importarlo en Google Calendar, que no puede leer `127.0.0.1`).
- Horas en UTC (`…Z`); los hitos de todo el día, con `VALUE=DATE`.
- Texto escapado (`\\`, `;`, `,`, saltos de línea), líneas plegadas a 75 octetos sin partir un
  carácter UTF-8 y fin de línea CRLF.
- `UID` estable por hito y `SEQUENCE` que sube con cada cambio, para que el calendario actualice
  el evento en vez de duplicarlo.
- El feed solo lleva los hitos programados de ofertas abiertas: un hito cancelado, hecho o de una
  oferta cerrada desaparece del feed (un calendario suscrito lo quita). `STATUS:CANCELLED` solo
  sale en el `.ics` de un hito, para reimportarlo a mano.
"""

import unicodedata
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Company, Job, Milestone
from app.models.base import utcnow
from app.services import process, tracking
from app.services.events import JobNotFoundError
from app.services.process import MilestoneNotFoundError, local_zone, start_of_local_day

PRODID = "-//CandidatAI//Seguimiento//ES"
UID_DOMAIN = "candidatai.local"
UI_URL = "http://127.0.0.1:5173"
CALENDAR_NAME = "CandidatAI"
LABELS = {
    "interview": "Entrevista",
    "test": "Prueba",
    "deadline": "Plazo",
    "other": "Hito",
    "application_deadline": "Plazo de la oferta",
}


def escape_text(value: str) -> str:
    """Escapa un valor TEXT (RFC 5545 §3.3.11)."""
    value = value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return value.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")


def fold(line: str) -> str:
    """Pliega una línea a 75 octetos (RFC 5545 §3.1) sin partir caracteres UTF-8."""
    parts: list[str] = []
    current = ""
    size = 0
    limit = 75
    for char in line:
        width = len(char.encode("utf-8"))
        if size + width > limit:
            parts.append(current)
            current, size = " ", 1  # la continuación empieza con un espacio
        current += char
        size += width
    parts.append(current)
    return "\r\n".join(parts)


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def _date(value: datetime) -> str:
    return value.astimezone(local_zone()).strftime("%Y%m%d")


def _event_lines(
    *,
    uid: str,
    summary: str,
    starts_at: datetime,
    ends_at: datetime,
    all_day: bool,
    stamp: datetime,
    sequence: int,
    location: str | None,
    description: str,
    cancelled: bool = False,
) -> list[str]:
    lines = ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{_utc(stamp)}", f"SEQUENCE:{sequence}"]
    if all_day:
        lines += [f"DTSTART;VALUE=DATE:{_date(starts_at)}", f"DTEND;VALUE=DATE:{_date(ends_at)}"]
    else:
        lines += [f"DTSTART:{_utc(starts_at)}", f"DTEND:{_utc(ends_at)}"]
    lines.append(f"SUMMARY:{escape_text(summary)}")
    if location:
        lines.append(f"LOCATION:{escape_text(location)}")
    lines.append(f"DESCRIPTION:{escape_text(description)}")
    lines.append(f"STATUS:{'CANCELLED' if cancelled else 'CONFIRMED'}")
    lines.append("END:VEVENT")
    return lines


def _calendar(events: Iterable[list[str]]) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{CALENDAR_NAME}",
        f"X-WR-TIMEZONE:{local_zone().key}",
    ]
    for event in events:
        lines += event
    lines.append("END:VCALENDAR")
    return "".join(fold(line) + "\r\n" for line in lines)


def _summary(kind: str, title: str, job_title: str, company: str) -> str:
    label = LABELS.get(kind, "Hito")
    head = title if title and title != label else label
    return f"{head} · {job_title} ({company})"


def _description(job_id: int, notes: str | None) -> str:
    link = f"Ficha en CandidatAI: {UI_URL}/jobs/{job_id}"
    return f"{notes}\n\n{link}" if notes else link


def _milestone_event(row: Milestone, job_title: str, company: str, stamp: datetime) -> list[str]:
    return _event_lines(
        uid=f"milestone-{row.id}@{UID_DOMAIN}",
        summary=_summary(row.kind, row.title, job_title, company),
        starts_at=row.starts_at,
        ends_at=process.default_end(row),
        all_day=row.all_day,
        stamp=stamp,
        sequence=row.sequence,
        location=row.location,
        description=_description(row.job_id, row.notes),
        cancelled=row.status == "cancelled",
    )


def milestone_ics(session: Session, milestone_id: int) -> tuple[str, str]:
    """El `.ics` de un hito y un nombre de fichero para descargarlo."""
    row = session.get(Milestone, milestone_id)
    if row is None:
        raise MilestoneNotFoundError(f"No existe el hito {milestone_id}.")
    job = session.get(Job, row.job_id)
    if job is None:
        raise JobNotFoundError(f"No existe la oferta {row.job_id}.")
    company = session.get(Company, job.company_id)
    company_name = company.name if company else ""
    body = _calendar([_milestone_event(row, job.title, company_name, utcnow())])
    # Solo ASCII: la cabecera `Content-Disposition` va en latin-1 y la empresa viene de la oferta.
    decomposed = unicodedata.normalize("NFKD", f"{LABELS[row.kind]}-{company_name}")
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    slug = "".join(c if c.isascii() and c.isalnum() else "-" for c in plain)
    filename = "-".join(part for part in slug.lower().split("-") if part)[:60] or "hito"
    return body, f"{filename}.ics"


def feed_ics(session: Session, now: datetime | None = None) -> str:
    """Todos los hitos programados desde hoy y los plazos de las ofertas sin enviar."""
    now = now or utcnow()
    items = tracking.upcoming_items(session, start_of_local_day(now), None)
    ids = [i.milestone_id for i in items if i.milestone_id is not None]
    rows = {m.id: m for m in session.scalars(select(Milestone).where(Milestone.id.in_(ids)))}
    events: list[list[str]] = []
    for item in items:
        if item.milestone_id is not None:
            events.append(
                _milestone_event(rows[item.milestone_id], item.job_title, item.company, now)
            )
            continue
        events.append(
            _event_lines(
                uid=f"deadline-{item.job_id}-{_date(item.starts_at)}@{UID_DOMAIN}",
                summary=_summary(item.kind, item.title, item.job_title, item.company),
                starts_at=item.starts_at,
                ends_at=start_of_local_day(
                    item.starts_at.astimezone(local_zone()).date() + timedelta(days=1)
                ),
                all_day=True,
                stamp=now,
                sequence=0,
                location=None,
                description=_description(item.job_id, None),
            )
        )
    return _calendar(events)


def default_export_path() -> Path:
    return get_settings().data_dir / "calendar" / "candidatai.ics"


def export_feed(session: Session, out: Path | None = None) -> Path:
    """Escribe el feed en un fichero (por defecto `data/calendar/candidatai.ics`)."""
    path = out or default_export_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(feed_ics(session).encode("utf-8"))
    return path
