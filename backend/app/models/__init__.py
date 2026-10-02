"""Tablas SQLAlchemy (sin lógica). Importar este paquete registra todas en `Base.metadata`."""

from app.models.base import Base
from app.models.companies import Company
from app.models.documents import Document, DocumentRender
from app.models.events import Application, Event
from app.models.jobs import Job, JobExtraction
from app.models.matches import Match
from app.models.ops import McpCall, Task
from app.models.profiles import ProfileVersion
from app.models.sources import Source, SourceRun

__all__ = [
    "Application",
    "Base",
    "Company",
    "Document",
    "DocumentRender",
    "Event",
    "Job",
    "JobExtraction",
    "Match",
    "McpCall",
    "ProfileVersion",
    "Source",
    "SourceRun",
    "Task",
]
