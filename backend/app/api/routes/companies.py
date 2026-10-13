"""Dosier de empresa (fase 18): lo redacta el agente con `research-company`; la UI lo enseña."""

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.services import company_research

router = APIRouter(tags=["companies"])


@router.get("/jobs/{job_id}/company-research", operation_id="get_company_research")
def get_company_research(
    session: SessionDep, job_id: int
) -> company_research.CompanyResearchResult:
    """El dosier de la empresa de la oferta (con fuentes), si ya se investigó."""
    return company_research.get_company_research(session, job_id)
