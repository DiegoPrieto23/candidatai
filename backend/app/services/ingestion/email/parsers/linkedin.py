"""Alertas de empleo de LinkedIn (`jobalerts-noreply@linkedin.com` y similares).

Cada oferta es una tarjeta con enlace a `/comm/jobs/view/<id>/?trackingId=…`, el título como
texto del enlace y una línea «Empresa · Ubicación» (a veces con la modalidad detrás). Alrededor
hay líneas de ruido: «Solicitud sencilla», «Seleccionando candidatos activamente», «N antiguos
alumnos»… Los enlaces de LinkedIn nunca se siguen.
"""

from app.services.ingestion.email.message import AlertMessage
from app.services.ingestion.email.parsers.base import AlertItem, ParseOptions, extract_items

NOISE = (
    r"solicitud sencilla|easy apply",
    r"seleccionando candidatos|actively recruiting|contratando activamente",
    r"antiguos? alumnos?|alumni|contactos?|connections?|empleados?\b",
    r"^(?:ver todos? los empleos|see all jobs|ver empleo|view job)",
    r"^(?:linkedin|tu alerta|your job alert|job alert|alerta de empleo)",
    r"^(?:ofertas? similares|similar jobs)",
)

OPTIONS = ParseOptions(platform="linkedin", noise=NOISE)


def parse(message: AlertMessage) -> list[AlertItem]:
    return extract_items(message, OPTIONS)
