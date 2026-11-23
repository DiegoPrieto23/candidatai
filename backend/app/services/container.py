"""CandidatAI dentro de Docker (fase 26.3).

La imagen pone `CAI_IN_DOCKER=1`. Tu agente de IA vive fuera del contenedor, así que dentro no se
abren terminales, no se lanza el segundo plano y no hay navegador visible para la candidatura
asistida: la app lo dice en vez de intentarlo.

La API escucha en todas las interfaces del contenedor (si no, el puerto publicado no le llega) solo
si además hay una marca de contenedor: poner `CAI_IN_DOCKER=1` por error en tu equipo no la abre a
tu red. El compose publica el puerto solo en `127.0.0.1` de tu equipo.
"""

from pathlib import Path

from app.core.config import Settings, get_settings

LOOPBACK = "127.0.0.1"
ALL_INTERFACES = "0.0.0.0"  # noqa: S104 - solo dentro de un contenedor (ver `listen_host`)
# Ficheros que crean Docker y Podman en la raíz de un contenedor.
CONTAINER_MARKERS = (Path("/.dockerenv"), Path("/run/.containerenv"))
DATA_MOUNT = Path("/data")
# `cai demo seed` en Docker: otro volumen, que se abre con el compose de la demo.
DEMO_MOUNT = Path("/data-demo")
DEMO_COMPOSE = "docker compose -f docker-compose.yml -f docker-compose.demo.yml up -d"

MCP_COMMAND = "docker exec -i candidatai cai-mcp"
CLI_COMMAND = "docker exec -i candidatai cai"

TERMINAL = (
    "CandidatAI funciona en Docker: el agente no está en el contenedor y no se le puede abrir una "
    "terminal. Hay que copiar la "
    "orden y pegarla en el agente."
)
BACKGROUND = (
    "En Docker no hay segundo plano: el agente no está en el contenedor. Sirven los botones del "
    "agente, que copian la orden."
)
ASSISTED_APPLY = (
    "En Docker no hay un navegador visible para rellenar el formulario y pulsar «Enviar». La "
    "oferta se abre "
    "en el navegador habitual, se envía a mano y se pulsa «Marcar como enviada»."
)


def in_docker(settings: Settings | None = None) -> bool:
    return (settings or get_settings()).in_docker


def in_container() -> bool:
    return any(marker.exists() for marker in CONTAINER_MARKERS)


def listen_host(settings: Settings | None = None) -> str:
    """Dónde escucha `cai serve`: `127.0.0.1` siempre, salvo dentro de un contenedor de verdad."""
    if in_docker(settings) and in_container():
        return ALL_INTERFACES
    return LOOPBACK
