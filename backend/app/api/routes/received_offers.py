"""Ofertas recibidas (fase 21): datos en la ficha y comparación, solo para la UI.

La comparación con `private.salary_floor_eur` se calcula aquí y nunca sale por la interfaz para
agentes (POLICIES §4). CORS solo admite GET y POST: guardar y borrar van por POST.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import SessionDep
from app.services import received_offers

router = APIRouter(tags=["received_offers"])


class OkResult(BaseModel):
    ok: bool = True


@router.get("/received-offers", operation_id="compare_received_offers")
def compare_received_offers(session: SessionDep) -> received_offers.OfferComparisonView:
    """Ofertas recibidas lado a lado, con la diferencia con tu mínimo y con el rango publicado."""
    return received_offers.compare(session)


@router.get("/jobs/{job_id}/received-offer", operation_id="get_received_offer")
def get_received_offer(session: SessionDep, job_id: int) -> received_offers.ReceivedOfferOut | None:
    """Los datos de la oferta recibida de esa oferta, o `null` si aún no se han anotado."""
    return received_offers.get_received_offer(session, job_id)


@router.post("/jobs/{job_id}/received-offer", operation_id="save_received_offer")
def save_received_offer(
    session: SessionDep, job_id: int, data: received_offers.ReceivedOfferFields
) -> received_offers.ReceivedOfferOut:
    """Guarda (o sustituye) la oferta recibida. Registra `offer_received` si aún no lo hay."""
    return received_offers.save_received_offer(session, job_id, data)


@router.post("/jobs/{job_id}/received-offer/delete", operation_id="delete_received_offer")
def delete_received_offer(session: SessionDep, job_id: int) -> OkResult:
    """Borra los datos anotados; el `offer_received` del historial se queda."""
    received_offers.delete_received_offer(session, job_id)
    return OkResult()
