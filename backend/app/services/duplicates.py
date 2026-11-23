"""Las ofertas duplicadas de antes: listarlas y borrarlas (desde la UI) tras una vista previa.

Hasta la v1.0, la misma vacante con un título casi igual entraba como oferta nueva con
`duplicate_of` y se cerraba con `duplicate_detected`. Ya no se crean (`ingest.store_job` la anota
como una publicación más de la original), pero las guardadas siguen ahí: llenan «Cerradas» y no
aportan nada.

Una duplicada se puede borrar si sigue cerrada como duplicada y no tiene nada propio: solo lo que
la app hace sola (alta, publicación, extracción, puntuación de 0 a 100, riesgo, filtro previo). Si
ya no está cerrada como duplicada (se reabrió, aunque se cerrara después por otra vía) o tiene algo
hecho para ella (la valoración del agente, un CV, una carta, una candidatura, notas, hitos,
contactos, borradores, un correo…), se queda y se dice por qué. Una tabla nueva que cuelgue
de `jobs` cuenta como «algo propio» mientras no se añada a `AUTOMATIC_TABLES`.

El borrado copia antes la base de datos (`erase.backup_database`) y pasa las publicaciones de la
duplicada a su original, para que la próxima búsqueda reconozca esas URL sin abrirlas.
"""

from datetime import datetime
from functools import cache
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import Table, exists, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registra todas las tablas en los metadatos)
from app.models import Application, Company, Event, Job, JobSighting, Reply
from app.models.base import Base
from app.services import erase, reposts
from app.services.pipeline import EventType, Stage

# Lo que la app guarda sola para cualquier oferta: no es trabajo de nadie sobre la duplicada.
AUTOMATIC_TABLES = frozenset(
    {"events", "applications", "job_sightings", "job_extractions", "matches"}
)
AUTOMATIC_EVENTS = frozenset(
    {
        EventType.FOUND,
        EventType.DETAIL_CAPTURED,
        EventType.DUPLICATE_DETECTED,
        EventType.EXTRACTED,
        EventType.EXTRACTION_FAILED,
        EventType.HARD_FILTER_FAILED,
        EventType.INJECTION_SUSPECTED,
        EventType.CLOSURE_SUSPECTED,
        EventType.SCORED,
    }
)

KeepReason = Literal["no_longer_duplicate", "own_work"]


class DuplicateView(BaseModel):
    job_id: int
    title: str
    company: str
    url: str
    first_seen_at: datetime
    original_id: int
    original_title: str
    original_stage: str | None
    # Por qué no se borra: `no_longer_duplicate` (ya no está cerrada como duplicada) u `own_work`
    # (tiene algo hecho para ella). `None`: se puede borrar.
    keep_reason: KeepReason | None


class DuplicateList(BaseModel):
    items: list[DuplicateView]
    erasable: int
    kept: int


class DuplicatesErased(BaseModel):
    ok: bool = True
    deleted_jobs: int
    kept: int
    moved_sightings: int
    backup: str | None  # la copia previa, relativa a la carpeta de datos; sin borrar nada, `None`
    message: str


@cache
def _own_work_tables() -> tuple[Table, ...]:
    """Tablas con un enlace obligatorio a la oferta que no son de las automáticas."""
    tables: list[Table] = []
    for table in Base.metadata.sorted_tables:
        if table.name in AUTOMATIC_TABLES:
            continue
        if any(
            fk.column.table.name == "jobs" and fk.parent.name == "job_id" and not fk.parent.nullable
            for fk in table.foreign_keys
        ):
            tables.append(table)
    return tuple(tables)


def _has_own_work(session: Session, job_id: int) -> bool:
    for table in _own_work_tables():
        if session.scalar(select(exists().where(table.c.job_id == job_id))):
            return True
    if session.scalar(select(exists().where(Reply.job_id == job_id))):
        return True
    return bool(
        session.scalar(
            select(
                exists().where(
                    Event.job_id == job_id, Event.type.not_in([e.value for e in AUTOMATIC_EVENTS])
                )
            )
        )
    )


def _keep_reason(session: Session, job: Job) -> KeepReason | None:
    app = session.get(Application, job.id)
    if app is None or app.stage != Stage.CLOSED or app.closed_by != EventType.DUPLICATE_DETECTED:
        return "no_longer_duplicate"
    return "own_work" if _has_own_work(session, job.id) else None


def list_duplicates(session: Session) -> DuplicateList:
    """Las ofertas guardadas como duplicadas de otra, con su original y si se pueden borrar. Solo
    lee."""
    rows = session.scalars(select(Job).where(Job.duplicate_of.is_not(None)).order_by(Job.id)).all()
    items: list[DuplicateView] = []
    for job in rows:
        assert job.duplicate_of is not None
        original = session.get(Job, job.duplicate_of)
        if original is None:  # no pasa: borrar la original deja `duplicate_of` en blanco
            continue
        company = session.get(Company, job.company_id)
        original_app = session.get(Application, original.id)
        items.append(
            DuplicateView(
                job_id=job.id,
                title=job.title,
                company=company.name if company else "",
                url=job.url,
                first_seen_at=job.first_seen_at,
                original_id=original.id,
                original_title=original.title,
                original_stage=original_app.stage if original_app else None,
                keep_reason=_keep_reason(session, job),
            )
        )
    erasable = sum(1 for item in items if item.keep_reason is None)
    return DuplicateList(items=items, erasable=erasable, kept=len(items) - erasable)


def _move_sightings(session: Session, job: Job, original_id: int) -> int:
    """Pasa a la original las publicaciones de la duplicada que aún no tenga."""
    moved = 0
    for sighting in session.scalars(select(JobSighting).where(JobSighting.job_id == job.id)):
        clash = session.scalar(
            select(
                exists().where(
                    JobSighting.job_id == original_id,
                    JobSighting.channel == sighting.channel,
                    JobSighting.ref == sighting.ref,
                )
            )
        )
        if not clash:
            sighting.job_id = original_id
            moved += 1
    session.flush()
    original = session.get(Job, original_id)
    if moved and original is not None:
        reposts.refresh(session, original)
    return moved


def erase_duplicates(session: Session, job_ids: list[int]) -> DuplicatesErased:
    """Borra las duplicadas de `job_ids` (las que vio el usuario en la vista previa) que se pueden
    borrar; las demás se quedan. Antes copia la base de datos. Solo desde la UI."""
    listed = {item.job_id: item for item in list_duplicates(session).items}
    chosen = [listed[job_id] for job_id in dict.fromkeys(job_ids) if job_id in listed]
    erasable = [item for item in chosen if item.keep_reason is None]
    kept = len(chosen) - len(erasable)
    if not erasable:
        return DuplicatesErased(
            deleted_jobs=0,
            kept=kept,
            moved_sightings=0,
            backup=None,
            message="No hay duplicadas que borrar.",
        )
    backup = erase.backup_database()
    moved = 0
    for item in erasable:
        job = session.get(Job, item.job_id)
        assert job is not None
        moved += _move_sightings(session, job, item.original_id)
    erase.erase_jobs(session, [item.job_id for item in erasable])
    where = erase.relative_to_data(backup)
    message = f"Borradas {len(erasable)} ofertas duplicadas. Hay una copia previa en {where}."
    if kept:
        message += f" Se quedan {kept} con algo propio o reabiertas."
    return DuplicatesErased(
        deleted_jobs=len(erasable),
        kept=kept,
        moved_sightings=moved,
        backup=where,
        message=message,
    )
