"""Tablas SQLAlchemy (sin lógica). Importar este paquete registra todas en `Base.metadata`."""

from app.models.applier import ApplicationAttempt
from app.models.base import Base
from app.models.companies import Company, CompanyResearch
from app.models.documents import CoverLetterBrief, Document, DocumentRender
from app.models.events import Application, Event
from app.models.jobs import Job, JobExtraction, JobSighting
from app.models.matches import Match
from app.models.ops import McpCall, Task
from app.models.process import Contact, Milestone, NetworkContact
from app.models.profiles import ProfileVersion
from app.models.prompts import UserPrompt
from app.models.replies import MessageDraft, Reply
from app.models.skills import SkillGapMark
from app.models.sources import EmailMessage, Source, SourceRun

__all__ = [
    "Application",
    "ApplicationAttempt",
    "Base",
    "Company",
    "CompanyResearch",
    "Contact",
    "CoverLetterBrief",
    "Document",
    "DocumentRender",
    "EmailMessage",
    "Event",
    "Job",
    "JobExtraction",
    "JobSighting",
    "Match",
    "McpCall",
    "MessageDraft",
    "Milestone",
    "NetworkContact",
    "ProfileVersion",
    "Reply",
    "SkillGapMark",
    "Source",
    "SourceRun",
    "Task",
    "UserPrompt",
]
