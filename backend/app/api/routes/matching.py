"""Similitud semántica del score: si está instalada y, desde la UI, instalarla."""

from fastapi import APIRouter, Depends

from app.api.deps import EmptyBody, SessionDep, require_ui
from app.services.matching import extra

router = APIRouter(prefix="/matching", tags=["matching"])


@router.get("/semantic", operation_id="get_semantic_matching")
def get_semantic_matching(session: SessionDep) -> extra.MatchingExtraStatus:
    """Si la comparación por significado está instalada, pedida o instalándose."""
    return extra.status(session)


@router.post(
    "/semantic/install",
    operation_id="install_semantic_matching",
    dependencies=[Depends(require_ui)],
)
def install_semantic_matching(session: SessionDep, _body: EmptyBody) -> extra.MatchingExtraStatus:
    """Guarda que la quieres y la instala en segundo plano (el worker). Solo desde la UI."""
    return extra.request_install(session)
