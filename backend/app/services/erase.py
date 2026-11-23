"""Borrar una oferta, o todas, de la base de datos. Solo desde la UI y con confirmación escrita.

Es lo único que borra eventos además de quitar un hito anotado por error: la oferta desaparece con
todo lo que cuelga de ella (eventos, CVs, cartas, hitos, borradores, correos…) y no cuenta en el
embudo. Antes se hace siempre una copia de la base de datos en `data/backups/`, que es la única
forma de deshacerlo. Los ficheros de la carpeta de datos (PDF de los CVs, la copia de lo enviado,
dosieres) no se tocan.

El borrado recorre las claves ajenas del modelo, así que una tabla nueva que cuelgue de `jobs` entra
sola: si su enlace es obligatorio, sus filas se borran (y lo que cuelgue de ellas); si es opcional,
se quedan sin el enlace (p. ej. el registro de ejecuciones del agente).
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy import Table, delete, func, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

import app.models  # noqa: F401  (registra todas las tablas en los metadatos)
from app.core.config import get_settings
from app.models import Company, Job, Reply, Task
from app.models.base import Base
from app.services.events import JobNotFoundError

BACKUPS_KEPT = 10
ERASE_ALL_WORDS = ("BORRAR", "DELETE")  # lo que se escribe en la UI, en español o en inglés


class EraseError(ValueError):
    """La confirmación no coincide o no hay base de datos que copiar."""


class EraseResult(BaseModel):
    ok: bool = True
    deleted_jobs: int
    backup: str  # la copia previa, relativa a la carpeta de datos
    message: str


# --- Copia de seguridad ---------------------------------------------------------------------


def _database_file() -> Path:
    url = make_url(get_settings().db_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise EraseError("Solo se puede borrar con copia previa sobre una base de datos SQLite.")
    return Path(url.database)


def backups_dir() -> Path:
    return get_settings().data_dir / "backups"


def backup_database(now: datetime | None = None) -> Path:
    """Copia coherente de la base de datos (la API de copia de SQLite, no copiar el fichero) en
    `data/backups/`. Guarda las {BACKUPS_KEPT} más recientes."""
    source = _database_file()
    folder = backups_dir()
    folder.mkdir(parents=True, exist_ok=True)
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S-%f")
    target = folder / f"{source.stem}-{stamp}.db"
    src, dst = sqlite3.connect(source), sqlite3.connect(target)
    try:
        src.backup(dst)
    finally:
        src.close()
        dst.close()
    for old in sorted(folder.glob(f"{source.stem}-*.db"))[:-BACKUPS_KEPT]:
        old.unlink(missing_ok=True)
    return target


# --- Borrado en cascada ---------------------------------------------------------------------


def _pk(table: Table) -> Any:
    (column,) = table.primary_key.columns
    return column


def _erase_rows(session: Session, table: Table, ids: list[Any]) -> None:
    """Borra esas filas de `table` y, antes, lo que depende de ellas."""
    if not ids:
        return
    for child in Base.metadata.sorted_tables:
        for fk in child.foreign_keys:
            if fk.column.table is not table:
                continue
            refs = fk.parent.in_(ids)
            if child is table or fk.parent.nullable:
                # Un enlace opcional (o a otra fila de la misma tabla) se queda en blanco.
                session.execute(update(child).where(refs).values({fk.parent.name: None}))
            else:
                children = list(session.scalars(select(_pk(child)).where(refs)))
                _erase_rows(session, child, children)
    session.execute(delete(table).where(_pk(table).in_(ids)))


def _forget_in_replies(session: Session, job_ids: set[int]) -> None:
    """Los correos guardan sus ofertas candidatas en JSON: se quitan las borradas, y un correo que
    se queda sin ninguna se borra (solo se guardan los de tus procesos)."""
    for reply in session.scalars(select(Reply)):
        kept = [c for c in reply.candidates if int(c["job_id"]) not in job_ids]
        if not kept:
            session.delete(reply)
            continue
        if len(kept) != len(reply.candidates):
            reply.candidates = kept
        if reply.proposal and int(reply.proposal.get("job_id", 0)) in job_ids:
            reply.proposal = None
            reply.proposed_at = reply.proposed_by = None
            if reply.status == "proposed":
                reply.status = "new"


def erase_jobs(session: Session, job_ids: list[int]) -> None:
    """Borra esas ofertas con todo lo suyo. Sin copia previa: la hace quien llama."""
    _forget_in_replies(session, set(job_ids))
    session.flush()
    # Lo que la cola aún tenía pendiente para esas ofertas ya no tiene sobre qué trabajar.
    payload_job = func.json_extract(Task.payload, "$.job_id")
    session.execute(delete(Task).where(Task.status == "queued", payload_job.in_(job_ids)))
    _erase_rows(session, Job.__table__, job_ids)  # type: ignore[arg-type]
    # Las empresas que se quedan sin ofertas (con su dosier) sobran.
    orphans = list(
        session.scalars(select(Company.id).where(~Company.id.in_(select(Job.company_id))))
    )
    _erase_rows(session, Company.__table__, orphans)  # type: ignore[arg-type]
    session.flush()
    session.expire_all()


def relative_to_data(path: Path) -> str:
    try:
        return path.relative_to(get_settings().data_dir).as_posix()
    except ValueError:
        return str(path)


def erase_job(session: Session, job_id: int, confirm: str) -> EraseResult:
    """Borra una oferta con todo lo suyo. `confirm` es el nombre de la empresa, tal cual se ve."""
    job = session.get(Job, job_id)
    if job is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    company = session.get(Company, job.company_id)
    expected = company.name if company else ""
    if confirm.strip().casefold() != expected.strip().casefold():
        raise EraseError(f"Para borrarla, escribe el nombre de la empresa: «{expected}».")
    title = job.title
    # La copia, antes de tocar nada (la hace otra conexión: aquí aún no ha cambiado nada).
    backup = backup_database()
    erase_jobs(session, [job_id])
    where = relative_to_data(backup)
    return EraseResult(
        deleted_jobs=1,
        backup=where,
        message=f"Borrada «{title}» ({expected}). Hay una copia previa en {where}.",
    )


def erase_all(session: Session, confirm: str) -> EraseResult:
    """Borra todas las ofertas y lo que cuelga de ellas. Se quedan el perfil, las plantillas, las
    fuentes, los buzones, tu red de contactos y la configuración. `confirm` es «BORRAR» (o
    «DELETE», en la UI en inglés)."""
    if confirm.strip() not in ERASE_ALL_WORDS:
        raise EraseError("Para vaciarlo todo, escribe «BORRAR».")
    backup = backup_database()
    job_ids = list(session.scalars(select(Job.id)))
    erase_jobs(session, job_ids)
    return EraseResult(
        deleted_jobs=len(job_ids),
        backup=relative_to_data(backup),
        message=(
            f"Borradas {len(job_ids)} ofertas con sus candidaturas. Hay una copia previa en "
            f"{relative_to_data(backup)}."
        ),
    )
