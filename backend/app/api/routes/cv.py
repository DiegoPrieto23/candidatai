"""CV de una oferta y plantillas (fase 08.2). Capa fina sobre `services/documents/service.py`.

Renderizar desde aquí no usa IA: combina el contenido ya guardado con otra plantilla u opciones.
Los ficheros solo se sirven desde `data/` (renders) y desde las carpetas de plantillas (previews).
"""

from typing import Literal

from fastapi import APIRouter, File, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.schemas.cv import CvRenderOptions
from app.services import profile as profile_service
from app.services.documents import authoring, default_template, service, uploads
from app.services.documents.service import FileNotAvailableError
from app.services.pipeline import Actor

router = APIRouter(tags=["cv"])

_MEDIA_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.get("/templates", operation_id="list_templates")
def list_templates() -> service.TemplateList:
    """Plantillas de CV disponibles (integradas y tuyas) y las que no son válidas."""
    return service.list_cv_templates()


@router.get(
    "/templates/{template_id}/preview.png",
    operation_id="get_template_preview",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}}},
)
def get_template_preview(template_id: str) -> FileResponse:
    """Primera página de la preview de una plantilla, generada con el perfil demo."""
    return FileResponse(service.template_preview(template_id), media_type="image/png")


@router.get(
    "/templates/{template_id}/source.png",
    operation_id="get_template_source",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}}},
)
def get_template_source(template_id: str) -> FileResponse:
    """Primera página del CV original del que se creó la plantilla («Mi CV»)."""
    png = authoring.source_png(template_id)
    if png is None:
        raise FileNotAvailableError("Esta plantilla no tiene vista del original.")
    return FileResponse(png, media_type="image/png")


@router.get(
    "/templates/{template_id}/preview-real.png",
    operation_id="get_template_real_preview",
    response_class=FileResponse,
    responses={200: {"content": {"image/png": {}}}},
)
def get_template_real_preview(session: SessionDep, template_id: str) -> FileResponse:
    """La plantilla con tu perfil (sin agente). La primera vez tarda lo que la conversión a PDF."""
    return FileResponse(authoring.real_preview_png(session, template_id), media_type="image/png")


class DefaultTemplate(BaseModel):
    template_id: str | None  # `preferences.cv.default_template` del perfil vigente


@router.get("/templates/default", operation_id="get_default_template")
def get_default_template(session: SessionDep) -> DefaultTemplate:
    try:
        stored = profile_service.current(session)
    except profile_service.ProfileNotFoundError:
        return DefaultTemplate(template_id=None)
    return DefaultTemplate(template_id=stored.profile.preferences.cv.default_template)


@router.post("/templates/{template_id}/default", operation_id="set_default_template")
def set_default_template(
    session: SessionDep, template_id: str
) -> default_template.DefaultTemplateResult:
    """Fija la plantilla por defecto en data/profile.yaml (conserva comentarios) y lo importa."""
    return default_template.set_default_template(session, template_id)


@router.get("/uploads", operation_id="list_uploads")
def list_uploads() -> list[uploads.UploadInfo]:
    """CVs subidos para convertirlos en plantilla y si ya se importaron."""
    return uploads.list_uploads()


@router.post("/uploads", operation_id="upload_cv", status_code=status.HTTP_201_CREATED)
async def upload_cv(file: UploadFile = File(...)) -> uploads.UploadInfo:  # noqa: B008
    """Guarda un CV en data/uploads/ (máximo 10 MB) para importarlo con tu agente."""
    data = await file.read(uploads.MAX_BYTES + 1)
    return uploads.save_upload(file.filename or "cv", data)


@router.delete(
    "/uploads/{name}", operation_id="delete_upload", status_code=status.HTTP_204_NO_CONTENT
)
def delete_upload(name: str) -> Response:
    uploads.delete_upload(name)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/jobs/{job_id}/cv", operation_id="get_job_cv")
def get_job_cv(session: SessionDep, job_id: int) -> service.JobCv:
    """CV vigente de la oferta: contenido, verificación y renders con sus avisos."""
    return service.get_job_cv(session, job_id)


@router.post(
    "/documents/{document_id}/renders",
    operation_id="render_document",
    status_code=status.HTTP_201_CREATED,
)
def render_document(
    session: SessionDep, document_id: int, body: CvRenderOptions
) -> service.RenderResult:
    """Renderiza el CV con otra plantilla u opciones, sin agente (tarda lo que la conversión)."""
    return service.render(session, document_id, body, actor=Actor.USER)


@router.post("/renders/{render_id}/select", operation_id="select_render")
def select_render(session: SessionDep, render_id: int) -> service.RenderResult:
    """Marca este render como el que se enviará (uno por CV)."""
    return service.select_render(session, render_id)


def _render_file(session: SessionDep, render_id: int, kind: Literal["pdf", "docx"]) -> FileResponse:
    path = service.render_file(session, render_id, kind)
    return FileResponse(
        path,
        media_type=_MEDIA_TYPES[kind],
        filename=path.name,
        content_disposition_type="inline" if kind == "pdf" else "attachment",
    )


@router.get(
    "/renders/{render_id}/pdf",
    operation_id="get_render_pdf",
    response_class=FileResponse,
    responses={200: {"content": {"application/pdf": {}}}},
)
def get_render_pdf(session: SessionDep, render_id: int) -> FileResponse:
    return _render_file(session, render_id, "pdf")


@router.get(
    "/renders/{render_id}/docx",
    operation_id="get_render_docx",
    response_class=FileResponse,
    responses={200: {"content": {_MEDIA_TYPES["docx"]: {}}}},
)
def get_render_docx(session: SessionDep, render_id: int) -> FileResponse:
    return _render_file(session, render_id, "docx")
