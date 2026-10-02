"""Aplicación FastAPI. Escucha solo en 127.0.0.1 (`jh serve`) y solo admite CORS de la UI local."""

import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from app.api.errors import ERROR_RESPONSES, install_error_handlers
from app.api.routes import alerts, capture, cv, jobs, sources, status, triage

HOST = "127.0.0.1"
UI_ORIGIN = "http://127.0.0.1:5173"


def _operation_id(route: APIRoute) -> str:
    return route.name


def create_app() -> FastAPI:
    app = FastAPI(
        title="Job Hunter",
        version="0.1.0",
        description="API local de Job Hunter para la UI.",
        generate_unique_id_function=_operation_id,
        responses=ERROR_RESPONSES,
    )
    # Solo la UI. La extensión de captura (fase 09b) no necesita CORS: sus `host_permissions` sobre
    # `http://127.0.0.1:8000/*` la eximen. Añadir su origen le dejaría leer toda la API sin token.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[UI_ORIGIN],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    install_error_handlers(app)
    app.include_router(status.router)
    app.include_router(jobs.router)
    app.include_router(triage.router)
    app.include_router(cv.router)
    app.include_router(sources.router)
    app.include_router(alerts.router)
    app.include_router(capture.router)
    return app


def openapi_json(api: FastAPI) -> str:
    """Esquema OpenAPI serializado de forma estable (el que se versiona en el frontend)."""
    return json.dumps(api.openapi(), ensure_ascii=False, indent=2) + "\n"


app = create_app()
