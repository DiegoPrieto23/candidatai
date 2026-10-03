"""Paquete de candidatura (fase 10.3): CV elegido, respuestas de screening y carta.

Nada de aquí envía: el envío es de la fase 11 y siempre tras confirmación en la UI.
"""

from fastapi import APIRouter, status

from app.api.deps import SessionDep
from app.schemas.llm_io import ApplicationAnswers
from app.services import answers

router = APIRouter(tags=["applications"])


@router.get("/jobs/{job_id}/package", operation_id="get_job_package")
def get_job_package(session: SessionDep, job_id: int) -> answers.JobPackage:
    """CV elegido (con enlace al PDF), últimas respuestas y carta seleccionada (08c) o `null`."""
    return answers.get_package(session, job_id)


@router.post(
    "/jobs/{job_id}/answers",
    operation_id="save_user_answers",
    status_code=status.HTTP_201_CREATED,
)
def save_user_answers(
    session: SessionDep, job_id: int, body: ApplicationAnswers
) -> answers.SaveAnswersResult:
    """Edición del usuario: crea un documento nuevo «Editadas por ti»; el anterior se conserva."""
    return answers.save_user_answers(session, job_id, body)
