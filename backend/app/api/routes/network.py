"""Tu red de LinkedIn (fase 18): estado, importar `Connections.csv` y cruce con cada oferta.

Importar desde la UI lee solo el fichero de siempre (`data/documentos/linkedin/Connections.csv`):
nunca una ruta que llegue en la petición.
"""

from fastapi import APIRouter, Depends, status

from app.api.deps import EmptyBody, SessionDep, require_ui
from app.services import network, process

router = APIRouter(tags=["network"])


@router.get("/network", operation_id="get_network_status")
def get_network_status(session: SessionDep) -> network.NetworkStatus:
    """Cuántas personas hay importadas, cuándo y si está el `Connections.csv` en su carpeta."""
    return network.network_status(session)


@router.post("/network/import", operation_id="import_network", dependencies=[Depends(require_ui)])
def import_network(session: SessionDep, _body: EmptyBody) -> network.ImportResult:
    """Importa `data/documentos/linkedin/Connections.csv` (sincroniza: añade, actualiza, quita)."""
    return network.import_connections(session)


@router.get("/jobs/{job_id}/network", operation_id="get_job_network")
def get_job_network(session: SessionDep, job_id: int) -> network.JobNetwork:
    """Las personas de tu red que trabajan en la empresa de la oferta."""
    return network.job_network(session, job_id)


@router.post(
    "/jobs/{job_id}/contacts/from-network",
    operation_id="add_contact_from_network",
    status_code=status.HTTP_201_CREATED,
)
def add_contact_from_network(
    session: SessionDep, job_id: int, body: network.AddFromNetwork
) -> process.ContactOut:
    """«Añadir como contacto del proceso», con su papel (referencia, recruiter, responsable)."""
    return network.add_to_process(session, job_id, body)


@router.post("/contacts/{contact_id}/referral", operation_id="set_contact_referral")
def set_contact_referral(
    session: SessionDep, contact_id: int, body: process.ReferralChange
) -> process.ContactOut:
    """Marca «referencia pedida» o «dada» (o la quita). No es un evento: no cambia la etapa."""
    return process.set_referral(session, contact_id, body)
