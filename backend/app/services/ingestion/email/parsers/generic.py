"""Parser genérico: cualquier enlace de oferta de una plataforma conocida, con su tarjeta."""

from app.services.ingestion.email.message import AlertMessage
from app.services.ingestion.email.parsers.base import AlertItem, ParseOptions, extract_items


def parse(message: AlertMessage, platform: str | None = None) -> list[AlertItem]:
    return extract_items(message, ParseOptions(platform=platform))
