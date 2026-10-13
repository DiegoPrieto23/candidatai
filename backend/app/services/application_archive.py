"""Archivo de candidaturas enviadas (fase 13): una carpeta por oferta con lo que se envió.

Al registrar `applied` o `applied_manually` se encola `archive_application` con los ids de lo que
está seleccionado en ese momento (el CV enviado, la carta vigente con su render y las respuestas).
El worker copia esos ficheros a `data/documentos/candidaturas/<empresa>_<puesto>_<job_id>/` con un
`README.md`. Es idempotente: si la carpeta ya existe no se toca, aunque el CV o la carta se rehagan
después. Ver ADR-025.
"""

import json
import re
import shutil
import unicodedata
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Company, Document, DocumentRender, Event, Job
from app.services import context, tasks
from app.services import profile as profile_service
from app.services.events import JobNotFoundError
from app.services.pipeline import EventType

APPLIED_EVENTS = (EventType.APPLIED.value, EventType.APPLIED_MANUALLY.value)
README = "README.md"
ANSWERS_FILE = "respuestas.json"
RESEARCH_FILE = "empresa.md"
_TMP_PREFIX = ".tmp-"
_MAX_PART = 40


class ArchiveResult(BaseModel):
    job_id: int
    folder: str  # relativa a la carpeta de datos
    created: bool  # False si ya estaba archivada
    files: list[str]  # nombres dentro de la carpeta (vacío si ya existía)


class ArchiveError(ValueError):
    """La oferta no se ha registrado como enviada."""


def archive_root() -> Path:
    return context.documents_dir() / "candidaturas"


def slug(text: str) -> str:
    """Parte de un nombre de fichero: ASCII, sin signos, palabras unidas por `-`."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    words = re.findall(r"[A-Za-z0-9]+", plain)
    return "-".join(words)[:_MAX_PART].strip("-") or "sin-nombre"


def folder_name(company: str, title: str, job_id: int) -> str:
    """`Acme-Analytics_Data-Engineer_12`: ASCII, sin signos y apto para Windows."""
    return f"{slug(company)}_{slug(title)}_{job_id}"


def find_folder(job_id: int) -> Path | None:
    """La carpeta archivada de la oferta, si existe (se reconoce por el sufijo `_<job_id>`)."""
    root = archive_root()
    if not root.is_dir():
        return None
    suffix = f"_{job_id}"
    for path in sorted(root.iterdir()):
        if path.is_dir() and path.name.endswith(suffix) and not path.name.startswith(_TMP_PREFIX):
            return path
    return None


def relative_folder(job_id: int) -> str | None:
    found = find_folder(job_id)
    if found is None:
        return None
    return found.relative_to(get_settings().data_dir).as_posix()


def snapshot(session: Session, job_id: int, event_id: int) -> dict[str, Any]:
    """Ids de lo que se envió, tomados al registrar el envío (el payload de la tarea)."""
    from app.services import answers
    from app.services.documents import cover_letter
    from app.services.documents.service import selected_render_id

    event = session.get(Event, event_id)
    render_id = (event.payload or {}).get("render_id") if event else None
    letter = cover_letter.selected_letter(session, job_id)
    answers_doc = answers.latest_answers(session, job_id)
    return {
        "job_id": job_id,
        "event_id": event_id,
        "cv_render_id": render_id or selected_render_id(session, job_id),
        "letter_document_id": letter[0].id if letter else None,
        "letter_render_id": letter[1].id if letter and letter[1] else None,
        "answers_document_id": answers_doc.id if answers_doc else None,
    }


def enqueue(session: Session, job_id: int, event_id: int) -> None:
    """Encola el archivo de la candidatura que se acaba de registrar como enviada."""
    tasks.enqueue(session, "archive_application", snapshot(session, job_id, event_id))


def _copy_render(render_id: int | None, session: Session, dest: Path) -> str | None:
    if render_id is None:
        return None
    render = session.get(DocumentRender, render_id)
    if render is None or not render.pdf_path:
        return None
    source = get_settings().data_dir / render.pdf_path
    if not source.is_file():
        return None
    shutil.copy2(source, dest / source.name)
    return source.name


def _readme(
    session: Session,
    job: Job,
    company: str,
    event: Event | None,
    profile_version_id: int | None,
    files: list[str],
) -> str:
    from app.services.process import local_zone

    when = "desconocida"
    channel = "sin indicar"
    if event is not None:
        local = event.occurred_at.astimezone(local_zone())
        when = local.strftime("%Y-%m-%d %H:%M") + f" ({local_zone().key})"
        channel = (event.payload or {}).get("channel") or channel
        kind = "envío asistido" if event.type == EventType.APPLIED.value else "registrado por ti"
        channel = f"{channel} ({kind})"
    version = str(profile_version_id) if profile_version_id is not None else "desconocida"
    lines = [
        f"# {job.title} · {company}",
        "",
        f"- **Fecha del envío:** {when}",
        f"- **Canal:** {channel}",
        f"- **URL de la oferta:** {job.url or 'sin URL'}",
        f"- **Oferta en CandidatAI:** {job.id}",
        f"- **Versión del perfil:** {version}",
        "",
        "## Ficheros",
        "",
        *(f"- {name}" for name in files),
        *([] if files else ["- (ninguno: no había CV, carta ni respuestas guardados)"]),
        "",
        "Copia de lo que se envió. Si rehaces el CV o la carta después, esta carpeta no cambia.",
        *(
            [
                "",
                f"`{RESEARCH_FILE}` no se envió: es el dosier de la empresa vigente al archivar.",
            ]
            if RESEARCH_FILE in files
            else []
        ),
        "",
    ]
    return "\n".join(lines)


def archive(session: Session, payload: dict[str, Any]) -> ArchiveResult:
    """Escribe la carpeta de la candidatura a partir del `snapshot`. Idempotente."""
    from app.services import company_research
    from app.services.documents import cover_letter

    job_id = int(payload["job_id"])
    job = session.get(Job, job_id)
    if job is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    data_dir = get_settings().data_dir
    existing = find_folder(job_id)
    if existing is not None:
        relative = existing.relative_to(data_dir).as_posix()
        return ArchiveResult(job_id=job_id, folder=relative, created=False, files=[])

    company = session.get(Company, job.company_id)
    company_name = company.name if company else ""
    root = archive_root()
    root.mkdir(parents=True, exist_ok=True)
    tmp = root / f"{_TMP_PREFIX}{job_id}-{uuid.uuid4().hex[:8]}"
    tmp.mkdir()
    try:
        files: list[str] = []
        profile_version_id: int | None = None
        cv_name = _copy_render(payload.get("cv_render_id"), session, tmp)
        if cv_name:
            files.append(cv_name)
            render = session.get(DocumentRender, payload["cv_render_id"])
            cv_doc = session.get(Document, render.document_id) if render else None
            profile_version_id = cv_doc.profile_version_id if cv_doc else None
        letter_id = payload.get("letter_document_id")
        if letter_id is not None and session.get(Document, letter_id) is not None:
            txt_name = cover_letter.text_file_name(session, letter_id)
            (tmp / txt_name).write_bytes(
                cover_letter.plain_text(session, letter_id).encode("utf-8")
            )
            files.append(txt_name)
            pdf_name = _copy_render(payload.get("letter_render_id"), session, tmp)
            if pdf_name and pdf_name not in files:
                files.append(pdf_name)
        answers_id = payload.get("answers_document_id")
        answers_doc = session.get(Document, answers_id) if answers_id is not None else None
        if answers_doc is not None:
            dump = json.dumps(answers_doc.content, ensure_ascii=False, indent=2) + "\n"
            (tmp / ANSWERS_FILE).write_text(dump, encoding="utf-8")
            files.append(ANSWERS_FILE)
        # Dosier de la empresa (fase 18): el vigente al archivar, no forma parte del envío.
        research = company_research.research_file(session, job.company_id)
        if research is not None:
            shutil.copyfile(research, tmp / RESEARCH_FILE)
            files.append(RESEARCH_FILE)
        if profile_version_id is None:
            try:
                profile_version_id = profile_service.current(session).profile_version_id
            except profile_service.ProfileNotFoundError:
                profile_version_id = None
        event_id = payload.get("event_id")
        event = session.get(Event, event_id) if event_id is not None else None
        readme = _readme(session, job, company_name, event, profile_version_id, files)
        (tmp / README).write_text(readme, encoding="utf-8")
        target = root / folder_name(company_name, job.title, job_id)
        try:
            tmp.rename(target)
        except OSError:
            # Otro proceso (el worker y `cai applications archive` a la vez) la archivó antes.
            already = find_folder(job_id)
            if already is None:
                raise
            shutil.rmtree(tmp, ignore_errors=True)
            relative = already.relative_to(data_dir).as_posix()
            return ArchiveResult(job_id=job_id, folder=relative, created=False, files=[])
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return ArchiveResult(
        job_id=job_id,
        folder=target.relative_to(data_dir).as_posix(),
        created=True,
        files=[*files, README],
    )


def _last_applied_event(session: Session, job_id: int) -> Event | None:
    stmt = (
        select(Event)
        .where(Event.job_id == job_id, Event.type.in_(APPLIED_EVENTS))
        .order_by(Event.occurred_at.desc(), Event.id.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def archive_existing(session: Session, job_id: int | None = None) -> list[ArchiveResult]:
    """Archiva ya (sin worker) las candidaturas enviadas antes de existir el archivo.

    Usa lo seleccionado ahora mismo: el CV enviado queda en el evento, pero la carta y las
    respuestas son las vigentes. Las que ya tienen carpeta no se tocan.
    """
    if job_id is not None:
        job_ids = [job_id]
    else:
        stmt = select(Event.job_id).where(Event.type.in_(APPLIED_EVENTS)).distinct()
        job_ids = sorted(session.scalars(stmt))
    results: list[ArchiveResult] = []
    for jid in job_ids:
        event = _last_applied_event(session, jid)
        if event is None:
            raise ArchiveError(f"La oferta {jid} no se ha registrado como enviada.")
        try:
            results.append(archive(session, snapshot(session, jid, event.id)))
        except JobNotFoundError:
            if job_id is not None:
                raise
            # Con `--all`, una oferta que ya no existe no para el resto del lote.
    return results
