"""Parsers de correos de alertas: uno por plataforma, elegido por el dominio del remitente
(`config/policies.yaml` → `email_alerts.platforms`), y uno genérico de respaldo que reconoce
cualquier enlace de oferta de una plataforma conocida.

Los formatos de estos correos cambian: cada parser se construye a partir de un correo real que el
usuario deja en `data/inbox/samples/` (fuera de git) y se prueba con un fixture inventado que
imita su estructura (`tests/fixtures/email/`).
"""

from collections.abc import Callable

from app.core.policies import get_policies
from app.services.ingestion.email.message import AlertMessage
from app.services.ingestion.email.parsers import generic, linkedin
from app.services.ingestion.email.parsers.base import AlertItem, dedupe

Parser = Callable[[AlertMessage], list[AlertItem]]

# Plataformas con parser propio. Las demás de `email_alerts.platforms` usan el genérico
# restringido a su plataforma hasta que haya una alerta real con la que afinarlo.
PARSERS: dict[str, Parser] = {"linkedin": linkedin.parse}


def _domain_matches(domain: str, allowed: str) -> bool:
    allowed = allowed.lower().strip(".")
    return domain == allowed or domain.endswith("." + allowed)


def platform_for_sender(domain: str) -> str | None:
    domain = domain.lower().strip(".")
    for platform, domains in get_policies().email_alerts.platforms.items():
        if any(_domain_matches(domain, d) for d in domains):
            return platform
    return None


def parse_alert(message: AlertMessage) -> tuple[str | None, list[AlertItem]]:
    """Plataforma del remitente (o `None`) y ofertas del correo."""
    platform = platform_for_sender(message.sender_domain)
    if platform is None:
        return None, dedupe(generic.parse(message))
    parser = PARSERS.get(platform)
    items = parser(message) if parser else generic.parse(message, platform)
    return platform, dedupe(items)
