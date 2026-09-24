"""Extracción estructurada de ofertas: la hace el rol `extractor` y la valida el código."""

from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job
from app.models import JobExtraction as JobExtractionRow
from app.schemas.llm_io import JOB_EXTRACTION_SCHEMA_VERSION, JobExtraction
from app.services import events
from app.services.events import JobNotFoundError
from app.services.pipeline import Actor, EventType, Stage


class ExtractionNotFoundError(LookupError):
    pass


class SaveExtractionResult(BaseModel):
    ok: bool
    job_id: int
    extraction_id: int
    stage: Stage
    injection_suspected: bool


class StoredExtraction(BaseModel):
    job_id: int
    extraction_id: int
    schema_version: int
    created_at: datetime
    extraction: JobExtraction


def save_extraction(
    session: Session, job_id: int, extraction: JobExtraction, agent_name: str | None = None
) -> SaveExtractionResult:
    """Guarda una extracción y registra `extracted` (y antes `injection_suspected` si procede).

    Los filtros duros (que pueden cerrar la oferta) llegan en la fase 07. Si algún evento no es
    válido en la etapa actual, se lanza el error y la sesión no debe confirmarse.
    """
    if session.get(Job, job_id) is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    if extraction.injection_suspected:
        events.record(
            session,
            job_id,
            EventType.INJECTION_SUSPECTED,
            Actor.AGENT,
            payload={"source": "agent", "excerpt": extraction.injection_excerpt},
            agent_name=agent_name,
        )
    row = JobExtractionRow(
        job_id=job_id,
        schema_version=JOB_EXTRACTION_SCHEMA_VERSION,
        data=extraction.model_dump(mode="json"),
    )
    session.add(row)
    session.flush()
    events.record(
        session,
        job_id,
        EventType.EXTRACTED,
        Actor.AGENT,
        payload={"extraction_id": row.id},
        agent_name=agent_name,
    )
    return SaveExtractionResult(
        ok=True,
        job_id=job_id,
        extraction_id=row.id,
        stage=events.current_stage(session, job_id),
        injection_suspected=extraction.injection_suspected,
    )


def get_extraction(session: Session, job_id: int) -> StoredExtraction:
    """La extracción vigente (la más reciente) de una oferta."""
    if session.get(Job, job_id) is None:
        raise JobNotFoundError(f"No existe la oferta {job_id}.")
    row = session.scalars(
        select(JobExtractionRow)
        .where(JobExtractionRow.job_id == job_id)
        .order_by(JobExtractionRow.created_at.desc(), JobExtractionRow.id.desc())
        .limit(1)
    ).first()
    if row is None:
        raise ExtractionNotFoundError(f"La oferta {job_id} aún no tiene extracción.")
    return StoredExtraction(
        job_id=job_id,
        extraction_id=row.id,
        schema_version=row.schema_version,
        created_at=row.created_at,
        extraction=JobExtraction.model_validate(row.data),
    )
